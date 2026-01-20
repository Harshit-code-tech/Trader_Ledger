import sqlite3
from typing import TypedDict

DB_PATH = 'data/trades.db'


class FifoMatchError(Exception):
    pass


# Type definitions
class BuyQueueItem(TypedDict):
    id: int
    remaining_quantity: int


class MatchRecord(TypedDict):
    sell_id: int
    buy_id: int
    matched_quantity: int


# Trade tuple from DB: (id, trade_date, trade_type, quantity, price, brokerage, notes, is_active)
TradeTuple = tuple[int, str, str, int, int, int, str, int]


def fetch_active_trades() -> list[TradeTuple]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, trade_date, trade_type, quantity, price, brokerage, notes, is_active
        FROM trade_events
        WHERE is_active = 1
        ORDER BY trade_date, id
    ''')
    trades = cursor.fetchall()
    conn.close()
    return trades


def match_fifo(trades: list[TradeTuple], collect_matches: bool = True) -> list[MatchRecord] | None:
    """
    Matches SELLs to BUYs. If collect_matches is True, returns a list of match records (sell_id, buy_id, matched_quantity).
    Raises FifoMatchError if oversell is detected.
    """
    buy_queue: list[BuyQueueItem] = []  # Each item: dict with id, remaining_quantity
    matches: list[MatchRecord] = []
    for trade in trades:
        trade_id, trade_date, trade_type, quantity, _price, _brokerage, _notes, _is_active = trade
        if trade_type == 'BUY':
            buy_queue.append(BuyQueueItem(
                id=trade_id,
                remaining_quantity=quantity
            ))
        elif trade_type == 'SELL':
            sell_qty: int = quantity
            while sell_qty > 0:
                if not buy_queue:
                    raise FifoMatchError(f"Not enough BUYs to match SELL id={trade_id} on {trade_date}")
                oldest_buy: BuyQueueItem = buy_queue[0]
                match_qty: int = min(sell_qty, oldest_buy['remaining_quantity'])
                if collect_matches:
                    matches.append(MatchRecord(
                        sell_id=trade_id,
                        buy_id=oldest_buy['id'],
                        matched_quantity=match_qty
                    ))
                oldest_buy['remaining_quantity'] -= match_qty
                sell_qty -= match_qty
                if oldest_buy['remaining_quantity'] == 0:
                    buy_queue.pop(0)
    if collect_matches:
        return matches
    return None


def validate_fifo(trades: list[TradeTuple]) -> bool:
    """
    Only checks for oversell. Does not mutate or record matches.
    Raises FifoMatchError if oversell is detected.
    """
    # Just call match_fifo with collect_matches=False
    match_fifo(trades, collect_matches=False)
    return True


if __name__ == '__main__':
    trades = fetch_active_trades()
    # Validate FIFO (no oversell)
    try:
        validate_fifo(trades)
    except FifoMatchError as e:
        print("FIFO Validation Error:", e)
        exit(1)
    # Perform matching
    match_records = match_fifo(trades)
    # Example: print match records (UI concern, not in matcher)
    if match_records:
        for m in match_records:
            print(m)








