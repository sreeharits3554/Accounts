"""Tiny stdlib HTTP helper. Honors HTTPS_PROXY / SSL_CERT_FILE from the environment.

Error messages deliberately omit request headers so tokens can never leak into logs.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import SourceError

HttpFn = Callable[..., Dict[str, Any]]  # (url, params=None, headers=None, data=None) -> parsed JSON


def http_json(url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
              data: Optional[dict] = None, retries: int = 3, timeout: int = 30) -> Dict[str, Any]:
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    body = urlencode(data).encode() if data is not None else None
    req = Request(url, data=body, headers=headers or {})
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except HTTPError as e:
            raw = e.read()
            if e.code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            try:
                msg = json.loads(raw).get("message") or json.loads(raw)
            except Exception:
                msg = raw[:200].decode("utf-8", "replace")
            raise SourceError(f"HTTP {e.code} from {url.split('?')[0]}: {msg}") from None
        except (URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise SourceError(f"Network error reaching {url.split('?')[0]}: {getattr(e, 'reason', e)}") from None
    raise SourceError("unreachable")  # pragma: no cover
