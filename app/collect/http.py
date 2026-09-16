import logging
import threading
import time

import httpx

log = logging.getLogger("collect")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DEFAULT_TIMEOUT = 30.0

_clients: dict[bool, httpx.Client] = {}
_lock = threading.Lock()


def _client(verify: bool) -> httpx.Client:
    """按 verify 复用连接池：一期要抓几百个详情页，复用长连接明显更快。

    连接数给得比并发数宽裕：慢站会把连接卡在握手/读取上，池子太小会让其他源
    的请求排不到连接而直接 PoolTimeout 失败（珠海/惠州站就曾被深圳站拖垮）。
    """
    with _lock:
        if verify not in _clients:
            _clients[bool(verify)] = httpx.Client(
                headers={"User-Agent": UA}, follow_redirects=True,
                verify=bool(verify), limits=httpx.Limits(
                    max_connections=32, max_keepalive_connections=16),
                timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=8.0))
        return _clients[verify]


# 确定性的 TLS 失败：站点证书链或椭圆曲线参数有问题（如深圳人社的 BAD_ECPOINT），
# 重试多少次都一样，只能改用 http 或放弃。
# 注意 UNEXPECTED_EOF_WHILE_READING 是常见的瞬时抖动，属于可重试，不要放进来。
_HARD_SSL = ("bad ecpoint", "sslv3_alert", "certificate verify failed",
             "unknown ca", "wrong version number", "no shared cipher")


def _retryable(e: Exception) -> bool:
    """只重试网络抖动与 5xx；4xx（除 429）是地址不对，重试纯属浪费。"""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        return code == 429 or code >= 500
    if isinstance(e, httpx.ConnectError):
        low = str(e).lower()
        if any(s in low for s in _HARD_SSL):
            return False
    return True


def close_clients() -> None:
    """进程退出时关闭连接池。httpx.Client 持有 socket，不关是资源泄漏（审计 16）。"""
    for c in _clients.values():
        try:
            c.close()
        except Exception:  # noqa: BLE001 退出路径的清理，失败就失败
            pass
    _clients.clear()


def fetch(url: str, *, encoding: str | None = None, verify: bool = True,
          params: dict | None = None, tries: int = 3,
          timeout: float = DEFAULT_TIMEOUT,
          method: str = "GET", json_body: dict | None = None,
          headers: dict | None = None) -> httpx.Response:
    """抓一个 URL。

    超时故意做得比较短：一期一次要抓几百个详情页，个别政务站单页要挂 20 秒以上，
    与其死等不如放弃这条（正文留空，岗位本身仍会入库），把时间留给其他源。

    method/json_body/headers 是给 JSON 接口用的（如省人社厅国企专区要求 POST +
    Referer，不带就返回空数据）。headers 会覆盖默认 UA 之外的头。
    """
    delay = 1.0
    last: Exception | None = None
    for attempt in range(tries):
        try:
            client = _client(verify)
            if method.upper() == "POST":
                r = client.post(url, params=params, json=json_body, timeout=timeout,
                                headers=headers)
            else:
                r = client.get(url, params=params, timeout=timeout, headers=headers)
            r.raise_for_status()
            if encoding:
                r.encoding = encoding
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            if not _retryable(e) or attempt == tries - 1:
                raise
            log.warning("fetch %s failed: %s, retrying", url, e)
            time.sleep(delay)
            delay *= 2
    raise last  # type: ignore[misc]


def post_json(url: str, *, json_body: dict, params: dict | None = None,
              encoding: str | None = None, verify: bool = True, tries: int = 3,
              timeout: float = DEFAULT_TIMEOUT,
              headers: dict | None = None) -> dict:
    """POST 一个 JSON 接口并解析响应，顺手补上 Referer（多数政务接口校验它）。"""
    h = {"Referer": url, **(headers or {})}
    r = fetch(url, encoding=encoding, verify=verify, params=params, tries=tries,
              timeout=timeout, method="POST", json_body=json_body, headers=h)
    return r.json()
