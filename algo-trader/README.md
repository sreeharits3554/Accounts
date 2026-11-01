# algo-trader

Milestone 1: **backtester + paper broker** for intraday Nifty/BankNifty. Pure Python 3, no dependencies (pytest for tests).

```bash
python -m algo_trader --synthetic-days 250          # sanity run on random-walk data
python -m algo_trader --csv nifty_5min.csv --qty 75 # your real data
python -m pytest -q
python -m algo_trader.web                            # GUI at http://127.0.0.1:8765 (localhost only)
```

## Syncing real data
```bash
# Free, no login. ~60 days of 5-minute bars only (pipeline testing, not validation)
python -m algo_trader.sync yahoo --symbol NIFTY          # or BANKNIFTY

# Kite Connect (needs the paid Connect plan). Keys come from the environment, never from files in git.
export KITE_API_KEY=...  KITE_API_SECRET=...
python -m algo_trader.sync kite-url                       # open it, log in, copy request_token from the redirect
python -m algo_trader.sync kite-login <request_token>     # saves .kite_session.json (0600, valid for today)
python -m algo_trader.sync kite --symbol NIFTY --days 730

python -m algo_trader.sync check data/nifty_5minute_kite.csv   # quality report
```
Files land in `data/` (git-ignored) and are **merged** on each sync, so history grows. They appear in the GUI's data menu.
The Kite loader is written to the documented API but has **not been run against the live service yet**;
the Yahoo endpoint is unofficial and may change. Check the quality report before trusting any backtest.

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
