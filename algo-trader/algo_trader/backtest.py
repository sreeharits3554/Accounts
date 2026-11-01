"""Backtest driver + performance metrics.

The driver talks to a `Broker`, so the exact same loop can later run against live
bars with a Kite-backed broker (paper-first, then live).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import List

from .broker import Broker, PaperBroker
from .models import Bar, Trade
from .risk import RiskManager
from .strategy import Strategy


def run_backtest(bars: List[Bar], strategy: Strategy, broker: Broker,
                 risk: RiskManager, square_off: time = time(15, 15)) -> List[Trade]:
    day = None
    day_start = 0
    for bar in bars:
        if bar.ts.date() != day:
            day, day_start = bar.ts.date(), len(broker.trades)
        t = bar.ts.time()
        if t >= square_off and broker.position:
            broker.close_position("eod")
        broker.on_bar(bar)
        if t >= square_off:
            continue  # never open new positions into the close
        in_pos = broker.position is not None
        order = strategy.on_bar(bar, in_pos)
        if order is None:
            continue
        today = broker.trades[day_start:]
        day_pnl = sum(tr.pnl for tr in today)
        trades_today = len(today) + (1 if in_pos else 0)
        if risk.allow_entry(day_pnl, trades_today, order.qty):
            broker.submit(order)
    if bars and isinstance(broker, PaperBroker):
        broker.force_close_at(bars[-1])
    return broker.trades


@dataclass(frozen=True)
class Metrics:
    trades: int
    net_pnl: float
    total_costs: float
    win_rate: float
    profit_factor: float
    avg_trade: float
    max_drawdown: float

    def __str__(self) -> str:
        return (f"trades={self.trades}  net_pnl={self.net_pnl:,.0f}  costs={self.total_costs:,.0f}  "
                f"win_rate={self.win_rate:.1%}  profit_factor={self.profit_factor:.2f}  "
                f"avg_trade={self.avg_trade:,.1f}  max_drawdown={self.max_drawdown:,.0f}")


def compute_metrics(trades: List[Trade]) -> Metrics:
    if not trades:
        return Metrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [-p for p in pnls if p < 0]
    equity = peak = dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return Metrics(
        trades=len(trades), net_pnl=sum(pnls), total_costs=sum(t.costs for t in trades),
        win_rate=len(wins) / len(pnls),
        profit_factor=(sum(wins) / sum(losses)) if losses else float("inf"),
        avg_trade=sum(pnls) / len(pnls), max_drawdown=dd,
    )
