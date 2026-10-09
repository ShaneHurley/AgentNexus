import socket
import pytest
from agent_core.providers import http

@pytest.mark.parametrize("url",["http://169.254.169.254/latest","http://10.0.0.1/","http://[::1]/","http://user:password@public.test/","file:///etc/passwd"])
def test_public_retrieval_denies_private_or_credential_urls(url,monkeypatch):
    def forbidden(*a,**kw): pytest.fail("denied URL opened a socket")
    monkeypatch.setattr(socket,"create_connection",forbidden)
    monkeypatch.setattr(socket,"getaddrinfo",lambda host,port,**kw:[(socket.AF_INET,socket.SOCK_STREAM,6,"",(host,port))])
    assert hasattr(http,"get_public_text"), "public-only retrieval boundary missing"
    with pytest.raises(http.ProviderError): http.get_public_text(url)

class Response:
    def __init__(self,status=200,location=None,body=b"public content"):
        self.status=status;self.location=location;self.body=body
    def getheader(self,key,default=None):
        if key=="Location": return self.location
        if key=="Content-Type": return "text/plain; charset=utf-8"
        return default
    def read(self,limit):
        out=self.body[:limit];self.body=self.body[limit:];return out
    def close(self): pass

def install(monkeypatch,responses):
    endpoints=[]
    monkeypatch.setattr(socket,"getaddrinfo",lambda host,port,**kw:[(socket.AF_INET,socket.SOCK_STREAM,6,"",("93.184.216.34" if host=="public.test" else "127.0.0.1",port))])
    class Socket:
        def close(self): pass
        def do_handshake(self): pass
    def connect(endpoint,timeout=None): endpoints.append(endpoint);return Socket()
    monkeypatch.setattr(socket,"create_connection",connect)
    class Connection:
        def __init__(self,host,port=None,timeout=None): self.host=host;self.sock=None
        def request(self,method,path,headers=None): assert self.sock is not None
        def getresponse(self): return responses.pop(0)
        def close(self): self.sock.close()
    import http.client
    monkeypatch.setattr(http.client,"HTTPConnection",Connection)
    return endpoints

def test_socket_connects_to_validated_ip_without_hostname_rebinding(monkeypatch):
    endpoints=install(monkeypatch,[Response()])
    assert hasattr(http,"get_public_text"), "public-only retrieval boundary missing"
    assert http.get_public_text("http://public.test/abc")=="public content"
    assert endpoints==[("93.184.216.34",80)]

def test_redirect_to_private_host_is_rejected_before_connect(monkeypatch):
    endpoints=install(monkeypatch,[Response(302,"http://private.test/secret")])
    assert hasattr(http,"get_public_text"), "public-only retrieval boundary missing"
    with pytest.raises(http.ProviderError): http.get_public_text("http://public.test/")
    assert endpoints==[("93.184.216.34",80)]

def test_oversized_body_is_rejected(monkeypatch):
    install(monkeypatch,[Response(body=b"x"*400001)])
    assert hasattr(http,"get_public_text"), "public-only retrieval boundary missing"
    with pytest.raises(http.ProviderError): http.get_public_text("http://public.test/")


def test_https_keeps_original_hostname_authentication(monkeypatch):
    from http import client
    import ssl
    endpoints=install(monkeypatch,[Response()]);hostnames=[]
    connection=client.HTTPConnection
    monkeypatch.setattr(client,"HTTPSConnection",lambda host,port,timeout,context:connection(host,port,timeout))
    class Context:
        def wrap_socket(self,sock,server_hostname,do_handshake_on_connect=True): hostnames.append(server_hostname);return sock
    monkeypatch.setattr(ssl,"create_default_context",lambda:Context())
    assert http.get_public_text("https://public.test/")=="public content"
    assert endpoints==[("93.184.216.34",443)] and hostnames==["public.test"]


def test_dns_resolution_obeys_call_deadline(monkeypatch):
    import threading,time
    release=threading.Event();finished=threading.Event()
    def resolve(*a,**kw):
        try: release.wait(1);return []
        finally: finished.set()
    monkeypatch.setattr(socket,"getaddrinfo",resolve)
    started=time.monotonic()
    try:
        with pytest.raises(http.ProviderError): http.get_public_text("http://slow.test/",timeout=.03)
        assert time.monotonic()-started < .3
    finally:
        release.set();assert finished.wait(1)

def test_slow_headers_are_interrupted_by_deadline(monkeypatch):
    import threading,time
    from http import client
    install(monkeypatch,[Response()]);closed=threading.Event()
    class Socket:
        def shutdown(self,*a): closed.set()
        def close(self): closed.set()
    monkeypatch.setattr(socket,"create_connection",lambda *a,**kw:Socket())
    class Connection:
        def __init__(self,*a,**kw): self.sock=None
        def request(self,*a,**kw): pass
        def getresponse(self):
            assert closed.wait(1), "absolute deadline did not interrupt headers"
            return Response()
        def close(self): self.sock.close()
    monkeypatch.setattr(client,"HTTPConnection",Connection)
    started=time.monotonic()
    with pytest.raises(http.ProviderError): http.get_public_text("http://public.test/",timeout=.03)
    assert time.monotonic()-started < .3
