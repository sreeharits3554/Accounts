"""Broker interface + PaperBroker simulator.

The live Kite broker (later milestone) must implement the same `Broker` interface,
so strategies and the risk layer never change between paper and live.

Fill rules (deliberately pessimistic, no look-ahead):
  * Orders submitted on bar N fill at the OPEN of bar N+1, plus adverse slippage.
  * Stop/target are checked against each bar's high/low. If both could be hit in
    the same bar, the STOP is assumed to hit first.
  * A gap through the stop fills at the open, not at the stop price.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .costs import CostModel
from .models import Bar, Order, Position, Side, Trade


class Broker(ABC):
    @abstractmethod
    def submit(self, order: Order) -> None: ...

    @abstractmethod
    def close_position(self, reason: str = "manual") -> None: ...

    @abstractmethod
    def on_bar(self, bar: Bar) -> None: ...

    @property
    @abstractmethod
    def position(self) -> Optional[Position]: ...

    @property
    @abstractmethod
    def trades(self) -> List[Trade]: ...


class PaperBroker(Broker):
    def __init__(self, costs: Optional[CostModel] = None, slippage_points: float = 0.5):
        self.costs = costs or CostModel()
        self.slippage = slippage_points
        self._position: Optional[Position] = None
        self._pending: List[Order] = []
        self._close_reason: Optional[str] = None
        self._trades: List[Trade] = []

    # --- Broker interface -------------------------------------------------
    @property
    def position(self) -> Optional[Position]:
        return self._position

    @property
    def trades(self) -> List[Trade]:
        return self._trades

    def submit(self, order: Order) -> None:
        self._pending.append(order)

    def close_position(self, reason: str = "manual") -> None:
        if self._position is not None:
            self._close_reason = reason

    def on_bar(self, bar: Bar) -> None:
        # 1. Fill what was queued on the previous bar at this bar's open.
        if self._close_reason and self._position:
            self._exit(bar.ts, bar.open, self._close_reason)
        self._close_reason = None
        for order in self._pending:
            if self._position is None:
                self._enter(order, bar)
        self._pending.clear()
        # 2. Protective exits during this bar.
        self._check_exits(bar)

    def force_close_at(self, bar: Bar, reason: str = "end_of_data") -> None:
        if self._position:
            self._exit(bar.ts, bar.close, reason)

    # --- internals --------------------------------------------------------
    def _slip(self, side: Side, price: float) -> float:
        return price + self.slippage * side.value  # buys pay up, sells receive less

    def _enter(self, o: Order, bar: Bar) -> None:
        price = self._slip(o.side, bar.open)
        self._position = Position(
            side=o.side, qty=o.qty, entry_price=price, entry_ts=bar.ts,
            entry_costs=self.costs.cost(o.side, price, o.qty),
            stop=o.stop, target=o.target,
        )

    def _check_exits(self, bar: Bar) -> None:
        p = self._position
        if p is None:
            return
        if p.side is Side.BUY:
            if p.stop is not None and bar.low <= p.stop:
                self._exit(bar.ts, min(p.stop, bar.open), "stop")
            elif p.target is not None and bar.high >= p.target:
                self._exit(bar.ts, p.target, "target")
        else:
            if p.stop is not None and bar.high >= p.stop:
                self._exit(bar.ts, max(p.stop, bar.open), "stop")
            elif p.target is not None and bar.low <= p.target:
                self._exit(bar.ts, p.target, "target")

    def _exit(self, ts, raw_price: float, reason: str) -> None:
        p = self._position
        assert p is not None
        exit_side = Side.SELL if p.side is Side.BUY else Side.BUY
        price = self._slip(exit_side, raw_price)
        exit_costs = self.costs.cost(exit_side, price, p.qty)
        gross = (price - p.entry_price) * p.qty * p.side.value
        costs = p.entry_costs + exit_costs
        self._trades.append(Trade(
            entry_ts=p.entry_ts, exit_ts=ts, side=p.side, qty=p.qty,
            entry_price=p.entry_price, exit_price=price,
            costs=costs, pnl=gross - costs, reason=reason,
        ))
        self._position = None
