# Calcolo P&L del portafoglio – logica CoinMarketCap

Specifica del motore di calcolo del "P/L stile CoinMarketCap" mostrato nella
dashboard (riquadro *Performance* e *Riepilogo asset*). Da NON confondere con il
modulo fiscale (`utils/tax_calculator.py`), che per l'Italia usa il **LIFO**
obbligatorio ed è un calcolo distinto.

---

## Obiettivo Tecnico
Replicare l'esatta logica utilizzata da CoinMarketCap (CMC) per il Portfolio Tracker.

## Metodo Contabile Fondamentale
CMC **non** usa FIFO o LIFO; utilizza il **Costo Medio Ponderato (Weighted Average
Cost)** globale, comprensivo delle commissioni (fee).

## 1. Parametri tracciati per transazione / asset
- **Acquisti (B):** Quantità (Qb), Prezzo unitario (Pb), Commissioni di acquisto (Fee_b).
- **Vendite (S):** Quantità (Qs), Prezzo unitario (Ps), Commissioni di vendita (Fee_s).
- **Trasferimenti (In/Out):** Quantità trasferita, Prezzo di mercato al momento del trasferimento.
- **Prezzo di Mercato Attuale (P_market):** Aggiornato in tempo reale.

## 2. Formule di Calcolo

**A. Cost Basis Totale (cumulativo, non ridotto dalle vendite)**

    Cost Basis = Σ(Qb × Pb) + Σ Fee_b

**B. Average Buy Cost (costo medio unitario, fee incluse)**

    Avg Buy Cost = Cost Basis / Σ Qb

**C. Realized Profit**

    Realized Profit = Σ[ (Qs × Ps) − (Qs × Avg Buy Cost) − Fee_s ]

**D. Unrealized Profit** (sulla quantità residua Q_held)

    Unrealized Profit = Q_held × (P_market − Avg Buy Cost)
    Q_held = Σ Qb − Σ Qs ± Transfers

**E. All-Time Profit**

    All-Time Profit = Realized Profit + Unrealized Profit

**F. P&L %** (sul capitale totale impegnato)

    P&L % = All-Time Profit / Cost Basis × 100

## 3. Gestione Trasferimenti (In / Out)
- **Transfer In:** non genera profitto realizzato; aumenta Q_held.
- **Transfer Out:** riduce Q_held (Unrealized → 0 se l'asset si azzera) ma **non**
  modifica il Realized Profit già consolidato.

## 4. Caso di Validazione (test unitario)

Input:
1. Buy 1: 1,0 BTC, riga 10.000 + 50 fee
2. Buy 2: 0,5 BTC, riga 6.000 + 30 fee  (prezzo unitario 12.000)
3. Sell 1: 0,75 BTC, incasso 12.000 (prezzo unitario 16.000) + 60 fee
4. P_market = 18.000 / BTC

Output attesi:
- Cost Basis = 10.000 + 6.000 + 50 + 30 = **16.080**
- Avg Buy Cost = 16.080 / 1,5 = **10.720 / BTC**
- Realized Profit = 12.000 − (0,75 × 10.720) − 60 = **3.900**
- Unrealized Profit = (0,75 × 18.000) − (0,75 × 10.720) = **5.460**
- All-Time Profit = **9.360**
- P&L % = 9.360 / 16.080 = **58,21 %**

Regressione: `tests/test_cmc_style.py::test_caso_di_validazione_ufficiale_cmc`.

## 5. Punti critici
1. **Fee separate:** Fee_b capitalizzate nel Cost Basis; Fee_s detratte dal margine realizzato.
2. **Divisione per zero:** gestire Σ Qb == 0 o posizione aperta solo da trasferimenti.
3. **WAC statico vs rolling:** CMC usa il WAC **statico** (Avg Buy Cost fisso, % sul Cost
   Basis cumulativo). La vecchia voce "PERFORMANCE" della dashboard usa invece un WAC
   *rolling* (costo base ridotto a ogni vendita, solo non realizzato): entrambe le
   letture restano visibili in dashboard.

---

## Implementazione in CryptoAssistant

| Elemento | Dove |
|---|---|
| Calcolo per token | `utils/calculations.py` → `calculate_cmc_style_stats()` |
| Aggregato portafoglio | `utils/calculations.py` → `calculate_portfolio_cmc_style()` |
| Visualizzazione | riquadro *Performance* e dialog *Riepilogo asset* in `gui/main_window.py` |
| Test | `tests/test_cmc_style.py` |

I CSV di alcuni wallet hanno prezzi inaffidabili (righe a 0 per reward/airdrop,
valori gonfiati/in USD). Menu **Impostazioni → "Ricalcola prezzi storici
transazioni"** (`utils/reprice.py`) riscarica il prezzo di mercato alla data di
ogni transazione via CoinMarketCap (fallback CoinGecko), riducendo lo scostamento
residuo dal portafoglio CMC.
