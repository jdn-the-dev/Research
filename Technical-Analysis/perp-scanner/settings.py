import json
import os
from pathlib import Path

# Default configuration values
DEFAULT_CONFIG = {
    "telegram_token": "",
    "telegram_chat_id": "",
    "alert_threshold": 10.0
}

CONFIG_FILENAME = "kraken_alerts_config.json"


def get_config_path() -> Path:
    """
    Returns the path to the user-specific configuration file.
    """
    # Use platform-appropriate config directory
    home = Path.home()
    config_dir = home / "Total" / ".kraken_usd_alerts"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / CONFIG_FILENAME


def load_settings() -> dict:
    """
    Loads the configuration from a JSON file. If the file does not exist,
    returns DEFAULT_CONFIG and creates the file.
    """
    path = get_config_path()
    if not path.exists():
        save_settings(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        # If corrupt or unreadable, overwrite with defaults
        save_settings(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    # Merge with defaults to ensure all keys are present
    config = DEFAULT_CONFIG.copy()
    config.update({k: data.get(k, v) for k, v in DEFAULT_CONFIG.items()})
    return config


def save_settings(config: dict) -> None:
    """
    Saves the provided configuration dictionary to the JSON file.
    """
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        # In production, consider logging this error
        print(f"Failed to save configuration: {e}")
