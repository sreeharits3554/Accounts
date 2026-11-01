"""python -m algo_trader [--csv FILE | --synthetic-days N] [--qty 75] [--slippage 0.5]"""
import argparse

from . import (OpeningRangeBreakout, PaperBroker, RiskManager, compute_metrics,
               run_backtest)
from .data import load_csv, synthetic_intraday


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest the baseline ORB strategy.")
    ap.add_argument("--csv", help="CSV with timestamp,open,high,low,close[,volume]")
    ap.add_argument("--synthetic-days", type=int, default=250)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--qty", type=int, default=75, help="units per trade (verify current lot size)")
    ap.add_argument("--slippage", type=float, default=0.5, help="index points per side")
    a = ap.parse_args()

    if a.csv:
        bars = load_csv(a.csv)
        print(f"Loaded {len(bars)} bars from {a.csv}")
    else:
        bars = synthetic_intraday(a.synthetic_days, a.seed)
        print(f"SYNTHETIC random-walk data ({a.synthetic_days} days): no real edge exists; "
              "profit here would indicate a bug.")
    trades = run_backtest(bars, OpeningRangeBreakout(qty=a.qty),
                          PaperBroker(slippage_points=a.slippage), RiskManager())
    print(compute_metrics(trades))


if __name__ == "__main__":
    main()
