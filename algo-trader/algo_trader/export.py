"""Run a backtest and return a JSON-serialisable dict for the GUI."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from .backtest import compute_metrics, run_backtest
from .broker import PaperBroker
from .data import synthetic_intraday
from .models import Bar
from .risk import RiskManager
from .strategy import OpeningRangeBreakout


def run_to_dict(bars: Optional[List[Bar]] = None, *, days: int = 250, seed: int = 1,
                qty: int = 75, slippage: float = 0.5, rr: float = 1.5,
                max_daily_loss: float = 5000.0, max_trades: int = 3,
                max_qty: int = 150, source: str = "synthetic") -> Dict[str, Any]:
    if qty > max_qty:
        raise ValueError(f"qty {qty} exceeds risk cap max_qty={max_qty}")
    synthetic = bars is None
    if bars is None:
        bars = synthetic_intraday(days, seed)
    risk = RiskManager(max_daily_loss=max_daily_loss, max_trades_per_day=max_trades, max_qty=max_qty)
    trades = run_backtest(bars, OpeningRangeBreakout(qty=qty, reward_risk=rr),
                          PaperBroker(slippage_points=slippage), risk)
    m = compute_metrics(trades)

    equity, drawdown, cum, peak = [], [], 0.0, 0.0
    monthly: Dict[str, float] = defaultdict(float)
    for t in trades:
        cum += t.pnl
        peak = max(peak, cum)
        d = t.exit_ts.date().isoformat()
        equity.append({"d": d, "e": round(cum, 2)})
        drawdown.append({"d": d, "v": round(cum - peak, 2)})
        monthly[d[:7]] += t.pnl

    return {
        "synthetic": synthetic,
        "source": source,
        "config": {"days": days, "seed": seed, "qty": qty, "slippage": slippage, "rr": rr,
                   "max_daily_loss": max_daily_loss, "max_trades": max_trades, "max_qty": max_qty,
                   "bars": len(bars),
                   "from": bars[0].ts.date().isoformat() if bars else None,
                   "to": bars[-1].ts.date().isoformat() if bars else None},
        "metrics": {
            "trades": m.trades, "net_pnl": round(m.net_pnl, 2), "costs": round(m.total_costs, 2),
            "gross_pnl": round(m.net_pnl + m.total_costs, 2), "win_rate": m.win_rate,
            "profit_factor": None if m.profit_factor == float("inf") else m.profit_factor,
            "avg_trade": round(m.avg_trade, 2), "max_drawdown": round(m.max_drawdown, 2),
        },
        "equity": equity,
        "drawdown": drawdown,
        "monthly": [{"m": k, "pnl": round(v, 2)} for k, v in sorted(monthly.items())],
        "exit_reasons": dict(Counter(t.reason for t in trades)),
        "trades": [{
            "entry": t.entry_ts.isoformat(timespec="minutes"), "exit": t.exit_ts.isoformat(timespec="minutes"),
            "side": "LONG" if t.side.value > 0 else "SHORT", "qty": t.qty,
            "ep": round(t.entry_price, 2), "xp": round(t.exit_price, 2),
            "costs": round(t.costs, 2), "pnl": round(t.pnl, 2), "reason": t.reason,
        } for t in trades],
    }
