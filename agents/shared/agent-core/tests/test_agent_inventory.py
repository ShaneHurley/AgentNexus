"""Inventory evidence and negative controls; no runtime execution or model calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[4]
PUBLIC = {"deep-research", "research-messenger", "plan-prep", "use-master", "daily-coder", "researcher"}

class AgentInventoryTests(unittest.TestCase):
    def build(self, root, **kw):
        from agent_core.agent_inventory import build_inventory
        return build_inventory(root, **kw)

    def fixture(self, root):
        def write(rel, text):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        rows = [{"name": name, "user_invocable": True, "delegate_only": False} for name in sorted(PUBLIC)]
        rows.append({"name": "code-reviewer", "user_invocable": False, "delegate_only": True})
        write("agents/ide/MANIFEST.yml", yaml.safe_dump({"contract_version": "1.0", "agents": rows}))
        for row in rows:
            write(f"agents/ide/canonical/{row['name']}.md", "---\n" + yaml.safe_dump(dict(row, contract_version="1.0")) + "---\n# Prompt\n")
        shard = {"agent_count": 2, "families": ["alpha", "stale"], "agents": [
            {"family": "alpha", "variant": None, "path": "alpha"},
            {"family": "alpha", "variant": "small", "path": "alpha/variants/small"}]}
        write("agents/coding/browser/MANIFEST.json", json.dumps(shard))
        write("agents/shared/browser/MANIFEST.index.json", json.dumps({"families": ["alpha"], "shards": [{"id": "coding", "root": "agents/coding/browser", "manifest": "agents/coding/browser/MANIFEST.json", "family_ids": ["alpha"]}]}))
        for entry in shard["agents"]:
            write("agents/coding/browser/" + entry["path"] + "/AGENT_MESSAGE.md", "Embedded contract\n")
        return write

    def test_real_roster_counts_and_no_browser_runtime_inference(self):
        result = self.build(ROOT)
        self.assertEqual(result["counts"]["ide_agents"], 41)
        self.assertEqual(result["counts"]["public_agents"], 6)
        self.assertEqual(result["counts"]["browser_pastes"], 96)
        self.assertEqual(result["counts"]["browser_families"], 10)
        self.assertEqual(result["counts"]["browser_variants"], 86)
        self.assertTrue(all(row["execution_surface"] == "paste-only" for row in result["browser_agents"]))
        self.assertTrue(result["runtime"]["roles"])

    def test_determinism_hashes_and_selected_load_sizes(self):
        first = self.build(ROOT, selected=["ide:researcher", "browser:code-crafter"])
        self.assertEqual(first, self.build(ROOT, selected=["browser:code-crafter", "ide:researcher", "ide:researcher"]))
        path = "agents/ide/canonical/researcher.md"
        self.assertEqual(first["sources"][path]["sha256"], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        self.assertEqual(len(first["selected_load"]["items"]), 2)
        self.assertGreater(first["selected_load"]["bytes"], 0)
        self.assertIn("estimate", first["selected_load"]["token_estimate_note"])

    def test_existing_path_and_authority_findings_have_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = self.fixture(root)
            prompt = root / "agents/ide/canonical/researcher.md"
            prompt.write_text(prompt.read_text() + "python ide-agents/scripts/import_daily_coder_agents.py\n")
            write("agents/shared/browser/_shared/AUTHORITY.md", "Use /code-reviewer directly.\n")
            write("agents/ide/canonical/master-orchestrator.md", "Emit only valid JSON.\nReturn one fenced JSON block.\n")
            findings = self.build(root)["findings"]
            self.assertTrue(any(f["code"] == "broken-generator-path" and f["path"] == "agents/ide/canonical/researcher.md" for f in findings))
            self.assertTrue(any(f["code"] == "delegate-public-claim" and f["path"].endswith("AUTHORITY.md") for f in findings))
            self.assertTrue(any(f["code"] == "conflicting-output-contract" for f in findings))
            self.assertTrue(all("line" in f and "path" in f for f in findings))

    def test_duplicate_ids_missing_pastes_and_shard_actual_family_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / "agents/coding/browser/MANIFEST.json"
            manifest = json.loads(path.read_text())
            manifest["agents"].append(dict(manifest["agents"][0]))
            manifest["agents"][1]["path"] = "absent"
            path.write_text(json.dumps(manifest))
            codes = {f["code"] for f in self.build(root)["findings"]}
            self.assertTrue({"duplicate-id", "missing-path", "shard-family-list-mismatch", "declared-count-mismatch"} <= codes)

    def test_public_six_parent_unknown_and_contract_missing_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / "agents/ide/MANIFEST.yml"
            manifest = yaml.safe_load(path.read_text())
            manifest["agents"][0]["user_invocable"] = False
            manifest["agents"][-1]["parent"] = "absent-parent"
            path.write_text(yaml.safe_dump(manifest))
            prompt = root / "agents/ide/canonical/code-reviewer.md"
            prompt.write_text(prompt.read_text().replace("contract_version: '1.0'\n", ""))
            result = self.build(root)
            codes = {f["code"] for f in result["findings"]}
            self.assertTrue({"public-six-invariant", "unknown-parent", "missing-contract"} <= codes)
            self.assertEqual(next(r for r in result["ide_agents"] if r["id"] == "ide:researcher")["parent"], "unknown")

    def test_projection_body_drift_and_logical_alias_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = self.fixture(root)
            write(".cursor/agents/researcher.md", "---\nname: researcher\nuser_invocable: true\ncontract_version: '1.0'\n---\nDifferent body\n")
            path = root / "agents/ide/MANIFEST.yml"
            manifest = yaml.safe_load(path.read_text())
            manifest["agents"][0]["canonical"] = "ide-agents/canonical/" + manifest["agents"][0]["name"] + ".md"
            path.write_text(yaml.safe_dump(manifest))
            result = self.build(root)
            self.assertTrue(any(f["code"] == "projection-drift" for f in result["findings"]))
            self.assertTrue(result["logical_aliases"])
            self.assertFalse(any(f["code"] == "missing-path" and "ide-agents/canonical" in f["message"] for f in result["findings"]))

    def test_projection_tool_authority_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = self.fixture(root)
            write(".cursor/agents/researcher.md", "---\nname: researcher\nuser_invocable: true\ndelegate_only: false\ncontract_version: '1.0'\nreadonly: true\ntools: {deny: []}\n---\n# Prompt\n")
            result = self.build(root)
            self.assertTrue(any(f["code"] == "projection-drift" and f["path"] == ".cursor/agents/researcher.md" for f in result["findings"]))

    def test_missing_hook_command_and_aggregate_manifest_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = self.fixture(root)
            write(".cursor/hooks.json", json.dumps({"hooks": {"preToolUse": [{"command": "python .cursor/hooks/absent.py"}]}}))
            write("agents/shared/browser/MANIFEST.json", json.dumps({"agent_count": 0, "agents": []}))
            codes = {f["code"] for f in self.build(root)["findings"]}
            self.assertTrue({"missing-hook-command", "aggregate-browser-mismatch"} <= codes)

    def test_dc_declared_hashes_normalize_crlf_and_keep_raw_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = self.fixture(root)
            source_dir = "agents/coding/daily-coder-ecosystem/agents/researcher"
            prompt = "prompt line\r\nsecond line\r\n"
            metadata = '{"id": "researcher"}\r\n'
            write(source_dir + "/prompt.md", prompt)
            write(source_dir + "/agent.json", metadata)
            path = root / "agents/ide/MANIFEST.yml"
            manifest = yaml.safe_load(path.read_text())
            row = next(r for r in manifest["agents"] if r["name"] == "researcher")
            canonical = root / "agents/ide/canonical/researcher.md"
            canonical.write_bytes(canonical.read_bytes().replace(b"\n", b"\r\n"))
            row["canonical_sha256"] = hashlib.sha256(canonical.read_text().encode()).hexdigest()
            row["projection"] = {"source_agent": "daily-coder-ecosystem/agents/researcher", "prompt_sha256": hashlib.sha256(prompt.replace("\r\n", "\n").encode()).hexdigest(), "agent_json_sha256": hashlib.sha256(metadata.replace("\r\n", "\n").encode()).hexdigest()}
            path.write_text(yaml.safe_dump(manifest))
            result = self.build(root)
            self.assertFalse(any(f["code"] == "source-hash-mismatch" for f in result["findings"]))
            rel = source_dir + "/prompt.md"
            self.assertEqual(result["sources"][rel]["sha256"], hashlib.sha256(prompt.encode()).hexdigest())
            self.assertNotEqual(result["sources"][rel]["sha256"], row["projection"]["prompt_sha256"])
            write(rel, "actual changed content\r\n")
            self.assertTrue(any(f["code"] == "source-hash-mismatch" and "prompt_sha256" in f["message"] for f in self.build(root)["findings"]))

    def test_declared_provenance_hash_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / "agents/ide/MANIFEST.yml"
            manifest = yaml.safe_load(path.read_text())
            manifest["agents"][0]["canonical_sha256"] = "0" * 64
            path.write_text(yaml.safe_dump(manifest))
            self.assertTrue(any(f["code"] == "source-hash-mismatch" for f in self.build(root)["findings"]))

    def test_browser_guides_broken_links_counterparts_and_logical_fragment_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write = self.fixture(root)
            write("agents/coding/browser/alpha/HOW_TO.md", "[missing](./absent.md)\n[logical](_shared#CORE_AGENT_CONTRACT.md)\n[external](https://example.invalid)\nUse /code-reviewer directly.\n")
            path = root / "agents/coding/browser/MANIFEST.json"
            manifest = json.loads(path.read_text())
            manifest["agents"][0]["ide_counterpart"] = "/code-reviewer"
            path.write_text(json.dumps(manifest))
            result = self.build(root)
            broken = [f for f in result["findings"] if f["code"] == "broken-markdown-link"]
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0]["line"], 1)
            self.assertTrue(any(f["code"] == "delegate-public-claim" and f["path"].endswith("HOW_TO.md") for f in result["findings"]))
            self.assertTrue(any(f["code"] == "delegate-public-claim" and f["path"].endswith("MANIFEST.json") for f in result["findings"]))

    def test_source_symlink_escape_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            self.fixture(root)
            path = root / "agents/coding/browser/alpha/AGENT_MESSAGE.md"
            path.unlink()
            target = Path(outside) / "secret.md"
            target.write_text("private contract")
            path.symlink_to(target)
            result = self.build(root)
            rel = "agents/coding/browser/alpha/AGENT_MESSAGE.md"
            self.assertNotIn(rel, result["sources"])
            self.assertTrue(any(f["code"] == "escaped-path" and f["path"] == rel for f in result["findings"]))

    def test_escaped_paths_and_unknown_selection_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / "agents/coding/browser/MANIFEST.json"
            manifest = json.loads(path.read_text())
            manifest["agents"][0]["path"] = "../../../../outside"
            path.write_text(json.dumps(manifest))
            result = self.build(root, selected=["ide:no-such-role"])
            codes = {f["code"] for f in result["findings"]}
            self.assertTrue({"escaped-path", "unknown-selection"} <= codes)
            self.assertEqual(result["selected_load"]["bytes"], 0)

if __name__ == "__main__":
    unittest.main()
