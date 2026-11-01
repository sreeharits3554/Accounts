"""Strategy interface and a baseline Opening Range Breakout (ORB).

ORB is a *baseline to test the machinery*, not a claim of edge. Expect it to be
roughly flat-to-negative after costs on random data - that is the sanity check.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, time
from typing import Optional

from .models import Bar, Order, Side


class Strategy(ABC):
    @abstractmethod
    def on_bar(self, bar: Bar, in_position: bool) -> Optional[Order]:
        """Called once per COMPLETED bar. Return an Order (filled next bar open) or None."""


class OpeningRangeBreakout(Strategy):
    def __init__(self, qty: int = 75, range_end: time = time(9, 30),
                 last_entry: time = time(14, 30), reward_risk: float = 1.5):
        self.qty = qty
        self.range_end = range_end
        self.last_entry = last_entry
        self.rr = reward_risk
        self._day: Optional[date] = None
        self._hi = self._lo = None
        self._done = False

    def on_bar(self, bar: Bar, in_position: bool) -> Optional[Order]:
        if bar.ts.date() != self._day:
            self._day, self._hi, self._lo, self._done = bar.ts.date(), None, None, False
        t = bar.ts.time()
        if t < self.range_end:  # still building the opening range
            self._hi = bar.high if self._hi is None else max(self._hi, bar.high)
            self._lo = bar.low if self._lo is None else min(self._lo, bar.low)
            return None
        if in_position or self._done or self._hi is None or t > self.last_entry:
            return None
        if bar.close > self._hi:
            risk = bar.close - self._lo
            self._done = True
            return Order(Side.BUY, self.qty, stop=self._lo,
                         target=bar.close + self.rr * risk, tag="orb_long")
        if bar.close < self._lo:
            risk = self._hi - bar.close
            self._done = True
            return Order(Side.SELL, self.qty, stop=self._hi,
                         target=bar.close - self.rr * risk, tag="orb_short")
        return None
