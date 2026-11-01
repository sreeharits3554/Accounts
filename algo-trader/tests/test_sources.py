import hashlib
import json
import os
from datetime import datetime, timedelta

import pytest

from algo_trader import sync
from algo_trader.data import clean_bars, load_csv, merge_csv, quality_report
from algo_trader.models import Bar
from algo_trader.sources import SourceError
from algo_trader.sources import kite as K
from algo_trader.sources.yahoo import fetch_yahoo, parse_chart

# 2024-01-02 03:45:00 UTC == 09:15 IST
T0 = int((datetime(2024, 1, 2, 3, 45) - datetime(1970, 1, 1)).total_seconds())


def yahoo_payload():
    return {"chart": {"error": None, "result": [{
        "meta": {"gmtoffset": 19800},
        "timestamp": [T0, T0 + 300, T0 + 600],
        "indicators": {"quote": [{
            "open": [100, None, 102], "high": [101, None, 103], "low": [99, None, 101],
            "close": [100.5, None, 102.5], "volume": [0, 0, 0]}]}}]}}


def test_yahoo_parse_converts_to_ist_and_drops_null_candles():
    bars = parse_chart(yahoo_payload())
    assert len(bars) == 2
    assert bars[0].ts == datetime(2024, 1, 2, 9, 15)
    assert bars[1].ts == datetime(2024, 1, 2, 9, 25)
    assert bars[0].close == 100.5


def test_yahoo_error_payload_raises():
    with pytest.raises(SourceError):
        parse_chart({"chart": {"result": None, "error": {"description": "No data found"}}})


def test_fetch_yahoo_maps_symbol_and_default_range():
    seen = {}

    def fake(url, params=None, headers=None, data=None):
        seen.update(url=url, params=params)
        return yahoo_payload()

    fetch_yahoo("NIFTY", "5m", http=fake)
    assert "%5ENSEI" in seen["url"] and seen["params"] == {"interval": "5m", "range": "60d"}


def kite_payload():
    return {"status": "success", "data": {"candles": [
        ["2024-01-02T09:15:00+0530", 21700, 21720, 21690, 21710, 0],
        ["2024-01-02T09:20:00+0530", 21710, 21730, 21700, 21725, 0]]}}


def test_kite_parse_candles_naive_ist():
    bars = K.parse_candles(kite_payload())
    assert bars[0].ts == datetime(2024, 1, 2, 9, 15) and bars[1].close == 21725


def test_kite_error_payload_raises_without_secrets():
    with pytest.raises(SourceError) as e:
        K.parse_candles({"status": "error", "error_type": "TokenException", "message": "Incorrect api_key"})
    assert "TokenException" in str(e.value)


def test_kite_chunking_covers_range_without_overlap():
    a, b = datetime(2023, 1, 1), datetime(2024, 1, 1)
    spans = K.chunks(a, b, 100)
    assert spans[0][0] == a and spans[-1][1] == b
    assert all(s[1] - s[0] <= timedelta(days=100) for s in spans)
    assert all(spans[i][1] < spans[i + 1][0] for i in range(len(spans) - 1))


def test_kite_historical_calls_per_chunk_sends_auth_and_throttles():
    calls, sleeps = [], []

    def fake(url, params=None, headers=None, data=None):
        calls.append((url, params, headers))
        return kite_payload()

    c = K.KiteClient("KEY", "TOKEN", http=fake, sleep=sleeps.append)
    bars = c.historical(256265, "5minute", datetime(2023, 1, 1), datetime(2023, 12, 31))
    assert len(calls) == len(K.chunks(datetime(2023, 1, 1), datetime(2023, 12, 31), 100)) >= 4
    assert len(sleeps) == len(calls) - 1  # throttled between requests
    url, params, headers = calls[0]
    assert url.endswith("/instruments/historical/256265/5minute")
    assert headers["Authorization"] == "token KEY:TOKEN" and headers["X-Kite-Version"] == "3"
    assert len(bars) == 2 * len(calls)


def test_kite_rejects_unknown_interval():
    with pytest.raises(SourceError):
        K.KiteClient("k", "t", http=lambda *a, **k: {}).historical(1, "7minute", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_kite_login_checksum_is_sha256_of_key_token_secret():
    captured = {}

    def fake(url, params=None, headers=None, data=None):
        captured.update(data=data)
        return {"status": "success", "data": {"access_token": "AT"}}

    assert K.exchange_request_token("KEY", "SECRET", "REQ", http=fake) == "AT"
    assert captured["data"]["checksum"] == hashlib.sha256(b"KEYREQSECRET").hexdigest()
    assert "SECRET" not in json.dumps(captured["data"])  # the secret itself is never sent


def test_credentials_env_file_and_expiry(tmp_path, monkeypatch):
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    p = str(tmp_path / "s.json")
    with pytest.raises(SourceError):
        K.load_credentials(p)  # nothing configured
    K.save_session("k", "t", p)
    assert oct(os.stat(p).st_mode & 0o777) == "0o600"
    assert K.load_credentials(p) == ("k", "t")
    json.dump({"api_key": "k", "access_token": "t", "date": "2000-01-01"}, open(p, "w"))
    with pytest.raises(SourceError, match="earlier day"):
        K.load_credentials(p)
    monkeypatch.setenv("KITE_API_KEY", "ek"); monkeypatch.setenv("KITE_ACCESS_TOKEN", "et")
    assert K.load_credentials(p) == ("ek", "et")


def mk(h, m, o=100, hi=101, lo=99, c=100, d=2):
    return Bar(datetime(2024, 1, d, h, m), o, hi, lo, c)


def test_clean_bars_filters_bad_candles_session_and_duplicates():
    bars = [mk(9, 15), mk(9, 15), mk(8, 0), mk(15, 30), mk(10, 0, hi=95), mk(10, 5, o=0, lo=0), mk(10, 10)]
    out = clean_bars(bars)
    assert [b.ts.strftime("%H:%M") for b in out] == ["09:15", "10:10"]


def test_merge_csv_grows_history_and_new_wins(tmp_path):
    p = str(tmp_path / "d" / "x.csv")
    merge_csv([mk(9, 15), mk(9, 20)], p)
    out = merge_csv([mk(9, 20, c=105, hi=106), mk(9, 25)], p)
    assert len(out) == 3 and out[1].close == 105
    assert len(load_csv(p)) == 3


def test_quality_report_warns_on_short_history_and_incomplete_days():
    # 3 days x 10 bars, plus a 4th day with only 2 bars
    bars = [Bar(datetime(2024, 1, 2 + d, 9, 15) + timedelta(minutes=5 * i), 1, 1, 1, 1) for d in range(3) for i in range(10)]
    bars += [Bar(datetime(2024, 1, 5, 9, 15) + timedelta(minutes=5 * i), 1, 1, 1, 1) for i in range(2)]
    r = quality_report(bars)
    assert r["bars"] == 32 and r["days"] == 4 and r["incomplete_days"] == ["2024-01-05"]
    assert any("trading days" in w for w in r["warnings"]) and any("incomplete" in w for w in r["warnings"])
    assert quality_report([])["bars"] == 0


def test_sync_cli_yahoo_writes_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "fetch_yahoo", lambda *a, **k: parse_chart(yahoo_payload()))
    out = str(tmp_path / "n.csv")
    assert sync.main(["yahoo", "--out", out]) == 0
    assert len(load_csv(out)) == 2


def test_sync_cli_reports_source_errors_as_exit_code_1(monkeypatch, capsys):
    def boom(*a, **k):
        raise SourceError("blocked")
    monkeypatch.setattr(sync, "fetch_yahoo", boom)
    assert sync.main(["yahoo"]) == 1
    assert "blocked" in capsys.readouterr().err


def test_web_data_path_rejects_traversal():
    from algo_trader.web import _safe_data_path
    for bad in ["../x.csv", "/etc/passwd", "a/b.csv", "x.txt", ""]:
        with pytest.raises(ValueError):
            _safe_data_path(bad)
