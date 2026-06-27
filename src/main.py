import sys
import pandas as pd
import requests
import json
import os
import warnings
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, 
                             QComboBox, QFrame, QGroupBox, QGridLayout, QInputDialog, 
                             QDateEdit, QCheckBox, QStackedWidget, QProgressBar)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from fpdf import FPDF

# --- LIBRERIE PER IL GRAFICO ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- ZITTIAMO I WARNING ---
warnings.filterwarnings("ignore")

# --- WORKER PER SCARICARE I TASSI DI CAMBIO STORICI ---
class HistoricalRatesWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, start_date, end_date, base="USD", target="EUR"):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.base = base
        self.target = target

    def run(self):
        rates = {}
        try:
            # Usa l'API pubblica Frankfurter per lo storico
            start_str = self.start_date.strftime("%Y-%m-%d")
            end_str = self.end_date.strftime("%Y-%m-%d")
            url = f"https://api.frankfurter.app/{start_str}..{end_str}?from={self.base}&to={self.target}"
            res = requests.get(url).json()
            if 'rates' in res:
                for date_str, rate_dict in res['rates'].items():
                    rates[date_str] = rate_dict.get(self.target, 1.0)
        except Exception as e:
            print(f"Errore download storico cambi: {e}")
        self.finished.emit(rates)

class TradingTerminalExpert(QWidget):
    def __init__(self):
        super().__init__()
        self.CONFIG_FILE = "config.json"
        self.DB_FILE = "data_history.csv"
        self.CMC_API_KEY = self.carica_o_chiedi_api()
        
        # Default impostato su EURO
        self.valuta = "EUR" 
        self.tasso_cambio_live = 0.92 # Fallback live
        
        # Cache per i tassi storici (Data -> Cambio)
        self.tassi_storici = {} 

        self.df_master = self.carica_database_esistente()
        self.prezzi_live = {}
        self.dati_correnti = {'pmc': 0, 'qta': 0, 'costo_tot': 0, 'investito': 0}

        # --- DATABASE COLORI UFFICIALI ---
        self.coin_colors = {
            'BTC': '#F7931A', 'ETH': '#627EEA', 'USDT': '#26A17B', 'BNB': '#F3BA2F',
            'SOL': '#14F195', 'XRP': '#23292F', 'USDC': '#2775CA', 'ADA': '#0033AD',
            'AVAX': '#E84142', 'DOGE': '#C2A633', 'TRX': '#EF0027', 'LINK': '#2A5ADA',
            'DOT': '#E6007A', 'MATIC': '#8247E5', 'LTC': '#345D9D', 'SHIB': '#FFA409',
            'BCH': '#8DC351', 'ATOM': '#2E3148', 'XLM': '#14B6E7', 'XMR': '#FF6600',
            'ALGO': '#000000', 'UNI': '#FF007A', 'NEAR': '#000000', 'APT': '#000000',
            'FIL': '#0090FF', 'HBAR': '#3C454A', 'ICP': '#29ABE2', 'LDO': '#F07A55',
            'ARB': '#2D374B', 'VET': '#15BDFF', 'QNT': '#000000', 'MKR': '#1AAB9B',
            'TON': '#0098EA', 'VSN': '#131A26', 'NEXO': '#1E4DD8', 'ETC': '#34FA99'
        }
        
        self.fallback_colors = [
            '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', 
            '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', 
            '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', 
            '#000075', '#808080', '#000000'
        ]
        
        if self.CMC_API_KEY:
            self.initUI()
            if self.df_master is not None:
                self.aggiorna_menu_token()
                self.avvia_download_storico()

    def carica_o_chiedi_api(self):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f).get("api_key")
        key, ok = QInputDialog.getText(None, "Configurazione", "API Key CoinMarketCap:")
        if ok and key:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"api_key": key}, f)
            return key
        sys.exit()

    def carica_database_esistente(self):
        if os.path.exists(self.DB_FILE):
            try:
                df = pd.read_csv(self.DB_FILE)
                return self.pulisci_dataframe(df)
            except: return None
        return None

    def pulisci_dataframe(self, df):
        # --- FIX COMPATIBILITÀ COLONNE ---
        rename_map = {
            'Price (USD)': 'Price',
            'Total value (USD)': 'Total value'
        }
        df = df.rename(columns=rename_map)
        
        # Se manca Price, creala
        if 'Price' not in df.columns: df['Price'] = 0.0

        if 'Date (UTC+1:00)' in df.columns:
            df['Date (UTC+1:00)'] = pd.to_datetime(df['Date (UTC+1:00)'], dayfirst=True, errors='coerce')
        
        # --- DEFAULT VALUTA: EUR ---
        if 'Original Currency' not in df.columns:
            df['Original Currency'] = 'EUR' # Se non c'è scritto nulla, è EURO

        cols = ['Amount', 'Price', 'Fee']
        for col in cols:
            if col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.replace(',', '', regex=False) 
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                else:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df[col] = df[col].round(8)

        if 'Notes' not in df.columns: df['Notes'] = ""
        df['Notes'] = df['Notes'].fillna("").astype(str)

        # Auto-tagging Earn
        def auto_tag_zero_cost(row):
            if str(row.get('Type', '')).lower() == 'buy' and float(row.get('Price', 0)) == 0:
                current_note = str(row['Notes'])
                tag = "Earn/Staking/Airdrop"
                if tag not in current_note:
                    return (current_note + " " + tag).strip()
            return row['Notes']

        df['Notes'] = df.apply(auto_tag_zero_cost, axis=1)
        return df

    def salva_database(self):
        if self.df_master is not None:
            self.df_master.to_csv(self.DB_FILE, index=False)
            QMessageBox.information(self, "OK", "Database salvato correttamente!")

    def avvia_download_storico(self):
        if self.df_master is None or self.df_master.empty: return
        
        df_dates = self.df_master['Date (UTC+1:00)'].dropna()
        if df_dates.empty: return
        
        min_date = df_dates.min().date()
        max_date = datetime.now().date()
        
        self.progress_bar.setVisible(True)
        self.worker = HistoricalRatesWorker(min_date, max_date, base="USD", target="EUR")
        self.worker.finished.connect(self.salva_tassi_storici)
        self.worker.start()

    def salva_tassi_storici(self, rates):
        self.tassi_storici = rates
        self.progress_bar.setVisible(False)
        self.aggiorna_vista()

    def get_historical_rate(self, data_obj):
        """Restituisce il tasso di cambio per una data specifica"""
        if self.valuta == "USD": return 1.0 
        
        try:
            d_str = data_obj.strftime("%Y-%m-%d")
            if d_str in self.tassi_storici:
                return self.tassi_storici[d_str]
        except: pass
        
        return self.tasso_cambio_live

    def initUI(self):
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
        
        self.btn_aggiungi = QPushButton("➕ Importa CSV")
        self.btn_aggiungi.clicked.connect(self.importa_files)
        
        self.check_usa_filtro = QCheckBox("✅ ATTIVA FILTRO DATE")
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

        self.btn_valuta = QPushButton(f"💱 Valuta: {self.valuta}")
        self.btn_valuta.clicked.connect(self.toggle_valuta)

        layout_h.addWidget(QLabel("<b>Asset:</b>"))
        layout_h.addWidget(self.combo_token)
        layout_h.addSpacing(20)
        layout_h.addWidget(self.check_usa_filtro)
        layout_h.addWidget(QLabel("Da:"))
        layout_h.addWidget(self.date_inizio)
        layout_h.addWidget(QLabel("A:"))
        layout_h.addWidget(self.date_fine)
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
        self.tabella.setHorizontalHeaderLabels(["Data", "Tipo", "Quantità", "Prezzo Unit.", "Valore Tot.", "Note"])
        self.tabella.setAlternatingRowColors(True)
        self.tabella.setShowGrid(False)
        self.tabella.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabella.verticalHeader().setVisible(False)
        
        header_tab = self.tabella.horizontalHeader()
        for i in range(5): header_tab.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header_tab.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.stack_visualizzazione.addWidget(self.tabella)

        # 2. Vista Grafico
        self.chart_view = QFrame()
        self.chart_view.setStyleSheet("background-color: white; border-radius: 8px;")
        self.chart_layout = QVBoxLayout(self.chart_view)
        
        self.lbl_chart_title = QLabel("📊 ALLOCAZIONE PORTAFOGLIO")
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
        group_glob = QGroupBox("💰 PATRIMONIO ATTUALE")
        layout_g = QVBoxLayout()
        self.label_total_netto = QLabel("---")
        self.label_total_netto.setStyleSheet("font-size: 26px; font-weight: bold; color: #2c3e50;")
        layout_g.addWidget(self.label_total_netto)
        group_glob.setLayout(layout_g)
        sidebar.addWidget(group_glob)

        # 2. Dati Mercato
        group_price = QGroupBox("📊 DATI ASSET & MERCATO")
        layout_pr = QVBoxLayout()
        self.label_live_price = QLabel("---")
        self.label_live_price.setStyleSheet("font-size: 20px; color: #007bff; font-weight: bold;")
        self.label_qta_visibile = QLabel("Quantità: ---")
        self.label_qta_visibile.setStyleSheet("font-size: 16px; font-weight: bold; color: #28a745; margin-top: 5px;")
        self.label_pmc = QLabel("PMC: ---")
        self.label_pmc.setStyleSheet("font-size: 14px; color: #555; font-weight: bold; margin-bottom: 5px;")
        btn_refresh = QPushButton("🔄 Aggiorna Prezzi")
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
        self.group_strat = QGroupBox("🎯 STRATEGIA MEDIA")
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

        sidebar.addStretch()
        layout_corpo.addWidget(sidebar_widget)
        layout_principale.addLayout(layout_corpo)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_pdf = QPushButton("📄 Report Fiscale PDF")
        self.btn_pdf.clicked.connect(self.genera_pdf_fiscale)
        self.btn_pdf.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_salva = QPushButton("💾 Salva")
        self.btn_salva.clicked.connect(self.salva_database)
        self.btn_salva.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_esci = QPushButton("🚪 Esci")
        self.btn_esci.setStyleSheet("background-color: #6c757d; color: white; padding: 8px 20px;")
        self.btn_esci.clicked.connect(QApplication.instance().quit)
        footer.addWidget(self.btn_pdf)
        footer.addWidget(self.btn_salva)
        footer.addWidget(self.btn_esci)
        layout_principale.addLayout(footer)

        self.setLayout(layout_principale)

    def importa_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleziona CSV", "", "CSV Files (*.csv)")
        if not paths: return

        dfs = []
        for p in paths:
            try:
                try: df = pd.read_csv(p)
                except: df = pd.DataFrame()
                if df.empty or len(df.columns) <= 1: df = pd.read_csv(p, sep=';')
                df.columns = [c.strip() for c in df.columns]
                
                col_data = next((c for c in df.columns if any(x in c.upper() for x in ["DATE", "DATA", "TIME"])), None)
                col_token = next((c for c in df.columns if any(x in c.upper() for x in ["TOKEN", "COIN", "ASSET", "CURRENCY TICKER"])), None)
                col_type = next((c for c in df.columns if any(x in c.upper() for x in ["TYPE", "TIPO", "DIRECTION"])), None)
                col_amount = next((c for c in df.columns if any(x in c.upper() for x in ["AMOUNT", "QUANTIT", "QTA", "OPERATION AMOUNT"])), None)
                col_price = next((c for c in df.columns if any(x in c.upper() for x in ["PRICE", "PREZZO", "VALORE", "VALUE", "COUNTER VALUE"])), None)
                col_fee = next((c for c in df.columns if any(x in c.upper() for x in ["FEE", "COMMISSION"])), None)
                col_notes = next((c for c in df.columns if any(x in c.upper() for x in ["NOTE", "NOTES", "MEMO", "COMMENT"])), None)

                if col_data and col_amount:
                    rename_dict = {col_data: 'Date (UTC+1:00)', col_amount: 'Amount'}
                    if col_token: rename_dict[col_token] = 'Token'
                    if col_type: rename_dict[col_type] = 'Type'
                    if col_price: rename_dict[col_price] = 'Price' 
                    if col_fee: rename_dict[col_fee] = 'Fee'
                    if col_notes: rename_dict[col_notes] = 'Notes'
                    
                    # LOGICA RILEVAMENTO VALUTA (MODIFICATA)
                    detected_currency = 'EUR' # Default: EURO se non specificato
                    if col_price and 'USD' in col_price.upper(): 
                        detected_currency = 'USD' # Solo se esplicito USD
                    
                    df = df.rename(columns=rename_dict)
                    df['Original Currency'] = detected_currency
                    
                    if 'Token' not in df.columns: df['Token'] = os.path.basename(p).split('.')[0].upper()
                    if 'Price' not in df.columns: df['Price'] = 0
                    if 'Fee' not in df.columns: df['Fee'] = 0
                    if 'Notes' not in df.columns: df['Notes'] = ""

                    for col in ['Amount', 'Price', 'Fee']:
                        if col in df.columns:
                            val_str = df[col].astype(str).replace(['nan', 'None', ''], '0')
                            val_str = val_str.str.replace(',', '', regex=False)
                            df[col] = pd.to_numeric(val_str, errors='coerce').fillna(0)
                    
                    df['Notes'] = df['Notes'].fillna("").astype(str)

                    if 'Type' in df.columns:
                        df['Type'] = df['Type'].astype(str).str.lower()
                        df['Type'] = df['Type'].apply(lambda x: 'buy' if 'in' in x or 'buy' in x or 'receive' in x else ('sell' if 'out' in x or 'sell' in x or 'send' in x else 'unknown'))
                    else:
                        df['Type'] = df['Amount'].apply(lambda x: 'sell' if x < 0 else 'buy')
                        df['Amount'] = df['Amount'].abs()

                    cols_final = ['Date (UTC+1:00)', 'Token', 'Type', 'Amount', 'Price', 'Fee', 'Notes', 'Original Currency']
                    for c in cols_final: 
                        if c not in df.columns: df[c] = "" if c == 'Notes' else 0
                    
                    dfs.append(df[cols_final])
            except Exception as e: print(f"Errore {p}: {e}")

        if dfs:
            new_data = pd.concat(dfs)
            if self.df_master is not None and not self.df_master.empty:
                if 'Price (USD)' in self.df_master.columns:
                    self.df_master = self.df_master.rename(columns={'Price (USD)': 'Price'})
                
                for c in ['Amount', 'Price', 'Fee']:
                    if c in self.df_master.columns: self.df_master[c] = pd.to_numeric(self.df_master[c], errors='coerce').fillna(0)
                if 'Notes' not in self.df_master.columns: self.df_master['Notes'] = ""
                
                # Default a EUR anche per dati master precedenti se non settati
                if 'Original Currency' not in self.df_master.columns: self.df_master['Original Currency'] = "EUR"
                
                combined = pd.concat([self.df_master, new_data]).drop_duplicates(subset=['Date (UTC+1:00)', 'Token', 'Type', 'Amount', 'Notes'], keep='first')
                rows_added = len(combined) - len(self.df_master)
                self.df_master = combined
            else:
                self.df_master = new_data.drop_duplicates(subset=['Date (UTC+1:00)', 'Token', 'Type', 'Amount', 'Notes'])
                rows_added = len(self.df_master)

            if 'Date (UTC+1:00)' in self.df_master.columns:
                 self.df_master['Date (UTC+1:00)'] = pd.to_datetime(self.df_master['Date (UTC+1:00)'], dayfirst=True, errors='coerce')
                 self.df_master = self.df_master.sort_values(by='Date (UTC+1:00)', ascending=False)
            
            self.df_master = self.pulisci_dataframe(self.df_master)
            self.aggiorna_menu_token()
            self.avvia_download_storico() 
            QMessageBox.information(self, "Import", f"✅ Importazione completata! (+{rows_added})")
        else: QMessageBox.warning(self, "Import", "Nessun dato valido.")

    def aggiorna_menu_token(self):
        if self.df_master is None or self.df_master.empty: return
        tokens = sorted(self.df_master['Token'].astype(str).unique())
        self.combo_token.clear()
        self.combo_token.addItem("Generale")
        self.combo_token.addItems(tokens)
        self.get_all_live_prices()

    def get_all_live_prices(self):
        if self.df_master is None or self.df_master.empty: return
        tokens = self.df_master['Token'].unique().tolist()
        try:
            # 1. Prezzi Crypto (CoinMarketCap)
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {'X-CMC_PRO_API_KEY': self.CMC_API_KEY}
            res = requests.get(url, headers=headers, params={'symbol': ",".join(tokens), 'convert': 'USD'}).json()
            for t in tokens: 
                try: self.prezzi_live[t] = res['data'][t]['quote']['USD']['price']
                except: self.prezzi_live[t] = 0
            
            # 2. Tasso Cambio USD/EUR LIVE (Frankfurter)
            if self.valuta == "EUR":
                try:
                    res_f = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR").json()
                    self.tasso_cambio_live = res_f['rates']['EUR']
                except: 
                    self.tasso_cambio_live = 0.92 # Fallback
            
            self.aggiorna_vista()
        except: print("Errore API CMC")

    def aggiorna_vista(self):
        if self.df_master is None or self.df_master.empty: return
        selection = self.combo_token.currentText()
        
        simb = "€" if self.valuta == "EUR" else "$"
        mult_live = self.tasso_cambio_live if self.valuta == "EUR" else 1.0

        df_lavoro = self.df_master.copy()
        df_lavoro['Date (UTC+1:00)'] = pd.to_datetime(df_lavoro['Date (UTC+1:00)'], dayfirst=True, errors='coerce')
        df_lavoro = df_lavoro.dropna(subset=['Date (UTC+1:00)'])
        if pd.api.types.is_datetime64_any_dtype(df_lavoro['Date (UTC+1:00)']):
            if hasattr(df_lavoro['Date (UTC+1:00)'].dt, 'tz') and df_lavoro['Date (UTC+1:00)'].dt.tz is not None:
                df_lavoro['Date (UTC+1:00)'] = df_lavoro['Date (UTC+1:00)'].dt.tz_localize(None)
        
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

            tot_investito = 0
            tot_valore = 0
            dati_grafico = []
            labels_grafico = []
            colori_grafico = []
            
            fallback_idx = 0

            for t in df_filtrato['Token'].unique():
                sub = df_filtrato[df_filtrato['Token'] == t]
                buys = sub[sub['Type'] == 'buy']
                sells = sub[sub['Type'] == 'sell']
                
                qta = buys['Amount'].sum() - sells['Amount'].sum()
                if qta < 0: qta = 0
                
                spesa_asset = 0
                for _, row in buys.iterrows():
                    p = row['Price']
                    orig_curr = str(row.get('Original Currency', 'EUR')) # Default EUR qui
                    
                    if self.valuta == "EUR" and orig_curr == "USD":
                        rate = self.get_historical_rate(row['Date (UTC+1:00)'])
                        spesa_asset += (row['Amount'] * p * rate) + (row['Fee'] * rate)
                    else:
                        # Se è già EUR o altro, non converto
                        spesa_asset += (row['Amount'] * p) + row['Fee']

                valore_t = qta * self.prezzi_live.get(t, 0) * mult_live
                
                if qta > 0.000001:
                    tot_investito += spesa_asset
                    tot_valore += valore_t
                    if valore_t > 0:
                        dati_grafico.append(valore_t)
                        labels_grafico.append(t)
                        if t.upper() in self.coin_colors:
                            colori_grafico.append(self.coin_colors[t.upper()])
                        else:
                            color = self.fallback_colors[fallback_idx % len(self.fallback_colors)]
                            colori_grafico.append(color)
                            fallback_idx += 1

            self.label_total_netto.setText(f"{tot_valore:,.2f} {simb}")
            self.dati_correnti['investito'] = tot_investito
            self.dati_correnti['qta'] = 0 
            self.dati_correnti['pmc'] = 0 
            
            self.figure.clear()
            ax = self.figure.add_axes([0.4, 0.0, 0.6, 1.0])

            if dati_grafico and sum(dati_grafico) > 0:
                wedges, texts = ax.pie(dati_grafico, startangle=90, colors=colori_grafico, wedgeprops=dict(width=0.45))
                legend_labels = []
                total = sum(dati_grafico)
                for i, l in enumerate(labels_grafico):
                    val = dati_grafico[i]
                    perc = (val / total) * 100
                    legend_labels.append(f"{l}: {perc:.1f}% ({val:,.0f}{simb})")
                ax.legend(wedges, legend_labels, title="Asset", loc="center left", bbox_to_anchor=(-0.6, 0.5), fontsize=10, frameon=False)
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
                
                # Applica fattore di conversione SOLO se era USD e siamo in EUR
                if self.valuta == "EUR" and orig_curr == "USD":
                    factor = self.get_historical_rate(row['Date (UTC+1:00)'])
                
                prezzo_storico = row['Price'] * factor
                val_tot_storico = row['Amount'] * prezzo_storico
                
                if str(row['Type']).lower() == 'buy':
                    investito_singolo += val_tot_storico + (row['Fee'] * factor)

                try: data_fmt = row['Date (UTC+1:00)'].strftime("%d/%m/%Y")
                except: data_fmt = str(row['Date (UTC+1:00)'])
                
                item_data = QTableWidgetItem(data_fmt)
                item_type = QTableWidgetItem(str(row['Type']).upper())
                item_qta = QTableWidgetItem(f"{row['Amount']:.6f}")
                item_price = QTableWidgetItem(f"{prezzo_storico:,.4f} {simb}")
                item_val_tot = QTableWidgetItem(f"{val_tot_storico:,.2f} {simb}")
                
                note_text = str(row.get('Notes', ''))
                if note_text == "nan": note_text = ""
                item_note = QTableWidgetItem(note_text)
                
                for item in [item_data, item_type, item_qta, item_price, item_val_tot]: 
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_note.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                
                if 'buy' in str(row['Type']).lower():
                    item_type.setForeground(QColor("#28a745"))
                    item_type.setIcon(QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ArrowUp))
                else:
                    item_type.setForeground(QColor("#dc3545"))
                    item_type.setIcon(QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ArrowDown))

                self.tabella.setItem(r, 0, item_data)
                self.tabella.setItem(r, 1, item_type)
                self.tabella.setItem(r, 2, item_qta)
                self.tabella.setItem(r, 3, item_price)
                self.tabella.setItem(r, 4, item_val_tot) 
                self.tabella.setItem(r, 5, item_note)

            buys = df_t[df_t['Type'] == 'buy']
            sells = df_t[df_t['Type'] == 'sell']
            qta_tot = buys['Amount'].sum() - sells['Amount'].sum()
            
            qta_buys = buys['Amount'].sum()
            pmc = (investito_singolo / qta_buys) if qta_buys > 0 else 0
            
            self.dati_correnti['investito'] = investito_singolo
            self.dati_correnti['pmc'] = pmc
            self.dati_correnti['qta'] = qta_tot
            
            prezzo_mkt = self.prezzi_live.get(selection, 0) * mult_live
            self.label_live_price.setText(f"{prezzo_mkt:,.4f} {simb}")
            self.label_pmc.setText(f"PMC: {pmc:,.4f} {simb}")
            self.label_qta_visibile.setText(f"Quantità: {qta_tot:,.6f}")
            valore_oggi = qta_tot * prezzo_mkt
            self.label_total_netto.setText(f"{valore_oggi:,.2f} {simb}")

            self.aggiorna_performance_globale(investito_singolo, valore_oggi, simb)

    def aggiorna_performance_globale(self, investito, valore_attuale, simb):
        self.label_invest_perf.setText(f"{investito:,.2f} {simb}")
        self.label_val_att_perf.setText(f"{valore_attuale:,.2f} {simb}")
        if investito > 0:
            perc = ((valore_attuale / investito) - 1) * 100
            diff = valore_attuale - investito
            colore = "#28a745" if perc >= 0 else "#dc3545"
            bg = "#e8f5e9" if perc >= 0 else "#ffebee"
            self.label_titolo_perf.setText(f"PERFORMANCE ({perc:+.2f}%  {diff:+,.2f} {simb})")
            self.label_titolo_perf.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {colore};")
            self.group_perf.setStyleSheet(f"QGroupBox {{ background-color: {bg}; border: 2px solid {colore}; border-radius: 10px; }}")
        else:
            self.label_titolo_perf.setText("PERFORMANCE (N/A)")
            self.group_perf.setStyleSheet("")

    def calcola_target(self):
        try:
            target = float(self.input_target.text().replace(',', '.'))
            simb = "€" if self.valuta == "EUR" else "$"
            mkt = self.prezzi_live.get(self.combo_token.currentText(), 0) * (self.tasso_cambio_live if self.valuta == "EUR" else 1.0)
            q_c, p_c = self.dati_correnti['qta'], self.dati_correnti['pmc']
            
            if mkt == target:
                self.label_ris.setText("Il prezzo è già al target.")
                return
            
            q_n = (q_c * (target - p_c)) / (mkt - target)
            
            if q_n > 0: 
                spesa = q_n * mkt
                self.label_ris.setText(f"🎯 Acquista <b>{q_n:,.4f}</b> unità.<br>Spesa: <b>{spesa:,.2f} {simb}</b>")
            else: 
                self.label_ris.setText("❌ Target non raggiungibile.")
        except: self.label_ris.setText("Errore calcolo.")

    def toggle_valuta(self):
        self.valuta = "EUR" if self.valuta == "USD" else "USD"
        self.btn_valuta.setText(f"💱 Valuta: {self.valuta}")
        self.get_all_live_prices()

    def genera_pdf_fiscale(self):
        df_temp = self.df_master.copy()
        df_temp['Date (UTC+1:00)'] = pd.to_datetime(df_temp['Date (UTC+1:00)'], dayfirst=True, errors='coerce')
        if df_temp['Date (UTC+1:00)'].dt.tz is not None: df_temp['Date (UTC+1:00)'] = df_temp['Date (UTC+1:00)'].dt.tz_localize(None)
        
        if 'Notes' not in df_temp.columns: df_temp['Notes'] = ""
        df_temp['Notes'] = df_temp['Notes'].fillna("").astype(str)

        if self.check_usa_filtro.isChecked():
            d_inizio = self.date_inizio.date().toPyDate()
            d_fine = self.date_fine.date().toPyDate()
            mask = (df_temp['Date (UTC+1:00)'].dt.date >= d_inizio) & (df_temp['Date (UTC+1:00)'].dt.date <= d_fine)
            df_f = df_temp.loc[mask]
            periodo_str = f"{d_inizio.strftime('%d/%m/%Y')} - {d_fine.strftime('%d/%m/%Y')}"
        else:
            df_f = self.df_master
            periodo_str = "Storico Completo"

        if df_f is None or df_f.empty:
            QMessageBox.warning(self, "PDF", "Nessun dato.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Salva Report", "Report_Fiscale.pdf", "PDF (*.pdf)")
        if not path: return
        
        pdf = FPDF()
        valuta_pdf = "EUR" if self.valuta == "EUR" else "USD"
        mult_live = self.tasso_cambio_live if self.valuta == "EUR" else 1.0
        
        for t in sorted(df_f['Token'].unique()):
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(190, 10, f"ESTRATTO CONTO: {t}", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.cell(190, 8, f"Periodo: {periodo_str}", ln=True)
            pdf.ln(5)
            
            pdf.set_font("Arial", "B", 8)
            pdf.cell(25, 8, "Data", 1); 
            pdf.cell(15, 8, "Tipo", 1); 
            pdf.cell(30, 8, "Qta", 1);       
            pdf.cell(30, 8, f"Prezzo", 1)
            pdf.cell(30, 8, f"Totale ({valuta_pdf})", 1) 
            pdf.cell(60, 8, "Note", 1, ln=True)
            
            pdf.set_font("Arial", "", 8)
            sub = df_f[df_f['Token'] == t]
            
            investito_f = 0
            
            for _, r in sub.iterrows():
                try: d_str = r['Date (UTC+1:00)'].strftime('%d/%m/%Y')
                except: d_str = str(r['Date (UTC+1:00)'])
                
                factor = 1.0
                orig = str(r.get('Original Currency', 'EUR'))
                if self.valuta == "EUR" and orig == "USD":
                     factor = self.get_historical_rate(r['Date (UTC+1:00)'])
                
                price_hist = r['Price'] * factor
                val_tot_riga = r['Amount'] * price_hist
                if str(r['Type']).lower() == 'buy': investito_f += val_tot_riga + (r['Fee'] * factor)

                pdf.cell(25, 7, d_str, 1)
                pdf.cell(15, 7, r['Type'][:4], 1)
                pdf.cell(30, 7, f"{r['Amount']:.6f}", 1)
                pdf.cell(30, 7, f"{price_hist:,.4f}", 1)
                pdf.cell(30, 7, f"{val_tot_riga:,.2f}", 1) 
                
                note_orig = str(r.get('Notes', ''))
                note_safe = note_orig.encode('latin-1', 'replace').decode('latin-1').replace('?', '')
                pdf.cell(60, 7, note_safe[:30], 1, ln=True)

            pdf.ln(10); pdf.set_font("Arial", "B", 12); pdf.cell(190, 10, "RIEPILOGO FINALE", ln=True)
            pdf.set_font("Arial", "", 10)
            buys = sub[sub['Type'] == 'buy']
            qta_f = buys['Amount'].sum() - sub[sub['Type'] == 'sell']['Amount'].sum()
            
            val_f = qta_f * (self.prezzi_live.get(t, 0) * mult_live)
            perf_f = ((val_f / investito_f) - 1) * 100 if investito_f > 0 else 0
            
            pdf.cell(190, 7, f"Qta: {qta_f:,.6f} | Inv: {investito_f:,.2f} {valuta_pdf} | Val: {val_f:,.2f} {valuta_pdf} | Perf: {perf_f:+.2f}%", ln=True)
        
        try:
            pdf.output(path)
            QMessageBox.information(self, "PDF", "Report Fiscale Generato!")
        except Exception as e:
            QMessageBox.critical(self, "Errore PDF", f"Errore salvataggio: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = TradingTerminalExpert()
    win.showMaximized()
    sys.exit(app.exec())