"""Tiny HTTP helper with retries (requests is the only dependency)."""

from __future__ import annotations

import time


def post(url: str, retries: int = 3, timeout: int = 120, **kw):
    import requests
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(url, timeout=timeout, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                last = RuntimeError("HTTP %d: %s" % (r.status_code, r.text[:200]))
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                # do not retry client errors; never echo request headers (they carry keys)
                raise RuntimeError("HTTP %d: %s" % (r.status_code, r.text[:300]))
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError("request failed after %d attempts: %s" % (retries, last))
