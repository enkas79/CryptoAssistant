"""
Tax Rules Module for CryptoAssistant
Defines tax rules for different countries (Italy, France, Germany, etc.).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class TaxRule:
    """
    Represents tax rules for a specific country.
    """
    country: str
    country_code: str  # ISO 3166-1 alpha-2 (e.g., "IT" for Italy)
    capital_gain_rate: float  # e.g., 0.33 for Italy (33% from 2026)
    capital_gain_threshold: float  # Annual threshold for capital gains tax (EUR)
    stamp_duty: float  # Fixed stamp duty per transaction (EUR)
    stamp_duty_threshold: float  # Transaction value threshold for stamp duty (EUR)
    declaration_threshold: float  # Annual portfolio value threshold for declaration (EUR)
    holding_period_exemption: int  # Years to hold for exemption (0 = no exemption)
    tax_free_allowance: float  # Annual tax-free allowance (EUR)
    fifo_required: bool  # Whether FIFO method is required for cost basis
    notes: str = ""  # Additional notes (e.g., "Applies from 2026")


@dataclass
class TaxCalculationResult:
    """
    Result of tax calculation for a portfolio.
    """
    country: str
    year: int
    capital_gain: float  # Total capital gain (positive only)
    capital_gain_tax: float  # Tax on capital gains
    stamp_duty: float  # Total stamp duty
    total_tax: float  # capital_gain_tax + stamp_duty
    taxable_transactions: List[Dict]  # List of taxable transactions
    declaration_required: bool  # Whether declaration is required
    notes: List[str] = field(default_factory=list)  # Warnings or notes


class TaxRulesManager:
    """
    Manages tax rules for different countries.
    """
    
    # Default tax rules for supported countries
    DEFAULT_RULES: Dict[str, TaxRule] = {
        "IT": TaxRule(
            country="Italia",
            country_code="IT",
            capital_gain_rate=0.33,  # 33% from 2026
            capital_gain_threshold=51645.69,  # EUR 51.645,69 (annual threshold)
            stamp_duty=2.0,  # EUR 2 per transaction
            stamp_duty_threshold=5000.0,  # EUR 5.000
            declaration_threshold=15000.0,  # EUR 15.000 (annual portfolio value)
            holding_period_exemption=2,  # 2 years holding for exemption (if < threshold)
            tax_free_allowance=0.0,  # No tax-free allowance in Italy
            fifo_required=True,  # FIFO is required
            notes="Dal 2026, aliquota al 33% sulle plusvalenze. Soglia annuale: €51.645,69. Dichiarazione RW se portafoglio > €15.000."
        ),
        "FR": TaxRule(
            country="Francia",
            country_code="FR",
            capital_gain_rate=0.30,  # 30% flat tax (PFU - Prélèvement Forfaitaire Unique)
            capital_gain_threshold=0.0,  # No threshold
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=1,  # 1 year for long-term exemption
            tax_free_allowance=0.0,
            fifo_required=True,
            notes="Flat tax del 30% (PFU). Esenzione dopo 1 anno di detenzione per cessioni < €308."
        ),
        "DE": TaxRule(
            country="Germania",
            country_code="DE",
            capital_gain_rate=0.25,  # 25% + solidarity surcharge (5.5%)
            capital_gain_threshold=1000.0,  # EUR 1.000 annual allowance
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=1,  # 1 year for exemption
            tax_free_allowance=1000.0,  # EUR 1.000 annual allowance
            fifo_required=True,
            notes="Aliquota del 25% + 5,5% di solidarietà. Esenzione dopo 1 anno se < €1.000 annuali."
        ),
        "ES": TaxRule(
            country="Spagna",
            country_code="ES",
            capital_gain_rate=0.23,  # 19%-23% progressive (2024 rates)
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=0,  # No holding period exemption
            tax_free_allowance=0.0,
            fifo_required=True,
            notes="Aliquota progressiva: 19% (€0-€6.000), 21% (€6.001-€50.000), 23% (>€50.000)."
        ),
        "NL": TaxRule(
            country="Paesi Bassi",
            country_code="NL",
            capital_gain_rate=0.31,  # 31% capital gains tax
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=0,  # No holding period exemption
            tax_free_allowance=50000.0,  # EUR 50.000 tax-free allowance for crypto
            fifo_required=True,
            notes="Aliquota del 31% sulle plusvalenze. Esenzione annuale di €50.000 per crypto (2024)."
        ),
        "BE": TaxRule(
            country="Belgio",
            country_code="BE",
            capital_gain_rate=0.33,  # 33% capital gains tax
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=0,  # No holding period exemption
            tax_free_allowance=0.0,
            fifo_required=True,
            notes="Aliquota del 33% sulle plusvalenze. Tassazione solo se vendita > €50.000 annuali."
        ),
        "PT": TaxRule(
            country="Portogallo",
            country_code="PT",
            capital_gain_rate=0.28,  # 28% capital gains tax
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=1,  # 1 year for exemption
            tax_free_allowance=0.0,
            fifo_required=True,
            notes="Aliquota del 28% sulle plusvalenze. Esenzione dopo 1 anno di detenzione."
        ),
        "AT": TaxRule(
            country="Austria",
            country_code="AT",
            capital_gain_rate=0.275,  # 27.5% capital gains tax
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=1,  # 1 year for exemption
            tax_free_allowance=0.0,
            fifo_required=True,
            notes="Aliquota del 27,5% sulle plusvalenze. Esenzione dopo 1 anno di detenzione."
        ),
        "CH": TaxRule(
            country="Svizzera",
            country_code="CH",
            capital_gain_rate=0.0,  # No capital gains tax for private individuals
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=0,
            tax_free_allowance=0.0,
            fifo_required=False,
            notes="Nessuna tassa sulle plusvalenze per persone fisiche (tassazione solo per attività professionale)."
        ),
        "US": TaxRule(
            country="Stati Uniti",
            country_code="US",
            capital_gain_rate=0.20,  # 20% long-term capital gains (federal)
            capital_gain_threshold=0.0,
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=1,  # 1 year for long-term rate
            tax_free_allowance=0.0,
            fifo_required=True,
            notes="Aliquota federale: 0%-20% a seconda del reddito. Tassazione statale aggiuntiva possibile."
        ),
        "GB": TaxRule(
            country="Regno Unito",
            country_code="GB",
            capital_gain_rate=0.20,  # 20% capital gains tax (basic rate)
            capital_gain_threshold=3000.0,  # £3,000 annual exemption (2024-25)
            stamp_duty=0.0,
            stamp_duty_threshold=0.0,
            declaration_threshold=0.0,
            holding_period_exemption=0,
            tax_free_allowance=3000.0,  # £3,000 annual exemption
            fifo_required=True,
            notes="Aliquota: 10% (basic rate) o 20% (higher rate). Esenzione annuale di £3.000."
        ),
    }
    
    def __init__(self):
        """Initialize the tax rules manager."""
        self.rules: Dict[str, TaxRule] = self.DEFAULT_RULES.copy()
    
    def get_rule(self, country_code: str) -> Optional[TaxRule]:
        """
        Get tax rule for a country by its ISO code.
        
        Args:
            country_code (str): ISO 3166-1 alpha-2 country code (e.g., "IT").
        
        Returns:
            Optional[TaxRule]: Tax rule for the country, or None if not found.
        """
        return self.rules.get(country_code.upper())
    
    def get_country_by_name(self, country_name: str) -> Optional[TaxRule]:
        """
        Get tax rule for a country by its name.
        
        Args:
            country_name (str): Country name (e.g., "Italia").
        
        Returns:
            Optional[TaxRule]: Tax rule for the country, or None if not found.
        """
        for rule in self.rules.values():
            if rule.country.lower() == country_name.lower():
                return rule
        return None
    
    def get_all_rules(self) -> Dict[str, TaxRule]:
        """
        Get all available tax rules.
        
        Returns:
            Dict[str, TaxRule]: Dictionary of all tax rules, keyed by country code.
        """
        return self.rules.copy()
    
    def list_countries(self) -> List[str]:
        """
        Get a list of supported country names.
        
        Returns:
            List[str]: List of country names (e.g., ["Italia", "Francia"]).
        """
        return [rule.country for rule in self.rules.values()]
    
    def list_country_codes(self) -> List[str]:
        """
        Get a list of supported country codes.
        
        Returns:
            List[str]: List of ISO country codes (e.g., ["IT", "FR"]).
        """
        return list(self.rules.keys())
    
    def add_custom_rule(self, rule: TaxRule) -> None:
        """
        Add a custom tax rule for a country.
        
        Args:
            rule (TaxRule): Custom tax rule to add.
        """
        self.rules[rule.country_code.upper()] = rule
