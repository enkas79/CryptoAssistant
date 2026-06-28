"""
Test Module for Tax Rules
Tests the tax rules configuration without requiring pandas.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from data.tax_rules import TaxRulesManager, TaxRule
from utils.logger import setup_logging

# Setup logging for tests
logger = setup_logging(log_level="INFO")


def test_tax_rules_manager():
    """Test that tax rules are properly configured."""
    logger.info("=" * 60)
    logger.info("Testing Tax Rules Manager")
    logger.info("=" * 60)
    
    manager = TaxRulesManager()
    
    # Test Italy
    logger.info("\n--- Testing Italy (IT) rules ---")
    it_rule = manager.get_rule("IT")
    if it_rule:
        logger.info(f"Country: {it_rule.country}")
        logger.info(f"Country Code: {it_rule.country_code}")
        logger.info(f"Capital Gain Rate: {it_rule.capital_gain_rate * 100}%")
        logger.info(f"Capital Gain Threshold: €{it_rule.capital_gain_threshold:,.2f}")
        logger.info(f"Stamp Duty: €{it_rule.stamp_duty:,.2f}")
        logger.info(f"Stamp Duty Threshold: €{it_rule.stamp_duty_threshold:,.2f}")
        logger.info(f"Declaration Threshold: €{it_rule.declaration_threshold:,.2f}")
        logger.info(f"Holding Period Exemption: {it_rule.holding_period_exemption} years")
        logger.info(f"Tax Free Allowance: €{it_rule.tax_free_allowance:,.2f}")
        logger.info(f"FIFO Required: {it_rule.fifo_required}")
        
        # Validate Italy-specific rules
        assert it_rule.country_code == "IT", "Italy country code should be IT"
        assert it_rule.capital_gain_rate > 0, "Italy should have capital gain tax rate"
        assert it_rule.declaration_threshold == 15000, "Italy declaration threshold should be €15,000"
        logger.info("✓ Italy rules validation passed")
    else:
        logger.error("✗ Italy rules not found!")
        return False
    
    # Test France
    logger.info("\n--- Testing France (FR) rules ---")
    fr_rule = manager.get_rule("FR")
    if fr_rule:
        logger.info(f"Country: {fr_rule.country}")
        logger.info(f"Country Code: {fr_rule.country_code}")
        logger.info(f"Capital Gain Rate: {fr_rule.capital_gain_rate * 100}%")
        logger.info(f"Capital Gain Threshold: €{fr_rule.capital_gain_threshold:,.2f}")
        
        # Validate France-specific rules
        assert fr_rule.country_code == "FR", "France country code should be FR"
        logger.info("✓ France rules validation passed")
    else:
        logger.warning("France rules not found (this is expected if not implemented yet)")
    
    # Test Germany
    logger.info("\n--- Testing Germany (DE) rules ---")
    de_rule = manager.get_rule("DE")
    if de_rule:
        logger.info(f"Country: {de_rule.country}")
        logger.info(f"Country Code: {de_rule.country_code}")
        logger.info(f"Capital Gain Rate: {de_rule.capital_gain_rate * 100}%")
        
        # Validate Germany-specific rules
        assert de_rule.country_code == "DE", "Germany country code should be DE"
        logger.info("✓ Germany rules validation passed")
    else:
        logger.warning("Germany rules not found (this is expected if not implemented yet)")
    
    # Test all available rules
    logger.info("\n--- All Available Rules ---")
    all_rules = manager.get_all_rules()
    for code, rule in all_rules.items():
        logger.info(f"{code}: {rule.country} - Capital Gain Rate: {rule.capital_gain_rate * 100}%")
    
    logger.info(f"\nTotal rules available: {len(all_rules)}")
    logger.info("✓ Tax rules manager test completed")
    
    return True


def test_tax_calculator_rules():
    """Test that TaxCalculator rules are accessible without pandas."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing TaxCalculator Rules Access")
    logger.info("=" * 60)
    
    # We can't import TaxCalculator directly because it requires pandas
    # But we can test the rules through TaxRulesManager
    manager = TaxRulesManager()
    
    # Test that we can get rules for all supported countries
    countries = manager.list_country_codes()
    logger.info(f"\nSupported country codes: {countries}")
    
    for code in countries:
        rule = manager.get_rule(code)
        if rule:
            logger.info(f"  {code}: {rule.country} - Rate: {rule.capital_gain_rate * 100}%")
        else:
            logger.error(f"  {code}: Rule not found!")
            return False
    
    logger.info("\n✓ TaxCalculator rules access test passed")
    return True


def main():
    """Run all tax rules tests."""
    logger.info("Starting Tax Rules Tests")
    logger.info("=" * 60)
    
    success = True
    
    # Test tax rules manager
    if not test_tax_rules_manager():
        success = False
    
    # Test tax calculator rules
    if not test_tax_calculator_rules():
        success = False
    
    logger.info("\n" + "=" * 60)
    if success:
        logger.info("All tests completed successfully!")
    else:
        logger.error("Some tests failed!")
    logger.info("=" * 60)
    
    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
