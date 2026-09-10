"""
PDF Generator Module for CryptoAssistant
Handles generating fiscal reports in PDF format.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Larghezza dell'area stampabile in un A4 con i margini di default di fpdf2 (10 mm).
CONTENT_W = 190

_CHAR_MAP = {
    "–": "-", "—": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", " ": " ",
}


def _pdf_safe(text) -> str:
    """Rende una stringa compatibile col font core latin-1 di fpdf2.

    Sostituisce i caratteri fuori latin-1 piu' comuni (euro, trattini lunghi,
    virgolette curve, puntini di sospensione) e rimpiazza gli altri con '?'
    invece di eliminarli, cosi' le parole non vengono troncate.
    """
    s = str(text)
    for src, dst in _CHAR_MAP.items():
        s = s.replace(src, dst)
    s = s.replace("€", "EUR ")
    return s.encode('latin-1', 'replace').decode('latin-1')


def _fit(pdf: FPDF, text: str, width: float) -> str:
    """Accorcia `text` con '...' finche' non rientra in `width` mm alla larghezza
    corrente del font (evita che il testo sbordi dalle celle a larghezza fissa)."""
    text = _pdf_safe(text)
    if pdf.get_string_width(text) <= width - 2:
        return text
    ell = "..."
    while text and pdf.get_string_width(text + ell) > width - 2:
        text = text[:-1]
    return text + ell if text else ell


def _line(pdf: FPDF, text: str, h: float = 6, bold: bool = False, size: int = 10) -> None:
    """Riga di testo a piena larghezza che va sempre a capo correttamente.

    Riporta sempre X al margine sinistro prima di scrivere: `multi_cell`
    consecutive in fpdf2 lasciano il cursore a destra e la chiamata successiva
    stampa fuori pagina troncando la riga."""
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, _pdf_safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


class FiscalReportGenerator:
    """
    Generates fiscal reports in PDF format for cryptocurrency transactions.
    """

    def __init__(self, live_prices: Dict[str, float], exchange_rate: float, currency: str = "EUR"):
        """
        Initialize the generator.
        
        Args:
            live_prices (Dict[str, float]): Current prices for each token.
            exchange_rate (float): Exchange rate (USD to EUR if currency is EUR).
            currency (str): Target currency (EUR or USD).
        """
        self.live_prices = live_prices
        self.exchange_rate = exchange_rate
        self.currency = currency
        self.valuta_pdf = "EUR" if currency == "EUR" else "USD"
        self.mult = exchange_rate if currency == "EUR" else 1.0
    
    def generate_report(
        self,
        df: pd.DataFrame,
        output_path: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> bool:
        """
        Generate a fiscal report PDF.
        
        Args:
            df (pd.DataFrame): DataFrame with transactions.
            output_path (str): Path to save the PDF.
            start_date (Optional[datetime]): Start date for filtering.
            end_date (Optional[datetime]): End date for filtering.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            pdf = FPDF()
            
            # Normalizza le date (possono arrivare come datetime.date o datetime.datetime)
            start_d = start_date.date() if hasattr(start_date, "hour") else start_date
            end_d = end_date.date() if hasattr(end_date, "hour") else end_date

            # Filter data if dates are provided
            if start_d and end_d:
                mask_periodo = (df['Date (UTC+1:00)'].dt.date >= start_d) & \
                               (df['Date (UTC+1:00)'].dt.date <= end_d)
                df_filtered = df.loc[mask_periodo]
                mask_precedente = df['Date (UTC+1:00)'].dt.date < start_d
                df_precedente = df.loc[mask_precedente]
                periodo_str = f"{start_d.strftime('%d/%m/%Y')} - {end_d.strftime('%d/%m/%Y')}"
            else:
                df_filtered = df
                df_precedente = df.iloc[0:0]
                periodo_str = "Storico Completo"

            if df_filtered.empty:
                return False

            # Group by token
            for token in sorted(df_filtered['Token'].unique()):
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(190, 10, f"ESTRATTO CONTO: {token}", ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.cell(190, 8, f"Periodo: {periodo_str}", ln=True)
                pdf.ln(5)

                # Saldo iniziale (movimenti antecedenti al periodo selezionato)
                prec = df_precedente[df_precedente['Token'] == token]
                qta_iniziale = prec[prec['Type'] == 'buy']['Amount'].sum() - \
                               prec[prec['Type'] == 'sell']['Amount'].sum()
                investito_iniziale = 0.0
                for _, prow in prec[prec['Type'] == 'buy'].iterrows():
                    factor_p = 1.0
                    orig_p = str(prow.get('Original Currency', 'EUR'))
                    if self.currency == "EUR" and orig_p == "USD":
                        factor_p = self.exchange_rate
                    investito_iniziale += prow['Amount'] * prow['Price'] * factor_p + prow['Fee'] * factor_p

                if not prec.empty:
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(190, 7,
                        f"Saldo iniziale (ante {periodo_str.split(' - ')[0]}): "
                        f"Qta {qta_iniziale:,.6f} | Investito {investito_iniziale:,.2f} {self.valuta_pdf}",
                        ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.ln(2)

                # Table header
                pdf.set_font("Arial", "B", 8)
                pdf.cell(25, 8, "Data", 1)
                pdf.cell(15, 8, "Tipo", 1)
                pdf.cell(30, 8, "Qta", 1)
                pdf.cell(30, 8, f"Prezzo", 1)
                pdf.cell(30, 8, f"Totale ({self.valuta_pdf})", 1)
                pdf.cell(60, 8, "Note", 1, ln=True)

                # Table rows
                pdf.set_font("Arial", "", 8)
                sub = df_filtered[df_filtered['Token'] == token]

                investito_f = investito_iniziale

                for _, row in sub.iterrows():
                    try:
                        d_str = row['Date (UTC+1:00)'].strftime('%d/%m/%Y')
                    except:
                        d_str = str(row['Date (UTC+1:00)'])
                    
                    # Calculate converted price
                    factor = 1.0
                    orig = str(row.get('Original Currency', 'EUR'))
                    if self.currency == "EUR" and orig == "USD":
                        # Use historical rate (simplified here)
                        factor = self.exchange_rate  # In full app, use get_rate_for_date
                    
                    price_hist = row['Price'] * factor
                    val_tot_riga = row['Amount'] * price_hist
                    
                    if str(row['Type']).lower() == 'buy':
                        investito_f += val_tot_riga + (row['Fee'] * factor)
                    
                    # Write row
                    pdf.cell(25, 7, d_str, 1)
                    pdf.cell(15, 7, str(row['Type'])[:4], 1)
                    pdf.cell(30, 7, f"{row['Amount']:.6f}", 1)
                    pdf.cell(30, 7, f"{price_hist:,.4f}", 1)
                    pdf.cell(30, 7, f"{val_tot_riga:,.2f}", 1)
                    
                    # Note: accorciate con "..." se non stanno nella colonna
                    pdf.cell(60, 7, _fit(pdf, str(row.get('Notes', '')), 60), 1, ln=True)
                
                # Summary
                pdf.ln(10)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(190, 10, "RIEPILOGO FINALE", ln=True)
                pdf.set_font("Arial", "", 10)
                
                buys = sub[sub['Type'] == 'buy']
                qta_f = qta_iniziale + buys['Amount'].sum() - sub[sub['Type'] == 'sell']['Amount'].sum()
                val_f = qta_f * (self.live_prices.get(token, 0) * self.mult)
                perf_f = ((val_f / investito_f) - 1) * 100 if investito_f > 0 else 0
                
                pdf.cell(190, 7, 
                    f"Qta: {qta_f:,.6f} | Inv: {investito_f:,.2f} {self.valuta_pdf} | "
                    f"Val: {val_f:,.2f} {self.valuta_pdf} | Perf: {perf_f:+.2f}%", 
                    ln=True)
            
            # Save PDF
            pdf.output(output_path)
            return True
            
        except Exception as e:
            print(f"Errore generazione PDF: {e}")
            return False

    def generate_tax_report(self, tax_summary: Dict, output_path: str) -> bool:
        """
        Genera il PDF del calcolo tasse per l'anno e la nazione selezionati:
        Quadro RW (monitoraggio + imposta cripto-attivita 0,2%) e Quadro RT
        (plusvalenze/minusvalenze col metodo previsto dalla normativa, LIFO
        per l'Italia).

        Args:
            tax_summary (Dict): Risultato di TaxCalculator.get_tax_summary().
            output_path (str): Percorso di salvataggio del PDF.

        Returns:
            bool: True se generato con successo, False altrimenti.
        """
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(True, margin=15)
            pdf.add_page()

            def riga_tabella(valori, larghezze, h=7, header=False, align=None):
                """Una riga di tabella: ogni cella accorciata per stare nella
                sua colonna, l'ultima chiude la riga (ritorno a capo)."""
                pdf.set_font("Helvetica", "B" if header else "", 8)
                if pdf.get_y() > 275:
                    pdf.add_page()
                n = len(valori)
                for i, (v, w) in enumerate(zip(valori, larghezze)):
                    ultima = i == n - 1
                    pdf.cell(
                        w, h, _fit(pdf, v, w), border=1,
                        align=(align[i] if align else "L"),
                        new_x=(XPos.LMARGIN if ultima else XPos.RIGHT),
                        new_y=(YPos.NEXT if ultima else YPos.TOP),
                    )

            rule = tax_summary["rule"]
            _line(pdf, f"REPORT FISCALE {tax_summary['year']} - {tax_summary['country']}", h=10, bold=True, size=16)
            pdf.ln(2)

            _line(pdf, "RIEPILOGO", h=8, bold=True, size=12)
            _line(pdf, f"Plusvalenze totali: EUR {tax_summary['capital_gain']:,.2f}", h=6)
            _line(pdf, f"Aliquota applicata: {rule['capital_gain_rate']} (franchigia: {rule['capital_gain_threshold']})", h=6)
            _line(pdf, f"Imposta su plusvalenze: EUR {tax_summary['capital_gain_tax']:,.2f}", h=6)
            _line(pdf, f"Imposta di bollo: EUR {tax_summary['stamp_duty']:,.2f}", h=6)
            _line(pdf, f"TOTALE IMPOSTE DOVUTE: EUR {tax_summary['total_tax']:,.2f}", h=7, bold=True)

            if tax_summary["declaration_required"]:
                _line(pdf, f"Dichiarazione RW obbligatoria (soglia {rule['declaration_threshold']}).", h=6)

            if tax_summary["notes"]:
                pdf.ln(2)
                _line(pdf, "Note:", h=6, bold=True, size=11)
                for note in tax_summary["notes"]:
                    _line(pdf, f"- {note}", h=5, size=9)

            metodo = tax_summary.get("cost_basis_method", "FIFO")

            quadro_rw = tax_summary.get("quadro_rw", [])
            if quadro_rw:
                pdf.ln(4)
                _line(pdf, "QUADRO RW - MONITORAGGIO CRIPTO-ATTIVITA", h=8, bold=True, size=12)
                _line(pdf, "Valori in EUR. Imposta cripto-attivita 0,2% sul valore finale, pro-rata giorni.", h=5, size=9)
                pdf.ln(1)

                w_rw = [20, 30, 30, 30, 30, 16, 24]
                riga_tabella(
                    ["Token", "Qta iniziale", "Val. iniziale", "Qta finale", "Val. finale", "Giorni", "Imposta"],
                    w_rw, h=8, header=True,
                )
                for r in quadro_rw:
                    riga_tabella([
                        r["token"],
                        f"{r['quantita_iniziale']:.6f}",
                        f"{r['valore_iniziale']:,.2f}",
                        f"{r['quantita_finale']:.6f}",
                        f"{r['valore_finale']:,.2f}",
                        str(r["giorni_possesso"]),
                        f"{r['ivafe']:,.2f}",
                    ], w_rw)

                _line(pdf, f"Imposta cripto-attivita totale: EUR {tax_summary.get('imposta_cripto_totale', 0):,.2f}", h=7, bold=True, size=9)
                for r in quadro_rw:
                    if r.get("note"):
                        _line(pdf, f"- {r['token']}: {r['note']}", h=5, size=8)

            zero_rows = tax_summary.get("zero_price_rows", [])
            if zero_rows:
                pdf.ln(3)
                _line(pdf, "RIGHE DA VERIFICARE (acquisti senza prezzo)", h=6, bold=True)
                _line(pdf, "Reward/airdrop/cashback o trasferimenti non valorizzati: assegnare il "
                           "valore EUR alla ricezione (proventi) o il costo originario (trasferimenti).", h=5, size=8)
                for z in zero_rows:
                    _line(pdf, f"- {z['date']} {z['token']} {z['amount']:.6f} {z.get('notes', '')}".rstrip(), h=5, size=8)

            taxable_transactions = tax_summary.get("taxable_transactions", [])
            if taxable_transactions:
                pdf.ln(4)
                _line(pdf, f"QUADRO RT - DETTAGLIO PLUSVALENZE/MINUSVALENZE ({metodo})", h=8, bold=True, size=12)
                w_rt = [28, 26, 28, 34, 34, 32]
                riga_tabella(
                    ["Data", "Token", "Qta", "Pr. Acquisto", "Pr. Vendita", "Plusvalenza"],
                    w_rt, h=8, header=True,
                )
                for e in taxable_transactions:
                    riga_tabella([
                        str(e["date"]), str(e["token"]), f"{e['amount']:.6f}",
                        f"{e['buy_price']:,.4f}", f"{e['sell_price']:,.4f}", f"{e['gain']:,.2f}",
                    ], w_rt)

            all_transactions = tax_summary.get("all_transactions", [])
            if all_transactions:
                pdf.add_page()
                _line(pdf, "DETTAGLIO DI TUTTE LE COMPRAVENDITE DELL'ANNO", h=8, bold=True, size=12)
                _line(pdf, "Include acquisti, vendite e swap crypto/crypto (registrati come vendita + acquisto).", h=5, size=9)
                pdf.ln(1)

                w_all = [22, 16, 12, 24, 26, 24, 66]
                riga_tabella(
                    ["Data", "Token", "Tipo", "Qta", "Prezzo", f"Totale ({self.valuta_pdf})", "Note"],
                    w_all, h=8, header=True,
                )
                for tx in all_transactions:
                    riga_tabella([
                        str(tx["date"]), str(tx["token"]), str(tx["type"]),
                        f"{tx['amount']:.6f}", f"{tx['price']:,.4f}", f"{tx['total']:,.2f}",
                        str(tx.get("notes", "")),
                    ], w_all)

            pdf.output(output_path)
            return True

        except Exception as e:
            print(f"Errore generazione PDF fiscale: {e}")
            return False
