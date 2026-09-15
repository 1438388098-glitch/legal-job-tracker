import httpx

from app.collect.http import fetch


def test_fetch_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise httpx.ConnectError("x")

    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr("app.collect.http.time.sleep", lambda s: None)
    try:
        fetch("https://example.com", tries=3)
        assert False, "应当抛出异常"
    except httpx.ConnectError:
        assert calls["n"] == 3
