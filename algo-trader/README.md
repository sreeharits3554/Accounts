# algo-trader

Milestone 1: **backtester + paper broker** for intraday Nifty/BankNifty. Pure Python 3, no dependencies (pytest for tests).

```bash
python -m algo_trader --synthetic-days 250          # sanity run on random-walk data
python -m algo_trader --csv nifty_5min.csv --qty 75 # your real data
python -m pytest -q
python -m algo_trader.web                            # GUI at http://127.0.0.1:8765 (localhost only)
```

CSV columns: `timestamp` (ISO, bar start), `open,high,low,close[,volume]`.

## Design
- `Broker` interface; `PaperBroker` implements it. The future Kite broker implements the same interface, so strategy and risk code never change between paper and live.
- Pessimistic fills: orders fill at the **next bar's open** plus slippage; stop beats target if both hit in one bar; gaps fill at the open.
- `RiskManager` gates every entry (daily loss cap, trades/day, max qty, kill switch).
- Forced square-off at 15:15; no entries after the strategy's cutoff.

## Read this before trusting any number
- **Cost rates are placeholders** (index-futures style). Verify against Zerodha's brokerage calculator.
- **Lot sizes change**; `--qty` is units, check the current NSE lot size.
- Strategy runs on the **index/futures price**, not option premiums. Kite's API does not serve historical data for *expired* option contracts, so an options backtest needs a separate data source (or you record the chain yourself from now on). That is the next design decision.
- The bundled ORB is a machinery baseline, not an edge. On random data it must lose after costs (a test enforces this).

## Roadmap
1. Real data loader via Kite historical API (needs Connect plan) + local cache.
2. Walk-forward / out-of-sample evaluation, parameter sweeps.
3. Options layer (defined-risk spreads) once option data is sorted.
4. `KiteBroker` (static IP, daily token login, order reconciliation), paper-trade live ticks first.
5. Swing/positional strategies.
