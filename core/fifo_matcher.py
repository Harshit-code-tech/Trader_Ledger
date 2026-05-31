import sqlite3
from dataclasses import dataclass
from typing import TypedDict
import config
from core.trade_validation import normalize_trade_classification
from core.brokerage import get_effective_brokerage

DB_PATH = str(config.DB_PATH)


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


# Trade tuple from DB:
# (id, trade_date, equity, trade_type, type1, type2, strike, expiry, quantity, price,
#  brokerage_effective, notes, is_active, brokerage_auto, brokerage_override, mtf_amount)
TradeTuple = tuple[int, str, str, str, str, str | None, float | None, str | None, int, int, int, str, int, int, int | None, int]
ContractKey = tuple[str, str, str | None, float | None, str | None]


@dataclass(frozen=True)
class TradeRecord:
    id: int
    trade_date: str
    equity: str
    trade_type: str
    type1: str
    type2: str | None
    strike: float | None
    expiry: str | None
    quantity: int
    price: int
    brokerage: int
    notes: str
    is_active: int
    brokerage_auto: int
    brokerage_override: int | None
    mtf_amount: int

    @classmethod
    def from_tuple(cls, trade: TradeTuple) -> "TradeRecord":
        return cls(*trade)


def fetch_active_trades() -> list[TradeTuple]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Apply profile filter if current profile is set (0 means combined view)
    import config as _config
    if _config.CURRENT_PROFILE_ID is None or _config.CURRENT_PROFILE_ID == 0:
        cursor.execute('''
           SELECT id, trade_date, equity, trade_type, type1, type2, strike, expiry,
               quantity, price, brokerage, notes, is_active,
               brokerage_auto, brokerage_override, mtf_amount
        FROM trade_events
        WHERE is_active = 1
        ORDER BY COALESCE(trade_ts, trade_date || ' 09:15:00'), id
        ''')
    else:
        cursor.execute('''
           SELECT id, trade_date, equity, trade_type, type1, type2, strike, expiry,
               quantity, price, brokerage, notes, is_active,
               brokerage_auto, brokerage_override, mtf_amount
        FROM trade_events
        WHERE is_active = 1 AND profile_id = ?
        ORDER BY COALESCE(trade_ts, trade_date || ' 09:15:00'), id
        ''', (_config.CURRENT_PROFILE_ID,))
    trades = cursor.fetchall()
    conn.close()
    
    # Normalize and validate fetched trades
    normalized_trades: list[TradeTuple] = []
    
    for trade in trades:
        (trade_id, trade_date, equity, trade_type, type1_raw, type2_raw, strike_raw, expiry_raw,
         quantity, price, brokerage, notes, is_active, brokerage_auto, brokerage_override, mtf_amount) = trade
        
        # Normalize equity (strip whitespace and uppercase)
        equity = equity.strip().upper()
        
        # Validate equity field
        if not equity:
            raise FifoMatchError(
                f"\n{'='*60}\n"
                f"INVALID EQUITY FIELD\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Equity field is empty or missing after normalization.\n"
                f"Every trade must specify a stock symbol (e.g., 'TCS', 'RELIANCE').\n"
                f"{'='*60}"
            )
        
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
        
        type1_input = type1_raw or "delivery"
        type2_input = type2_raw or ""
        strike_input = "" if strike_raw is None else str(strike_raw)
        expiry_input = expiry_raw or ""

        try:
            type1, type2, strike, expiry = normalize_trade_classification(
                type1_input,
                type2_input,
                strike_input,
                expiry_input,
                require_type1=True
            )
        except ValueError as exc:
            raise FifoMatchError(
                f"\n{'='*60}\n"
                f"INVALID CONTRACT CLASSIFICATION\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Equity: {equity}\n"
                f"Type1: {type1_input}\n"
                f"Type2: {type2_input or '(empty)'}\n"
                f"Strike: {strike_input or '(empty)'}\n"
                f"Expiry: {expiry_input or '(empty)'}\n"
                f"Error: {str(exc)}\n"
                f"{'='*60}"
            ) from exc

        effective_brokerage = get_effective_brokerage({
            'brokerage': brokerage,
            'brokerage_auto': brokerage_auto,
            'brokerage_override': brokerage_override
        })

        mtf_amount = int(mtf_amount or 0)

        # Add normalized trade to list
        normalized_trades.append(
            (trade_id, trade_date, equity, trade_type, type1, type2, strike, expiry,
             quantity, price, effective_brokerage, notes, is_active, int(brokerage_auto or 0),
             int(brokerage_override) if brokerage_override is not None else None, mtf_amount)
        )
    
    return normalized_trades


def match_fifo(trades: list[TradeTuple], collect_matches: bool = True) -> list[MatchRecord] | None:
    """
    Matches SELLs to BUYs per contract identity. FIFO is applied independently per contract.
    If collect_matches is True, returns a list of match records (sell_id, buy_id, matched_quantity, equity).
    Raises FifoMatchError if oversell is detected for any contract.
    """
    buy_queues: dict[ContractKey, list[BuyQueueItem]] = {}  # Per-contract buy queues
    contract_holdings: dict[ContractKey, int] = {}  # Track total holdings per contract
    matches: list[MatchRecord] = []
    
    for trade in trades:
        (trade_id, trade_date, equity, trade_type, type1, type2, strike, expiry,
         quantity, _price, _brokerage, _notes, _is_active, _brokerage_auto, _brokerage_override, _mtf_amount) = trade
        
        # Validate equity field
        if not equity or equity.strip() == '':
            raise FifoMatchError(
                f"Invalid trade: Trade ID {trade_id} has empty or missing equity field. "
                f"Every trade must specify a stock symbol (e.g., 'TCS', 'RELIANCE')."
            )
        
        contract_key: ContractKey = (equity, type1, type2, strike, expiry)
        contract_label = f"{equity} | {type1}"
        if type1 == 'options':
            contract_label = f"{equity} | options | {type2} | {strike} | {expiry}"
        elif type1 == 'futures':
            contract_label = f"{equity} | futures | {expiry}"

        # Initialize buy queue and holdings for this contract if not exists
        if contract_key not in buy_queues:
            buy_queues[contract_key] = []
            contract_holdings[contract_key] = 0
        
        if trade_type == 'BUY':
            buy_queues[contract_key].append(BuyQueueItem(
                id=trade_id,
                remaining_quantity=quantity
            ))
            contract_holdings[contract_key] += quantity
        elif trade_type == 'SELL':
            sell_qty: int = quantity
            buy_queue = buy_queues[contract_key]
            available_qty = contract_holdings[contract_key]
            
            while sell_qty > 0:
                if not buy_queue:
                    # Calculate oversell amount
                    oversell_amount = sell_qty
                    
                    raise FifoMatchError(
                        f"\n{'='*60}\n"
                        f"OVERSELL DETECTED for {contract_label}\n"
                        f"{'='*60}\n"
                        f"Trade ID: {trade_id}\n"
                        f"Date: {trade_date}\n"
                        f"Attempted SELL: {quantity} shares\n"
                        f"Available holdings: {available_qty} shares\n"
                        f"Oversell amount: {oversell_amount} shares\n"
                        f"\n"
                        f"💡 Suggestions:\n"
                        f"  1. Check if you have BUY trades for this contract before this date\n"
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
                contract_holdings[contract_key] -= match_qty
                
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








