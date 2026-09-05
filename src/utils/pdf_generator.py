"""
PDF Generator Module for CryptoAssistant
Handles generating fiscal reports in PDF format.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from fpdf import FPDF


def _pdf_safe(text) -> str:
    """Rende una stringa compatibile col font core latin-1 di fpdf2 (niente €, emoji, ecc.)."""
    return str(text).encode('latin-1', 'replace').decode('latin-1').replace('?', '')


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
                    
                    # Handle notes (sanitize for PDF)
                    note_orig = str(row.get('Notes', ''))
                    note_safe = note_orig.encode('latin-1', 'replace').decode('latin-1').replace('?', '')
                    pdf.cell(60, 7, note_safe[:30], 1, ln=True)
                
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
        Genera il PDF del calcolo tasse per l'anno e la nazione selezionati,
        con il dettaglio delle plusvalenze imponibili (FIFO).

        Args:
            tax_summary (Dict): Risultato di TaxCalculator.get_tax_summary().
            output_path (str): Percorso di salvataggio del PDF.

        Returns:
            bool: True se generato con successo, False altrimenti.
        """
        try:
            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial", "B", 16)
            pdf.cell(190, 10, _pdf_safe(f"REPORT FISCALE {tax_summary['year']} - {tax_summary['country']}"), ln=True)
            pdf.ln(4)

            rule = tax_summary["rule"]
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, "RIEPILOGO", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.cell(190, 7, f"Plusvalenze totali: EUR {tax_summary['capital_gain']:,.2f}", ln=True)
            pdf.cell(190, 7, _pdf_safe(
                f"Aliquota applicata: {rule['capital_gain_rate']} (franchigia: {rule['capital_gain_threshold']})"
            ), ln=True)
            pdf.cell(190, 7, f"Imposta su plusvalenze: EUR {tax_summary['capital_gain_tax']:,.2f}", ln=True)
            pdf.cell(190, 7, f"Imposta di bollo: EUR {tax_summary['stamp_duty']:,.2f}", ln=True)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(190, 8, f"TOTALE IMPOSTE DOVUTE: EUR {tax_summary['total_tax']:,.2f}", ln=True)
            pdf.set_font("Arial", "", 10)

            if tax_summary["declaration_required"]:
                pdf.ln(2)
                pdf.cell(190, 7, _pdf_safe(
                    f"Dichiarazione RW obbligatoria (soglia {rule['declaration_threshold']})."
                ), ln=True)

            if tax_summary["notes"]:
                pdf.ln(4)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(190, 7, "Note:", ln=True)
                pdf.set_font("Arial", "", 9)
                for note in tax_summary["notes"]:
                    pdf.multi_cell(190, 6, _pdf_safe(f"- {note}"))

            taxable_transactions = tax_summary.get("taxable_transactions", [])
            if taxable_transactions:
                pdf.ln(6)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(190, 8, "DETTAGLIO PLUSVALENZE IMPONIBILI (FIFO)", ln=True)

                pdf.set_font("Arial", "B", 8)
                pdf.cell(25, 8, "Data", 1)
                pdf.cell(25, 8, "Token", 1)
                pdf.cell(25, 8, "Qta", 1)
                pdf.cell(30, 8, "Pr. Acquisto", 1)
                pdf.cell(30, 8, "Pr. Vendita", 1)
                pdf.cell(30, 8, "Plusvalenza", 1, ln=True)

                pdf.set_font("Arial", "", 8)
                for event in taxable_transactions:
                    if pdf.get_y() > 270:
                        pdf.add_page()
                    pdf.cell(25, 7, str(event["date"]), 1)
                    pdf.cell(25, 7, str(event["token"])[:10], 1)
                    pdf.cell(25, 7, f"{event['amount']:.6f}", 1)
                    pdf.cell(30, 7, f"{event['buy_price']:,.4f}", 1)
                    pdf.cell(30, 7, f"{event['sell_price']:,.4f}", 1)
                    pdf.cell(30, 7, f"{event['gain']:,.2f}", 1, ln=True)

            pdf.output(output_path)
            return True

        except Exception as e:
            print(f"Errore generazione PDF fiscale: {e}")
            return False
