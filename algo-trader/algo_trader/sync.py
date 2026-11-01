"""Data sync CLI.

  python -m algo_trader.sync yahoo --symbol NIFTY --interval 5m
  python -m algo_trader.sync kite-url                    # prints the Zerodha login URL
  python -m algo_trader.sync kite-login REQUEST_TOKEN    # exchanges it, saves session (not printed)
  python -m algo_trader.sync kite --symbol NIFTY --days 365 --interval 5minute
  python -m algo_trader.sync check data/nifty_5m.csv     # quality report for any CSV

API key/secret come from KITE_API_KEY / KITE_API_SECRET. Output defaults to data/<symbol>_<interval>.csv
and is MERGED into any existing file, so repeated syncs grow your history.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

from .data import clean_bars, load_csv, merge_csv, quality_report
from .sources import SourceError
from .sources import kite as K
from .sources.yahoo import fetch_yahoo


def _report(bars, path) -> None:
    r = quality_report(bars)
    print(f"Saved {r['bars']} bars to {path}  ({r.get('from')} -> {r.get('to')}, {r['days']} days)")
    for w in r["warnings"]:
        print(f"  WARNING: {w}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="algo_trader.sync", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    y = sub.add_parser("yahoo"); y.add_argument("--symbol", default="NIFTY")
    y.add_argument("--interval", default="5m"); y.add_argument("--range", dest="rng"); y.add_argument("--out")
    sub.add_parser("kite-url")
    kl = sub.add_parser("kite-login"); kl.add_argument("request_token")
    k = sub.add_parser("kite"); k.add_argument("--symbol", default="NIFTY")
    k.add_argument("--token", type=int, help="instrument token (default: index token for --symbol)")
    k.add_argument("--interval", default="5minute"); k.add_argument("--days", type=int, default=365)
    k.add_argument("--out")
    c = sub.add_parser("check"); c.add_argument("csv")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "yahoo":
            out = a.out or f"data/{a.symbol.lower()}_{a.interval}_yahoo.csv"
            bars = clean_bars(fetch_yahoo(a.symbol, a.interval, a.rng), intraday=a.interval != "1d")
            _report(merge_csv(bars, out), out)
        elif a.cmd == "kite-url":
            key = os.environ.get("KITE_API_KEY") or sys.exit("Set KITE_API_KEY first.")
            print(K.login_url(key))
            print("Log in, then copy request_token from the redirect URL and run: kite-login <request_token>")
        elif a.cmd == "kite-login":
            key, secret = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_API_SECRET")
            if not (key and secret):
                sys.exit("Set KITE_API_KEY and KITE_API_SECRET first.")
            K.save_session(key, K.exchange_request_token(key, secret, a.request_token))
            print(f"Logged in. Session saved to {K.SESSION_FILE} (valid for today only).")
        elif a.cmd == "kite":
            key, tok = K.load_credentials()
            token = a.token or K.INDEX_TOKENS.get(a.symbol.upper()) or sys.exit("Unknown symbol; pass --token.")
            end = datetime.now().replace(microsecond=0)
            bars = K.KiteClient(key, tok).historical(token, a.interval, end - timedelta(days=a.days), end)
            out = a.out or f"data/{a.symbol.lower()}_{a.interval}_kite.csv"
            _report(merge_csv(clean_bars(bars, intraday=a.interval != "day"), out), out)
        elif a.cmd == "check":
            r = quality_report(load_csv(a.csv))
            for kx, v in r.items():
                print(f"{kx}: {v}")
    except SourceError as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
