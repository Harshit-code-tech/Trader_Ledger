import json
import os
from core.logger import setup_logger
import config

logger = setup_logger()

def load_settings() -> dict:
    """Load settings from JSON file. Returns empty dict if not found."""
    if not os.path.exists(config.SETTINGS_FILE):
        return {}
    
    try:
        with open(config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load settings from {config.SETTINGS_FILE}: {e}")
        return {}

def save_settings(settings: dict) -> bool:
    """Save settings to JSON file. Returns True on success."""
    try:
        # Create directory if it doesn't exist (handled by config.py but safe to ensure)
        os.makedirs(os.path.dirname(config.SETTINGS_FILE), exist_ok=True)
        
        with open(config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Failed to save settings to {config.SETTINGS_FILE}: {e}")
        return False

def get_setting(key: str, default_value=None):
    """Get a specific setting by key."""
    settings = load_settings()
    return settings.get(key, default_value)

def set_setting(key: str, value) -> bool:
    """Set a specific setting and save to file."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)

def get_default_mtf_rate_pct() -> float:
    """Get the default MTF rate percentage. Defaults to 9.65 if not set."""
    # Convert to float to ensure consistency
    try:
        val = get_setting('default_mtf_rate_pct', 9.65)
        return float(val)
    except (ValueError, TypeError):
        return 9.65
        
def set_default_mtf_rate_pct(rate: float) -> bool:
    """Set the default MTF rate percentage."""
    return set_setting('default_mtf_rate_pct', float(rate))
