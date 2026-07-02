"""
Main Window for CryptoAssistant
Contains the main GUI class (TradingTerminalWindow).
"""

import os
import sys
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QComboBox, QFrame, QGroupBox, QGridLayout, QInputDialog, QDateEdit,
    QCheckBox, QStackedWidget, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# Absolute imports (assuming src/ is in sys.path)
from data.database import TransactionDatabase
from data.importer import CSVImporter
from data.models import COIN_COLORS, FALLBACK_COLORS
from data.tax_rules import TaxRulesManager
from api.coinmarketcap import CoinMarketCapAPI
from api.frankfurter import HistoricalRatesWorker, get_live_exchange_rate
from utils.currency import CurrencyConverter
from utils.calculations import (
    calculate_portfolio_allocation,
    calculate_token_stats,
    calculate_target_quantity,
    calculate_performance
)
from utils.pdf_generator import FiscalReportGenerator
from utils.tax_calculator import TaxCalculator


class TradingTerminalWindow(QWidget):
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

        # Initialize tax calculator (default: Italy)
        self.tax_rules_manager = TaxRulesManager()
        self.tax_calculator = TaxCalculator(country_code="IT", historical_rates=self.tassi_storici)

        # Initialize UI
        self.initUI()
        
        # Load data and update UI
        self.df_master = self.database.get_dataframe()
        if self.df_master is not None and not self.df_master.empty:
            self.aggiorna_menu_token()
            self.avvia_download_storico()
    
    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("Trading Assistant Pro - Dashboard")
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
        """)

        layout_principale = QVBoxLayout()

        # --- HEADER ---
        header = QFrame()
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #ddd; padding: 10px; border-radius: 8px;")
        layout_h = QHBoxLayout(header)
        
        self.btn_aggiungi = QPushButton("\u2795 Importa CSV")
        self.btn_aggiungi.clicked.connect(self.importa_files)
        
        self.check_usa_filtro = QCheckBox("\u2705 ATTIVA FILTRO DATE")
        self.check_usa_filtro.toggled.connect(lambda: self.aggiorna_vista())

        self.date_inizio = QDateEdit()
        self.date_inizio.setCalendarPopup(True)
        self.date_inizio.setDisplayFormat("dd/MM/yyyy")
        self.date_inizio.setFixedWidth(120)
        self.date_inizio.setDate(QDate.currentDate().addYears(-1))
        self.date_inizio.dateChanged.connect(lambda: self.aggiorna_vista())

        self.date_fine = QDateEdit()
        self.date_fine.setCalendarPopup(True)
        self.date_fine.setDisplayFormat("dd/MM/yyyy")
        self.date_fine.setFixedWidth(120)
        self.date_fine.setDate(QDate.currentDate())
        self.date_fine.dateChanged.connect(lambda: self.aggiorna_vista())

        self.combo_token = QComboBox()
        self.combo_token.setMinimumWidth(150)
        self.combo_token.currentIndexChanged.connect(lambda: self.aggiorna_vista())

        self.btn_valuta = QPushButton(f"\ud83d\udcb1 Valuta: {self.valuta}")
        self.btn_valuta.clicked.connect(self.toggle_valuta)

        # --- Selettore Nazione per Tasse ---
        self.combo_nazione = QComboBox()
        self.combo_nazione.setMinimumWidth(120)
        self.combo_nazione.addItems(self.tax_rules_manager.list_countries())
        self.combo_nazione.currentIndexChanged.connect(self.on_nazione_changed)

        layout_h.addWidget(QLabel("<b>Asset:</b>"))
        layout_h.addWidget(self.combo_token)
        layout_h.addSpacing(20)
        layout_h.addWidget(self.check_usa_filtro)
        layout_h.addWidget(QLabel("Da:"))
        layout_h.addWidget(self.date_inizio)
        layout_h.addWidget(QLabel("A:"))
        layout_h.addWidget(self.date_fine)
        layout_h.addSpacing(20)
        layout_h.addWidget(QLabel("<b>Nazione:</b>"))
        layout_h.addWidget(self.combo_nazione)
        layout_h.addStretch()
        layout_h.addWidget(self.btn_valuta)
        layout_h.addWidget(self.btn_aggiungi)
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

        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.chart_layout.addWidget(self.canvas)
        
        self.stack_visualizzazione.addWidget(self.chart_view)
        
        layout_corpo.addWidget(self.stack_visualizzazione, stretch=1)

        # Sidebar
        sidebar_widget = QFrame()
        sidebar_widget.setFixedWidth(350)
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
        
        layout_tasse.addWidget(QLabel("Anno:"))
        layout_tasse.addWidget(self.combo_anno_tasse)
        layout_tasse.addWidget(btn_calcola_tasse)
        layout_tasse.addWidget(self.label_tasse_risultato)
        self.group_tasse.setLayout(layout_tasse)
        sidebar.addWidget(self.group_tasse)

        sidebar.addStretch()
        layout_corpo.addWidget(sidebar_widget)
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

        self.setLayout(layout_principale)

    # --- Methods ---
    
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
        
        country_name = self.combo_nazione.currentText()
        year = int(self.combo_anno_tasse.currentText())
        
        try:
            # Calculate taxes
            tax_summary = self.tax_calculator.get_tax_summary(self.df_master, year)
            
            # Format the result
            result_text = f"""
            <b>Calcolo Tasse per {tax_summary['country']} ({tax_summary['year']})</b><br><br>
            <b>Plusvalenze:</b> €{tax_summary['capital_gain']:,.2f}<br>
            <b>Imposta su Plusvalenze ({tax_summary['rule']['capital_gain_rate']}):</b> €{tax_summary['capital_gain_tax']:,.2f}<br>
            <b>Imposta di Bollo:</b> €{tax_summary['stamp_duty']:,.2f}<br>
            <b>Totale Tasse:</b> <span style='color: #dc3545; font-weight: bold;'>€{tax_summary['total_tax']:,.2f}</span><br><br>
            """
            
            if tax_summary['declaration_required']:
                result_text += "⚠️ <b>Dichiarazione RW obbligatoria</b> (portafoglio > €{:,.2f}).<br>".format(
                    tax_summary['rule']['declaration_threshold']
                )
            
            if tax_summary['notes']:
                result_text += "<br><b>Note:</b><br>" + "<br>".join(tax_summary['notes'])
            
            self.label_tasse_risultato.setText(result_text)
            
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nel calcolo delle tasse: {e}")
            self.label_tasse_risultato.setText("Errore nel calcolo delle tasse.")

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

    def aggiorna_menu_token(self):
        """Update the token dropdown menu."""
        tokens = self.database.get_tokens()
        self.combo_token.clear()
        self.combo_token.addItem("Generale")
        self.combo_token.addItems(tokens)
        self.get_all_live_prices()

    def get_all_live_prices(self):
        """Fetch live prices for all tokens."""
        if self.df_master is None or self.df_master.empty:
            return
        
        tokens = self.df_master['Token'].unique().tolist()
        
        try:
            # Get live prices from CoinMarketCap
            self.prezzi_live = self.cmc_api.get_live_prices(tokens, convert="USD")
            
            # Update live exchange rate
            if self.valuta == "EUR":
                self.tasso_cambio_live = self.currency_converter.live_rate
                self.currency_converter.set_live_rate(self.tasso_cambio_live)
            
            self.aggiorna_vista()
        except Exception as e:
            print(f"Errore API CMC: {e}")

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
        df_lavoro['Date (UTC+1:00)'] = pd.to_datetime(df_lavoro['Date (UTC+1:00)'], dayfirst=True, errors='coerce')
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
            values, labels, colors, invested = calculate_portfolio_allocation(
                df_filtrato, self.prezzi_live, self.tasso_cambio_live, self.valuta
            )

            tot_investito = sum(invested)
            tot_valore = sum(values)

            self.label_total_netto.setText(f"{tot_valore:,.2f} {simb}")
            self.dati_correnti['investito'] = tot_investito
            self.dati_correnti['qta'] = 0
            self.dati_correnti['pmc'] = 0

            # Update pie chart
            self.figure.clear()
            ax = self.figure.add_axes([0.4, 0.0, 0.6, 1.0])

            if values and sum(values) > 0:
                wedges, texts = ax.pie(values, startangle=90, colors=colors, wedgeprops=dict(width=0.45))
                legend_labels = []
                total = sum(values)
                for i, l in enumerate(labels):
                    val = values[i]
                    perc = (val / total) * 100
                    legend_labels.append(f"{l}: {perc:.1f}% ({val:,.0f}{simb})")
                ax.legend(wedges, legend_labels, title="Asset", loc="center left", 
                         bbox_to_anchor=(-0.6, 0.5), fontsize=10, frameon=False)
            else:
                ax.text(0.5, 0.5, "Dati insufficienti", ha='center', va='center')
                ax.set_axis_off()

            self.canvas.draw()
            self.aggiorna_performance_globale(tot_investito, tot_valore, simb)

        # --- MODALITÀ SINGOLA MONETA ---
        else:
            self.stack_visualizzazione.setCurrentWidget(self.tabella)
            self.group_strat.setVisible(True)
            df_t = df_filtrato[df_filtrato['Token'] == selection]

            self.tabella.setRowCount(0)
            investito_singolo = 0

            for _, row in df_t.iterrows():
                r = self.tabella.rowCount()
                self.tabella.insertRow(r)
                
                orig_curr = str(row.get('Original Currency', 'EUR'))
                factor = 1.0
                
                if self.valuta == "EUR" and orig_curr == "USD":
                    factor = self.get_historical_rate(row['Date (UTC+1:00)'])
                
                prezzo_storico = row['Price'] * factor
                val_tot_storico = row['Amount'] * prezzo_storico
                
                if str(row['Type']).lower() == 'buy':
                    investito_singolo += val_tot_storico + (row['Fee'] * factor)

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
                self.tasso_cambio_live, self.valuta
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
