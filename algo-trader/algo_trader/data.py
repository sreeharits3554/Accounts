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
