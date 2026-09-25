"""Daily Coder adapter — HTTP proxy + local process lifecycle."""
from __future__ import annotations
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

# Keep in sync with daily_coder.providers.registry.LIVE_PROVIDERS (mock is the only non-live).
LIVE_PROVIDERS = frozenset({
    "openai", "anthropic", "gemini", "openrouter", "local", "command", "http",
})


class DailyCoderAdapter:
    def __init__(self, agent_id: str, name: str, description: str, options: dict[str, Any]):
        self.id = agent_id
        self.name = name
        self.description = description
        self.base_url = options.get("base_url", "http://127.0.0.1:8765").rstrip("/") + "/"
        self.token = (options.get("token") or os.environ.get(options.get("token_env", "DAILY_CODER_API_TOKEN"), "") or "").strip()
        self.default_repo = options.get("default_repo", ".")
        self.repo_root = Path(options.get("repo_root") or ".").resolve()
        self.provider = options.get("provider", "mock")
        self.provider_command = (
            options.get("provider_command")
            or os.environ.get(options.get("provider_command_env", "DAILY_CODER_PROVIDER_COMMAND"), "")
            or ""
        ).strip()
        self.provider_endpoint = (
            options.get("provider_endpoint")
            or os.environ.get(options.get("provider_endpoint_env", "DAILY_CODER_PROVIDER_ENDPOINT"), "")
            or ""
        ).strip()
        parsed = urlparse(self.base_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 8765
        self._proc: subprocess.Popen | None = None
        self._managed_token: str | None = None

    def capabilities(self) -> list[str]:
        return [
            "health", "runs", "start", "approve", "resume", "cancel",
            "activity", "metrics", "steer", "backend",
        ]

    # --- HTTP -------------------------------------------------------------
    def _request(self, method: str, path: str, body: dict | None = None, auth: bool = True) -> Any:
        url = urljoin(self.base_url, path.lstrip("/"))
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth and self.token:
            headers["X-Api-Token"] = self.token
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"daily-coder {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"daily-coder unreachable at {self.base_url}: {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        try:
            payload = self._request("GET", "/api/health", auth=False)
            return {"online": True, "detail": payload}
        except Exception as exc:  # noqa: BLE001
            return {"online": False, "detail": str(exc)}

    def _auth_ok(self) -> bool:
        if not self.token:
            return False
        try:
            self._request("GET", "/api/runs?limit=1")
            return True
        except Exception:
            return False

    def backend_status(self) -> dict[str, Any]:
        health = self.health()
        online = bool(health.get("online"))
        managed = self._proc is not None and self._proc.poll() is None
        auth_ok = False
        state = "down"
        message = "Server is not running."
        if online:
            if not self.token:
                state = "unauthorized"
                message = "Server is up but API token is missing. Start/restart from the dashboard, or paste the token."
            else:
                try:
                    self._request("GET", "/api/runs?limit=1")
                    auth_ok = True
                    state = "ready"
                    message = "Server online and authenticated."
                except RuntimeError as exc:
                    msg = str(exc).lower()
                    if "401" in msg or "unauthorized" in msg:
                        state = "unauthorized"
                        message = "Server is up but API token is missing or wrong. Start/restart from the dashboard, or paste the token."
                    else:
                        state = "degraded"
                        message = f"Server is up but API failed: {exc}"
                except Exception as exc:  # noqa: BLE001
                    state = "degraded"
                    message = f"Server is up but API failed: {exc}"
        return {
            "startable": True,
            "stoppable": managed or online,
            "online": online,
            "auth_ok": auth_ok,
            "managed": managed,
            "state": state,
            "message": message,
            "base_url": self.base_url.rstrip("/"),
            "has_token": bool(self.token),
            "pid": self._proc.pid if managed else None,
            "provider": self.provider,
            "bridges": self.bridge_availability(),
        }

    def bridge_availability(self) -> dict[str, bool]:
        return {
            "command": bool(self.provider_command),
            "http": bool(self.provider_endpoint),
        }

    def set_backend_token(self, token: str) -> dict[str, Any]:
        """Hold token in process memory only — never written to disk."""
        self.token = (token or "").strip()
        status = self.backend_status()
        return {"ok": status["auth_ok"], "backend": status}

    def set_provider(self, provider: str) -> dict[str, Any]:
        """Remember provider for the next managed `serve` start (default remains mock)."""
        name = (provider or "mock").strip().lower()
        allowed = {
            "mock", "gemini", "openrouter", "openai", "anthropic",
            "local", "command", "http",
        }
        if name not in allowed:
            raise ValueError(f"unsupported provider: {name}")
        bridges = self.bridge_availability()
        if name == "command" and not bridges["command"]:
            raise ValueError("command bridge requires provider_command in config or DAILY_CODER_PROVIDER_COMMAND")
        if name == "http" and not bridges["http"]:
            raise ValueError("http bridge requires provider_endpoint in config or DAILY_CODER_PROVIDER_ENDPOINT")
        self.provider = name
        return {"ok": True, "provider": self.provider}

    def clear_secrets(self) -> None:
        self.token = ""
        self._managed_token = None

    def start_backend(self, *, force: bool = False, provider: str | None = None) -> dict[str, Any]:
        status = self.backend_status()
        if status["state"] == "ready" and not force:
            return {"ok": True, "already_running": True, "backend": status}

        if force or status["state"] == "unauthorized":
            # Stop only the managed child first.
            self.stop_backend(force=False)

        # Port still busy after managed stop (or never managed)?
        if self._port_open() and force:
            self._kill_port_listener()
            time.sleep(0.4)
        elif self._port_open() and not force:
            return {
                "ok": False,
                "error": f"Port {self.port} is already in use. Use Restart (force) or stop the other process.",
                "backend": self.backend_status(),
            }

        token = secrets.token_urlsafe(24)
        cmd = self._serve_command(token, provider or self.provider)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo_root) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUNBUFFERED"] = "1"
        # Do not leak token via env to children beyond argv; serve reads --token

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        log_path = Path(tempfile.gettempdir()) / f"daily-coder-{self.port}.log"
        try:
            log_fh = open(log_path, "w", encoding="utf-8", errors="replace")
        except OSError:
            log_fh = subprocess.DEVNULL
            log_path = None

        try:
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(self.repo_root),
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        except FileNotFoundError as exc:
            if log_fh is not subprocess.DEVNULL:
                log_fh.close()
            raise RuntimeError(f"Failed to start daily-coder: {exc}") from exc
        finally:
            if log_fh is not subprocess.DEVNULL:
                try:
                    log_fh.close()
                except OSError:
                    pass

        self.token = token
        self._managed_token = token

        # Wait until health responds
        deadline = time.time() + 12
        last_err = ""
        while time.time() < deadline:
            if self._proc.poll() is not None:
                tail = ""
                if log_path and log_path.is_file():
                    try:
                        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                        tail = "\n".join(lines[-12:])
                    except OSError:
                        pass
                detail = f" Check repo_root={self.repo_root} and Python 3.10+."
                if tail:
                    detail += f" Last output:\n{tail}"
                raise RuntimeError(
                    f"daily-coder exited early (code {self._proc.returncode}).{detail}"
                )
            try:
                self._request("GET", "/api/health", auth=False)
                if self._auth_ok():
                    break
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
            time.sleep(0.35)
        else:
            raise RuntimeError(f"daily-coder started but did not become ready: {last_err or 'timeout'}")

        return {
            "ok": True,
            "started": True,
            "managed": True,
            "backend": self.backend_status(),
            "hint": "Token is held by the dashboard — no need to paste it in the browser.",
        }

    def stop_backend(self, *, force: bool = False) -> dict[str, Any]:
        stopped = False
        if self._proc is not None:
            stopped = self._terminate(self._proc)
            self._proc = None
        if force and self._port_open():
            self._kill_port_listener()
            stopped = True
        if self._managed_token and self.token == self._managed_token:
            # Clear only the managed token; keep user-supplied tokens
            self.token = ""
            self._managed_token = None
        return {"ok": True, "stopped": stopped, "backend": self.backend_status()}

    def _serve_command(self, token: str, provider: str) -> list[str]:
        py = self._python()
        name = (provider or "mock").strip().lower()
        cmd = [
            *py,
            "-m", "daily_coder",
            "serve",
            "--provider", name,
            "--host", self.host,
            "--port", str(self.port),
            "--token", token,
        ]
        if name in LIVE_PROVIDERS:
            cmd.append("--live")
        if name == "command" and self.provider_command:
            cmd.extend(["--provider-command", self.provider_command])
        if name == "http" and self.provider_endpoint:
            cmd.extend(["--provider-endpoint", self.provider_endpoint])
        return cmd

    def _python(self) -> list[str]:
        """Pick a Python 3.10+ interpreter to run daily-coder.

        Prefer the dashboard's own interpreter when it is new enough, so a
        stale `python` earlier on PATH cannot hijack the managed backend.
        """
        if sys.version_info >= (3, 10):
            return [sys.executable]

        def _ok(cmd: list[str]) -> bool:
            try:
                subprocess.check_call(
                    cmd + ["-c", "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                return False

        if sys.platform == "win32" and shutil.which("py"):
            for ver in ("-3.13", "-3.12", "-3.11", "-3.10", "-3"):
                cmd = ["py", ver]
                if _ok(cmd):
                    return cmd
        for name in (
            "python3.13", "python3.12", "python3.11", "python3.10",
            "python3", "python",
        ):
            path = shutil.which(name)
            if path and _ok([path]):
                return [path]
        return [sys.executable]

    def _port_open(self) -> bool:
        import socket
        try:
            with socket.create_connection((self.host, self.port), timeout=0.4):
                return True
        except OSError:
            return False

    def _listen_pids(self) -> list[int]:
        pids: list[int] = []
        if sys.platform == "win32":
            try:
                out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="replace")
            except (subprocess.CalledProcessError, FileNotFoundError):
                return pids
            needle = f":{self.port}"
            for line in out.splitlines():
                if "LISTENING" not in line.upper() or needle not in line:
                    continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    pids.append(int(parts[-1]))
                except ValueError:
                    continue
        else:
            try:
                out = subprocess.check_output(["lsof", "-ti", f"TCP:{self.port}", "-sTCP:LISTEN"], text=True)
                for line in out.splitlines():
                    line = line.strip()
                    if line.isdigit():
                        pids.append(int(line))
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        return sorted(set(pids))

    def _kill_port_listener(self) -> None:
        for pid in self._listen_pids():
            if pid == os.getpid():
                continue
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.kill(pid, signal.SIGTERM)
            except OSError:
                continue

    def _terminate(self, proc: subprocess.Popen) -> bool:
        if proc.poll() is not None:
            return False
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except OSError:
            return False
        return True

    # --- runs / approvals -------------------------------------------------
    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        runs = self._request("GET", f"/api/runs?limit={int(limit)}")
        return [self._normalize(r) for r in runs]

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._normalize(self._request("GET", f"/api/runs/{run_id}"))

    def start_run(self, request: str, **kwargs: Any) -> dict[str, Any]:
        # Pass only keys the Daily Coder API accepts; persist forced_subagents as a steer-style note intent.
        repo = kwargs.get("repo") or self.default_repo
        # Resolve relative repos against the ecosystem package (serve cwd); absolute paths pass through.
        if repo and not Path(str(repo)).is_absolute():
            repo = str((self.repo_root / str(repo)).resolve())
        else:
            repo = str(Path(str(repo)).resolve()) if repo else str(self.repo_root)
        body = {"request": request, "repo": repo}
        forced = kwargs.get("forced_subagents")
        if forced:
            names = forced if isinstance(forced, list) else [forced]
            names = [str(n).strip() for n in names if str(n).strip()]
            if names:
                body["request"] = (
                    f"{request}\n\n[forced_subagents: {', '.join(names)}]"
                )
        result = self._request("POST", "/api/runs", body)
        run_id = result.get("run_id")
        if run_id:
            detail = self.get_run(run_id)
            return {**result, **{k: detail[k] for k in (
                "repo_path", "git_head", "git_dirty", "status", "phase",
            ) if k in detail}, "forced_subagents": forced or []}
        return result

    def approve(self, run_id: str, *, reject: bool = False, note: str | None = None, kind: str = "plan") -> dict[str, Any]:
        return self._request("POST", f"/api/runs/{run_id}/approve", {
            "reject": reject, "note": note, "kind": kind, "actor": "agent-dashboard",
        })

    def resume(self, run_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/runs/{run_id}/resume", {})

    def cancel(self, run_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/runs/{run_id}/cancel", {})

    def pending_approvals(self) -> list[dict[str, Any]]:
        items = self._request("GET", "/api/approvals")
        return [{
            "run_id": a.get("run_id"),
            "agent_id": self.id,
            "kind": a.get("kind", "plan"),
            "summary": a.get("kind", "plan"),
        } for a in items]

    def activity(self, run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if not run_id:
            runs = self.list_runs(limit=5)
            if not runs:
                return []
            run_id = runs[0]["run_id"]
        events = self._request("GET", f"/api/runs/{run_id}/events")
        out = []
        for ev in events[-limit:]:
            out.append({
                "ts": str(ev.get("ts") or ev.get("created_at") or ""),
                "agent_id": self.id,
                "run_id": run_id,
                "role": ev.get("role") or ev.get("actor") or "",
                "kind": ev.get("kind") or ev.get("type") or "event",
                "summary": ev.get("summary") or ev.get("message") or json.dumps(ev)[:160],
            })
        return out

    def metrics(self) -> dict[str, Any]:
        return self._request("GET", "/api/metrics")

    @staticmethod
    def _repo_git_info(repo: str | None) -> dict[str, Any]:
        if not repo:
            return {}
        path = Path(repo)
        if not path.is_dir():
            return {"repo_path": str(path)}
        try:
            rev = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=15,
            )
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return {"repo_path": str(path.resolve())}
        head = rev.stdout.strip() if rev.returncode == 0 else None
        dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
        out: dict[str, Any] = {"repo_path": str(path.resolve())}
        if head:
            out["git_head"] = head[:12]
        if dirty is not None:
            out["git_dirty"] = dirty
        return out

    def _normalize(self, run: dict[str, Any]) -> dict[str, Any]:
        repo = run.get("repo")
        git = self._repo_git_info(repo)
        stored_head = run.get("revision")
        head = (stored_head[:12] if stored_head else None) or git.get("git_head")
        return {
            "run_id": run.get("run_id"),
            "agent_id": self.id,
            "status": run.get("status", ""),
            "phase": run.get("phase", ""),
            "request": run.get("request", ""),
            "updated_at": str(run.get("updated_at") or run.get("created_at") or run.get("updated") or ""),
            "est_usd": float(run.get("est_usd") or 0),
            "profile": run.get("profile") or "",
            "repo_path": git.get("repo_path") or repo,
            "git_head": head,
            "git_dirty": git.get("git_dirty"),
            "raw": run,
        }
