"""Test del generatore della Dichiarazione sostitutiva dell'atto di notorieta'."""

from docx import Document

from utils.dichiarazione import (
    Anagrafica, AssetRW, VenditaAsset, genera_dichiarazione_docx, dati_da_summary,
)


def _testo(path):
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _anagrafica():
    return Anagrafica(
        nome="MARTINI ENRICO", nato_a="Castelfranco Veneto (TV)", nato_il="31/10/1979",
        codice_fiscale="MRTNRC79R31C111I", residente_a="Loria (TV)", indirizzo="via Sile 21B",
        caf="Caf Veneto Srl - CAAF CGIL NORDEST", luogo="Castelfranco Veneto", data="05/09/2026",
    )


def test_genera_docx_con_le_sezioni_principali(tmp_path):
    assets = [
        AssetRW("Ethereum (ETH)", "chiavetta Ledger", 7953.82, 12310.26),
        AssetRW("Bitcoin (BTC)", "wallet Binance", 20736.77, 24502.09, solo_monitoraggio=True),
        AssetRW("Chainlink (LINK)", "", 0.0, 284.0, acquisto=("23/11/2025", 14.21, 213.73)),
        AssetRW("Crypto.com (CRO)", "wallet Crypto.com", 625.0, 2067.77, staking=True),
    ]
    vendite = [
        VenditaAsset(
            "Bitcoin (BTC)",
            vendite=[("25/03/2025", 0.04504483, 2936.0), ("05/12/2025", 0.068, 6668.0)],
            pmc=32146.29, controvalore_carico=17359.0,
            plusvalenze=[("25/03/2025", 1488.89), ("05/12/2025", 4482.13)],
        )
    ]
    out = tmp_path / "dich.docx"

    ok = genera_dichiarazione_docx(_anagrafica(), assets, vendite, 2025, str(out))
    txt = _testo(out)

    assert ok is True and out.exists()
    assert "DICHIARAZIONE SOSTITUTIVA" in txt
    assert "MARTINI ENRICO" in txt and "MRTNRC79R31C111I" in txt
    assert "DICHIARA ED ATTESTA" in txt
    assert "Ethereum (ETH)" in txt and "7.953,82" in txt and "12.310,26" in txt
    assert "solo ai fini del monitoraggio" in txt          # BTC bollo autoliquidato
    assert "Di aver acquistato criptoattivita' denominata Chainlink (LINK)" in txt
    assert "staking" in txt                                  # CRO
    assert "prezzo medio di carico di 32.146,29" in txt
    assert "plusvalenza imponibile pari a 1.488,89" in txt
    assert "esonerare" in txt and "CAAF CGIL NORDEST" in txt
    assert "Castelfranco Veneto, 05/09/2026" in txt


def test_franchigia_2000_solo_fino_al_2024(tmp_path):
    v = [VenditaAsset("Bitcoin (BTC)", [("10/06/2025", 1.0, 100.0)], 50.0, 50.0, [("10/06/2025", 50.0)])]
    out24 = tmp_path / "24.docx"
    out25 = tmp_path / "25.docx"
    genera_dichiarazione_docx(_anagrafica(), [], v, 2024, str(out24))
    genera_dichiarazione_docx(_anagrafica(), [], v, 2025, str(out25))

    assert "franchigia di 2000" in _testo(out24)
    assert "franchigia di 2000" not in _testo(out25)


def test_dati_da_summary_costruisce_le_strutture():
    summary = {
        "year": 2025,
        "cost_basis_method": "PMC",
        "quadro_rw": [
            {"token": "BTC", "quantita_iniziale": 0.5, "valore_iniziale": 20000.0,
             "quantita_finale": 0.5, "valore_finale": 25000.0, "giorni_possesso": 365,
             "quota": 1.0, "ivafe": 50.0, "note": ""},
        ],
        "taxable_transactions": [
            {"date": "25/03/2025", "token": "BTC", "amount": 0.05, "buy_price": 32000.0,
             "sell_price": 65000.0, "gain": 1650.0, "holding_days": 0},
        ],
        "all_transactions": [
            {"date": "25/03/2025", "token": "BTC", "type": "sell", "amount": 0.05,
             "price": 65000.0, "total": 3250.0, "notes": ""},
        ],
    }
    assets, vendite = dati_da_summary(summary, wallet_map={"BTC": "wallet Binance"})

    assert assets[0].denominazione.startswith("BTC") or "BTC" in assets[0].denominazione
    assert assets[0].wallet == "wallet Binance"
    assert assets[0].valore_iniziale == 20000.0
    assert vendite[0].denominazione.endswith("BTC") or "BTC" in vendite[0].denominazione
    assert vendite[0].plusvalenze[0][1] == 1650.0
    assert vendite[0].vendite[0][2] == 3250.0
