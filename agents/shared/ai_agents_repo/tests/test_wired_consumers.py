"""High-value integration: audit script resolves #file: via ai_agents_repo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ai_agents_repo.discovery import repo_root
from ai_agents_repo.paths import ide_pack_root


def test_audit_prompt_bytes_runs_from_unrelated_cwd(tmp_path: Path):
    root = repo_root()
    script = ide_pack_root(root=root) / "scripts" / "audit_prompt_bytes.py"
    out = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, str(script), "--output", str(out)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
