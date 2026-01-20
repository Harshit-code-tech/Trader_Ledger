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
    equity: str


# Trade tuple from DB: (id, trade_date, equity, trade_type, quantity, price, brokerage, notes, is_active)
TradeTuple = tuple[int, str, str, str, int, int, int, str, int]


def fetch_active_trades() -> list[TradeTuple]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, trade_date, equity, trade_type, quantity, price, brokerage, notes, is_active
        FROM trade_events
        WHERE is_active = 1
        ORDER BY trade_date, id
    ''')
    trades = cursor.fetchall()
    conn.close()
    
    # Validate fetched trades
    for trade in trades:
        trade_id, _trade_date, equity, trade_type, quantity, price, brokerage, _notes, _is_active = trade
        
        # Check for invalid trade types
        if trade_type not in ('BUY', 'SELL'):
            raise FifoMatchError(
                f"\n{'='*60}\n"
                f"INVALID TRADE TYPE\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Invalid type: '{trade_type}'\n"
                f"Valid types: 'BUY' or 'SELL'\n"
                f"\n💡 Check the trade_type column in the database.\n"
                f"{'='*60}"
            )
        
        # Check for invalid quantities
        if quantity <= 0:
            raise FifoMatchError(
                f"\n{'='*60}\n"
                f"INVALID QUANTITY\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Equity: {equity}\n"
                f"Type: {trade_type}\n"
                f"Invalid quantity: {quantity}\n"
                f"\n💡 Quantity must be a positive number.\n"
                f"{'='*60}"
            )
        
        # Check for invalid prices
        if price <= 0:
            raise FifoMatchError(
                f"\n{'='*60}\n"
                f"INVALID PRICE\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Equity: {equity}\n"
                f"Type: {trade_type}\n"
                f"Invalid price: {price}\n"
                f"\n💡 Price must be a positive number (in paise).\n"
                f"{'='*60}"
            )
        
        # Check for negative brokerage
        if brokerage < 0:
            raise FifoMatchError(
                f"\n{'='*60}\n"
                f"INVALID BROKERAGE\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Equity: {equity}\n"
                f"Type: {trade_type}\n"
                f"Invalid brokerage: {brokerage}\n"
                f"\n💡 Brokerage cannot be negative.\n"
                f"{'='*60}"
            )
    
    return trades


def match_fifo(trades: list[TradeTuple], collect_matches: bool = True) -> list[MatchRecord] | None:
    """
    Matches SELLs to BUYs per equity. FIFO is applied independently for each stock.
    If collect_matches is True, returns a list of match records (sell_id, buy_id, matched_quantity, equity).
    Raises FifoMatchError if oversell is detected for any equity.
    """
    buy_queues: dict[str, list[BuyQueueItem]] = {}  # Per-equity buy queues
    equity_holdings: dict[str, int] = {}  # Track total holdings per equity
    matches: list[MatchRecord] = []
    
    for trade in trades:
        trade_id, trade_date, equity, trade_type, quantity, _price, _brokerage, _notes, _is_active = trade
        
        # Validate equity field
        if not equity or equity.strip() == '':
            raise FifoMatchError(
                f"Invalid trade: Trade ID {trade_id} has empty or missing equity field. "
                f"Every trade must specify a stock symbol (e.g., 'TCS', 'RELIANCE')."
            )
        
        # Initialize buy queue and holdings for this equity if not exists
        if equity not in buy_queues:
            buy_queues[equity] = []
            equity_holdings[equity] = 0
        
        if trade_type == 'BUY':
            buy_queues[equity].append(BuyQueueItem(
                id=trade_id,
                remaining_quantity=quantity
            ))
            equity_holdings[equity] += quantity
        elif trade_type == 'SELL':
            sell_qty: int = quantity
            buy_queue = buy_queues[equity]
            available_qty = equity_holdings[equity]
            
            while sell_qty > 0:
                if not buy_queue:
                    # Calculate oversell amount
                    oversell_amount = sell_qty
                    
                    raise FifoMatchError(
                        f"\n{'='*60}\n"
                        f"OVERSELL DETECTED for {equity}\n"
                        f"{'='*60}\n"
                        f"Trade ID: {trade_id}\n"
                        f"Date: {trade_date}\n"
                        f"Attempted SELL: {quantity} shares\n"
                        f"Available holdings: {available_qty} shares\n"
                        f"Oversell amount: {oversell_amount} shares\n"
                        f"\n"
                        f"💡 Suggestions:\n"
                        f"  1. Check if you have BUY trades for {equity} before this date\n"
                        f"  2. Verify the SELL quantity is correct (should be ≤ {available_qty})\n"
                        f"  3. Ensure trades are in chronological order\n"
                        f"  4. Check if equity symbol is spelled correctly\n"
                        f"{'='*60}"
                    )
                
                oldest_buy: BuyQueueItem = buy_queue[0]
                match_qty: int = min(sell_qty, oldest_buy['remaining_quantity'])
                
                if collect_matches:
                    matches.append(MatchRecord(
                        sell_id=trade_id,
                        buy_id=oldest_buy['id'],
                        matched_quantity=match_qty,
                        equity=equity
                    ))
                
                oldest_buy['remaining_quantity'] -= match_qty
                sell_qty -= match_qty
                equity_holdings[equity] -= match_qty
                
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








