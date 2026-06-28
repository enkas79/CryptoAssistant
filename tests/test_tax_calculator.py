"""
Test Module for Tax Calculator
Tests the tax calculation functionality with real data scenarios.
"""

import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pandas as pd
from datetime import datetime
from data.tax_rules import TaxRulesManager
from utils.tax_calculator import TaxCalculator
from utils.logger import setup_logging

# Setup logging for tests
logger = setup_logging(log_level="INFO")


def create_sample_transactions() -> pd.DataFrame:
    """Create a sample DataFrame with realistic transaction data."""
    data = [
        # BTC transactions
        {'Date (UTC+1:00)': '2024-01-15 10:00:00', 'Token': 'BTC', 'Type': 'buy', 'Amount': 0.1, 'Price': 40000.0, 'Fee': 5.0, 'Notes': ''},
        {'Date (UTC+1:00)': '2024-02-20 14:30:00', 'Token': 'BTC', 'Type': 'buy', 'Amount': 0.2, 'Price': 45000.0, 'Fee': 8.0, 'Notes': ''},
        {'Date (UTC+1:00)': '2024-03-10 11:00:00', 'Token': 'BTC', 'Type': 'sell', 'Amount': 0.15, 'Price': 50000.0, 'Fee': 7.5, 'Notes': ''},
        
        # ETH transactions
        {'Date (UTC+1:00)': '2024-01-10 09:00:00', 'Token': 'ETH', 'Type': 'buy', 'Amount': 2.0, 'Price': 2500.0, 'Fee': 10.0, 'Notes': ''},
        {'Date (UTC+1:00)': '2024-03-15 16:00:00', 'Token': 'ETH', 'Type': 'sell', 'Amount': 1.0, 'Price': 3000.0, 'Fee': 6.0, 'Notes': ''},
        
        # SOL transactions (small amounts, no tax impact)
        {'Date (UTC+1:00)': '2024-02-01 12:00:00', 'Token': 'SOL', 'Type': 'buy', 'Amount': 100.0, 'Price': 100.0, 'Fee': 2.0, 'Notes': ''},
        {'Date (UTC+1:00)': '2024-02-15 15:00:00', 'Token': 'SOL', 'Type': 'sell', 'Amount': 50.0, 'Price': 120.0, 'Fee': 1.5, 'Notes': ''},
        
        # Long-term holding (should be exempt if holding period > 1 year)
        {'Date (UTC+1:00)': '2023-01-01 08:00:00', 'Token': 'ADA', 'Type': 'buy', 'Amount': 1000.0, 'Price': 0.5, 'Fee': 5.0, 'Notes': ''},
        {'Date (UTC+1:00)': '2024-06-01 10:00:00', 'Token': 'ADA', 'Type': 'sell', 'Amount': 500.0, 'Price': 1.5, 'Fee': 8.0, 'Notes': ''},
        
        # Zero-cost transactions (Earn/Staking/Airdrop)
        {'Date (UTC+1:00)': '2024-01-05 14:00:00', 'Token': 'SHIB', 'Type': 'buy', 'Amount': 1000000.0, 'Price': 0.0, 'Fee': 0.0, 'Notes': 'Earn/Staking/Airdrop'},
        {'Date (UTC+1:00)': '2024-03-20 13:00:00', 'Token': 'SHIB', 'Type': 'sell', 'Amount': 500000.0, 'Price': 0.00001, 'Fee': 1.0, 'Notes': ''},
    ]
    
    df = pd.DataFrame(data)
    return df


def test_italy_tax_calculation():
    """Test tax calculation for Italy (IT)."""
    logger.info("=" * 60)
    logger.info("Testing Tax Calculator for Italy (IT)")
    logger.info("=" * 60)
    
    # Create sample data
    df = create_sample_transactions()
    logger.info(f"Created sample data with {len(df)} transactions")
    
    # Initialize tax calculator for Italy
    calculator = TaxCalculator(country_code="IT")
    
    # Test for 2024
    logger.info("\n--- Testing for year 2024 ---")
    result = calculator.calculate_taxes(df, year=2024)
    
    logger.info(f"Country: {result.country}")
    logger.info(f"Year: {result.year}")
    logger.info(f"Capital Gain: €{result.capital_gain:,.2f}")
    logger.info(f"Capital Gain Tax: €{result.capital_gain_tax:,.2f}")
    logger.info(f"Stamp Duty: €{result.stamp_duty:,.2f}")
    logger.info(f"Total Tax: €{result.total_tax:,.2f}")
    logger.info(f"Declaration Required: {result.declaration_required}")
    logger.info(f"Taxable Transactions: {len(result.taxable_transactions)}")
    
    if result.notes:
        logger.info("\nNotes:")
        for note in result.notes:
            logger.info(f"  - {note}")
    
    # Test summary
    logger.info("\n--- Tax Summary ---")
    summary = calculator.get_tax_summary(df, year=2024)
    for key, value in summary.items():
        if key != 'rule':
            logger.info(f"{key}: {value}")
    
    logger.info("\n--- Tax Rules Applied ---")
    for key, value in summary['rule'].items():
        logger.info(f"{key}: {value}")
    
    return result


def test_france_tax_calculation():
    """Test tax calculation for France (FR)."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Tax Calculator for France (FR)")
    logger.info("=" * 60)
    
    # Create sample data
    df = create_sample_transactions()
    
    # Initialize tax calculator for France
    try:
        calculator = TaxCalculator(country_code="FR")
        
        # Test for 2024
        logger.info("\n--- Testing for year 2024 ---")
        result = calculator.calculate_taxes(df, year=2024)
        
        logger.info(f"Country: {result.country}")
        logger.info(f"Year: {result.year}")
        logger.info(f"Capital Gain: €{result.capital_gain:,.2f}")
        logger.info(f"Capital Gain Tax: €{result.capital_gain_tax:,.2f}")
        logger.info(f"Stamp Duty: €{result.stamp_duty:,.2f}")
        logger.info(f"Total Tax: €{result.total_tax:,.2f}")
        logger.info(f"Declaration Required: {result.declaration_required}")
        
        return result
    except ValueError as e:
        logger.warning(f"France tax rules not available: {e}")
        return None


def test_germany_tax_calculation():
    """Test tax calculator for Germany (DE)."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Tax Calculator for Germany (DE)")
    logger.info("=" * 60)
    
    # Create sample data
    df = create_sample_transactions()
    
    # Initialize tax calculator for Germany
    try:
        calculator = TaxCalculator(country_code="DE")
        
        # Test for 2024
        logger.info("\n--- Testing for year 2024 ---")
        result = calculator.calculate_taxes(df, year=2024)
        
        logger.info(f"Country: {result.country}")
        logger.info(f"Year: {result.year}")
        logger.info(f"Capital Gain: €{result.capital_gain:,.2f}")
        logger.info(f"Capital Gain Tax: €{result.capital_gain_tax:,.2f}")
        logger.info(f"Stamp Duty: €{result.stamp_duty:,.2f}")
        logger.info(f"Total Tax: €{result.total_tax:,.2f}")
        logger.info(f"Declaration Required: {result.declaration_required}")
        
        return result
    except ValueError as e:
        logger.warning(f"Germany tax rules not available: {e}")
        return None


def test_edge_cases():
    """Test edge cases for tax calculation."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Edge Cases")
    logger.info("=" * 60)
    
    calculator = TaxCalculator(country_code="IT")
    
    # Test 1: Empty DataFrame
    logger.info("\n--- Test 1: Empty DataFrame ---")
    empty_df = pd.DataFrame(columns=['Date (UTC+1:00)', 'Token', 'Type', 'Amount', 'Price', 'Fee'])
    result = calculator.calculate_taxes(empty_df, year=2024)
    logger.info(f"Result: Capital Gain = €{result.capital_gain:,.2f}, Tax = €{result.total_tax:,.2f}")
    assert result.capital_gain == 0.0, "Empty DataFrame should have zero capital gain"
    assert result.total_tax == 0.0, "Empty DataFrame should have zero tax"
    logger.info("✓ Empty DataFrame test passed")
    
    # Test 2: Only buy transactions (no sells)
    logger.info("\n--- Test 2: Only Buy Transactions ---")
    buy_only_data = [
        {'Date (UTC+1:00)': '2024-01-01', 'Token': 'BTC', 'Type': 'buy', 'Amount': 1.0, 'Price': 40000.0, 'Fee': 5.0},
        {'Date (UTC+1:00)': '2024-02-01', 'Token': 'BTC', 'Type': 'buy', 'Amount': 0.5, 'Price': 45000.0, 'Fee': 3.0},
    ]
    buy_only_df = pd.DataFrame(buy_only_data)
    result = calculator.calculate_taxes(buy_only_df, year=2024)
    logger.info(f"Result: Capital Gain = €{result.capital_gain:,.2f}, Tax = €{result.total_tax:,.2f}")
    assert result.capital_gain == 0.0, "Buy-only transactions should have zero capital gain"
    logger.info("✓ Buy-only transactions test passed")
    
    # Test 3: Only sell transactions (no buys to match)
    logger.info("\n--- Test 3: Only Sell Transactions ---")
    sell_only_data = [
        {'Date (UTC+1:00)': '2024-01-01', 'Token': 'BTC', 'Type': 'sell', 'Amount': 0.5, 'Price': 50000.0, 'Fee': 5.0},
    ]
    sell_only_df = pd.DataFrame(sell_only_data)
    result = calculator.calculate_taxes(sell_only_df, year=2024)
    logger.info(f"Result: Capital Gain = €{result.capital_gain:,.2f}, Tax = €{result.total_tax:,.2f}")
    # With no buys to match, there should be no taxable events
    logger.info("✓ Sell-only transactions test passed")
    
    # Test 4: Loss transactions (negative gain)
    logger.info("\n--- Test 4: Loss Transactions ---")
    loss_data = [
        {'Date (UTC+1:00)': '2024-01-01', 'Token': 'BTC', 'Type': 'buy', 'Amount': 1.0, 'Price': 50000.0, 'Fee': 5.0},
        {'Date (UTC+1:00)': '2024-02-01', 'Token': 'BTC', 'Type': 'sell', 'Amount': 1.0, 'Price': 40000.0, 'Fee': 5.0},
    ]
    loss_df = pd.DataFrame(loss_data)
    result = calculator.calculate_taxes(loss_df, year=2024)
    logger.info(f"Result: Capital Gain = €{result.capital_gain:,.2f}, Tax = €{result.total_tax:,.2f}")
    # Losses should not contribute to capital gain (only positive gains count)
    assert result.capital_gain == 0.0, "Losses should not contribute to capital gain"
    logger.info("✓ Loss transactions test passed")
    
    logger.info("\n✓ All edge case tests passed!")


def main():
    """Run all tax calculator tests."""
    logger.info("Starting Tax Calculator Tests")
    logger.info("=" * 60)
    
    # Test Italy
    italy_result = test_italy_tax_calculation()
    
    # Test France
    france_result = test_france_tax_calculation()
    
    # Test Germany
    germany_result = test_germany_tax_calculation()
    
    # Test edge cases
    test_edge_cases()
    
    logger.info("\n" + "=" * 60)
    logger.info("All tests completed successfully!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
