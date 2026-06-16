"""
Database Operations Layer

Abstracts raw SQLite queries away from UI components.
"""
import sqlite3
from typing import List, Tuple, Optional
from core.logger import get_logger
import config

logger = get_logger('core.db_operations')

def get_connection() -> sqlite3.Connection:
    """Returns a connection to the application database."""
    return sqlite3.connect(str(config.DB_PATH))

def get_unique_equities(profile_id: Optional[int] = None) -> List[str]:
    """Fetch unique active equities, optionally filtered by profile."""
    try:
        conn = get_connection()
        c = conn.cursor()
        
        if profile_id is None or profile_id == 0:
            c.execute("SELECT DISTINCT equity FROM trade_events WHERE is_active = 1 ORDER BY equity")
        else:
            c.execute(
                "SELECT DISTINCT equity FROM trade_events WHERE is_active = 1 AND profile_id = ? ORDER BY equity", 
                (profile_id,)
            )
            
        equities = [row[0] for row in c.fetchall()]
        return equities
    except Exception as e:
        logger.error(f"Failed to fetch unique equities: {e}", exc_info=True)
        return []
    finally:
        conn.close()

def get_active_profiles() -> List[Tuple[int, str]]:
    """Fetch all active profiles (id, name)."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, profile_name FROM profiles WHERE is_active = 1 ORDER BY profile_name")
        profiles = c.fetchall()
        return profiles
    except Exception as e:
        logger.error(f"Failed to fetch profiles: {e}", exc_info=True)
        return []
    finally:
        conn.close()

def create_profile(name: str) -> bool:
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO profiles (profile_name, is_active) VALUES (?, 1)", (name,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to create profile: {e}", exc_info=True)
        raise e
    finally:
        conn.close()

def update_profile(profile_id: int, new_name: str) -> bool:
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE profiles SET profile_name = ? WHERE id = ?", (new_name, profile_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update profile: {e}", exc_info=True)
        raise e
    finally:
        conn.close()

def delete_profile(profile_id: int) -> bool:
    """Soft deletes a profile by setting is_active = 0"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE profiles SET is_active = 0 WHERE id = ?", (profile_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete profile: {e}", exc_info=True)
        raise e
    finally:
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    """Fetch a configuration setting from the database."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (key,))
        row = c.fetchone()
        if row:
            return row[0]
        return default
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {e}")
        return default
    finally:
        conn.close()

def set_setting(key: str, value: str) -> bool:
    """Insert or update a configuration setting in the database."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO settings (setting_key, setting_value) VALUES (?, ?) "
            "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
            (key, value)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set setting {key}: {e}")
        return False
    finally:
        conn.close()
