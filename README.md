# CryptoAssistant

Un tool **open-source** per la gestione del portafoglio di criptovalute, con supporto per:
- Importazione e tracciamento transazioni (buy/sell).
- Monitoraggio prezzi live (via API CoinMarketCap).
- Calcolo performance, PMC (Prezzo Medio di Carico), e valore attuale del portafoglio.
- Generazione report fiscali in PDF (con supporto per la normativa italiana).
- Visualizzazione grafica (pie chart) dell'allocazione del portafoglio.
- Supporto multi-valuta (EUR/USD) con conversione automatica dei tassi storici.

---

## 📌 **Requisiti**
- Python **3.9+**
- API Key **CoinMarketCap** (gratuita per uso limitato: [registrati qui](https://coinmarketcap.com/api/))

---

## 🛠 **Installazione**

### 1. Clona il repository
```bash
git clone https://github.com/enkas79/CryptoAssistant.git
cd CryptoAssistant
```

### 2. Crea un ambiente virtuale (consigliato)
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OPPURE
venv\Scripts\activate   # Windows
```

### 3. Installa le dipendenze
```bash
pip install -r requirements.txt
```

---

## ⚙ **Configurazione**

### 1. API Key CoinMarketCap
1. Registrati su [CoinMarketCap Developer Portal](https://coinmarketcap.com/api/) e ottieni una API Key.
2. Crea il file `config/config.json` con il seguente contenuto:
   ```json
   {
       "api_key": "TUA_API_KEY_COINMARKETCAP"
   }
   ```

### 2. (Opzionale) Configurazione avanzata
Puoi personalizzare altre impostazioni in `config/config.json`:
```json
{
    "api_key": "TUA_API_KEY",
    "default_currency": "EUR",
    "data_file": "data/transactions.csv",
    "backup_dir": "data/backups"
}
```

---

## 🚀 **Uso**

### 1. Esegui l'applicazione
```bash
python src/main.py
```

### 2. Importa le tue transazioni
- Clicca su **"Importa CSV"** e seleziona i tuoi file CSV (es. da Binance, CoinMarketCap, ecc.).
- L'applicazione riconosce automaticamente le colonne (Data, Token, Tipo, Quantità, Prezzo, Fee, Note).

### 3. Visualizza il portafoglio
- Seleziona un **token** dal menu a tendina per vedere le transazioni.
- Passa alla vista **"Generale"** per vedere l'allocazione del portafoglio (pie chart).

### 4. Genera un report fiscale
- Clicca su **"Report Fiscale PDF"** per generare un file PDF con tutte le transazioni.
- Il report include:
  - Estratto conto per ogni token.
  - Riepilogo finale (quantità, investito, valore attuale, performance).

---

## 📂 **Struttura del Progetto**
```
CryptoAssistant/
├── README.md                  # Documentazione
├── requirements.txt           # Dipendenze Python
├── config/                    # File di configurazione
│   └── config.json            # API Key e impostazioni
├── docs/                      # Documentazione aggiuntiva
│   └── tax_laws/              # Regole fiscali (PDF)
│       └── EBOOK-BITCOIN-E-CRIPTO_2026.pdf
├── src/                       # Codice sorgente
│   ├── main.py                # Punto di ingresso
│   ├── gui/                   # Interfaccia grafica (PyQt6)
│   │   └── main_window.py     # Finestra principale
│   ├── api/                   # Chiamate alle API
│   │   ├── coinmarketcap.py    # API CoinMarketCap
│   │   └── frankfurter.py      # API Frankfurter (tassi di cambio)
│   ├── data/                  # Gestione dati
│   │   ├── models.py           # Modelli dati (Transaction, Portfolio)
│   │   ├── database.py         # Gestione database (CSV/SQLite)
│   │   └── importer.py         # Importazione CSV
│   ├── utils/                 # Funzioni di utilità
│   │   ├── calculations.py     # Calcoli (PMC, performance)
│   │   ├── currency.py         # Conversione valute
│   │   └── pdf.py              # Generazione PDF
│   └── tests/                 # Test automatici
│       ├── test_data.py        # Test importazione dati
│       └── test_api.py         # Test API
├── data/                      # Dati dell'utente
│   ├── transactions.csv       # Transazioni (default)
│   └── backups/               # Backup automatici
└── .gitignore                 # File ignorati da Git
```

---

## 📊 **Funzionalità**

| Funzionalità | Descrizione |
|--------------|-------------|
| **Importazione CSV** | Supporta formati CSV da exchange (Binance, CoinMarketCap, ecc.). |
| **Tracciamento Transazioni** | Gestisce buy/sell con quantità, prezzo, fee, e note. |
| **Prezzi Live** | Scarica i prezzi live da CoinMarketCap. |
| **Tassi di Cambio** | Scarica i tassi USD/EUR storici e live da Frankfurter. |
| **Calcolo PMC** | Calcola il Prezzo Medio di Carico per ogni token. |
| **Performance** | Calcola la performance (investito vs valore attuale). |
| **Target PMC** | Calcola la quantità da acquistare per raggiungere un target PMC. |
| **Report Fiscale** | Genera un PDF con tutte le transazioni (allineato alla normativa italiana). |
| **Multi-Valuta** | Supporto per EUR e USD con conversione automatica. |
| **Grafici** | Visualizzazione pie chart dell'allocazione del portafoglio. |

---

## 🌍 **Normativa Fiscale (Italia)**
- Le regole fiscali italiane per le criptovalute sono disponibili in `docs/tax_laws/`.
- Il report PDF generato è allineato con la normativa **2026** (vedi `EBOOK-BITCOIN-E-CRIPTO_2026.pdf`).

---

## 🤝 **Contribuire**
1. **Fork** il repository su GitHub.
2. Crea un **branch** per le tue modifiche:
   ```bash
   git checkout -b feature/nome-feature
   ```
3. Fai le tue modifiche e **commit**:
   ```bash
   git commit -m "Aggiunta nuova funzionalità"
   ```
4. **Push** sul tuo branch:
   ```bash
   git push origin feature/nome-feature
   ```
5. Apri un **Pull Request** su GitHub.

---

## 📜 **Licenza**
Questo progetto è **open-source** e distribuito sotto licenza **MIT**. Vedi il file `LICENSE` per i dettagli.

---

## 📞 **Contatti**
- **Autore**: [enkas79](https://github.com/enkas79)
- **Repository**: [CryptoAssistant](https://github.com/enkas79/CryptoAssistant)
