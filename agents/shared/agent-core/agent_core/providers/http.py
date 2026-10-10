"""Resilient HTTP transport and JSON parsing helpers for hosted providers.

Standard library only. Provides timeout, retry, backoff, JSON extraction,
and streaming support.
"""
from __future__ import annotations

import io
import json
import time
import threading
import queue
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator


class ProviderError(RuntimeError):
    """Sanitized transport failure; acceptance uncertainty forbids replay."""
    def __init__(self, message="provider request failed", *, category="transport", remote_acceptance="unknown", retryable=False, provider_request_id=None):
        super().__init__(message)
        self.category=category
        self.remote_acceptance=remote_acceptance
        self.retryable=retryable
        self.provider_request_id=provider_request_id

RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504}
TOOL_RESULT_MAX_CHARS = 12000

def _close_at_deadline(response,deadline):
    """Interrupt slow incremental bodies at the original deadline."""
    def close():
        import socket
        sock=getattr(getattr(getattr(response,"fp",None),"raw",None),"_sock",None)
        if sock is not None:
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        try: response.close()
        except Exception: pass
    timer=threading.Timer(max(0,deadline-time.time()),close)
    timer.daemon=True;timer.start()
    return timer

def post_json(url, payload, headers=None, timeout=180.0, retries=0, backoff_factor=1.0, *, deadline=None):
    """One retry owner. Only explicit rejected throttling is replayable."""
    import math
    if not math.isfinite(timeout) or timeout <= 0 or retries not in (0,1,2) or (deadline is not None and not math.isfinite(deadline)):
        raise ValueError("invalid transport budget")
    stop=min(deadline if deadline is not None else time.time()+timeout, time.time()+timeout)
    body=json.dumps(payload).encode()
    for attempt in range(retries+1):
        remaining=stop-time.time()
        if remaining<=0:
            raise ProviderError("provider deadline exhausted",category="deadline",remote_acceptance="rejected")
        request=urllib.request.Request(url,data=body,method="POST",headers={"Content-Type":"application/json",**(headers or {})})
        try:
            with urllib.request.urlopen(request,timeout=remaining) as response:
                timer=_close_at_deadline(response,stop)
                try:
                    data=json.loads(response.read().decode())
                    if time.time()>=stop: raise ProviderError("provider deadline exhausted",category="deadline")
                    return data
                finally: timer.cancel()
        except urllib.error.HTTPError as exc:
            rejected=exc.code in {400,401,403,404,409,422,425,429}
            transient=exc.code in {425,429}
            error=ProviderError("provider HTTP failure",category="http",remote_acceptance="rejected" if rejected else "unknown",retryable=transient)
            if not transient or attempt==retries:
                raise error from None
            pause=min(backoff_factor*2**attempt,8)
            if time.time()+pause>=stop:
                raise error from None
            time.sleep(pause)
        except (OSError,ValueError):
            raise ProviderError("provider transport or response failure") from None


def post_stream(url,payload,headers=None,timeout=180.0,*,deadline=None):
    """SSE transport; never replay a partially accepted request."""
    import math
    if not math.isfinite(timeout) or timeout<=0 or (deadline is not None and not math.isfinite(deadline)):
        raise ValueError("invalid streaming budget")
    stop=min(deadline if deadline is not None else time.time()+timeout,time.time()+timeout)
    remaining=stop-time.time()
    if remaining<=0: raise ProviderError("provider deadline exhausted",category="deadline",remote_acceptance="rejected")
    body=json.dumps(payload).encode()
    request=urllib.request.Request(url,data=body,method="POST",headers={"Content-Type":"application/json","Accept":"text/event-stream",**(headers or {})})
    try:
        with urllib.request.urlopen(request,timeout=remaining) as response:
            timer=_close_at_deadline(response,stop)
            try:
                for raw_line in response:
                    if time.time()>=stop: raise ProviderError("provider streaming deadline exhausted",category="deadline")
                    line=raw_line.decode("utf-8",errors="replace").strip()
                    if line.startswith("data:"):
                        data=line[5:].strip()
                        if data=="[DONE]": break
                        yield data
                if time.time()>=stop: raise ProviderError("provider streaming deadline exhausted",category="deadline")
            finally: timer.cancel()
    except (urllib.error.HTTPError,OSError):
        raise ProviderError("provider stream failed") from None


def get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> dict[str, Any]:
    """Execute a resilient GET request and parse JSON response."""
    req_headers = {"Accept": "application/json", **(headers or {})}
    last: Exception | None = None

    for attempt in range(retries):
        request = urllib.request.Request(url, method="GET", headers=req_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            last = ProviderError("provider GET HTTP failure", category="http")
            if exc.code not in RETRYABLE:
                raise last
        except OSError as exc:
            last = ProviderError("provider GET transport failure")
        sleep_s = min(backoff_factor * (2 ** attempt), 8.0)
        time.sleep(sleep_s)

    raise last or ProviderError("get request failed")


def get_text(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> str:
    """Execute a GET request and return decoded text."""
    req_headers = {
        "User-Agent": "agent-core/1.0 (+https://github.com/agent-nexus)",
        **(headers or {}),
    }
    last: Exception | None = None

    for attempt in range(retries):
        request = urllib.request.Request(url, method="GET", headers=req_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            last = ProviderError("provider GET HTTP failure", category="http")
            if exc.code not in RETRYABLE:
                raise last
        except OSError as exc:
            last = ProviderError("provider GET transport failure")
        sleep_s = min(backoff_factor * (2 ** attempt), 8.0)
        time.sleep(sleep_s)

    raise last or ProviderError("get text failed")


def extract_json(text: str) -> dict[str, Any]:
    """Recover the first complete JSON object from text or markdown fences."""
    if not text:
        raise ProviderError("empty model response")
    stripped = text.strip()
    if stripped.startswith("```"):
        first_fence = stripped.split("```")[1]
        if first_fence.startswith("json"):
            first_fence = first_fence[4:]
        stripped = first_fence.strip()
    try:
        res = json.loads(stripped)
        if isinstance(res, dict):
            return res
    except ValueError:
        pass

    start = stripped.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for i in range(start, len(stripped)):
            ch = stripped[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        cand = json.loads(stripped[start:i + 1])
                        if isinstance(cand, dict):
                            return cand
                    except ValueError:
                        break
        start = stripped.find("{", start + 1)
    raise ProviderError("model did not return JSON", category="response")


def json_instruction(schema: dict[str, Any] | None) -> str:
    """Produce standard instruction prompt requiring single JSON response matching schema."""
    if not schema:
        return "\n\nReturn ONLY a single JSON object. No prose, no code fences."
    return (
        "\n\nReturn ONLY a single JSON object matching this schema. No prose, no code fences.\n"
        + json.dumps(schema, separators=(",", ":"))[:4000]
    )


def schema_field_list(schema: dict[str, Any] | None) -> str:
    """Compact required + property names only; never dump full schema JSON."""
    if not schema:
        return ""
    props = list((schema.get("properties") or {}).keys())
    req = list(schema.get("required") or [])
    return json.dumps({"required": req, "properties": props}, separators=(",", ":"))


def json_instruction_compact(schema: dict[str, Any] | None) -> str:
    """Compact JSON instruction for token-constrained contexts."""
    return (
        "\n\nReturn ONLY a single JSON object. Keys must include required fields. "
        "Full validation is server-side.\n" + schema_field_list(schema)
    )


def tool_result_text(result: Any) -> str:
    """Format tool result dict/list to compact text capped at length limit."""
    return json.dumps(result, separators=(",", ":"), default=str)[:TOOL_RESULT_MAX_CHARS]


_PUBLIC_DNS_SLOTS = threading.BoundedSemaphore(2)


def _public_resolution(host,port,deadline):
    import ipaddress,socket
    try:
        literal=ipaddress.ip_address(host)
        return [(socket.AF_INET6 if literal.version==6 else socket.AF_INET,socket.SOCK_STREAM,6,"",(str(literal),port))]
    except ValueError:
        pass
    remaining=max(0,deadline-time.monotonic())
    if not _PUBLIC_DNS_SLOTS.acquire(timeout=remaining):
        raise ProviderError("public retrieval resolver capacity/deadline exhausted")
    result=queue.Queue(maxsize=1)
    def resolve():
        try: result.put((True,socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)))
        except Exception: result.put((False,None))
        finally: _PUBLIC_DNS_SLOTS.release()
    worker=threading.Thread(target=resolve,daemon=True)
    try: worker.start()
    except RuntimeError:
        _PUBLIC_DNS_SLOTS.release()
        raise ProviderError("public retrieval resolver unavailable")
    try: ok,infos=result.get(timeout=max(0,deadline-time.monotonic()))
    except queue.Empty as exc:
        raise ProviderError("public retrieval DNS deadline exhausted") from exc
    if not ok: raise ProviderError("public retrieval DNS failed")
    return infos


def get_public_text(url: str, *, timeout: float = 5.0) -> str:
    """Credential-free public retrieval with pinned DNS endpoints and bounded body.

    This is deliberately separate from authenticated provider transports. No
    ambient proxy, cookies or credentials are used. Every redirect is checked.
    """
    import http.client
    import ipaddress
    import math
    import socket
    import ssl
    from email.message import Message
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise ProviderError("public retrieval timeout outside allowed range")
    deadline=time.monotonic()+timeout
    visited=set()
    for _ in range(4):
        if url in visited: raise ProviderError("public retrieval redirect loop")
        visited.add(url)
        try:
            parts=urllib.parse.urlsplit(url)
            host=parts.hostname
            port=parts.port or (443 if parts.scheme == "https" else 80)
            if parts.scheme not in {"http","https"} or not host or parts.username is not None or parts.password is not None:
                raise ProviderError("public retrieval URL denied")
            if port not in {80,443}: raise ProviderError("public retrieval port denied")
            infos=_public_resolution(host,port,deadline)
            addresses=[]
            for info in infos:
                address=ipaddress.ip_address(info[4][0])
                if not address.is_global or address.is_multicast or address.is_reserved:
                    raise ProviderError("public retrieval resolves to a non-public endpoint")
                addresses.append(str(address))
            if not addresses: raise ProviderError("public retrieval has no public endpoint")
        except (ValueError,OSError) as exc:
            raise ProviderError("public retrieval URL or resolution failed") from exc
        remaining=deadline-time.monotonic()
        if remaining <= 0: raise ProviderError("public retrieval deadline exhausted")
        connection=response=sock=timer=None
        active_socket={}
        socket_lock=threading.Lock()
        try:
            # Connect to the validated numeric address, not a second hostname
            # resolution. HTTPS still authenticates the original hostname.
            sock=socket.create_connection((addresses[0],port),timeout=remaining)
            active_socket["socket"]=sock
            def interrupt():
                with socket_lock:
                    current=active_socket.get("socket")
                    if current is not None:
                        try: current.shutdown(socket.SHUT_RDWR)
                        except (OSError,AttributeError): pass
                        try: current.close()
                        except OSError: pass
            timer=threading.Timer(max(0,deadline-time.monotonic()),interrupt)
            timer.daemon=True;timer.start()
            if parts.scheme == "https":
                context=ssl.create_default_context()
                with socket_lock:
                    sock=context.wrap_socket(sock,server_hostname=host,do_handshake_on_connect=False)
                    active_socket["socket"]=sock
                sock.do_handshake()
                connection=http.client.HTTPSConnection(host,port=port,timeout=remaining,context=context)
            else:
                connection=http.client.HTTPConnection(host,port=port,timeout=remaining)
            connection.sock=sock
            path=urllib.parse.urlunsplit(("","",parts.path or "/",parts.query,""))
            connection.request("GET",path,headers={"User-Agent":"agent-core/public-retrieval","Accept":"text/html,text/plain,application/json,application/xml"})
            response=connection.getresponse()
            if response.status in {301,302,303,307,308}:
                location=response.getheader("Location")
                if not location: raise ProviderError("public retrieval redirect missing target")
                url=urllib.parse.urljoin(url,location)
                continue
            if not 200 <= response.status < 300: raise ProviderError("public retrieval HTTP failure")
            content_type=response.getheader("Content-Type","")
            if not content_type.lower().startswith(("text/","application/json","application/xml","application/xhtml+xml")):
                raise ProviderError("public retrieval unsupported content type")
            body=bytearray()
            read=getattr(response,"read1",response.read)
            while True:
                remaining=deadline-time.monotonic()
                if remaining <= 0: raise ProviderError("public retrieval deadline exhausted")
                if hasattr(sock,"settimeout"): sock.settimeout(remaining)
                chunk=read(min(8192,400001-len(body)))
                if not chunk: break
                body.extend(chunk)
                if len(body)>400000: raise ProviderError("public retrieval body exceeds ceiling")
            if time.monotonic() >= deadline: raise ProviderError("public retrieval deadline exhausted")
            message=Message();message["content-type"]=content_type
            return body.decode(message.get_content_charset() or "utf-8",errors="replace")
        except (OSError,http.client.HTTPException,ValueError,LookupError) as exc:
            raise ProviderError("public retrieval transport failed") from exc
        finally:
            if timer is not None: timer.cancel()
            if response is not None: response.close()
            if connection is not None: connection.close()
            elif sock is not None: sock.close()
    raise ProviderError("public retrieval redirect limit exceeded")
