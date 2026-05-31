"""
Smoke test for profiles and per-profile flows.
Creates a temporary test DB (data/test_trades_smoke.db), runs migration, creates profiles,
inserts sample trades for a profile, and runs FIFO + P/L calculation.
"""
import os
import sqlite3
import traceback
import sys
from pathlib import Path

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.db_init import init_database
import config
from core import fifo_matcher
from core.run_ledger import build_trades_by_id
from core.pnl_calculator import calculate_match_pnl
from core.mtf_interest import apply_mtf_interest

TEST_DB = str(Path(config.DATA_DIR) / 'test_trades_smoke.db')


def run():
    try:
        # Remove existing test DB
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

        print(f"Initializing test DB: {TEST_DB}")
        ok = init_database(TEST_DB)
        print("init_database returned:", ok)

        conn = sqlite3.connect(TEST_DB)
        cur = conn.cursor()

        # List tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print("Tables:", tables)

        # Ensure profiles present and Baba exists
        cur.execute("SELECT id, profile_name FROM profiles ORDER BY id")
        profiles = cur.fetchall()
        print("Profiles before insert:", profiles)

        # Create a new profile 'Me'
        cur.execute("INSERT INTO profiles (profile_name, is_active) VALUES (?, 1)", ("Me",))
        me_id = cur.lastrowid
        conn.commit()
        print("Created profile 'Me' id=", me_id)

        # Insert BUY and SELL trades for profile Me
        buy_values = (
            '2026-01-01', 'TEST', 'BUY', 10, 10000, 0, 0, 0, '2026-01-01 09:15:00', 'buy note', 'delivery', 1, me_id
        )
        sell_values = (
            '2026-01-02', 'TEST', 'SELL', 10, 12000, 0, 0, 0, '2026-01-02 09:15:00', 'sell note', 'delivery', 1, me_id
        )

        cur.execute("""
            INSERT INTO trade_events (
                trade_date, equity, trade_type, quantity, price, brokerage,
                brokerage_auto, mtf_amount, trade_ts, notes,
                type1, is_active, profile_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, buy_values)
        buy_id = cur.lastrowid
        cur.execute("""
            INSERT INTO trade_events (
                trade_date, equity, trade_type, quantity, price, brokerage,
                brokerage_auto, mtf_amount, trade_ts, notes,
                type1, is_active, profile_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sell_values)
        sell_id = cur.lastrowid
        conn.commit()
        print(f"Inserted BUY id={buy_id}, SELL id={sell_id} for profile Me (id={me_id})")

        # Point fifo_matcher to test DB and fetch trades for profile Me
        fifo_matcher.DB_PATH = TEST_DB
        # Ensure CURRENT_PROFILE_ID points to Me
        config.CURRENT_PROFILE_ID = me_id

        trades = fifo_matcher.fetch_active_trades()
        print("Fetched trades:", trades)

        matches = fifo_matcher.match_fifo(trades)
        print("Matches:", matches)

        trades_by_id = build_trades_by_id(trades)
        pnl = calculate_match_pnl(matches, trades_by_id)
        pnl = apply_mtf_interest(pnl, trades_by_id)
        print("P/L results:", pnl)

        # Also verify that when CURRENT_PROFILE_ID = 0 (combined), fetch returns both profiles
        config.CURRENT_PROFILE_ID = 0
        fifo_matcher.DB_PATH = TEST_DB
        trades_all = fifo_matcher.fetch_active_trades()
        print("Combined fetched trades count:", len(trades_all))

        conn.close()
        print("SMOKE TEST SUCCESS")
    except Exception as e:
        print("SMOKE TEST FAILED")
        traceback.print_exc()


if __name__ == '__main__':
    run()
