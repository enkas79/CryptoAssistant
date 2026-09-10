"""
Percorso di salvataggio predefinito per le finestre "Salva con nome".

Di default punta alla cartella Download dell'utente; dopo il primo salvataggio
ricorda l'ultima cartella usata (in config, chiave "last_save_dir").
"""

import os
from pathlib import Path


def _download_dir() -> str:
    """Cartella Download dell'utente, con fallback a ~/Downloads."""
    try:
        from PyQt6.QtCore import QStandardPaths
        loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        if loc:
            return loc
    except Exception:
        pass
    return str(Path.home() / "Downloads")


def default_save_path(config: dict, filename: str) -> str:
    """Percorso iniziale da passare a QFileDialog.getSaveFileName()."""
    base = (config or {}).get("last_save_dir")
    if not base or not os.path.isdir(base):
        base = _download_dir()
    return os.path.join(base, filename)


def ensure_ext(path: str, ext: str) -> str:
    """Garantisce che `path` finisca con `.ext` (alcune finestre 'Salva con
    nome' non aggiungono l'estensione se l'utente digita solo il nome)."""
    if not path:
        return path
    ext = ext.lstrip(".").lower()
    return path if path.lower().endswith("." + ext) else f"{path}.{ext}"


def remember_save_dir(config: dict, chosen_path: str) -> None:
    """Memorizza in config la cartella del file appena salvato."""
    if config is None or not chosen_path:
        return
    d = os.path.dirname(chosen_path)
    if d and os.path.isdir(d):
        config["last_save_dir"] = d
