"""
PDF Generator Module for CryptoAssistant
Handles generating fiscal reports in PDF format.
"""

import os
from datetime import datetime
from typing import Dict, List
import pandas as pd
from fpdf import FPDF


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
            
            # Filter data if dates are provided
            if start_date and end_date:
                mask = (df['Date (UTC+1:00)'].dt.date >= start_date.date()) & \
                       (df['Date (UTC+1:00)'].dt.date <= end_date.date())
                df_filtered = df.loc[mask]
                periodo_str = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
            else:
                df_filtered = df
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
                
                investito_f = 0.0
                
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
                qta_f = buys['Amount'].sum() - sub[sub['Type'] == 'sell']['Amount'].sum()
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
