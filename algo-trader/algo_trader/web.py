"""Local GUI server (stdlib only):  python -m algo_trader.web  ->  http://127.0.0.1:8765

Binds to localhost only. There is no live trading here; it only runs backtests.
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .export import run_to_dict

UI_FILE = os.path.join(os.path.dirname(__file__), "..", "ui", "app.html")
WRAP = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>{}</body></html>')

PARAMS = {"days": int, "seed": int, "qty": int, "slippage": float, "rr": float,
          "max_daily_loss": float, "max_trades": int}


def render_page() -> bytes:
    with open(UI_FILE, encoding="utf-8") as f:
        return WRAP.format(f.read()).encode()


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def _safe_data_path(name: str) -> str:
    """Only plain *.csv names inside data/ - no paths, no traversal."""
    if not name or name != os.path.basename(name) or not name.endswith(".csv"):
        raise ValueError("invalid data file name")
    path = os.path.join(DATA_DIR, name)
    if not os.path.isfile(path):
        raise ValueError(f"data file not found: {name}")
    return path


def list_files() -> list:
    from .data import load_csv, quality_report
    out = []
    if os.path.isdir(DATA_DIR):
        for n in sorted(os.listdir(DATA_DIR)):
            if n.endswith(".csv"):
                try:
                    out.append({"name": n, **quality_report(load_csv(os.path.join(DATA_DIR, n)))})
                except Exception as e:  # unreadable file should not break the page
                    out.append({"name": n, "bars": 0, "days": 0, "warnings": [f"unreadable: {e}"]})
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, render_page(), "text/html; charset=utf-8")
        if u.path == "/api/files":
            return self._send(200, json.dumps(list_files()).encode(), "application/json")
        if u.path == "/api/run":
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                kw = {k: PARAMS[k](v) for k, v in q.items() if k in PARAMS}
                if not 5 <= kw.get("days", 250) <= 2000:
                    raise ValueError("days must be between 5 and 2000")
                if q.get("file"):
                    from .data import clean_bars, load_csv
                    bars = clean_bars(load_csv(_safe_data_path(q["file"])))
                    if not bars:
                        raise ValueError("no usable bars in that file")
                    kw.pop("days", None); kw.pop("seed", None)
                    out = run_to_dict(bars, source=q["file"], **kw)
                    out["quality"] = next((f for f in list_files() if f["name"] == q["file"]), None)
                else:
                    out = run_to_dict(**kw)
                return self._send(200, json.dumps(out).encode(), "application/json")
            except (ValueError, TypeError) as e:
                return self._send(400, json.dumps({"error": str(e)}).encode(), "application/json")
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a) -> None:  # keep console quiet
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Algo Trader console: http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
