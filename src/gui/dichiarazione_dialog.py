"""
Dialog per generare la "Dichiarazione sostitutiva dell'atto di notorieta'"
(.docx) per le cripto-attivita', nel formato usato dai CAF.

Anagrafica del dichiarante (salvata in config) + tabella asset del Quadro RW
precompilata dal calcolo tasse ed editabile (nome wallet, staking, solo
monitoraggio) con possibilita' di aggiungere righe per wallet non importati.
"""

from typing import Dict, List

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QDialogButtonBox, QHeaderView, QHBoxLayout, QGroupBox, QCheckBox,
    QFileDialog, QMessageBox
)

from utils.dichiarazione import (
    Anagrafica, AssetRW, genera_dichiarazione_docx, dati_da_summary,
)
from utils.paths import default_save_path, remember_save_dir, ensure_ext

_CAMPI_ANAGRAFICA = [
    ("nome", "Cognome e nome"),
    ("nato_a", "Nato/a a"),
    ("nato_il", "Nato/a il"),
    ("codice_fiscale", "Codice fiscale"),
    ("residente_a", "Residente a"),
    ("indirizzo", "Indirizzo"),
    ("caf", "CAF / intermediario"),
    ("luogo", "Luogo (firma)"),
    ("data", "Data (firma)"),
]

COL_INCL, COL_DENOM, COL_WALLET, COL_VI, COL_VF, COL_DACQ, COL_QACQ, COL_CACQ, COL_STK, COL_MON = range(10)


class DichiarazioneDialog(QDialog):
    def __init__(self, summary: Dict, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Dichiarazione sostitutiva {summary.get('year', '')}")
        screen = QGuiApplication.primaryScreen()
        disponibile = screen.availableGeometry() if screen else None
        larghezza = min(1000, disponibile.width() - 80) if disponibile else 900
        altezza = min(700, disponibile.height() - 80) if disponibile else 620
        self.resize(larghezza, altezza)
        if disponibile:
            self.setMaximumSize(disponibile.width(), disponibile.height())
        self._summary = summary
        self._config = config

        layout = QVBoxLayout(self)

        # --- Anagrafica ---
        gb = QGroupBox("Dati del dichiarante")
        form = QFormLayout(gb)
        salvati = config.get("dichiarante", {}) or {}
        self._campi: Dict[str, QLineEdit] = {}
        for chiave, etichetta in _CAMPI_ANAGRAFICA:
            le = QLineEdit(str(salvati.get(chiave, "")))
            if chiave == "caf" and not le.text():
                le.setText("Caf Veneto Srl - CAAF CGIL NORDEST")
            self._campi[chiave] = le
            form.addRow(etichetta + ":", le)
        layout.addWidget(gb)

        # --- Tabella asset ---
        layout.addWidget(QLabel(
            "Asset del Quadro RW (valori in EUR). Spunta «Includi» per le crypto da riportare "
            "in dichiarazione, compila il wallet, staking / «solo monitoraggio» (bollo gia' "
            "versato), aggiungi righe per wallet non importati."
        ))
        self._assets, self._vendite = dati_da_summary(summary)
        self.tabella = QTableWidget(len(self._assets), 10, self)
        self.tabella.setHorizontalHeaderLabels([
            "Includi", "Denominazione", "Wallet", "Val. 1/1", "Val. 31/12",
            "Data acq.", "Qta acq.", "Costo acq.", "Staking", "Solo monit.",
        ])
        header = self.tabella.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_DENOM, QHeaderView.ResizeMode.Stretch)
        self.tabella.setColumnWidth(COL_INCL, 55)
        self.tabella.setColumnWidth(COL_WALLET, 110)
        self.tabella.setColumnWidth(COL_VI, 85)
        self.tabella.setColumnWidth(COL_VF, 85)
        self.tabella.setColumnWidth(COL_DACQ, 85)
        self.tabella.setColumnWidth(COL_QACQ, 75)
        self.tabella.setColumnWidth(COL_CACQ, 85)
        self.tabella.setColumnWidth(COL_STK, 60)
        self.tabella.setColumnWidth(COL_MON, 90)
        self.tabella.horizontalHeader().setStretchLastSection(False)
        for riga, a in enumerate(self._assets):
            self._scrivi_riga(riga, a)
        layout.addWidget(self.tabella)

        riga_btn = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi asset")
        btn_add.clicked.connect(lambda: self._scrivi_riga(self._nuova_riga(), AssetRW("")))
        riga_btn.addWidget(btn_add)
        btn_del = QPushButton("- Rimuovi selezionata")
        btn_del.clicked.connect(self._rimuovi_riga)
        riga_btn.addWidget(btn_del)
        btn_tutti = QPushButton("Seleziona tutti")
        btn_tutti.clicked.connect(lambda: self._imposta_inclusione(True))
        riga_btn.addWidget(btn_tutti)
        btn_nessuno = QPushButton("Deseleziona tutti")
        btn_nessuno.clicked.connect(lambda: self._imposta_inclusione(False))
        riga_btn.addWidget(btn_nessuno)
        riga_btn.addStretch()
        layout.addLayout(riga_btn)

        if self._vendite:
            righe = "; ".join(
                f"{v.denominazione}: {len(v.vendite)} vendite, plusv. "
                f"{sum(g for _, g in v.plusvalenze):,.2f} EUR" for v in self._vendite
            )
            layout.addWidget(QLabel(f"Vendite/plusvalenze (dal calcolo, metodo "
                                    f"{summary.get('cost_basis_method', '')}): {righe}"))

        buttons = QDialogButtonBox()
        b_gen = buttons.addButton("Genera .docx", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        b_gen.clicked.connect(self._genera)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _nuova_riga(self) -> int:
        r = self.tabella.rowCount()
        self.tabella.insertRow(r)
        return r

    def _rimuovi_riga(self):
        r = self.tabella.currentRow()
        if r >= 0:
            self.tabella.removeRow(r)

    def _imposta_inclusione(self, incluso: bool):
        for r in range(self.tabella.rowCount()):
            chk = self.tabella.cellWidget(r, COL_INCL)
            if chk is not None:
                chk.setChecked(incluso)

    def _scrivi_riga(self, riga: int, a: AssetRW):
        def cella(col, testo):
            self.tabella.setItem(riga, col, QTableWidgetItem(str(testo)))

        chk_incl = QCheckBox()
        chk_incl.setChecked(True)
        self.tabella.setCellWidget(riga, COL_INCL, chk_incl)
        cella(COL_DENOM, a.denominazione)
        cella(COL_WALLET, a.wallet)
        cella(COL_VI, f"{a.valore_iniziale:.2f}" if a.valore_iniziale else "")
        cella(COL_VF, f"{a.valore_finale:.2f}" if a.valore_finale else "")
        d, q, c = a.acquisto if a.acquisto else ("", "", "")
        cella(COL_DACQ, d)
        cella(COL_QACQ, q if q == "" else f"{q:g}")
        cella(COL_CACQ, c if c == "" else f"{c:.2f}")
        for col, val in ((COL_STK, a.staking), (COL_MON, a.solo_monitoraggio)):
            chk = QCheckBox()
            chk.setChecked(bool(val))
            self.tabella.setCellWidget(riga, col, chk)

    @staticmethod
    def _f(item) -> float:
        try:
            return float(str(item.text()).strip().replace(",", ".")) if item and item.text().strip() else 0.0
        except (ValueError, AttributeError):
            return 0.0

    def _leggi_assets(self) -> List[AssetRW]:
        out = []
        for r in range(self.tabella.rowCount()):
            denom_item = self.tabella.item(r, COL_DENOM)
            denom = denom_item.text().strip() if denom_item else ""
            if not denom:
                continue
            chk_incl = self.tabella.cellWidget(r, COL_INCL)
            if chk_incl is not None and not chk_incl.isChecked():
                continue
            dacq = (self.tabella.item(r, COL_DACQ).text().strip()
                    if self.tabella.item(r, COL_DACQ) else "")
            acquisto = None
            if dacq:
                acquisto = (dacq, self._f(self.tabella.item(r, COL_QACQ)),
                            self._f(self.tabella.item(r, COL_CACQ)))
            wallet_item = self.tabella.item(r, COL_WALLET)
            out.append(AssetRW(
                denominazione=denom,
                wallet=wallet_item.text().strip() if wallet_item else "",
                valore_iniziale=self._f(self.tabella.item(r, COL_VI)),
                valore_finale=self._f(self.tabella.item(r, COL_VF)),
                acquisto=acquisto,
                staking=self.tabella.cellWidget(r, COL_STK).isChecked(),
                solo_monitoraggio=self.tabella.cellWidget(r, COL_MON).isChecked(),
            ))
        return out

    def _genera(self):
        dati = {k: le.text().strip() for k, le in self._campi.items()}
        if not dati["nome"] or not dati["codice_fiscale"]:
            QMessageBox.warning(self, "Dati mancanti", "Inserisci almeno cognome/nome e codice fiscale.")
            return

        from utils.config import save_config
        self._config["dichiarante"] = dati
        save_config(self._config)

        anno = int(self._summary.get("year"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva dichiarazione",
            default_save_path(self._config, f"Dichiarazione_cripto_{anno}.docx"),
            "Word (*.docx)"
        )
        if not path:
            return
        path = ensure_ext(path, 'docx')
        remember_save_dir(self._config, path)
        save_config(self._config)

        assets = self._leggi_assets()
        denominazioni_incluse = {a.denominazione for a in assets}
        vendite = [v for v in self._vendite if v.denominazione in denominazioni_incluse]

        ok = genera_dichiarazione_docx(
            Anagrafica(**dati), assets, vendite, anno, path
        )
        if ok:
            QMessageBox.information(self, "Dichiarazione", "Documento generato.\n"
                                   "Fallo validare dal commercialista/CAF prima dell'invio.")
            self.accept()
        else:
            QMessageBox.critical(self, "Errore", "Errore nella generazione del documento.")
