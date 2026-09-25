"""Read-only web retrieval.

URL fetch and search are the only network capabilities. Both validate every hop against
SSRF rules, enforce size and content-type limits, and return citations.
"""
from __future__ import annotations
import ipaddress, json, re, socket, threading, urllib.parse, urllib.request
from html.parser import HTMLParser

class NetworkDenied(PermissionError): pass

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_MAX_BYTES = 400_000
ALLOWED_TYPES = ("text/", "application/json", "application/xml", "application/xhtml")

def _resolve_public(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise NetworkDenied(f"cannot resolve host: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise NetworkDenied(f"host {host} resolves to a non-public address")
    return True

def validate_url(url, policy):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise NetworkDenied(f"scheme {parts.scheme or '(none)'} is not allowed")
    host = parts.hostname
    if not host:
        raise NetworkDenied("URL has no host")
    deny = policy.get("deny_domains", [])
    allow = policy.get("allow_domains", [])
    if any(host == d or host.endswith("." + d) for d in deny):
        raise NetworkDenied(f"domain {host} is denied by policy")
    if allow and not any(host == d or host.endswith("." + d) for d in allow):
        raise NetworkDenied(f"domain {host} is not in the allow list")
    _resolve_public(host)
    return parts

def _assert_public_peer(response):
    """Reject DNS rebinding by checking the connected socket, not only DNS answers."""
    obj = response
    sock = None
    for attr in ("fp", "raw", "_sock"):
        obj = getattr(obj, attr, None)
        if obj is None:
            break
        if attr == "_sock":
            sock = obj
    if sock is None:
        raise NetworkDenied("could not verify the connected peer address")
    ip = ipaddress.ip_address(sock.getpeername()[0])
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise NetworkDenied("connected peer is not a public address")

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self._skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"): self._skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip: self._skip -= 1
    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text: self.parts.append(text)

def _to_text(body, content_type):
    if "html" in content_type:
        parser = _Text(); parser.feed(body); return re.sub(r"\n{3,}", "\n\n", "\n".join(parser.parts))
    return body

class WebClient:
    def __init__(self, policy=None, secrets=None, user_agent="daily-coder/1.0"):
        self.policy = policy or {}
        self.secrets = secrets
        self.user_agent = user_agent
        self.calls = 0
        self._lock = threading.Lock()
        self._fetch_cache = {}
        self._search_cache = {}

    def _budget(self):
        with self._lock:
            cap = self.policy.get("max_calls_per_run")
            if cap is not None and self.calls >= cap:
                raise NetworkDenied("network call budget exhausted for this run")
            self.calls += 1

    def fetch(self, args):
        url = args["url"]
        max_bytes = min(int(args.get("max_bytes", DEFAULT_MAX_BYTES)), DEFAULT_MAX_BYTES)
        cache_key = (url, max_bytes)
        if cache_key in self._fetch_cache:
            return self._fetch_cache[cache_key]
        self._budget()
        hops = 0
        visited = set()
        while True:
            if url in visited:
                return {"url": url, "status": None, "error": "circular redirect detected"}
            visited.add(url)
            validate_url(url, self.policy)
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,text/plain,application/json;q=0.9"})
            opener = urllib.request.build_opener(_NoRedirect())
            try:
                response = opener.open(request, timeout=int(self.policy.get("timeout_s", 20)))
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308) and hops < 3:
                    url = urllib.parse.urljoin(url, exc.headers.get("Location", "")); hops += 1; continue
                return {"url": url, "status": exc.code, "error": f"HTTP {exc.code}"}
            except OSError as exc:
                return {"url": url, "status": None, "error": str(exc)[:500]}
            with response:
                _assert_public_peer(response)
                content_type = (response.headers.get("Content-Type") or "").lower()
                if not any(t in content_type for t in ALLOWED_TYPES):
                    return {"url": url, "status": response.status, "error": f"unsupported content type: {content_type or 'unknown'}"}
                body = response.read(max_bytes + 1).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            truncated = len(body) > max_bytes
            text = _to_text(body[:max_bytes], content_type)
            result = {"url": url, "status": 200, "content_type": content_type, "truncated": truncated,
                    "citation": url, "text": text}
            self._fetch_cache[cache_key] = result
            return result

    def search(self, args):
        """Brave Search is the reference backend. Other backends register the same contract."""
        cache_key = (args["query"].strip().lower(), min(int(args.get("count", 5)), 10))
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        self._budget()
        backend = self.policy.get("search_backend", "brave")
        if backend != "brave":
            raise NetworkDenied(f"search backend {backend} has no configured adapter")
        key = self.secrets.get("BRAVE_SEARCH_API_KEY") if self.secrets else None
        if not key:
            raise NetworkDenied("BRAVE_SEARCH_API_KEY is not configured")
        query = urllib.parse.urlencode({"q": args["query"], "count": min(int(args.get("count", 5)), 10)})
        request = urllib.request.Request(f"https://api.search.brave.com/res/v1/web/search?{query}",
                                         headers={"X-Subscription-Token": key, "Accept": "application/json",
                                                  "User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=int(self.policy.get("timeout_s", 20))) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except OSError as exc:
            return {"query": args["query"], "error": str(exc)[:500], "results": []}
        results = [{"title": r.get("title"), "url": r.get("url"), "snippet": r.get("description")}
                   for r in (payload.get("web", {}).get("results") or [])]
        result = {"query": args["query"], "results": results}
        self._search_cache[cache_key] = result
        return result

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are surfaced as errors so every hop is revalidated against SSRF rules."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
