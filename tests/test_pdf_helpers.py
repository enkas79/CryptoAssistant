"""Test degli helper di formattazione del PDF fiscale."""

from fpdf import FPDF

from utils.pdf_generator import _pdf_safe, _fit


def test_pdf_safe_sostituisce_e_non_elimina():
    assert _pdf_safe("Guadagno 10 EUR") == "Guadagno 10 EUR"
    assert _pdf_safe("Soglia €15.000,00") == "Soglia EUR 15.000,00"   # € prefisso -> "EUR "
    assert _pdf_safe("virgolette “curve”") == 'virgolette "curve"'
    # un carattere non mappato diventa '?', NON viene tolto (niente parole tagliate)
    assert "?" in _pdf_safe("emoji \U0001F600 fine")
    assert _pdf_safe("emoji \U0001F600 fine").endswith(" fine")


def test_fit_accorcia_con_ellissi_se_non_ci_sta():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 8)

    corto = "Vendita BTC"
    assert _fit(pdf, corto, 60) == corto

    lungo = "Vendita Injective e acquisto su Bitpanda tramite bonifico SEPA istantaneo"
    fitted = _fit(pdf, lungo, 40)
    assert fitted.endswith("...")
    assert pdf.get_string_width(fitted) <= 40
