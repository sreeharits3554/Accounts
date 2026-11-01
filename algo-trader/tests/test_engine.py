from datetime import datetime, time, timedelta

from algo_trader import (Bar, CostModel, OpeningRangeBreakout, Order, PaperBroker,
                         RiskManager, Side, compute_metrics, run_backtest)
from algo_trader.data import synthetic_intraday


def mk(ts, o, h, l, c):
    return Bar(ts, o, h, l, c)


D = datetime(2024, 3, 4, 9, 15)


def day_bars(rows, start=D):
    return [mk(start + timedelta(minutes=5 * i), *r) for i, r in enumerate(rows)]


def zero_cost_broker(slip=0.0):
    z = CostModel(0, 0, 0, 0, 0, 0, 0)
    return PaperBroker(z, slippage_points=slip)


def test_costs_positive_and_sell_has_stt():
    c = CostModel()
    assert c.cost(Side.BUY, 24000, 75) > 0
    assert c.cost(Side.SELL, 24000, 75) > c.cost(Side.BUY, 24000, 75)


def test_fill_at_next_bar_open_no_lookahead():
    b = zero_cost_broker()
    bars = day_bars([(100, 101, 99, 100), (105, 106, 104, 105), (106, 107, 105, 106)])
    b.on_bar(bars[0])
    b.submit(Order(Side.BUY, 10))
    b.on_bar(bars[1])
    assert b.position.entry_price == 105  # open of the NEXT bar, not bar 0's close


def test_stop_wins_when_stop_and_target_both_hit():
    b = zero_cost_broker()
    bars = day_bars([(100, 100, 100, 100), (100, 120, 80, 100)])
    b.on_bar(bars[0])
    b.submit(Order(Side.BUY, 1, stop=90, target=110))
    b.on_bar(bars[1])
    assert b.trades[0].reason == "stop" and b.trades[0].exit_price == 90


def test_gap_through_stop_fills_at_open():
    b = zero_cost_broker()
    bars = day_bars([(100, 100, 100, 100), (100, 100, 100, 100), (80, 85, 78, 82)])
    b.on_bar(bars[0]); b.submit(Order(Side.BUY, 1, stop=95)); b.on_bar(bars[1])
    b.on_bar(bars[2])
    assert b.trades[0].exit_price == 80


def test_short_pnl_and_slippage_hurts():
    b = zero_cost_broker(slip=1.0)
    bars = day_bars([(100, 100, 100, 100), (100, 100, 100, 100), (90, 90, 90, 90)])
    b.on_bar(bars[0]); b.submit(Order(Side.SELL, 1, target=90)); b.on_bar(bars[1])
    b.on_bar(bars[2])
    t = b.trades[0]
    assert t.entry_price == 99 and t.exit_price == 91 and t.pnl == 8  # 10 gross - 2 slippage


def test_risk_manager_blocks():
    r = RiskManager(max_daily_loss=1000, max_trades_per_day=2, max_qty=100)
    assert r.allow_entry(0, 0, 50)
    assert not r.allow_entry(-1000, 0, 50)
    assert not r.allow_entry(0, 2, 50)
    assert not r.allow_entry(0, 0, 101)
    r.kill()
    assert not r.allow_entry(0, 0, 1)


def test_orb_long_trade_and_eod_squareoff():
    # Range bars 9:15-9:25 (hi 101, lo 99), breakout close at 9:30, then drift, no stop/target hit.
    rows = [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100),
            (100, 103, 100, 102)]  # 9:30 breakout, close 102 > 101
    rows += [(102, 102.5, 101.5, 102)] * 70
    bars = day_bars(rows)
    broker = zero_cost_broker()
    trades = run_backtest(bars, OpeningRangeBreakout(qty=10, reward_risk=50),
                          broker, RiskManager())
    assert len(trades) == 1
    t = trades[0]
    assert t.side is Side.BUY and t.entry_price == 102  # open of 9:35 bar
    assert t.reason == "eod" and t.exit_ts.time() == time(15, 15)


def test_one_trade_per_day_and_no_open_positions_left():
    bars = synthetic_intraday(days=40, seed=3)
    broker = PaperBroker()
    trades = run_backtest(bars, OpeningRangeBreakout(), broker, RiskManager())
    per_day = {}
    for t in trades:
        per_day[t.entry_ts.date()] = per_day.get(t.entry_ts.date(), 0) + 1
    assert all(n == 1 for n in per_day.values())
    assert broker.position is None


def test_synthetic_random_walk_has_no_edge_after_costs():
    # Sanity check: a strategy must NOT print money on a random walk.
    bars = synthetic_intraday(days=300, seed=7)
    m = compute_metrics(run_backtest(bars, OpeningRangeBreakout(), PaperBroker(), RiskManager()))
    assert m.net_pnl < m.total_costs * 5  # not a money machine; costs matter
    assert m.profit_factor < 1.5
