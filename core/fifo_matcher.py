import sqlite3
from dataclasses import dataclass
from typing import TypedDict
import config
from core.trade_validation import normalize_trade_classification
from core.brokerage import get_effective_brokerage
from core.trading_rules import TradeDirection, EventRole

DB_PATH = str(config.DB_PATH)


class FifoMatchError(Exception):
    pass


# Type definitions
class OpeningQueueItem(TypedDict):
    id: int
    remaining_quantity: int


class MatchRecord(TypedDict):
    sell_id: int
    buy_id: int
    matched_quantity: int
    equity: str


# Trade tuple from DB:
# (id, trade_date, equity, trade_type, type1, type2, strike, expiry, quantity, price,
#  brokerage_effective, notes, is_active, brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm)
TradeTuple = tuple[int, str, str, str, str, str | None, float | None, str | None, int, int, int, str, int, int, int | None, int, int | None]
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
    mtf_rate_ppm: int | None

    @classmethod
    def from_tuple(cls, trade: TradeTuple) -> "TradeRecord":
        return cls(*trade)


def fetch_active_trades() -> list[TradeTuple]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Apply profile filter if current profile is set (0 means combined view)
    import config as _config
    active_ids = _config.ACTIVE_PROFILE_IDS
    if not active_ids:
        cursor.execute('''
           SELECT id, trade_date, equity, trade_type, type1, type2, strike, expiry,
               quantity, price, brokerage, notes, is_active,
               brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm
        FROM trade_events
        WHERE is_active = 1
        ORDER BY trade_date, COALESCE(trade_ts, trade_date || ' 09:15:00'), id
        ''')
    else:
        placeholders = ','.join('?' * len(active_ids))
        cursor.execute(f'''
           SELECT id, trade_date, equity, trade_type, type1, type2, strike, expiry,
               quantity, price, brokerage, notes, is_active,
               brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm
        FROM trade_events
        WHERE is_active = 1 AND profile_id IN ({placeholders})
        ORDER BY trade_date, COALESCE(trade_ts, trade_date || ' 09:15:00'), id
        ''', tuple(active_ids))
    trades = cursor.fetchall()
    conn.close()
    
    # Normalize and validate fetched trades
    normalized_trades: list[TradeTuple] = []
    
    for trade in trades:
        (trade_id, trade_date, equity, trade_type, type1_raw, type2_raw, strike_raw, expiry_raw,
         quantity, price, brokerage, notes, is_active, brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm) = trade
        
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
             int(brokerage_override) if brokerage_override is not None else None, mtf_amount, mtf_rate_ppm)
        )
    
    return normalized_trades


def match_fifo(trades: list[TradeTuple], collect_matches: bool = True) -> list[MatchRecord] | None:
    """
    Matches CLOSING trades to OPENING trades per contract using FIFO.

    Version 2.0: Uses the Position State Engine to classify trades as
    OPENING or CLOSING before matching.  The matcher itself is a generic
    quantity matching engine — it contains no product-specific knowledge.

    For backward compatibility, MatchRecord still uses sell_id/buy_id:
    - sell_id = the SELL trade (regardless of whether it opened or closed)
    - buy_id = the BUY trade (regardless of whether it opened or closed)
    This keeps the downstream PnL formula (sell_value - buy_cost) valid
    for both LONG and SHORT positions.

    Raises FifoMatchError if matching fails.
    """
    # Lazy import to avoid circular dependency
    # (position_state_engine imports TradeTuple/ContractKey from this module)
    from core.position_state_engine import process_trades, PositionStateError

    # Phase 1: Classify trades via Position State Engine
    try:
        events = process_trades(trades)
    except PositionStateError as exc:
        raise FifoMatchError(str(exc)) from exc

    # Phase 2: Generic FIFO quantity matching
    opening_queues: dict[ContractKey, list[OpeningQueueItem]] = {}
    matches: list[MatchRecord] = []

    for event in events:
        contract_key = event.contract_key

        if contract_key not in opening_queues:
            opening_queues[contract_key] = []

        if event.event_role is EventRole.OPENING:
            opening_queues[contract_key].append(OpeningQueueItem(
                id=event.trade_id,
                remaining_quantity=event.quantity,
            ))
        elif event.event_role is EventRole.CLOSING:
            closing_qty: int = event.quantity
            opening_queue = opening_queues[contract_key]

            while closing_qty > 0:
                if not opening_queue:
                    # Build contract label for error message
                    if event.type1 == 'options':
                        contract_label = f"{event.equity} | options | {event.type2} | {event.strike} | {event.expiry}"
                    elif event.type1 == 'futures':
                        contract_label = f"{event.equity} | futures | {event.expiry}"
                    else:
                        contract_label = f"{event.equity} | {event.type1}"

                    raise FifoMatchError(
                        f"\n{'='*60}\n"
                        f"OVERSELL DETECTED for {contract_label}\n"
                        f"{'='*60}\n"
                        f"Trade ID: {event.trade_id}\n"
                        f"Date: {event.trade_date}\n"
                        f"Direction: {event.original_direction.value}\n"
                        f"Attempted close: {event.quantity} shares\n"
                        f"Unmatched: {closing_qty} shares\n"
                        f"\n"
                        f"💡 Suggestions:\n"
                        f"  1. Check if you have opening trades for this contract before this date\n"
                        f"  2. Verify the quantity is correct\n"
                        f"  3. Ensure trades are in chronological order\n"
                        f"  4. Check if equity symbol is spelled correctly\n"
                        f"{'='*60}"
                    )

                oldest_opening: OpeningQueueItem = opening_queue[0]
                match_qty: int = min(closing_qty, oldest_opening['remaining_quantity'])

                if collect_matches:
                    # Map to MatchRecord: sell_id = SELL trade, buy_id = BUY trade
                    if event.original_direction is TradeDirection.SELL:
                        # Closing trade is SELL → opening trade was BUY (LONG)
                        sell_id = event.trade_id
                        buy_id = oldest_opening['id']
                    else:
                        # Closing trade is BUY → opening trade was SELL (SHORT)
                        sell_id = oldest_opening['id']
                        buy_id = event.trade_id

                    matches.append(MatchRecord(
                        sell_id=sell_id,
                        buy_id=buy_id,
                        matched_quantity=match_qty,
                        equity=event.equity,
                    ))

                oldest_opening['remaining_quantity'] -= match_qty
                closing_qty -= match_qty

                if oldest_opening['remaining_quantity'] == 0:
                    opening_queue.pop(0)

    # Open positions (pending square-off or ongoing) are allowed.
    # No error is raised for remaining items in opening queues.

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








