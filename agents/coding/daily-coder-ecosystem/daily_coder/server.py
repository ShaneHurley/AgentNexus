"""REST service host (API + thin pointer page).

Standard library only, so the package keeps a zero-dependency install. The service is
optional: the CLI works without it. The shared orchestration UI lives in sibling
`gui/` and talks to this API via an adapter. Multi-host worker execution
is intentionally not enabled here (see `storage.py`).
"""
from __future__ import annotations
import collections, json, secrets as _secrets, threading, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .budget import BudgetManager
from .evolution import EvolutionManager
from .jobs import JobManager
from .secrets import SecretStore
from .util import load_json

class _Handler(BaseHTTPRequestHandler):
    server_version = "daily-coder"

    # --- plumbing -----------------------------------------------------
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        ctx = self.server.ctx
        if not ctx["auth_required"]:
            return True
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else self.headers.get("X-Api-Token", "")
        return _secrets.compare_digest(token or "", ctx["token"])

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    # --- routes -------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, query = parsed.path, urllib.parse.parse_qs(parsed.query)
        ctx = self.server.ctx
        store = ctx["store"]

        if path in ("/", "/index.html"):
            page = Path(__file__).resolve().parent / "dashboard" / "index.html"
            return self._send(200, page.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/health":
            return self._send(200, {"ok": True, "live": ctx["orchestrator"].live,
                                    "provider": type(ctx["orchestrator"].provider).__name__,
                                    "auth_required": ctx["auth_required"]})
        if path == "/api/openapi.json":
            return self._send(200, _openapi())
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})

        if path == "/api/runs":
            return self._send(200, store.list_runs(int(query.get("limit", ["50"])[0])))
        if path.startswith("/api/runs/"):
            parts = [p for p in path.split("/") if p]
            run_id = parts[2]
            try:
                run = store.get(run_id)
            except KeyError:
                return self._send(404, {"error": "unknown run"})
            if len(parts) == 3:
                return self._send(200, run)
            tail = parts[3]
            if tail == "events": return self._send(200, store.events(run_id))
            if tail == "artifacts": return self._send(200, store.artifacts(run_id))
            if tail == "invocations": return self._send(200, store.invocations(run_id))
            if tail == "tools": return self._send(200, store.tool_calls(run_id))
            if tail == "jobs": return self._send(200, store.jobs(run_id))
            if tail == "cost": return self._send(200, ctx["budget"].report(run_id))
            return self._send(404, {"error": "unknown sub-resource"})
        if path == "/api/approvals":
            return self._send(200, store.pending_approvals())
        if path == "/api/jobs":
            return self._send(200, store.jobs(active_only=query.get("active", ["0"])[0] == "1"))
        if path == "/api/metrics":
            return self._send(200, _metrics(store, ctx))
        if path == "/api/providers":
            from .providers.registry import PROVIDERS
            return self._send(200, {"providers": list(PROVIDERS), "secrets": ctx["secrets"].list()})
        if path == "/api/candidates":
            return self._send(200, store.candidates())
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        ctx = self.server.ctx
        store = ctx["store"]
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if "//" in path:
            return self._send(404, {"error": "malformed path"})
        body = self._body()
        parts = [urllib.parse.unquote(p) for p in path.split("/") if p]

        if path == "/api/runs":
            if not body.get("request"):
                return self._send(400, {"error": "request is required"})
            try:
                repo = _safe_repo(body.get("repo", "."), ctx["allowed_repo_roots"])
                run_id = ctx["orchestrator"].create(body["request"], repo)
            except (ValueError, PermissionError) as exc:
                return self._send(400, {"error": str(exc)})
            ctx["executor"].submit(_safe_resume, ctx, run_id)
            return self._send(202, {"accepted": True, "run_id": run_id})
        if path.endswith("/resume") and path.startswith("/api/runs/"):
            if len(parts) != 4: return self._send(404, {"error": "not found"})
            run_id = parts[2]
            ctx["executor"].submit(_safe_resume, ctx, run_id)
            return self._send(202, {"accepted": True, "run_id": run_id})
        if path.endswith("/approve") and path.startswith("/api/runs/"):
            if len(parts) != 4: return self._send(404, {"error": "not found"})
            run_id = parts[2]
            run = store.get(run_id)
            state = "rejected" if body.get("reject") else "approved"
            ok = store.decide_approval(run_id, body.get("kind", "plan"), run.get("plan_hash"),
                                       state, body.get("actor", "api"), body.get("note"))
            return self._send(200, {"decided": ok, "state": state})
        if path.endswith("/cancel") and path.startswith("/api/runs/"):
            if len(parts) != 4: return self._send(404, {"error": "not found"})
            run_id = parts[2]
            store.set_status(run_id, "CANCELLED")
            for job in store.jobs(run_id, active_only=True):
                ctx["jobs"].cancel(job["job_id"])
            return self._send(200, {"cancelled": True})
        if path == "/api/secrets":
            name, value = body.get("name"), body.get("value")
            if not name or not value:
                return self._send(400, {"error": "name and value are required"})
            try:
                return self._send(200, ctx["secrets"].set(name, value))
            except RuntimeError as exc:
                return self._send(503, {"error": str(exc)})
        if path.startswith("/api/jobs/") and path.endswith("/cancel"):
            if len(parts) != 4: return self._send(404, {"error": "not found"})
            return self._send(200, ctx["jobs"].cancel(parts[2]))
        if path.startswith("/api/candidates/") and path.endswith("/promote"):
            if len(parts) != 4: return self._send(404, {"error": "not found"})
            try:
                return self._send(200, ctx["evolution"].promote(parts[2], body.get("actor", "api")))
            except (KeyError, PermissionError) as exc:
                return self._send(409, {"error": str(exc)})
        if path.startswith("/api/candidates/") and path.endswith("/evaluate"):
            if len(parts) != 4: return self._send(404, {"error": "not found"})
            if not body.get("frozen_command") or not body.get("holdout_command"):
                return self._send(400, {"error": "frozen_command and holdout_command are required"})
            try:
                verdict = ctx["evolution"].evaluate_commands(parts[2], body["frozen_command"],
                                                               body["holdout_command"], int(body.get("timeout", 1800)))
                return self._send(200, {"verdict": verdict})
            except (KeyError, PermissionError, RuntimeError) as exc:
                return self._send(409, {"error": str(exc)})
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        path = urllib.parse.urlparse(self.path).path
        parts = [urllib.parse.unquote(p) for p in path.split("/") if p]
        if path.startswith("/api/secrets/"):
            if len(parts) != 3: return self._send(404, {"error": "not found"})
            return self._send(200, {"deleted": self.server.ctx["secrets"].delete(parts[2])})
        return self._send(404, {"error": "not found"})


def _safe_start(ctx, request, repo):
    try:
        ctx["orchestrator"].start(request, repo)
    except Exception as exc:  # surfaced through /api/runs state
        ctx["errors"].append(str(exc))

def _safe_resume(ctx, run_id):
    try:
        ctx["orchestrator"].run(run_id)
    except Exception as exc:
        ctx["errors"].append(str(exc))

def _safe_repo(value, allowed_roots):
    path = Path(value).resolve()
    for root in allowed_roots:
        root = Path(root).resolve()
        if path == root or root in path.parents:
            if not path.is_dir():
                raise ValueError("repository path is not a directory")
            return str(path)
    raise PermissionError("repository path is outside server.allowed_repo_roots")

def _openapi():
    return {"openapi":"3.0.3","info":{"title":"Daily Coder API","version":"1.0"},"paths":{
        "/api/health":{"get":{"summary":"Health check"}},
        "/api/runs":{"get":{"summary":"List runs"},"post":{"summary":"Create a run"}},
        "/api/runs/{run_id}":{"get":{"summary":"Get authoritative run state"}},
        "/api/runs/{run_id}/resume":{"post":{"summary":"Resume a run"}},
        "/api/runs/{run_id}/approve":{"post":{"summary":"Approve or reject a plan"}},
        "/api/runs/{run_id}/cancel":{"post":{"summary":"Cancel a run and its jobs"}},
        "/api/jobs":{"get":{"summary":"List durable jobs"}},
        "/api/metrics":{"get":{"summary":"Usage and quality metrics"}},
        "/api/secrets":{"post":{"summary":"Store a provider secret"}},
        "/api/candidates":{"get":{"summary":"List evolution candidates"}},
        "/api/candidates/{candidate_id}/evaluate":{"post":{"summary":"Run frozen and holdout gates"}},
        "/api/candidates/{candidate_id}/promote":{"post":{"summary":"Human promotion after gates pass"}}
    }}

def _metrics(store, ctx):
    generation=time.monotonic()
    with ctx["metrics_lock"]:
        cached=ctx.get("metrics_cache")
        if cached and time.monotonic()-cached[0] < 15:
            return cached[1]
    runs = store.list_runs(200)
    aggregate = store.metrics_aggregate(50)
    active = [r for r in runs if r["status"] in ("ACTIVE", "WAITING_HUMAN", "WAITING_JOB")]
    totals = {"runs": len(runs), "active": len(active),
              "waiting_human": sum(1 for r in runs if r["status"] == "WAITING_HUMAN"),
              "waiting_job": sum(1 for r in runs if r["status"] == "WAITING_JOB"),
              "complete": sum(1 for r in runs if r["status"] == "COMPLETE"),
              "failed": sum(1 for r in runs if r["status"] == "FAILED")}
    roles = {r["role"]:{"calls":r["calls"],"tokens":r["tokens"],"usd":round(r["usd"],6),
                         "errors":r["errors"],"avg_latency_ms":int(r["avg_latency_ms"])}
             for r in aggregate["roles"]}
    verified = [r for r in runs if r["status"] == "COMPLETE"]
    spend = store.spend(date.today().isoformat())
    result={"totals": totals, "roles": roles, "tool_denials": aggregate["tool_denials"], "today": spend,
            "limits": ctx["limits"],
            "accuracy": {"acceptance_rate": round(len(verified) / max(1, len(runs)), 3),
                         "repair_rate": round(sum(1 for r in runs if (r.get("repair_cycles") or 0) > 0) / max(1, len(runs)), 3)},
            "cost_per_verified_pass": round(sum(float(r.get("est_usd") or 0) for r in runs) / max(1, len(verified)), 6),
            "jobs_active": aggregate["jobs_active"]}
    with ctx["metrics_lock"]:
        cached=ctx.get("metrics_cache")
        if not cached or generation>=cached[0]:
            ctx["metrics_cache"]=(generation,result)
    return result


def serve(store, orchestrator, root, host="127.0.0.1", port=8765, token=None, auth_required=True):
    config = load_json(Path(root) / "config/default.json")
    budgets = load_json(Path(root) / "config/budgets.json")
    pricing = load_json(Path(root) / "config/pricing.json")
    token = token or _secrets.token_urlsafe(24)
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.ctx = {
        "store": store, "orchestrator": orchestrator, "root": Path(root),
        "budget": BudgetManager(budgets, store, pricing=pricing, limits=config.get("limits", {})),
        "jobs": JobManager(store, Path(root) / config["runtime_dir"] / "jobs"),
        "secrets": SecretStore(Path(root) / config["runtime_dir"] / "secrets.json"),
        "evolution": EvolutionManager(root, store),
        "limits": config.get("limits", {}), "auth_required": auth_required,
        "token": token, "errors": collections.deque(maxlen=100),
        "executor": ThreadPoolExecutor(max_workers=config.get("max_parallel_agents",4),thread_name_prefix="run"),
        "metrics_lock": threading.Lock(), "metrics_cache": None,
        "allowed_repo_roots": [str((Path(root)/p).resolve()) if not Path(p).is_absolute() else str(Path(p).resolve())
                       for p in config.get("server",{}).get("allowed_repo_roots",["."])],
    }
    print(json.dumps({"listening": f"http://{host}:{port}", "auth_required": auth_required,
                      "api_token": token if auth_required else None}, indent=2))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    finally:
        httpd.ctx["executor"].shutdown(wait=True)
