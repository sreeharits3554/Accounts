"""Zerodha Kite Connect loader (needs the paid Connect plan for market data).

Written against the documented REST API. Not yet verified against the live service
from this project - run `python -m algo_trader.sync kite-check` after your first login.

Secrets: API key/secret/token come from environment variables or `.kite_session.json`
(mode 0600, git-ignored). They are never printed or put into error messages.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from ..models import Bar
from . import SourceError
from ._http import HttpFn, http_json

BASE = "https://api.kite.trade"
LOGIN_URL = "https://kite.zerodha.com/connect/login?v=3&api_key={}"
SESSION_FILE = ".kite_session.json"

# Index instrument tokens commonly documented for NSE. Verify against the instruments dump.
INDEX_TOKENS = {"NIFTY": 256265, "BANKNIFTY": 260105}

# Max days of history per historical-data request (Kite docs). Chunk conservatively.
MAX_DAYS = {"minute": 60, "3minute": 100, "5minute": 100, "10minute": 100,
            "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000}
MIN_GAP_SECONDS = 0.4  # historical endpoint allows ~3 requests/second


def parse_candles(payload: dict) -> List[Bar]:
    if payload.get("status") != "success":
        raise SourceError(f"Kite error ({payload.get('error_type', 'unknown')}): {payload.get('message', '')}")
    out: List[Bar] = []
    for c in payload["data"]["candles"]:
        ts = datetime.fromisoformat(c[0]).replace(tzinfo=None)  # "2024-01-01T09:15:00+0530", already IST
        out.append(Bar(ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]) if len(c) > 5 else 0.0))
    return out


def chunks(start: datetime, end: datetime, max_days: int) -> List[Tuple[datetime, datetime]]:
    spans, cur = [], start
    while cur < end:
        nxt = min(cur + timedelta(days=max_days), end)
        spans.append((cur, nxt))
        cur = nxt + timedelta(seconds=1)
    return spans


class KiteClient:
    def __init__(self, api_key: str, access_token: str, http: Optional[HttpFn] = None,
                 sleep=time.sleep):
        self._key, self._tok = api_key, access_token
        self._http = http or http_json
        self._sleep = sleep

    def _headers(self) -> dict:
        return {"X-Kite-Version": "3", "Authorization": f"token {self._key}:{self._tok}"}

    def historical(self, token: int, interval: str, start: datetime, end: datetime) -> List[Bar]:
        if interval not in MAX_DAYS:
            raise SourceError(f"Unsupported interval {interval!r}. Use one of {sorted(MAX_DAYS)}.")
        bars: List[Bar] = []
        for i, (a, b) in enumerate(chunks(start, end, MAX_DAYS[interval])):
            if i:
                self._sleep(MIN_GAP_SECONDS)
            payload = self._http(f"{BASE}/instruments/historical/{token}/{interval}",
                                 params={"from": a.strftime("%Y-%m-%d %H:%M:%S"),
                                         "to": b.strftime("%Y-%m-%d %H:%M:%S")},
                                 headers=self._headers())
            bars.extend(parse_candles(payload))
        return bars


# ---------------- login & credentials ----------------
def login_url(api_key: str) -> str:
    return LOGIN_URL.format(api_key)


def exchange_request_token(api_key: str, api_secret: str, request_token: str,
                           http: Optional[HttpFn] = None) -> str:
    checksum = hashlib.sha256((api_key + request_token + api_secret).encode()).hexdigest()
    payload = (http or http_json)(f"{BASE}/session/token", headers={"X-Kite-Version": "3"},
                                  data={"api_key": api_key, "request_token": request_token,
                                        "checksum": checksum})
    if payload.get("status") != "success":
        raise SourceError(f"Kite login failed: {payload.get('message', 'unknown error')}")
    return payload["data"]["access_token"]


def save_session(api_key: str, access_token: str, path: str = SESSION_FILE) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"api_key": api_key, "access_token": access_token, "date": date.today().isoformat()}, f)


def load_credentials(path: str = SESSION_FILE) -> Tuple[str, str]:
    key, tok = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_ACCESS_TOKEN")
    if key and tok:
        return key, tok
    if os.path.exists(path):
        with open(path) as f:
            s = json.load(f)
        if s.get("date") != date.today().isoformat():
            raise SourceError("Saved Kite session is from an earlier day. Tokens expire daily; run kite-login again.")
        return s["api_key"], s["access_token"]
    raise SourceError("No Kite credentials. Set KITE_API_KEY and KITE_ACCESS_TOKEN, or run kite-login.")
