"""
Automated test runner for profile migration and isolation.
Exits with code 0 on success, non-zero on failure.
"""
import os
import sqlite3
import sys
from pathlib import Path

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.db_init import init_database
import config
from core import fifo_matcher

TEST_DB = str(Path(config.DATA_DIR) / 'test_trades_auto.db')


def fail(msg):
    print('FAIL:', msg)
    sys.exit(2)


def run():
    # Clean
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    ok = init_database(TEST_DB)
    if not ok:
        fail('init_database returned False')

    conn = sqlite3.connect(TEST_DB)
    cur = conn.cursor()

    # Check tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    if 'profiles' not in tables or 'trade_events' not in tables:
        fail('Required tables missing: ' + str(tables))

    # Default 'Baba' exists
    cur.execute("SELECT id FROM profiles WHERE profile_name = ?", ('Baba',))
    r = cur.fetchone()
    if not r:
        fail("Default profile 'Baba' missing")
    baba_id = r[0]

    # Create profile and insert trades
    cur.execute("INSERT INTO profiles (profile_name, is_active) VALUES (?, 1)", ('Tester',))
    tester_id = cur.lastrowid

    buy_vals = ('2026-01-01', 'AAA', 'BUY', 5, 10000, 0, 0, 0, '2026-01-01 09:15:00', 'b', 'delivery', 1, tester_id)
    sell_vals = ('2026-01-02', 'AAA', 'SELL', 5, 12000, 0, 0, 0, '2026-01-02 09:15:00', 's', 'delivery', 1, tester_id)

    cur.execute("""
        INSERT INTO trade_events (trade_date, equity, trade_type, quantity, price, brokerage,
            brokerage_auto, mtf_amount, trade_ts, notes, type1, is_active, profile_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, buy_vals)
    cur.execute("""
        INSERT INTO trade_events (trade_date, equity, trade_type, quantity, price, brokerage,
            brokerage_auto, mtf_amount, trade_ts, notes, type1, is_active, profile_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sell_vals)
    conn.commit()

    # Point fifo matcher to test DB
    fifo_matcher.DB_PATH = TEST_DB
    config.CURRENT_PROFILE_ID = tester_id

    trades = fifo_matcher.fetch_active_trades()
    if len(trades) < 2:
        fail('Did not fetch inserted trades for Tester profile')

    # Combined view should fetch trades for all profiles
    config.CURRENT_PROFILE_ID = 0
    trades_all = fifo_matcher.fetch_active_trades()
    if len(trades_all) < len(trades):
        fail('Combined view returned fewer trades than profile view')

    conn.close()
    print('All automated profile tests passed')


if __name__ == '__main__':
    run()
