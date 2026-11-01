"""Core data types shared by the backtester, paper broker and (later) the live broker."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(Enum):
    BUY = 1
    SELL = -1


@dataclass(frozen=True)
class Bar:
    ts: datetime  # bar START time
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Order:
    """Market order with optional protective stop / target (absolute prices)."""

    side: Side
    qty: int
    stop: Optional[float] = None
    target: Optional[float] = None
    tag: str = ""


@dataclass
class Position:
    side: Side
    qty: int
    entry_price: float
    entry_ts: datetime
    entry_costs: float
    stop: Optional[float] = None
    target: Optional[float] = None


@dataclass(frozen=True)
class Trade:
    entry_ts: datetime
    exit_ts: datetime
    side: Side
    qty: int
    entry_price: float
    exit_price: float
    costs: float
    pnl: float  # net of costs
    reason: str  # "stop" | "target" | "eod" | "end_of_data" | "manual"
