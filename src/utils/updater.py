"""
Updater Module for CryptoAssistant
Verifica e scarica in background nuove versioni da GitHub Releases.
"""

import os
import sys
import tempfile
import subprocess
from typing import Optional, Tuple

import requests
from PyQt6.QtCore import QThread, pyqtSignal

GITHUB_REPO = "enkas79/CryptoAssistant"
GITHUB_API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT = 10  # seconds


def _versione_a_tupla(versione: str) -> Tuple[int, ...]:
    """Converte 'v1.2.3' o '1.2.3' in (1, 2, 3) per il confronto numerico."""
    pulita = versione.strip().lstrip("vV")
    parti = []
    for p in pulita.split("."):
        numero = "".join(ch for ch in p if ch.isdigit())
        parti.append(int(numero) if numero else 0)
    return tuple(parti) if parti else (0,)


def is_newer_version(remota: str, locale: str) -> bool:
    """True se la versione remota è maggiore di quella locale."""
    return _versione_a_tupla(remota) > _versione_a_tupla(locale)


class UpdateCheckWorker(QThread):
    """Controlla in background se è disponibile una nuova release su GitHub."""

    aggiornamento_disponibile = pyqtSignal(str, str, str)  # versione, url_asset, changelog
    nessun_aggiornamento = pyqtSignal()
    errore = pyqtSignal(str)

    def __init__(self, versione_corrente: str, parent=None):
        super().__init__(parent)
        self.versione_corrente = versione_corrente

    def run(self):
        try:
            response = requests.get(GITHUB_API_LATEST_RELEASE, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            dati = response.json()

            versione_remota = str(dati.get("tag_name", "")).strip()
            if not versione_remota:
                self.errore.emit("Risposta GitHub priva di tag_name.")
                return

            if not is_newer_version(versione_remota, self.versione_corrente):
                self.nessun_aggiornamento.emit()
                return

            asset_url = ""
            for asset in dati.get("assets", []):
                nome = str(asset.get("name", ""))
                if nome.lower().endswith((".exe", ".zip")):
                    asset_url = asset.get("browser_download_url", "")
                    break

            changelog = str(dati.get("body", "")).strip() or "Nessuna nota di rilascio disponibile."
            self.aggiornamento_disponibile.emit(versione_remota, asset_url, changelog)

        except requests.RequestException as e:
            self.errore.emit(f"Connessione non disponibile: {e}")
        except Exception as e:
            self.errore.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Scarica l'installer della nuova versione in background."""

    progresso = pyqtSignal(int)  # percentuale 0-100
    completato = pyqtSignal(str)  # percorso file scaricato
    errore = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            nome_file = os.path.basename(self.url) or "CryptoAssistant-Setup.exe"
            percorso_destinazione = os.path.join(tempfile.gettempdir(), nome_file)

            with requests.get(self.url, stream=True, timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
                totale = int(response.headers.get("content-length", 0))
                scaricato = 0

                with open(percorso_destinazione, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        f.write(chunk)
                        scaricato += len(chunk)
                        if totale > 0:
                            self.progresso.emit(int(scaricato * 100 / totale))

            self.completato.emit(percorso_destinazione)

        except requests.RequestException as e:
            self.errore.emit(f"Download fallito: {e}")
        except OSError as e:
            self.errore.emit(f"Impossibile salvare il file scaricato: {e}")


def avvia_installer_e_esci(percorso_installer: str) -> None:
    """Lancia l'installer scaricato e chiude l'applicazione corrente."""
    if sys.platform == "win32":
        os.startfile(percorso_installer)
    else:
        subprocess.Popen([percorso_installer])
    sys.exit(0)
