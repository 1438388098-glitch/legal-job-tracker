import httpx
import pytest

from app.collect import http as httpmod
from app.collect.http import fetch


class _FakeClient:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        self.timeout = timeout
        return self.behavior(url, params)


def _patch(monkeypatch, behavior):
    client = _FakeClient(behavior)
    monkeypatch.setattr(httpmod, "_client", lambda verify: client)
    monkeypatch.setattr(httpmod.time, "sleep", lambda s: None)
    return client


def test_fetch_retries_network_error_then_raises(monkeypatch):
    def boom(url, params):
        raise httpx.ConnectError("x")

    client = _patch(monkeypatch, boom)
    with pytest.raises(httpx.ConnectError):
        fetch("https://example.com", tries=3)
    assert client.calls == 3


def test_fetch_does_not_retry_404(monkeypatch):
    """4xx 是地址不对，重试三次纯属浪费（一期要抓几百个详情页）。"""
    def notfound(url, params):
        return httpx.Response(404, request=httpx.Request("GET", url))

    client = _patch(monkeypatch, notfound)
    with pytest.raises(httpx.HTTPStatusError):
        fetch("https://example.com/gone", tries=3)
    assert client.calls == 1


def test_fetch_retries_5xx(monkeypatch):
    def server_error(url, params):
        return httpx.Response(503, request=httpx.Request("GET", url))

    client = _patch(monkeypatch, server_error)
    with pytest.raises(httpx.HTTPStatusError):
        fetch("https://example.com/busy", tries=2)
    assert client.calls == 2


@pytest.mark.parametrize("msg,calls", [
    ("[SSL: BAD_ECPOINT] bad ecpoint (_ssl.c:1032)", 1),          # 确定性失败，不重试
    ("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred", 3),      # 瞬时抖动，要重试
])
def test_fetch_ssl_error_retry_policy(monkeypatch, msg, calls):
    def boom(url, params):
        raise httpx.ConnectError(msg)

    client = _patch(monkeypatch, boom)
    with pytest.raises(httpx.ConnectError):
        fetch("https://example.com/tls", tries=3)
    assert client.calls == calls


def test_fetch_applies_encoding_override(monkeypatch):
    def gb(url, params):
        return httpx.Response(200, content="中文".encode("gb2312"),
                              headers={"content-type": "text/html"},
                              request=httpx.Request("GET", url))

    _patch(monkeypatch, gb)
    r = fetch("https://example.com/gb", encoding="gb2312")
    assert "中文" in r.text


def test_fetch_passes_per_request_timeout(monkeypatch):
    """慢站不能拖垮整轮采集：详情抓取要能用更短的超时。"""
    def ok(url, params):
        return httpx.Response(200, request=httpx.Request("GET", url))

    client = _patch(monkeypatch, ok)
    fetch("https://example.com/slow", timeout=7.5)
    assert client.timeout == 7.5
