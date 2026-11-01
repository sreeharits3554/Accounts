import json

import pytest

from algo_trader.export import run_to_dict


def test_export_is_json_serialisable_and_consistent():
    d = run_to_dict(days=60, seed=2)
    json.dumps(d)  # must not raise (no inf/nan)
    m = d["metrics"]
    assert m["trades"] == len(d["trades"]) == len(d["equity"])
    assert abs(m["gross_pnl"] - (m["net_pnl"] + m["costs"])) < 0.01
    assert abs(d["equity"][-1]["e"] - m["net_pnl"]) < 0.01
    assert all(v["v"] <= 0 for v in d["drawdown"])


def test_qty_above_risk_cap_is_rejected():
    with pytest.raises(ValueError):
        run_to_dict(days=10, qty=500)
