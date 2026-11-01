"""Yahoo Finance loader (unofficial, free, no login).

Limits you must know about:
  * 5-minute bars only reach back ~60 days; 1-minute ~7 days. Fine for testing the
    pipeline, too short to validate an intraday strategy.
  * Unofficial endpoint: it can change, rate-limit or disappear without notice.
  * Index volume is 0.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote

from ..models import Bar
from . import SourceError
from ._http import HttpFn, http_json

SYMBOLS = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
MAX_RANGE = {"1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d", "30m": "60d", "60m": "730d", "1d": "max"}
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (algo-trader research script)"}


def parse_chart(payload: dict) -> List[Bar]:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise SourceError(f"Yahoo error: {chart['error'].get('description') or chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise SourceError("Yahoo returned no data (symbol/interval/range not available).")
    r = results[0]
    stamps = r.get("timestamp") or []
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    offset = int((r.get("meta") or {}).get("gmtoffset", 19800))  # exchange tz (IST = +19800s)
    bars: List[Bar] = []
    for i, t in enumerate(stamps):
        try:
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        except (KeyError, IndexError):
            continue
        if None in (o, h, l, c):  # Yahoo emits nulls for missing candles
            continue
        v = (q.get("volume") or [0] * len(stamps))[i] or 0
        ts = datetime.fromtimestamp(t + offset, tz=timezone.utc).replace(tzinfo=None)
        bars.append(Bar(ts, float(o), float(h), float(l), float(c), float(v)))
    return bars


def fetch_yahoo(symbol: str = "NIFTY", interval: str = "5m", range_: Optional[str] = None,
                http: Optional[HttpFn] = None) -> List[Bar]:
    sym = SYMBOLS.get(symbol.upper(), symbol)
    rng = range_ or MAX_RANGE.get(interval, "60d")
    payload = (http or http_json)(URL.format(quote(sym)), params={"interval": interval, "range": rng},
                                  headers=HEADERS)
    return parse_chart(payload)
