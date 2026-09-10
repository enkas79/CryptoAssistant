"""
Dialog per la valorizzazione del Quadro RW.

Mostra i token detenuti nell'anno d'imposta con le quantità al 1° gennaio e
al 31 dicembre; le quotazioni EUR a quelle due date vengono scaricate da
CoinGecko in background e restano modificabili a mano (per i token non
riconosciuti o per correggere il dato). All'accettazione restituisce i due
dizionari prezzi da passare a TaxCalculator.get_tax_summary().
"""

from typing import Dict, List, Tuple

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QDialogButtonBox, QHeaderView
)


class _FetchThread(QThread):
    """Scarica in background le quotazioni di inizio/fine anno dal provider."""

    finished = pyqtSignal(dict, dict)

    def __init__(self, provider, symbols: List[str], year: int):
        super().__init__()
        self._provider = provider
        self._symbols = symbols
        self._year = year

    def run(self) -> None:  # pragma: no cover - thread Qt
        try:
            start, end = self._provider.get_prices_for_year_bounds(self._symbols, self._year)
        except Exception:
            start, end = {}, {}
        self.finished.emit(start or {}, end or {})


class QuadroRWDialog(QDialog):
    """Tabella editabile Token / Qtà e Prezzo 1-1 / Qtà e Prezzo 31-12."""

    COL_TOKEN, COL_QTA_IN, COL_PREZZO_IN, COL_QTA_FIN, COL_PREZZO_FIN = range(5)

    def __init__(self, bounds: List[Tuple[str, float, float]], year: int,
                 price_provider=None, prefill=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Quadro RW {year} - Valorizzazione cripto-attività")
        self.resize(640, 460)
        self._year = year
        self._bounds = bounds
        self._provider = price_provider
        self._worker = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Quotazioni in EUR al 01/01/{year} e al 31/12/{year}. "
            "Le celle in giallo non sono state trovate: inseriscile a mano."
        ))

        self.tabella = QTableWidget(len(bounds), 5, self)
        self.tabella.setHorizontalHeaderLabels(
            ["Token", "Qtà 01/01", "Prezzo 01/01", "Qtà 31/12", "Prezzo 31/12"]
        )
        self.tabella.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        pf_in, pf_fin = prefill if prefill else ({}, {})
        for riga, (token, qta_in, qta_fin) in enumerate(bounds):
            self._set_readonly(riga, self.COL_TOKEN, token)
            self._set_readonly(riga, self.COL_QTA_IN, f"{qta_in:.8f}")
            self._set_readonly(riga, self.COL_QTA_FIN, f"{qta_fin:.8f}")
            p_in = pf_in.get(token, 0.0)
            p_fin = pf_fin.get(token, 0.0)
            self.tabella.setItem(riga, self.COL_PREZZO_IN,
                                 QTableWidgetItem(f"{p_in:.6f}" if p_in else ""))
            self.tabella.setItem(riga, self.COL_PREZZO_FIN,
                                 QTableWidgetItem(f"{p_fin:.6f}" if p_fin else ""))
            self._marca_mancante(riga, self.COL_PREZZO_IN)
            self._marca_mancante(riga, self.COL_PREZZO_FIN)

        layout.addWidget(self.tabella)

        riga_btn = QHBoxLayout()
        self.btn_scarica = QPushButton("↻ Scarica quotazioni")
        self.btn_scarica.clicked.connect(self._scarica_prezzi)
        riga_btn.addWidget(self.btn_scarica)
        riga_btn.addStretch()
        layout.addLayout(riga_btn)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        # Scarica in automatico solo se non ci sono gia' valori salvati (che
        # altrimenti verrebbero sovrascritti); il pulsante resta disponibile.
        if self._provider is not None and not prefill:
            self._scarica_prezzi()

    def _set_readonly(self, riga: int, col: int, testo: str) -> None:
        item = QTableWidgetItem(testo)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.tabella.setItem(riga, col, item)

    def _marca_mancante(self, riga: int, col: int) -> None:
        item = self.tabella.item(riga, col)
        if item is not None and not item.text().strip():
            item.setBackground(QColor("#fff3cd"))

    def _smarca(self, riga: int, col: int) -> None:
        item = self.tabella.item(riga, col)
        if item is not None:
            item.setBackground(QColor("white"))

    def _scarica_prezzi(self) -> None:
        if self._provider is None:
            return
        self.btn_scarica.setEnabled(False)
        self.btn_scarica.setText("Scarico in corso...")
        simboli = [t for t, _, _ in self._bounds]
        self._worker = _FetchThread(self._provider, simboli, self._year)
        self._worker.finished.connect(self._prezzi_pronti)
        self._worker.start()

    def _prezzi_pronti(self, prezzi_inizio: Dict[str, float], prezzi_fine: Dict[str, float]) -> None:
        for riga, (token, _, _) in enumerate(self._bounds):
            if token in prezzi_inizio:
                self.tabella.item(riga, self.COL_PREZZO_IN).setText(f"{prezzi_inizio[token]:.6f}")
                self._smarca(riga, self.COL_PREZZO_IN)
            if token in prezzi_fine:
                self.tabella.item(riga, self.COL_PREZZO_FIN).setText(f"{prezzi_fine[token]:.6f}")
                self._smarca(riga, self.COL_PREZZO_FIN)
        self.btn_scarica.setEnabled(True)
        self.btn_scarica.setText("↻ Scarica quotazioni")

    @staticmethod
    def _num(item) -> float:
        if item is None:
            return 0.0
        try:
            return float(item.text().strip().replace(",", "."))
        except (ValueError, AttributeError):
            return 0.0

    def prezzi(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Restituisce (prezzi_1_gennaio, prezzi_31_dicembre) dalla tabella."""
        inizio, fine = {}, {}
        for riga, (token, _, _) in enumerate(self._bounds):
            inizio[token] = self._num(self.tabella.item(riga, self.COL_PREZZO_IN))
            fine[token] = self._num(self.tabella.item(riga, self.COL_PREZZO_FIN))
        return inizio, fine
