"""
Main Window for CryptoAssistant
Contains the main GUI class (TradingTerminalWindow).
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QComboBox, QFrame, QGroupBox, QGridLayout, QInputDialog, QDateEdit,
    QCheckBox, QStackedWidget, QProgressBar, QApplication, QScrollArea,
    QMainWindow, QDialog
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QAction


def _leggi_versione() -> str:
    """Legge il numero di versione da version.txt.

    In sviluppo il file si trova nella root del progetto; nell'eseguibile
    PyInstaller (onedir) viene copiato accanto all'exe (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        version_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "version.txt"
    else:
        version_path = Path(__file__).resolve().parent.parent.parent / "version.txt"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "sconosciuta"


from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# Absolute imports (assuming src/ is in sys.path)
from data.database import TransactionDatabase
from data.importer import CSVImporter
from data.models import COIN_COLORS, FALLBACK_COLORS
from data.tax_rules import TaxRulesManager
from api.coinmarketcap import CoinMarketCapAPI, LivePricesWorker
from api.coingecko import CoinGeckoAPI
from api.historical_prices import ChainedHistoricalPrices
from api.frankfurter import HistoricalRatesWorker, get_live_exchange_rate
from utils.config import save_config, get_user_data_dir
from utils.currency import CurrencyConverter
from utils.dates import parse_dates_safe
from utils.calculations import (
    calculate_portfolio_allocation,
    calculate_token_stats,
    calculate_target_quantity,
    calculate_performance,
    calculate_invested_over_time
)
from utils.pdf_generator import FiscalReportGenerator
from utils.tax_calculator import TaxCalculator
from utils.updater import UpdateCheckWorker, UpdateDownloadWorker, avvia_installer_e_esci
from gui.quadro_rw_dialog import QuadroRWDialog


class TradingTerminalWindow(QMainWindow):
    """
    Main window for the CryptoAssistant application.
    Handles the GUI and user interactions.
    """
    
    def __init__(
        self,
        database: TransactionDatabase,
        cmc_api: CoinMarketCapAPI,
        currency_converter: CurrencyConverter,
        config: Dict
    ):
        """
        Initialize the main window.
        
        Args:
            database (TransactionDatabase): Database instance.
            cmc_api (CoinMarketCapAPI): CoinMarketCap API client.
            currency_converter (CurrencyConverter): Currency converter instance.
            config (Dict): Application configuration.
        """
        super().__init__()
        
        # Store dependencies
        self.database = database
        self.cmc_api = cmc_api
        self.currency_converter = currency_converter
        self.config = config
        
        # Initialize UI state
        self.valuta = config.get("default_currency", "EUR")
        self.tasso_cambio_live = currency_converter.live_rate
        self.tassi_storici = {}
        self.prezzi_live = {}
        self.dati_correnti = {'pmc': 0, 'qta': 0, 'costo_tot': 0, 'investito': 0}
        self.chart_mode = 'torta'  # 'torta' (allocazione) o 'andamento' (capitale investito nel tempo)

        # Initialize tax calculator (default: Italy)
        self.tax_rules_manager = TaxRulesManager()
        self.tax_calculator = TaxCalculator(country_code="IT", historical_rates=self.tassi_storici)
        # Quotazioni storiche 1/1 e 31/12 valorizzate a mano nel dialog Quadro RW,
        # riusate dal report PDF: {anno: (prezzi_inizio, prezzi_fine)}
        self._rw_prezzi: Dict[int, tuple] = {}

        # Initialize UI
        self.initUI()

        # Controllo aggiornamenti automatico in background, senza bloccare la GUI
        self._controlla_aggiornamenti(automatico=True)
        
        # Load data and update UI
        self.df_master = self.database.get_dataframe()
        if self.df_master is not None and not self.df_master.empty:
            self.aggiorna_menu_token()
            self.avvia_download_storico()
    
    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("Trading Assistant Pro - Dashboard")
        self._crea_menu_bar()
        self.setStyleSheet("""
            QWidget { background-color: #f4f7f6; font-family: 'Segoe UI', Arial; color: #333; }
            QGroupBox { 
                background-color: white; border: 1px solid #e1e4e8; border-radius: 8px; 
                margin-top: 15px; font-weight: bold; padding-top: 15px;
            }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 10px; color: #555; }
            QTableWidget {
                background-color: white; border: 1px solid #cfcfcf; border-radius: 6px;
                gridline-color: #f0f0f0; selection-background-color: #e6f2ff; selection-color: #000;
                alternate-background-color: #fafafa; font-size: 13px;
            }
            QHeaderView::section {
                background-color: #ffffff; border: none; border-bottom: 2px solid #007bff;
                padding: 6px; font-weight: bold; color: #444;
            }
            QPushButton { border-radius: 5px; padding: 6px 12px; font-weight: bold; }
            QCheckBox { color: #0056b3; font-weight: bold; font-size: 13px; margin-right: 10px; }
            QComboBox {
                background-color: white; color: #333; border: 1px solid #cfcfcf;
                border-radius: 4px; padding: 4px 8px;
            }
            QComboBox QAbstractItemView {
                background-color: white; color: #333; border: 1px solid #cfcfcf;
                selection-background-color: #007bff; selection-color: white;
                outline: none;
            }
        """)

        layout_principale = QVBoxLayout()

        # --- HEADER ---
        header = QFrame()
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #ddd; padding: 10px; border-radius: 8px;")
        layout_h_outer = QVBoxLayout(header)
        layout_h_outer.setSpacing(8)
        riga_filtri = QHBoxLayout()

        self.btn_aggiungi = QPushButton("\u2795 Importa CSV")
        self.btn_aggiungi.clicked.connect(self.importa_files)

        self.btn_reset_db = QPushButton("\ud83d\uddd1 Reset")
        self.btn_reset_db.setToolTip("Cancella tutte le transazioni importate per ricaricare i CSV da zero")
        self.btn_reset_db.setStyleSheet("background-color: #dc3545; color: white;")
        self.btn_reset_db.clicked.connect(self.reset_database)

        # --- Selettore rapido Anno (imposta Da/A sull'intero anno) ---
        self.combo_anno_filtro = QComboBox()
        self.combo_anno_filtro.setMinimumWidth(80)
        self.combo_anno_filtro.setToolTip("Seleziona un anno per filtrare rapidamente l'intero periodo")
        self.combo_anno_filtro.addItem("Anno")
        current_year = datetime.now().year
        for y in range(current_year + 1, 2009, -1):
            self.combo_anno_filtro.addItem(str(y))
        self.combo_anno_filtro.currentIndexChanged.connect(self.on_anno_filtro_changed)

        self.check_usa_filtro = QCheckBox("Filtro periodo attivo")
        self.check_usa_filtro.setToolTip("Se disattivo, viene mostrato lo storico completo")
        self.check_usa_filtro.toggled.connect(self._aggiorna_stato_date_filtro)
        self.check_usa_filtro.toggled.connect(lambda: self.aggiorna_vista())

        self.date_inizio = QDateEdit()
        self.date_inizio.setCalendarPopup(True)
        self.date_inizio.setDisplayFormat("dd/MM/yyyy")
        self.date_inizio.setFixedWidth(100)
        self.date_inizio.setDate(QDate.currentDate().addYears(-1))
        self.date_inizio.dateChanged.connect(lambda: self.aggiorna_vista())

        self.date_fine = QDateEdit()
        self.date_fine.setCalendarPopup(True)
        self.date_fine.setDisplayFormat("dd/MM/yyyy")
        self.date_fine.setFixedWidth(100)
        self.date_fine.setDate(QDate.currentDate())
        self.date_fine.dateChanged.connect(lambda: self.aggiorna_vista())

        # Le date sono modificabili solo quando il filtro periodo e' attivo
        self._aggiorna_stato_date_filtro(self.check_usa_filtro.isChecked())

        self.combo_token = QComboBox()
        self.combo_token.setMinimumWidth(140)
        self.combo_token.currentIndexChanged.connect(lambda: self.aggiorna_vista())

        self.btn_valuta = QPushButton(f"\ud83d\udcb1 {self.valuta}")
        self.btn_valuta.setToolTip("Cambia valuta di visualizzazione (EUR/USD)")
        self.btn_valuta.clicked.connect(self.toggle_valuta)

        # --- Selettore Nazione per Tasse ---
        self.combo_nazione = QComboBox()
        self.combo_nazione.setMinimumWidth(110)
        self.combo_nazione.addItems(self.tax_rules_manager.list_countries())
        self.combo_nazione.currentIndexChanged.connect(self.on_nazione_changed)

        riga_filtri.setSpacing(6)
        riga_filtri.addWidget(self.btn_valuta)
        riga_filtri.addSpacing(14)
        riga_filtri.addWidget(QLabel("<b>Asset:</b>"))
        riga_filtri.addWidget(self.combo_token)
        riga_filtri.addSpacing(14)
        riga_filtri.addWidget(QLabel("<b>Periodo:</b>"))
        riga_filtri.addWidget(self.combo_anno_filtro)
        riga_filtri.addWidget(self.check_usa_filtro)
        riga_filtri.addWidget(self.date_inizio)
        riga_filtri.addWidget(QLabel("\u2192"))
        riga_filtri.addWidget(self.date_fine)
        riga_filtri.addStretch()
        riga_filtri.addWidget(QLabel("<b>Nazione:</b>"))
        riga_filtri.addWidget(self.combo_nazione)
        riga_filtri.addSpacing(14)
        riga_filtri.addWidget(self.btn_reset_db)
        riga_filtri.addWidget(self.btn_aggiungi)

        layout_h_outer.addLayout(riga_filtri)
        layout_principale.addWidget(header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout_principale.addWidget(self.progress_bar)

        # --- CORPO ---
        layout_corpo = QHBoxLayout()

        self.stack_visualizzazione = QStackedWidget()
        
        # 1. Vista Tabella
        self.tabella = QTableWidget(0, 6)
        self.tabella.setHorizontalHeaderLabels(["Data", "Tipo", "Quantit\u00e0", "Prezzo Unit.", "Valore Tot.", "Note"])
        self.tabella.setAlternatingRowColors(True)
        self.tabella.setShowGrid(False)
        self.tabella.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabella.verticalHeader().setVisible(False)
        
        header_tab = self.tabella.horizontalHeader()
        for i in range(5): 
            header_tab.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header_tab.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.stack_visualizzazione.addWidget(self.tabella)

        # 2. Vista Grafico
        self.chart_view = QFrame()
        self.chart_view.setStyleSheet("background-color: white; border-radius: 8px;")
        self.chart_layout = QVBoxLayout(self.chart_view)
        
        self.lbl_chart_title = QLabel("\ud83d\udcca ALLOCAZIONE PORTAFOGLIO")
        self.lbl_chart_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #333; margin: 15px 0;")
        self.chart_layout.addWidget(self.lbl_chart_title)

        # Toggle tra vista "Allocazione" (torta) e "Andamento" (capitale investito nel tempo)
        chart_toolbar = QHBoxLayout()
        self.btn_vista_torta = QPushButton("\ud83e\udd67 Allocazione")
        self.btn_vista_andamento = QPushButton("\ud83d\udcc8 Andamento")
        for btn in (self.btn_vista_torta, self.btn_vista_andamento):
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { padding: 6px 14px; border: 1px solid #007bff; border-radius: 5px; color: #007bff; background: white; }
                QPushButton:checked { background-color: #007bff; color: white; }
            """)
        self.btn_vista_torta.setChecked(True)
        self.btn_vista_torta.clicked.connect(lambda: self.set_chart_mode('torta'))
        self.btn_vista_andamento.clicked.connect(lambda: self.set_chart_mode('andamento'))
        chart_toolbar.addStretch()
        chart_toolbar.addWidget(self.btn_vista_torta)
        chart_toolbar.addWidget(self.btn_vista_andamento)
        chart_toolbar.addStretch()
        self.chart_layout.addLayout(chart_toolbar)

        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.chart_layout.addWidget(self.canvas)

        # Interazione con la legenda della torta (hover/click), impostata una
        # sola volta: aggiorna_vista si limita a ripopolare questi riferimenti.
        self._pie_wedges = []
        self._pie_tokens = []
        self._pie_hover_idx = None
        self.canvas.mpl_connect('motion_notify_event', self._on_pie_legend_hover)
        self.canvas.mpl_connect('button_press_event', self._on_pie_legend_click)

        self.stack_visualizzazione.addWidget(self.chart_view)
        
        layout_corpo.addWidget(self.stack_visualizzazione, stretch=1)

        # Sidebar
        sidebar_widget = QFrame()
        sidebar_widget.setStyleSheet("background-color: transparent;")
        sidebar = QVBoxLayout(sidebar_widget)

        # 1. Patrimonio
        group_glob = QGroupBox("\ud83d\udcb0 PATRIMONIO ATTUALE")
        layout_g = QVBoxLayout()
        self.label_total_netto = QLabel("---")
        self.label_total_netto.setStyleSheet("font-size: 26px; font-weight: bold; color: #2c3e50;")
        layout_g.addWidget(self.label_total_netto)
        group_glob.setLayout(layout_g)
        sidebar.addWidget(group_glob)

        # 2. Dati Mercato
        group_price = QGroupBox("\ud83d\udcca DATI ASSET & MERCATO")
        layout_pr = QVBoxLayout()
        self.label_live_price = QLabel("---")
        self.label_live_price.setStyleSheet("font-size: 20px; color: #007bff; font-weight: bold;")
        self.label_qta_visibile = QLabel("Quantit\u00e0: ---")
        self.label_qta_visibile.setStyleSheet("font-size: 16px; font-weight: bold; color: #28a745; margin-top: 5px;")
        self.label_pmc = QLabel("PMC: ---")
        self.label_pmc.setStyleSheet("font-size: 14px; color: #555; font-weight: bold; margin-bottom: 5px;")
        btn_refresh = QPushButton("\ud83d\udd04 Aggiorna Prezzi")
        btn_refresh.clicked.connect(self.get_all_live_prices)
        layout_pr.addWidget(self.label_live_price)
        layout_pr.addWidget(self.label_qta_visibile)
        layout_pr.addWidget(self.label_pmc)
        layout_pr.addWidget(btn_refresh)
        group_price.setLayout(layout_pr)
        sidebar.addWidget(group_price)

        # 3. Performance
        self.group_perf = QGroupBox()
        layout_perf = QVBoxLayout()
        self.label_titolo_perf = QLabel("PERFORMANCE")
        self.label_titolo_perf.setStyleSheet("font-weight: bold; font-size: 15px; color: #333;")
        info_layout = QGridLayout()
        info_layout.addWidget(QLabel("Investito Totale:"), 0, 0)
        self.label_invest_perf = QLabel("---")
        self.label_invest_perf.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.label_invest_perf.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.label_invest_perf, 0, 1)
        info_layout.addWidget(QLabel("Valore Attuale:"), 1, 0)
        self.label_val_att_perf = QLabel("---")
        self.label_val_att_perf.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.label_val_att_perf.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.label_val_att_perf, 1, 1)
        layout_perf.addWidget(self.label_titolo_perf)
        layout_perf.addLayout(info_layout)
        self.group_perf.setLayout(layout_perf)
        sidebar.addWidget(self.group_perf)

        # 4. Strategia
        self.group_strat = QGroupBox("\ud83c\udfaf STRATEGIA MEDIA")
        layout_st = QVBoxLayout()
        self.input_target = QLineEdit()
        self.input_target.setPlaceholderText("Target PMC")
        btn_calc = QPushButton("Calcola Piano")
        btn_calc.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
        btn_calc.clicked.connect(self.calcola_target)
        self.label_ris = QLabel("-")
        self.label_ris.setWordWrap(True)
        self.label_ris.setStyleSheet("background-color: #f9f9f9; padding: 10px; border: 1px solid #ddd; border-radius: 5px; color: #333;")
        layout_st.addWidget(self.input_target)
        layout_st.addWidget(btn_calc)
        layout_st.addWidget(self.label_ris)
        self.group_strat.setLayout(layout_st)
        sidebar.addWidget(self.group_strat)

        # 5. Calcolo Tasse (NUOVO)
        self.group_tasse = QGroupBox("\ud83d\udcb3 CALCOLO TASSE")
        layout_tasse = QVBoxLayout()
        
        self.combo_anno_tasse = QComboBox()
        self.combo_anno_tasse.setMinimumWidth(100)
        # Populate with years from 2020 to current year + 1
        current_year = datetime.now().year
        for y in range(2020, current_year + 2):
            self.combo_anno_tasse.addItem(str(y))
        self.combo_anno_tasse.setCurrentText(str(current_year))
        
        btn_calcola_tasse = QPushButton("\ud83d\udc69 Calcola Tasse")
        btn_calcola_tasse.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 10px;")
        btn_calcola_tasse.clicked.connect(self.calcola_tasse)
        
        self.label_tasse_risultato = QLabel("Seleziona una nazione e un anno per calcolare le tasse.")
        self.label_tasse_risultato.setWordWrap(True)
        self.label_tasse_risultato.setStyleSheet("background-color: #fff3cd; padding: 10px; border: 1px solid #ffc107; border-radius: 5px; color: #856404;")
        
        self.btn_quadro_rw = QPushButton("📋 Valorizza Quadro RW (1/1 e 31/12)")
        self.btn_quadro_rw.setStyleSheet("background-color: #6f42c1; color: white; font-weight: bold; padding: 8px;")
        self.btn_quadro_rw.clicked.connect(self.apri_quadro_rw)

        btn_report_anno_tasse = QPushButton("📄 Report Fiscale Anno (RW + RT)")
        btn_report_anno_tasse.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 8px;")
        btn_report_anno_tasse.clicked.connect(self.genera_pdf_tasse_anno)

        layout_tasse.addWidget(QLabel("Anno:"))
        layout_tasse.addWidget(self.combo_anno_tasse)
        layout_tasse.addWidget(btn_calcola_tasse)
        layout_tasse.addWidget(self.label_tasse_risultato)
        layout_tasse.addWidget(self.btn_quadro_rw)
        layout_tasse.addWidget(btn_report_anno_tasse)
        self.group_tasse.setLayout(layout_tasse)
        sidebar.addWidget(self.group_tasse)

        sidebar.addStretch()

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidget(sidebar_widget)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFixedWidth(370)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        layout_corpo.addWidget(sidebar_scroll)
        layout_principale.addLayout(layout_corpo)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_pdf = QPushButton("\ud83d\udcc4 Report Fiscale PDF")
        self.btn_pdf.clicked.connect(self.genera_pdf_fiscale)
        self.btn_pdf.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_salva = QPushButton("\ud83d\udcbe Salva")
        self.btn_salva.clicked.connect(self.salva_database)
        self.btn_salva.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_esci = QPushButton("\ud83d\udeaa Esci")
        self.btn_esci.setStyleSheet("background-color: #6c757d; color: white; padding: 8px 20px;")
        self.btn_esci.clicked.connect(QApplication.instance().quit)
        footer.addWidget(self.btn_pdf)
        footer.addWidget(self.btn_salva)
        footer.addWidget(self.btn_esci)
        layout_principale.addLayout(footer)

        central_widget = QWidget()
        central_widget.setLayout(layout_principale)
        self.setCentralWidget(central_widget)

    def _crea_menu_bar(self):
        """Crea la barra dei menu con i menu 'Impostazioni' e 'Aiuto'."""
        menu_impostazioni = self.menuBar().addMenu("&Impostazioni")

        self.azione_dust_attivo = QAction("Nascondi asset sotto soglia (dust)", self)
        self.azione_dust_attivo.setCheckable(True)
        self.azione_dust_attivo.setChecked(self.config.get('dust_filter_enabled', True))
        self.azione_dust_attivo.toggled.connect(self._on_dust_filter_toggled)
        menu_impostazioni.addAction(self.azione_dust_attivo)

        azione_soglia_dust = QAction("Imposta soglia dust...", self)
        azione_soglia_dust.triggered.connect(self._imposta_soglia_dust)
        menu_impostazioni.addAction(azione_soglia_dust)

        menu_aiuto = self.menuBar().addMenu("&Aiuto")

        azione_info = QAction("Informazioni", self)
        azione_info.triggered.connect(self.mostra_informazioni)
        menu_aiuto.addAction(azione_info)

        azione_guida = QAction("Guida", self)
        azione_guida.triggered.connect(self.mostra_guida)
        menu_aiuto.addAction(azione_guida)

        azione_update = QAction("Controlla Aggiornamenti", self)
        azione_update.triggered.connect(lambda: self._controlla_aggiornamenti(automatico=False))
        menu_aiuto.addAction(azione_update)

    def mostra_informazioni(self):
        """Mostra la finestra 'Informazioni' con autore e versione (da version.txt)."""
        versione = _leggi_versione()
        QMessageBox.about(
            self,
            "Informazioni su CryptoAssistant",
            f"<b>CryptoAssistant</b><br>"
            f"Versione: {versione}<br><br>"
            f"Autore: enkas79<br>"
            f"Tool open-source per la gestione del portafoglio di criptovalute."
        )

    def mostra_guida(self):
        """Mostra un dialogo con la guida rapida all'uso dell'applicazione."""
        QMessageBox.information(
            self,
            "Guida - CryptoAssistant",
            "<b>Guida rapida</b><br><br>"
            "1. Importa le transazioni con '➕ Importa CSV'.<br>"
            "2. Seleziona un asset o 'Generale' per la vista d'insieme.<br>"
            "3. Usa il filtro date per limitare il periodo analizzato.<br>"
            "4. Genera il report fiscale PDF dal pulsante dedicato.<br>"
            "5. Salva le modifiche con '💾 Salva'."
        )

    def _on_dust_filter_toggled(self, attivo: bool):
        """Attiva/disattiva il filtro dust e salva la preferenza."""
        self.config['dust_filter_enabled'] = attivo
        save_config(self.config)
        self.aggiorna_vista()

    def _imposta_soglia_dust(self):
        """Chiede all'utente la soglia (in EUR) sotto cui un asset è considerato dust."""
        soglia_attuale = self.config.get('dust_threshold', 1.0)
        nuova_soglia, ok = QInputDialog.getDouble(
            self, "Soglia Dust",
            "Nascondi gli asset con valore inferiore a (€):",
            soglia_attuale, 0.0, 100000.0, 2
        )
        if ok:
            self.config['dust_threshold'] = nuova_soglia
            save_config(self.config)
            self.aggiorna_vista()

    # --- Autoupdate ---

    def _controlla_aggiornamenti(self, automatico: bool):
        """Avvia in background la verifica di nuove versioni su GitHub Releases."""
        self._update_automatico = automatico
        versione_corrente = _leggi_versione()

        self._update_check_worker = UpdateCheckWorker(versione_corrente)
        self._update_check_worker.aggiornamento_disponibile.connect(self._on_aggiornamento_disponibile)
        self._update_check_worker.nessun_aggiornamento.connect(self._on_nessun_aggiornamento)
        self._update_check_worker.errore.connect(self._on_errore_controllo_aggiornamenti)
        self._update_check_worker.start()

    def _on_aggiornamento_disponibile(self, versione: str, asset_url: str, changelog: str):
        """Mostra il changelog e chiede conferma prima di scaricare l'aggiornamento."""
        risposta = QMessageBox.question(
            self,
            "Aggiornamento disponibile",
            f"È disponibile la versione {versione}.\n\n"
            f"Note di rilascio:\n{changelog}\n\n"
            "Vuoi scaricarla e installarla ora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if risposta != QMessageBox.StandardButton.Yes:
            return

        if not asset_url:
            QMessageBox.warning(
                self, "Aggiornamento",
                "Nessun installer trovato nella release. Scaricala manualmente da GitHub."
            )
            return

        self._update_download_worker = UpdateDownloadWorker(asset_url)
        self._update_download_worker.completato.connect(self._on_download_completato)
        self._update_download_worker.errore.connect(self._on_errore_controllo_aggiornamenti)
        self._update_download_worker.start()

    def _on_nessun_aggiornamento(self):
        if not self._update_automatico:
            QMessageBox.information(self, "Aggiornamenti", "Stai già usando l'ultima versione disponibile.")

    def _on_errore_controllo_aggiornamenti(self, messaggio: str):
        if not self._update_automatico:
            QMessageBox.warning(self, "Aggiornamenti", f"Impossibile verificare gli aggiornamenti:\n{messaggio}")

    def _on_download_completato(self, percorso_installer: str):
        QMessageBox.information(
            self, "Aggiornamento",
            "Download completato. L'applicazione verrà chiusa per avviare l'installazione."
        )
        avvia_installer_e_esci(percorso_installer)

    # --- Methods ---

    def _aggiorna_stato_date_filtro(self, attivo: bool):
        """Abilita/disabilita visivamente i campi Da/A in base al filtro periodo."""
        self.date_inizio.setEnabled(attivo)
        self.date_fine.setEnabled(attivo)

    def set_chart_mode(self, mode: str):
        """Switch the "Generale" chart between allocation (pie) and trend (line) view."""
        self.chart_mode = mode
        self.btn_vista_torta.setChecked(mode == 'torta')
        self.btn_vista_andamento.setChecked(mode == 'andamento')
        self.aggiorna_vista()

    def on_anno_filtro_changed(self, index: int):
        """Set the date range filter to a full calendar year when selected from the dropdown."""
        text = self.combo_anno_filtro.currentText()
        if not text.isdigit():
            return

        year = int(text)
        oggi = QDate.currentDate()
        inizio = QDate(year, 1, 1)
        fine = oggi if year == oggi.year() else QDate(year, 12, 31)

        self.date_inizio.blockSignals(True)
        self.date_fine.blockSignals(True)
        self.check_usa_filtro.blockSignals(True)
        self.date_inizio.setDate(inizio)
        self.date_fine.setDate(fine)
        self.check_usa_filtro.setChecked(True)
        self.date_inizio.blockSignals(False)
        self.date_fine.blockSignals(False)
        self.check_usa_filtro.blockSignals(False)

        self.aggiorna_vista()

    def on_nazione_changed(self, index: int):
        """Update tax calculator when country changes."""
        country_name = self.combo_nazione.currentText()
        rule = self.tax_rules_manager.get_country_by_name(country_name)
        if rule:
            self.tax_calculator = TaxCalculator(
                country_code=rule.country_code,
                historical_rates=self.tassi_storici
            )
            self.label_tasse_risultato.setText(f"Calcolo tasse per {country_name} - Seleziona un anno.")

    def calcola_tasse(self):
        """Calculate taxes for the selected country and year."""
        if self.df_master is None or self.df_master.empty:
            QMessageBox.warning(self, "Tasse", "Nessun dato disponibile per il calcolo delle tasse.")
            return
        
        year = int(self.combo_anno_tasse.currentText())

        try:
            prezzi_inizio, prezzi_fine = self._rw_prezzi.get(year, (None, None))
            tax_summary = self.tax_calculator.get_tax_summary(
                self.df_master, year, prices_start=prezzi_inizio, prices_end=prezzi_fine
            )

            result_text = f"""
            <b>Calcolo Tasse per {tax_summary['country']} ({tax_summary['year']})</b><br>
            <i>Metodo costo base: {tax_summary['cost_basis_method']}</i><br><br>
            <b>Quadro RT - Plusvalenze:</b> €{tax_summary['capital_gain']:,.2f}<br>
            <b>Imposta su Plusvalenze ({tax_summary['rule']['capital_gain_rate']}):</b> €{tax_summary['capital_gain_tax']:,.2f}<br>
            <b>Imposta di Bollo:</b> €{tax_summary['stamp_duty']:,.2f}<br>
            """

            if tax_summary['quadro_rw']:
                result_text += (
                    f"<b>Quadro RW - Imposta cripto-attività (0,2%):</b> "
                    f"€{tax_summary['imposta_cripto_totale']:,.2f}<br>"
                )
            else:
                result_text += (
                    "<i>Quadro RW non valorizzato: usa il pulsante «Valorizza Quadro RW».</i><br>"
                )

            result_text += (
                f"<b>Totale Tasse:</b> <span style='color: #dc3545; font-weight: bold;'>"
                f"€{tax_summary['total_tax']:,.2f}</span><br><br>"
            )

            if tax_summary['declaration_required']:
                result_text += "⚠️ <b>Dichiarazione RW obbligatoria</b> (portafoglio > {}).<br>".format(
                    tax_summary['rule']['declaration_threshold']
                )

            if tax_summary['zero_price_rows']:
                result_text += (
                    f"⚠️ {len(tax_summary['zero_price_rows'])} righe di acquisto senza prezzo "
                    "da verificare (vedi report PDF).<br>"
                )

            if tax_summary['notes']:
                result_text += "<br><b>Note:</b><br>" + "<br>".join(tax_summary['notes'])

            result_text += (
                "<br><br><i>Output da far validare al commercialista.</i>"
            )

            self.label_tasse_risultato.setText(result_text)

        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nel calcolo delle tasse: {e}")
            self.label_tasse_risultato.setText("Errore nel calcolo delle tasse.")

    def apri_quadro_rw(self):
        """Apre il dialog per valorizzare le cripto-attività al 1/1 e al 31/12."""
        if self.df_master is None or self.df_master.empty:
            QMessageBox.warning(self, "Quadro RW", "Nessun dato disponibile.")
            return

        year = int(self.combo_anno_tasse.currentText())
        try:
            bounds = self.tax_calculator.holdings_bounds(self.df_master, year)
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nel calcolo delle giacenze: {e}")
            return

        if not bounds:
            QMessageBox.information(self, "Quadro RW", f"Nessuna cripto-attività detenuta nel {year}.")
            return

        data_dir = get_user_data_dir()
        provider = ChainedHistoricalPrices([
            CoinMarketCapAPI(self.cmc_api.api_key, cache_path=str(data_dir / "cmc_storico.json")),
            CoinGeckoAPI(cache_path=str(data_dir / "coingecko_cache.json")),
        ])
        dialog = QuadroRWDialog(bounds, year, price_provider=provider, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._rw_prezzi[year] = dialog.prezzi()
            self.calcola_tasse()

    def genera_pdf_tasse_anno(self):
        """Genera il report fiscale PDF con il calcolo tasse dell'anno selezionato."""
        if self.df_master is None or self.df_master.empty:
            QMessageBox.warning(self, "Report Fiscale", "Nessun dato disponibile.")
            return

        year = int(self.combo_anno_tasse.currentText())

        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Report Fiscale", f"Report_Fiscale_{year}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            prezzi_inizio, prezzi_fine = self._rw_prezzi.get(year, (None, None))
            if prezzi_inizio is None:
                risposta = QMessageBox.question(
                    self, "Quadro RW non valorizzato",
                    "Non hai ancora valorizzato il Quadro RW per questo anno "
                    "(quotazioni 1/1 e 31/12). Il report conterrà solo il Quadro RT.\n\n"
                    "Vuoi valorizzarlo ora?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if risposta == QMessageBox.StandardButton.Yes:
                    self.apri_quadro_rw()
                    prezzi_inizio, prezzi_fine = self._rw_prezzi.get(year, (None, None))

            tax_summary = self.tax_calculator.get_tax_summary(
                self.df_master, year, prices_start=prezzi_inizio, prices_end=prezzi_fine
            )

            generator = FiscalReportGenerator(
                live_prices=self.prezzi_live,
                exchange_rate=self.tasso_cambio_live,
                currency=self.valuta
            )
            success = generator.generate_tax_report(tax_summary, path)

            if success:
                QMessageBox.information(self, "Report Fiscale", "Report Fiscale dell'anno generato con successo!")
            else:
                QMessageBox.critical(self, "Errore PDF", "Errore nella generazione del report fiscale.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nella generazione del report fiscale: {e}")

    def importa_files(self):
        """Import CSV files with transactions."""
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleziona CSV", "", "CSV Files (*.csv)")
        if not paths:
            return

        dfs = CSVImporter.import_from_csv(paths)
        if dfs:
            new_data = pd.concat(dfs)
            rows_added = self.database.add_transactions(new_data)
            self.df_master = self.database.get_dataframe()

            if rows_added > 0:
                self.aggiorna_menu_token()
                self.avvia_download_storico()
                QMessageBox.information(self, "Import", f"\u2705 Importazione completata! (+{rows_added})")
            else:
                QMessageBox.information(self, "Import", "Nessun nuovo dato aggiunto.")
        else:
            QMessageBox.warning(self, "Import", "Nessun dato valido.")

    def reset_database(self):
        """Svuota il database delle transazioni per permettere un nuovo caricamento da zero."""
        risposta = QMessageBox.question(
            self, "Reset Database",
            "⚠️ Tutte le transazioni importate verranno eliminate.\n"
            "Vuoi continuare per poter ricaricare nuovi file CSV?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if risposta != QMessageBox.StandardButton.Yes:
            return

        self.database.clear_all()
        self.df_master = None
        self.prezzi_live = {}
        self.tabella.setRowCount(0)
        self.label_total_netto.setText("---")
        self.label_live_price.setText("---")
        self.label_qta_visibile.setText("Quantità: ---")
        self.label_pmc.setText("PMC: ---")
        self.label_invest_perf.setText("---")
        self.label_val_att_perf.setText("---")

        # Pulisce anche il grafico (aggiorna_vista esce subito se df_master è vuoto)
        self.figure.clear()
        self.canvas.draw()

        self.aggiorna_menu_token()
        QMessageBox.information(self, "Reset Database", "✅ Database svuotato. Puoi importare nuovi file CSV.")

    def aggiorna_menu_token(self):
        """Update the token dropdown menu."""
        tokens = self.database.get_tokens()
        self.combo_token.clear()
        self.combo_token.addItem("Generale")
        self.combo_token.addItems(tokens)
        self.get_all_live_prices()

    def get_all_live_prices(self):
        """Fetch live prices for all tokens in a background thread (does not block the UI)."""
        if self.df_master is None or self.df_master.empty:
            return

        if hasattr(self, 'prices_worker') and self.prices_worker.isRunning():
            return

        tokens = self.df_master['Token'].unique().tolist()

        self.prices_worker = LivePricesWorker(self.cmc_api, tokens, convert="USD")
        self.prices_worker.finished.connect(self._su_prezzi_live_ricevuti)
        self.prices_worker.start()

    def _su_prezzi_live_ricevuti(self, prices):
        """Handle live prices received from the background worker."""
        self.prezzi_live = prices

        # Update live exchange rate
        if self.valuta == "EUR":
            self.tasso_cambio_live = self.currency_converter.live_rate
            self.currency_converter.set_live_rate(self.tasso_cambio_live)

        self.aggiorna_vista()

    def avvia_download_storico(self):
        """Start downloading historical exchange rates."""
        if self.df_master is None or self.df_master.empty:
            return
        
        df_dates = self.df_master['Date (UTC+1:00)'].dropna()
        if df_dates.empty:
            return
        
        min_date = df_dates.min().date()
        max_date = datetime.now().date()
        
        self.progress_bar.setVisible(True)
        self.worker = HistoricalRatesWorker(min_date, max_date, base="USD", target="EUR")
        self.worker.finished.connect(self.salva_tassi_storici)
        self.worker.start()

    def salva_tassi_storici(self, rates):
        """Save historical exchange rates."""
        self.tassi_storici = rates
        self.currency_converter.set_historical_rates(rates)
        self.tax_calculator.set_historical_rates(rates)
        self.progress_bar.setVisible(False)
        self.aggiorna_vista()

    def get_historical_rate(self, date_obj):
        """Get historical exchange rate for a specific date."""
        return self.currency_converter.get_rate_for_date(date_obj)

    def aggiorna_vista(self):
        """Update the view based on current filters."""
        if self.df_master is None or self.df_master.empty:
            return
        
        selection = self.combo_token.currentText()
        simb = "\u20ac" if self.valuta == "EUR" else "$"
        mult_live = self.tasso_cambio_live if self.valuta == "EUR" else 1.0

        df_lavoro = self.df_master.copy()
        df_lavoro['Date (UTC+1:00)'] = parse_dates_safe(df_lavoro['Date (UTC+1:00)'])
        df_lavoro = df_lavoro.dropna(subset=['Date (UTC+1:00)'])
        
        if self.check_usa_filtro.isChecked():
            d_inizio = self.date_inizio.date().toPyDate()
            d_fine = self.date_fine.date().toPyDate()
            mask = (df_lavoro['Date (UTC+1:00)'].dt.date >= d_inizio) & (df_lavoro['Date (UTC+1:00)'].dt.date <= d_fine)
            df_filtrato = df_lavoro.loc[mask]
        else:
            df_filtrato = df_lavoro

        # --- MODALITÀ GENERALE (GRAFICO) ---
        if selection == "Generale":
            self.stack_visualizzazione.setCurrentWidget(self.chart_view)
            self.group_strat.setVisible(False)
            self.label_qta_visibile.setText(f"Asset in portafoglio: {len(df_filtrato['Token'].unique())}")
            self.label_pmc.setText("Visione d'insieme")
            self.label_live_price.setText("Globale")

            # Calculate portfolio allocation
            dust_threshold = 0.0
            if self.config.get('dust_filter_enabled', True):
                soglia_eur = self.config.get('dust_threshold', 1.0)
                dust_threshold = (
                    soglia_eur if self.valuta == "EUR"
                    else soglia_eur / self.tasso_cambio_live if self.tasso_cambio_live else soglia_eur
                )

            values, labels, colors, invested, quantities = calculate_portfolio_allocation(
                df_filtrato, self.prezzi_live, self.tasso_cambio_live, self.valuta,
                dust_threshold=dust_threshold, rate_for_date=self.get_historical_rate
            )

            # Order by allocation percentage (descending)
            if values:
                order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
                values = [values[i] for i in order]
                labels = [labels[i] for i in order]
                colors = [colors[i] for i in order]
                invested = [invested[i] for i in order]
                quantities = [quantities[i] for i in order]

            tot_investito = sum(invested)
            tot_valore = sum(values)

            self.label_total_netto.setText(f"{tot_valore:,.2f} {simb}")
            self.dati_correnti['investito'] = tot_investito
            self.dati_correnti['qta'] = 0
            self.dati_correnti['pmc'] = 0

            # Update chart (allocazione o andamento, in base a self.chart_mode)
            self.figure.clear()

            if self.chart_mode == 'andamento':
                self.lbl_chart_title.setText("📈 ANDAMENTO CAPITALE INVESTITO")
                self._disegna_andamento(df_filtrato, simb)
                self._pie_wedges = []
                self._pie_tokens = []
            else:
                self.lbl_chart_title.setText("📊 ALLOCAZIONE PORTAFOGLIO")
                ax = self.figure.add_axes([0.4, 0.0, 0.6, 1.0])

                if values and sum(values) > 0:
                    # Limita le fette in legenda: oltre MAX_FETTE asset, raggruppa i più
                    # piccoli in "Altri" per evitare legende enormi (lente e a rischio
                    # di problemi di rendering con portafogli molto frammentati).
                    MAX_FETTE = 12
                    if len(values) > MAX_FETTE:
                        order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
                        top_idx = order[:MAX_FETTE - 1]
                        altri_idx = order[MAX_FETTE - 1:]
                        values_plot = [values[i] for i in top_idx] + [sum(values[i] for i in altri_idx)]
                        labels_plot = [labels[i] for i in top_idx] + ["Altri"]
                        colors_plot = [colors[i] for i in top_idx] + ["#adb5bd"]
                        # Nessuna quantità sensata per "Altri" (asset diversi aggregati)
                        quantities_plot = [quantities[i] for i in top_idx] + [None]
                    else:
                        values_plot, labels_plot, colors_plot = values, labels, colors
                        quantities_plot = quantities

                    wedges, texts = ax.pie(values_plot, startangle=90, colors=colors_plot, wedgeprops=dict(width=0.45))

                    # Colonne allineate: calcola la larghezza massima di ogni campo
                    # e le formatta con font monospace, cosi le cifre si incolonnano.
                    total = sum(values_plot)
                    qta_strs, perc_strs, val_strs = [], [], []
                    for i, l in enumerate(labels_plot):
                        val = values_plot[i]
                        perc = (val / total) * 100
                        qta = quantities_plot[i]
                        qta_strs.append(f"{qta:,.3f}" if qta is not None else "")
                        perc_strs.append(f"{perc:.1f}%")
                        val_strs.append(f"{val:,.0f}{simb}")

                    w_qta = max(len(s) for s in qta_strs)
                    w_label = max(len(s) for s in labels_plot)
                    w_perc = max(len(s) for s in perc_strs)
                    w_val = max(len(s) for s in val_strs)

                    legend_labels = [
                        f"{qta_strs[i]:>{w_qta}} {l:<{w_label}} {perc_strs[i]:>{w_perc}} ({val_strs[i]:>{w_val}})"
                        for i, l in enumerate(labels_plot)
                    ]
                    legend = ax.legend(
                        wedges, legend_labels, title="Asset", loc="center left",
                        bbox_to_anchor=(-0.6, 0.5), fontsize=10, frameon=False,
                        prop={'family': 'monospace'}
                    )

                    self._pie_wedges = wedges
                    self._pie_tokens = labels_plot
                    self._pie_legend = legend
                    self._pie_hover_idx = None
                else:
                    ax.text(0.5, 0.5, "Dati insufficienti", ha='center', va='center')
                    ax.set_axis_off()
                    self._pie_wedges = []
                    self._pie_tokens = []

            self.canvas.draw()
            self.aggiorna_performance_globale(tot_investito, tot_valore, simb)

        # --- MODALITÀ SINGOLA MONETA ---
        else:
            self.stack_visualizzazione.setCurrentWidget(self.tabella)
            self.group_strat.setVisible(True)
            df_t = df_filtrato[df_filtrato['Token'] == selection]

            self.tabella.setRowCount(0)

            for _, row in df_t.iterrows():
                r = self.tabella.rowCount()
                self.tabella.insertRow(r)
                
                orig_curr = str(row.get('Original Currency', 'EUR'))
                factor = 1.0
                
                if self.valuta == "EUR" and orig_curr == "USD":
                    factor = self.get_historical_rate(row['Date (UTC+1:00)'])
                
                prezzo_storico = row['Price'] * factor
                val_tot_storico = row['Amount'] * prezzo_storico

                try:
                    data_fmt = row['Date (UTC+1:00)'].strftime("%d/%m/%Y")
                except:
                    data_fmt = str(row['Date (UTC+1:00)'])
                
                item_data = QTableWidgetItem(data_fmt)
                item_type = QTableWidgetItem(str(row['Type']).upper())
                item_qta = QTableWidgetItem(f"{row['Amount']:.6f}")
                item_price = QTableWidgetItem(f"{prezzo_storico:,.4f} {simb}")
                item_val_tot = QTableWidgetItem(f"{val_tot_storico:,.2f} {simb}")
                
                note_text = str(row.get('Notes', ''))
                if note_text == "nan":
                    note_text = ""
                item_note = QTableWidgetItem(note_text)
                
                for item in [item_data, item_type, item_qta, item_price, item_val_tot]:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_note.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                
                if 'buy' in str(row['Type']).lower():
                    item_type.setForeground(QColor("#28a745"))
                else:
                    item_type.setForeground(QColor("#dc3545"))

                self.tabella.setItem(r, 0, item_data)
                self.tabella.setItem(r, 1, item_type)
                self.tabella.setItem(r, 2, item_qta)
                self.tabella.setItem(r, 3, item_price)
                self.tabella.setItem(r, 4, item_val_tot)
                self.tabella.setItem(r, 5, item_note)

            # Calculate token stats
            stats = calculate_token_stats(
                df_filtrato, selection, self.prezzi_live.get(selection, 0),
                self.tasso_cambio_live, self.valuta, rate_for_date=self.get_historical_rate
            )
            
            qta_tot = stats['quantity']
            pmc = stats['pmc']
            investito_singolo = stats['invested']
            
            self.dati_correnti['investito'] = investito_singolo
            self.dati_correnti['pmc'] = pmc
            self.dati_correnti['qta'] = qta_tot
            
            prezzo_mkt = self.prezzi_live.get(selection, 0) * mult_live
            self.label_live_price.setText(f"{prezzo_mkt:,.4f} {simb}")
            self.label_pmc.setText(f"PMC: {pmc:,.4f} {simb}")
            self.label_qta_visibile.setText(f"Quantit\u00e0: {qta_tot:,.6f}")
            valore_oggi = qta_tot * prezzo_mkt
            self.label_total_netto.setText(f"{valore_oggi:,.2f} {simb}")

            self.aggiorna_performance_globale(investito_singolo, valore_oggi, simb)

    def _disegna_andamento(self, df, simb):
        """
        Draw the cumulative net invested capital over time (line chart).

        Nota: mostra il capitale investito netto (buy - sell cumulati) dalle
        transazioni, non il valore di mercato storico del portafoglio, che
        richiederebbe prezzi storici per singolo asset non disponibili con
        un piano CoinMarketCap gratuito.
        """
        dates, values = calculate_invested_over_time(
            df, self.tasso_cambio_live, self.valuta, rate_for_date=self.get_historical_rate
        )

        ax = self.figure.add_axes([0.12, 0.18, 0.85, 0.72])
        if dates:
            ax.plot(dates, values, color="#007bff", linewidth=2)
            ax.fill_between(dates, values, color="#007bff", alpha=0.1)
            ax.set_ylabel(f"Capitale investito ({simb})")
            ax.grid(True, alpha=0.3)
            self.figure.autofmt_xdate()
        else:
            ax.text(0.5, 0.5, "Dati insufficienti", ha='center', va='center')
            ax.set_axis_off()

    def _indice_legenda_sotto_mouse(self, event) -> Optional[int]:
        """Restituisce l'indice della voce di legenda della torta sotto il
        cursore (testo o riquadro colore), o None se il mouse non è su
        nessuna voce."""
        legend = getattr(self, '_pie_legend', None)
        if legend is None or not self._pie_tokens:
            return None
        for idx, (handle, text) in enumerate(zip(legend.legend_handles, legend.get_texts())):
            contains_handle, _ = handle.contains(event)
            contains_text, _ = text.contains(event)
            if contains_handle or contains_text:
                return idx
        return None

    def _on_pie_legend_hover(self, event):
        """Evidenzia la fetta della torta corrispondente alla voce di
        legenda sotto il mouse."""
        if not self._pie_wedges:
            return
        idx = self._indice_legenda_sotto_mouse(event)
        if idx == self._pie_hover_idx:
            return
        self._pie_hover_idx = idx
        for i, wedge in enumerate(self._pie_wedges):
            if i == idx:
                wedge.set_edgecolor('#333333')
                wedge.set_linewidth(3)
            else:
                wedge.set_edgecolor('white')
                wedge.set_linewidth(1)
        self.canvas.draw_idle()

    def _on_pie_legend_click(self, event):
        """Al click su una voce di legenda, apre il riepilogo dell'asset."""
        if not self._pie_tokens:
            return
        idx = self._indice_legenda_sotto_mouse(event)
        if idx is None:
            return
        token = self._pie_tokens[idx]
        if token == "Altri":
            QMessageBox.information(
                self, "Altri asset",
                "Questa fetta raggruppa gli asset più piccoli del portafoglio.\n"
                "Seleziona il singolo asset dal menu a tendina 'Asset' per vederne il dettaglio."
            )
            return
        self._mostra_riepilogo_asset(token)

    def _mostra_riepilogo_asset(self, token: str):
        """Mostra una finestra con il riepilogo delle performance di un
        singolo asset, con la possibilità di stamparlo/esportarlo in PDF."""
        simb = "€" if self.valuta == "EUR" else "$"
        stats = calculate_token_stats(
            self.df_master, token, self.prezzi_live.get(token, 0),
            self.tasso_cambio_live, self.valuta, rate_for_date=self.get_historical_rate
        )
        perc, diff = calculate_performance(stats['invested'], stats['current_value'])
        colore = "#28a745" if perc >= 0 else "#dc3545"

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Riepilogo {token}")
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)

        titolo = QLabel(f"📊 {token}")
        titolo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(titolo)

        griglia = QGridLayout()
        righe = [
            ("Quantità posseduta:", f"{stats['quantity']:,.6f} {token}"),
            ("PMC (prezzo medio):", f"{stats['pmc']:,.4f} {simb}"),
            ("Investito:", f"{stats['invested']:,.2f} {simb}"),
            ("Valore attuale:", f"{stats['current_value']:,.2f} {simb}"),
        ]
        for r, (etichetta, valore) in enumerate(righe):
            griglia.addWidget(QLabel(etichetta), r, 0)
            lbl_valore = QLabel(valore)
            lbl_valore.setStyleSheet("font-weight: bold;")
            griglia.addWidget(lbl_valore, r, 1)
        layout.addLayout(griglia)

        lbl_perf = QLabel(f"Performance: {perc:+.2f}% ({diff:+,.2f} {simb})")
        lbl_perf.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {colore}; margin-top: 10px;")
        layout.addWidget(lbl_perf)

        pulsanti = QHBoxLayout()
        btn_stampa = QPushButton("🖨 Stampa / Esporta PDF")
        btn_stampa.clicked.connect(lambda: self._stampa_riepilogo_asset(token))
        btn_chiudi = QPushButton("Chiudi")
        btn_chiudi.clicked.connect(dialog.accept)
        pulsanti.addWidget(btn_stampa)
        pulsanti.addWidget(btn_chiudi)
        layout.addLayout(pulsanti)

        dialog.exec()

    def _stampa_riepilogo_asset(self, token: str):
        """Genera un PDF con il solo estratto conto dell'asset selezionato."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Riepilogo", f"Riepilogo_{token}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return

        df_token = self.df_master[self.df_master['Token'] == token]
        generator = FiscalReportGenerator(
            live_prices=self.prezzi_live,
            exchange_rate=self.tasso_cambio_live,
            currency=self.valuta
        )
        successo = generator.generate_report(df_token, path)

        if successo:
            QMessageBox.information(self, "Riepilogo", "PDF generato con successo!")
        else:
            QMessageBox.critical(self, "Errore PDF", "Errore nella generazione del riepilogo.")

    def aggiorna_performance_globale(self, investito, valore_attuale, simb):
        """Update performance display."""
        self.label_invest_perf.setText(f"{investito:,.2f} {simb}")
        self.label_val_att_perf.setText(f"{valore_attuale:,.2f} {simb}")
        
        if investito > 0:
            perc, diff = calculate_performance(investito, valore_attuale)
            colore = "#28a745" if perc >= 0 else "#dc3545"
            bg = "#e8f5e9" if perc >= 0 else "#ffebee"
            self.label_titolo_perf.setText(f"PERFORMANCE ({perc:+.2f}%  {diff:+,.2f} {simb})")
            self.label_titolo_perf.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {colore};")
            self.group_perf.setStyleSheet(f"QGroupBox {{ background-color: {bg}; border: 2px solid {colore}; border-radius: 10px; }}")
        else:
            self.label_titolo_perf.setText("PERFORMANCE (N/A)")
            self.group_perf.setStyleSheet("")

    def calcola_target(self):
        """Calculate the quantity to buy to reach a target PMC."""
        try:
            target = float(self.input_target.text().replace(',', '.'))
            simb = "\u20ac" if self.valuta == "EUR" else "$"
            mkt = self.prezzi_live.get(self.combo_token.currentText(), 0) * (
                self.tasso_cambio_live if self.valuta == "EUR" else 1.0
            )
            q_c, p_c = self.dati_correnti['qta'], self.dati_correnti['pmc']
            
            if mkt == target:
                self.label_ris.setText("Il prezzo \u00e8 gi\u00e0 al target.")
                return
            
            q_n, spesa = calculate_target_quantity(q_c, p_c, target, mkt)
            
            if q_n > 0:
                self.label_ris.setText(f"\ud83c\udfaf Acquista <b>{q_n:,.4f}</b> unit\u00e0.<br>Spesa: <b>{spesa:,.2f} {simb}</b>")
            else:
                self.label_ris.setText("\u274c Target non raggiungibile.")
        except Exception as e:
            self.label_ris.setText("Errore calcolo.")
            print(f"Errore calcolo target: {e}")

    def toggle_valuta(self):
        """Toggle between EUR and USD."""
        self.valuta = "EUR" if self.valuta == "USD" else "USD"
        self.btn_valuta.setText(f"\ud83d\udcb1 Valuta: {self.valuta}")
        
        # Update exchange rate
        if self.valuta == "EUR":
            self.tasso_cambio_live = get_live_exchange_rate(base="USD", target="EUR")
            self.currency_converter.set_live_rate(self.tasso_cambio_live)
        else:
            self.tasso_cambio_live = 1.0
            self.currency_converter.set_live_rate(1.0)
        
        self.get_all_live_prices()

    def genera_pdf_fiscale(self):
        """Generate fiscal PDF report."""
        if self.df_master is None or self.df_master.empty:
            QMessageBox.warning(self, "PDF", "Nessun dato.")
            return
        
        # Get date filter
        if self.check_usa_filtro.isChecked():
            d_inizio = self.date_inizio.date().toPyDate()
            d_fine = self.date_fine.date().toPyDate()
        else:
            d_inizio = None
            d_fine = None
        
        # Get output path
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva Report", "Report_Fiscale.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        
        # Generate PDF
        generator = FiscalReportGenerator(
            live_prices=self.prezzi_live,
            exchange_rate=self.tasso_cambio_live,
            currency=self.valuta
        )
        
        success = generator.generate_report(
            self.df_master, path, d_inizio, d_fine
        )
        
        if success:
            QMessageBox.information(self, "PDF", "Report Fiscale Generato!")
        else:
            QMessageBox.critical(self, "Errore PDF", "Errore generazione report.")

    def salva_database(self):
        """Save the database to CSV."""
        if self.database.save():
            QMessageBox.information(self, "OK", "Database salvato correttamente!")
        else:
            QMessageBox.warning(self, "Errore", "Errore salvataggio database.")
