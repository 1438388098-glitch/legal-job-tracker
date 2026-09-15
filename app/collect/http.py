import logging
import time

import httpx

log = logging.getLogger("collect")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch(url: str, *, encoding: str | None = None, verify: bool = True,
          params: dict | None = None, tries: int = 3) -> httpx.Response:
    delay = 1.0
    last: Exception | None = None
    for _ in range(tries):
        try:
            r = httpx.get(url, headers={"User-Agent": UA}, timeout=30,
                          follow_redirects=True, verify=verify, params=params)
            r.raise_for_status()
            if encoding:
                r.encoding = encoding
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("fetch %s failed: %s, retrying", url, e)
            time.sleep(delay)
            delay *= 2
    raise last  # type: ignore[misc]
