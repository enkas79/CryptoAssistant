"""Test degli helper per il percorso di salvataggio predefinito."""

from utils.paths import default_save_path, remember_save_dir, ensure_ext


def test_ensure_ext_aggiunge_solo_se_manca():
    assert ensure_ext("C:/x/report", "pdf") == "C:/x/report.pdf"
    assert ensure_ext("C:/x/report.pdf", "pdf") == "C:/x/report.pdf"
    assert ensure_ext("C:/x/report.PDF", ".pdf") == "C:/x/report.PDF"
    assert ensure_ext("C:/x/doc.docx", "docx") == "C:/x/doc.docx"


def test_usa_la_cartella_ricordata_se_presente(tmp_path):
    cfg = {"last_save_dir": str(tmp_path)}
    p = default_save_path(cfg, "Report.pdf")
    assert p == str(tmp_path / "Report.pdf")


def test_ricorda_la_cartella_dal_file_scelto(tmp_path):
    cfg = {}
    f = tmp_path / "sub" / "Doc.docx"
    (tmp_path / "sub").mkdir()
    remember_save_dir(cfg, str(f))
    assert cfg["last_save_dir"] == str(tmp_path / "sub")


def test_fallback_su_download_quando_non_c_e_nulla(monkeypatch):
    # nessuna cartella ricordata e HOME finto
    import utils.paths as m
    monkeypatch.setattr(m.Path, "home", classmethod(lambda cls: m.Path("/home/tizio")))
    p = default_save_path({}, "X.pdf")
    assert p.replace("\\", "/").endswith("Downloads/X.pdf")
