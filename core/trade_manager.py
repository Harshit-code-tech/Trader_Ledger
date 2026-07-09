"""
Trade Manager

Handles business logic for trade validation, creation, and retrieval.
Decouples trade persistence from the UI presentation.
"""

import sqlite3
from datetime import date
from typing import Optional, Tuple, List, Dict, Any
from core.settings_manager import get_default_mtf_rate_pct
from core.logger import get_logger
from core.utils import make_trade_ts
from core.trade_validation import normalize_trade_classification
from core.brokerage import calculate_brokerage_auto
from core.db_operations import get_connection
import config

logger = get_logger('core.trade_manager')

def validate_trade_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates raw string data coming from the UI form.
    Returns (is_valid, error_message).
    """
    # Validate date
    date_str = data.get('date_str', '').strip()
    if not date_str:
        return False, "Date is required"
    try:
        day, month, year = date_str.split('-')
        _ = date(int(year), int(month), int(day))
    except (ValueError, IndexError):
        return False, "Invalid date format. Use DD-MM-YYYY"
        
    # Validate equity
    equity = data.get('equity', '').strip()
    if not equity:
        return False, "Stock symbol is required"
        
    # Validate quantity
    try:
        quantity = int(data.get('quantity', 0))
        if quantity <= 0:
            return False, "Quantity must be positive"
    except ValueError:
        return False, "Quantity must be a number"
        
    # Validate price
    try:
        price = float(data.get('price', 0))
        if price <= 0:
            return False, "Price must be positive"
    except ValueError:
        return False, "Price must be a number"
        
    # Validate brokerage
    try:
        brokerage = float(data.get('brokerage', 0))
        if brokerage < 0:
            return False, "Brokerage cannot be negative"
    except ValueError:
        return False, "Brokerage must be a number"
        
    # Validate classification
    try:
        type1, type2, strike, expiry = data.get('classification', ('', '', '', ''))
        normalize_trade_classification(type1, type2, strike, expiry, require_type1=True)
    except ValueError as exc:
        return False, str(exc)
        
    # Auto Brokerage Validation
    if not data.get('override_brokerage'):
        type1_norm = type1.strip().lower()
        trade_type = data.get('trade_type', 'BUY').strip().upper()
        try:
            calculate_brokerage_auto(quantity, int(price * 100), type1_norm, trade_type)
        except Exception:
            return False, (
                f"Auto brokerage not configured for {type1_norm.upper()} {trade_type}. "
                "Enable override and enter brokerage manually."
            )
            
    # MTF validation
    type1_norm = type1.strip().lower()
    if type1_norm == 'mtf' and data.get('trade_type') == 'BUY':
        try:
            mtf_amount = float(data.get('mtf_amount', 0) or 0)
        except ValueError:
            return False, "MTF amount must be a number"
        if mtf_amount <= 0:
            return False, "MTF amount is required for MTF BUY trades"
        try:
            mtf_rate_str = data.get('mtf_rate_pct', '')
            # If completely empty, we allow it to fail or fallback. The form should pass something.
            if mtf_rate_str is None or str(mtf_rate_str).strip() == '':
                return False, "MTF rate is required for MTF BUY trades"
            mtf_rate = float(mtf_rate_str)
            if mtf_rate < 0:
                return False, "MTF rate cannot be negative"
            if mtf_rate > 1000:  # Sensible upper bound to prevent overflow (1000%)
                return False, "MTF rate is unusually high (max 1000%)"
        except ValueError:
            return False, "MTF rate must be a valid number"

        trade_amount = quantity * int(price * 100)
        if int(mtf_amount * 100) > trade_amount:
            return False, "MTF amount cannot exceed buy trade amount"

    # Dynamic Position State Engine Validation
    from core.position_state_engine import process_trades, PositionStateError
    from core.fifo_matcher import fetch_active_trades, TradeTuple
    from core.utils import make_trade_ts
    
    # 1. Fetch existing trades
    active_profile_id = config.ACTIVE_PROFILE_IDS[0] if config.ACTIVE_PROFILE_IDS else 0
    try:
        existing_trades = fetch_active_trades(profile_id=active_profile_id)
    except Exception:
        existing_trades = []
        
    # 2. Build mock tuple for the proposed trade
    try:
        mock_id = 999999999
        date_str = data['date_str'].strip()
        day, month, year = date_str.split('-')
        trade_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        price_paise = int(float(data['price']) * 100)
        
        proposed = TradeTuple(
            id=mock_id,
            trade_date=trade_date,
            equity=data['equity'].strip().upper(),
            trade_type=data['trade_type'],
            quantity=int(data['quantity']),
            price=price_paise,
            brokerage=0,
            brokerage_auto=0,
            brokerage_override=None,
            mtf_amount=0,
            mtf_rate_ppm=0,
            trade_ts=make_trade_ts(trade_date),
            notes="",
            type1=type1,
            type2=type2,
            strike=strike_val,
            expiry=expiry,
            is_active=1,
            profile_id=active_profile_id
        )
        
        all_trades = existing_trades + [proposed]
        # Sort exactly as the FIFO matcher does: by date then ID
        all_trades.sort(key=lambda t: (t.trade_date, t.id))
        
        # 3. Validate mathematically
        process_trades(all_trades)
        
    except PositionStateError as e:
        return False, str(e)
    except Exception as e:
        pass # If we fail to build the mock, let the save function handle validation errors

    return True, ""


def save_trade(data: Dict[str, Any], profile_id: int) -> int:
    """
    Normalizes data and inserts the trade event into the DB.
    Returns the new trade ID.
    """
    date_str = data['date_str'].strip()
    day, month, year = date_str.split('-')
    trade_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    equity = data['equity'].strip().upper()
    trade_type = data['trade_type']
    quantity = int(data['quantity'])
    
    price_rupees = float(data['price'])
    price_paise = int(price_rupees * 100)
    
    type1_in, type2_in, strike_in, expiry_in = data.get('classification', ('', '', '', ''))
    type1, type2, strike, expiry = normalize_trade_classification(
        type1_in, type2_in, strike_in, expiry_in, require_type1=True
    )
    
    type1_norm = type1.strip().lower()
    if data.get('override_brokerage'):
        brokerage_paise = int(float(data['brokerage']) * 100)
        brokerage_auto = 0
        brokerage_override = brokerage_paise
    else:
        brokerage_paise, _ = calculate_brokerage_auto(quantity, price_paise, type1_norm, trade_type)
        brokerage_auto = brokerage_paise
        brokerage_override = None
        
    mtf_amount_paise = 0
    mtf_rate_ppm = None
    if type1_norm == 'mtf' and trade_type == 'BUY':
        default_rate = get_default_mtf_rate_pct()
        try:
            mtf_amount_paise = int(float(data.get('mtf_amount', 0) or 0) * 100)
            mtf_rate_pct = float(data.get('mtf_rate_pct', default_rate) or default_rate)
            mtf_rate_ppm = int(mtf_rate_pct * 10000)
        except (ValueError, TypeError):
            mtf_amount_paise = 0
            mtf_rate_ppm = int(default_rate * 10000)
        
    notes = data.get('notes', '').strip()
    selected_reference = data.get('selected_close_reference')
    if selected_reference:
        ref_id = selected_reference.get('id')
        ref_note = f"[CLOSE_REF id={ref_id} remaining_at_entry={selected_reference.get('remaining_qty')}]"
        notes = f"{notes}\n{ref_note}" if notes else ref_note
            
    trade_ts = make_trade_ts(trade_date)
    
    conn = get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        c = conn.cursor()
        c.execute("""
            INSERT INTO trade_events (
                trade_date, equity, trade_type, quantity, price, brokerage,
                brokerage_auto, brokerage_override, mtf_amount, trade_ts, notes,
                type1, type2, strike, expiry, is_active, profile_id, mtf_rate_ppm
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            trade_date, equity, trade_type, quantity, price_paise, brokerage_paise,
            brokerage_auto, brokerage_override, mtf_amount_paise, trade_ts, notes,
            type1, type2, strike, expiry, profile_id, mtf_rate_ppm
        ))
        trade_id = c.lastrowid
        conn.commit()
        return trade_id
    finally:
        conn.close()

def get_recent_trades(profile_id: Optional[int] = None, limit: int = 5) -> List[Tuple]:
    """Fetches the most recent trades for display."""
    conn = get_connection()
    try:
        c = conn.cursor()
        if profile_id is None or profile_id == 0:
            c.execute("""
                SELECT trade_date, equity, trade_type, quantity, price, brokerage
                FROM trade_events
                WHERE is_active = 1
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
        else:
            c.execute("""
                SELECT trade_date, equity, trade_type, quantity, price, brokerage
                FROM trade_events
                WHERE is_active = 1 AND profile_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (profile_id, limit))
        return c.fetchall()
    finally:
        conn.close()
