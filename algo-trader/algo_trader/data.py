"""Bar data sources: CSV loader and a SYNTHETIC generator for offline testing.

Synthetic data is a random walk. It has no real edge by construction, so a strategy
that "makes money" on it is a bug (look-ahead / cost error), not a discovery.
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from typing import Iterator, List

from .models import Bar


def load_csv(path: str) -> List[Bar]:
    """CSV columns: timestamp (ISO, bar start), open, high, low, close[, volume]."""
    bars: List[Bar] = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            bars.append(Bar(
                ts=datetime.fromisoformat(r["timestamp"]),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r.get("volume") or 0),
            ))
    bars.sort(key=lambda b: b.ts)
    return bars


def synthetic_intraday(days: int = 250, seed: int = 1, start_price: float = 24000.0,
                       bar_minutes: int = 5, vol_per_bar: float = 0.0006) -> List[Bar]:
    rng = random.Random(seed)
    bars: List[Bar] = []
    price = start_price
    day = datetime(2024, 1, 1)
    produced = 0
    while produced < days:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        produced += 1
        ts = day.replace(hour=9, minute=15)
        end = day.replace(hour=15, minute=30)
        while ts < end:
            o = price
            c = o * (1 + rng.gauss(0, vol_per_bar))
            h = max(o, c) * (1 + abs(rng.gauss(0, vol_per_bar / 3)))
            l = min(o, c) * (1 - abs(rng.gauss(0, vol_per_bar / 3)))
            bars.append(Bar(ts, round(o, 2), round(h, 2), round(l, 2), round(c, 2), 0))
            price = c
            ts += timedelta(minutes=bar_minutes)
    return bars


# ---------------- real-data helpers ----------------
from collections import Counter  # noqa: E402
from datetime import time as _time  # noqa: E402
from typing import Dict, Iterable  # noqa: E402

SESSION_OPEN, SESSION_LAST_BAR = _time(9, 15), _time(15, 29)


def save_csv(bars: Iterable[Bar], path: str) -> None:
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([b.ts.isoformat(), b.open, b.high, b.low, b.close, b.volume])


def merge_csv(new_bars: List[Bar], path: str) -> List[Bar]:
    """Union with any existing cache (new bars win on a duplicate timestamp), save, return all."""
    import os
    merged: Dict[datetime, Bar] = {}
    if os.path.exists(path):
        merged.update({b.ts: b for b in load_csv(path)})
    merged.update({b.ts: b for b in new_bars})
    out = [merged[k] for k in sorted(merged)]
    save_csv(out, path)
    return out


def clean_bars(bars: List[Bar], intraday: bool = True) -> List[Bar]:
    """Drop impossible candles and (for intraday) bars outside the 09:15-15:29 NSE session."""
    out = []
    for b in bars:
        if min(b.open, b.high, b.low, b.close) <= 0:
            continue
        if b.high < max(b.open, b.close) or b.low > min(b.open, b.close) or b.high < b.low:
            continue
        if intraday and not (SESSION_OPEN <= b.ts.time() <= SESSION_LAST_BAR):
            continue
        out.append(b)
    seen, dedup = set(), []
    for b in sorted(out, key=lambda x: x.ts):
        if b.ts not in seen:
            seen.add(b.ts)
            dedup.append(b)
    return dedup


def quality_report(bars: List[Bar]) -> Dict[str, object]:
    """Summary the user should read before trusting a backtest on this file."""
    if not bars:
        return {"bars": 0, "days": 0, "warnings": ["no bars"]}
    per_day = Counter(b.ts.date() for b in bars)
    typical = Counter(per_day.values()).most_common(1)[0][0]
    short = sorted(d.isoformat() for d, n in per_day.items() if n < 0.9 * typical)
    warnings = []
    if len(per_day) < 500:
        warnings.append(f"only {len(per_day)} trading days; need ~500+ (two years) before trusting a result")
    if short:
        warnings.append(f"{len(short)} incomplete day(s), e.g. {short[0]}")
    return {"bars": len(bars), "days": len(per_day), "from": bars[0].ts.date().isoformat(),
            "to": bars[-1].ts.date().isoformat(), "bars_per_day": typical,
            "incomplete_days": short, "warnings": warnings}
