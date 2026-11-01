"""Transaction-cost model.

DEFAULTS ARE PLACEHOLDERS modelled on index *futures* charges. Verify every rate
against Zerodha's brokerage calculator / the current NSE+SEBI schedule before you
trust any backtest result. Charges change; keep them configurable.

When the options leg is added, use options-premium rates (STT on sell premium etc.)
instead - the structure below stays the same.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Side


@dataclass
class CostModel:
    brokerage_per_order: float = 20.0      # flat per executed order (capped style)
    brokerage_pct_cap: float = 0.0003      # 0.03% of turnover, whichever is lower
    stt_sell_pct: float = 0.0002           # on sell turnover (futures-style)
    exchange_txn_pct: float = 0.0000183    # both sides
    sebi_pct: float = 0.000001             # both sides
    stamp_buy_pct: float = 0.00002         # buy side only
    gst_pct: float = 0.18                  # on brokerage + exchange + sebi

    def cost(self, side: Side, price: float, qty: int) -> float:
        turnover = price * qty
        brokerage = min(self.brokerage_per_order, turnover * self.brokerage_pct_cap)
        exchange = turnover * self.exchange_txn_pct
        sebi = turnover * self.sebi_pct
        gst = (brokerage + exchange + sebi) * self.gst_pct
        stt = turnover * self.stt_sell_pct if side is Side.SELL else 0.0
        stamp = turnover * self.stamp_buy_pct if side is Side.BUY else 0.0
        return brokerage + exchange + sebi + gst + stt + stamp
