"""Risk gate. Every entry must pass through here - in backtest, paper and live."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskManager:
    max_daily_loss: float = 5000.0     # INR; stop opening trades once realised loss reaches this
    max_trades_per_day: int = 3
    max_qty: int = 150                 # hard cap on order size (units, not lots)
    killed: bool = False               # manual / automatic kill switch

    def kill(self) -> None:
        self.killed = True

    def allow_entry(self, day_pnl: float, trades_today: int, qty: int) -> bool:
        if self.killed:
            return False
        if day_pnl <= -abs(self.max_daily_loss):
            return False
        if trades_today >= self.max_trades_per_day:
            return False
        if qty > self.max_qty:
            return False
        return True
