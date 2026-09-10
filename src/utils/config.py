"""
Config Module for CryptoAssistant
Gestisce il caricamento/salvataggio della configurazione utente
(cartella dati scrivibile, API key, soglia dust, ecc.).
"""

import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG = {
    "api_key": None,
    "coingecko_api_key": None,  # chiave "demo" gratuita, facoltativa
    "default_currency": "EUR",
    "dust_threshold": 1.0,
    "dust_filter_enabled": True,
}


def get_user_data_dir() -> Path:
    """
    Restituisce una cartella scrivibile per l'utente corrente, dove salvare
    configurazione e dati. Necessaria perché quando l'app è installata in
    'C:\\Program Files\\...' la cartella di installazione non è scrivibile
    senza permessi di amministratore (causa PermissionError/WinError 5).
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    data_dir = Path(base) / "CryptoAssistant"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def load_config() -> dict:
    """Load configuration from the user data directory."""
    config_path = get_user_data_dir() / "config.json"
    config = dict(DEFAULT_CONFIG)
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass
    return config


def save_config(config: dict) -> None:
    """Save configuration to the user data directory."""
    config_path = get_user_data_dir() / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
