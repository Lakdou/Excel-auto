import io
import json
import sqlite3
import zipfile

import msoffcrypto
import pytest

from app.analyzer import workbook as wbmod
from app.analyzer import AnalysisError, analyze_bytes

from .conftest import openpyxl_bytes, xlsxwriter_bytes


def ids(report):
    return {f["id"] for f in report["findings"]}


# ----------------------------------------------------------- formats / erreurs


@pytest.mark.parametrize("name", ["rapport.csv", "rapport.pdf", "sans_extension"])
def test_unsupported_extension(name):
    with pytest.raises(AnalysisError, match="non prise en charge"):
        analyze_bytes(b"PK\x03\x04...", name)


def test_empty_file():
    with pytest.raises(AnalysisError, match="vide"):
        analyze_bytes(b"", "x.xlsx")


def test_html_disguised_as_xls():
    with pytest.raises(AnalysisError, match="HTML"):
        analyze_bytes(b"<html><table><tr><td>1</td></tr></table></html>", "export.xls")


def test_random_bytes():
    with pytest.raises(AnalysisError, match="pas un classeur Excel valide"):
        analyze_bytes(b"\x00\x01garbage" * 100, "x.xlsx")


def test_truncated_zip():
    data = openpyxl_bytes(lambda wb: None)
    with pytest.raises(AnalysisError):
        analyze_bytes(data[: len(data) // 2], "coupé.xlsx")


def test_zip_that_is_not_excel():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w/>")
    with pytest.raises(AnalysisError, match="autre type"):
        analyze_bytes(buf.getvalue(), "faux.xlsx")


def test_zip_bomb_is_rejected(monkeypatch):
    monkeypatch.setattr(wbmod, "MAX_UNCOMPRESSED_BYTES", 10_000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/bomb.xml", b"0" * 50_000)
    with pytest.raises(AnalysisError, match="trop volumineux"):
        analyze_bytes(buf.getvalue(), "bombe.xlsx")


def test_password_protected_file(simple_bytes):
    out = io.BytesIO()
    msoffcrypto.OfficeFile(io.BytesIO(simple_bytes)).encrypt("secret", out)
    with pytest.raises(AnalysisError, match="mot de passe"):
        analyze_bytes(out.getvalue(), "secret.xlsx")


def test_xlsx_renamed_as_xls_is_analyzed(simple_bytes):
    report = analyze_bytes(simple_bytes, "planning.xls")
    assert report["file"]["format"] == "xlsx"
    assert report["formulas"]["available"]


# ------------------------------------------------------------ fichier complexe


@pytest.fixture(scope="module")
def complex_report(complex_bytes):
    return analyze_bytes(complex_bytes, "suivi_achats_2019.xlsm")


def test_complex_report_is_json_serializable(complex_report):
    assert json.loads(json.dumps(complex_report))["file"]["name"] == "suivi_achats_2019.xlsm"


def test_complex_summary(complex_report):
    s = complex_report["summary"]
    assert complex_report["file"]["format"] == "xlsm"
    assert s["sheets"] == 5
    assert s["hidden_sheets"] == 2 and s["very_hidden_sheets"] == 1
    assert s["protected_sheets"] == 1
    assert s["charts"] == 1
    assert s["external_links"] == 1
    assert s["data_validations"] == 3
    assert s["vba_modules"] == 1
    # 60 lignes × 4 formules (fournisseur, TVA, TTC, livraison) + 5 × 4 (synthèse) + 3 isolées
    assert s["formulas"] == 60 * 4 + 20 + 3
    assert s["unique_formulas"] < 20


def test_complex_findings(complex_report):
    found = ids(complex_report)
    assert {"formula_errors", "external_links", "hardcoded", "volatile", "nesting", "mixed_columns",
            "broken_names", "very_hidden", "hidden", "protection"} <= found
    severities = [f["severity"] for f in complex_report["findings"]]
    assert severities == sorted(severities, key=["critical", "warning", "info"].index)
    hard = next(f for f in complex_report["findings"] if f["id"] == "hardcoded")
    assert all(e.startswith("Commandes!G") for e in hard["examples"])  # pas les n° de colonne RECHERCHEV


def test_complex_entities_and_relations(complex_report):
    by_name = {e["name"]: e for e in complex_report["entities"]}
    assert set(by_name) == {"Paramètres", "TFournisseurs", "Commandes", "Synthèse", "Archives"}
    assert by_name["TFournisseurs"]["source"] == "excel_table"
    assert by_name["Paramètres"]["range"] == "A1:B3"
    assert by_name["Synthèse"]["kind"] == "view"
    cmd = {c["name"]: c for c in by_name["Commandes"]["columns"]}
    assert by_name["Commandes"]["rows"] == 60
    assert by_name["Commandes"]["primary_key_candidate"] == "n_commande"
    assert cmd["Date"]["type"] == "date"
    assert cmd["Montant HT"]["type"] == "currency"
    assert cmd["Montant TTC"]["computed"]
    assert cmd["Statut"]["type"] == "enum"
    assert cmd["Validé par"]["type"] == "mixed"
    assert cmd["Livraison prévue"]["type"] == "date"
    assert cmd["Code fournisseur"]["references"] == {"entity": "tfournisseurs", "field": "code"}
    assert [r["label"] for r in complex_report["relations"]] == ["Commandes.Code fournisseur → TFournisseurs.Code"]


def test_complex_formulas(complex_report):
    f = complex_report["formulas"]
    top = {x["name"] for x in f["top_functions"]}
    assert {"VLOOKUP", "IFERROR", "SUMIFS", "COUNTIF", "TODAY", "INDIRECT"} <= top
    assert f["max_nesting_depth"] >= 5 and f["deepest_formula"] == "Synthèse!B10"
    assert {"from": "Commandes", "to": "Fournisseurs", "formulas": 60} in f["sheet_dependencies"]
    assert f["external_references"][0]["link"] == "[Budget_2018.xlsx]"
    assert f["computed_errors"] == 1 and f["computed_error_examples"] == ["Synthèse!B11"]
    assert "TauxTVA" not in f["defined_names_used"]  # dette : le nom existe mais n'est pas utilisé


def test_complex_names_and_validations(complex_report):
    names = {n["name"]: n for n in complex_report["names"]}
    assert names["AncienneZone"]["broken"]
    assert names["TauxTVA"]["refers_to"] == "Paramètres!$B$2"
    statut = next(v for v in complex_report["validations"] if v["range"] == "I2:I61")
    assert statut["choices"] == ["Brouillon", "En attente", "Validée", "Refusée"]


def test_complex_score_and_plan(complex_report):
    c = complex_report["complexity"]
    assert 20 <= c["score"] <= 70
    assert c["effort_days"]["low"] < c["effort_days"]["high"]
    assert sum(f["points"] for f in c["factors"]) == pytest.approx(c["score"], abs=1)
    steps = [s["step"] for s in complex_report["migration_plan"]]
    assert steps[:4] == ["Modèle de données", "Formulaires de saisie", "Règles de calcul", "Automatisations"]
    assert "Reprise des données" in steps


def test_complex_sql_is_executable(complex_report):
    sqlite3.connect(":memory:").executescript(complex_report["sql_schema"])


# -------------------------------------------------------- autres classeurs


def test_simple_file_is_simple(simple_bytes):
    report = analyze_bytes(simple_bytes, "planning_equipe.xlsx")
    assert report["complexity"]["level"] == "simple"
    assert not [f for f in report["findings"] if f["severity"] != "info"]
    entity = report["entities"][0]
    assert entity["primary_key_candidate"] == "matricule"
    assert {c["name"]: c["type"] for c in entity["columns"]}["Équipe"] == "enum"
    assert report["vba"]["present"] is False


def test_legacy_xls(legacy_bytes):
    report = analyze_bytes(legacy_bytes, "inventaire_2004.xls")
    assert report["file"]["format"] == "xls"
    assert report["formulas"]["available"] is False
    assert report["summary"]["hidden_sheets"] == 1
    assert "legacy_format" in ids(report)
    entity = report["entities"][0]
    assert entity["rows"] == 30
    types = {c["name"]: c["type"] for c in entity["columns"]}
    assert types == {"Référence": "text", "Désignation": "text", "Entrepôt": "enum", "Quantité": "integer",
                     "Prix unitaire": "decimal", "Dernier inventaire": "date"}
    assert report["limitations"]
    json.dumps(report)


def test_never_recalculated_file_is_reported():
    def build(wb):
        ws = wb.active
        ws.append(["a", "b"])
        ws.append([1, "=A2*2"])

    report = analyze_bytes(openpyxl_bytes(build), "openpyxl.xlsx")
    assert any("jamais été recalculé" in l for l in report["limitations"])


def test_empty_workbook():
    report = analyze_bytes(openpyxl_bytes(lambda wb: None), "vide.xlsx")
    assert report["summary"]["non_empty_cells"] == 0
    assert "no_table" in ids(report)
    assert report["sql_schema"] == ""
    assert report["complexity"]["score"] == 0


def test_cell_budget_truncates(monkeypatch, simple_bytes):
    monkeypatch.setattr(wbmod, "MAX_CELLS_SCANNED", 20)
    report = analyze_bytes(simple_bytes, "planning.xlsx")
    assert report["sheets"][0]["truncated"]
    assert any("partielle" in l for l in report["limitations"])


def test_chartsheet_and_activex_like_features():
    def build(wb):
        ws = wb.add_worksheet("Data")
        ws.write_column(0, 0, ["Mois", 1, 2, 3])
        cs = wb.add_chartsheet("Graphique")
        chart = wb.add_chart({"type": "line"})
        chart.add_series({"values": "=Data!$A$2:$A$4"})
        cs.set_chart(chart)

    report = analyze_bytes(xlsxwriter_bytes(build), "graph.xlsx")
    kinds = {s["name"]: s["kind"] for s in report["sheets"]}
    assert kinds == {"Data": "worksheet", "Graphique": "chartsheet"}
    assert report["summary"]["charts"] == 1


def test_auto_exec_and_risky_macros_are_findings(monkeypatch, simple_bytes):
    from app.analyzer import vba

    monkeypatch.setattr(vba, "extract_modules", lambda d, f: ([vba.VBAModule(
        "ThisWorkbook", 'Sub Workbook_Open()\n Shell "cmd"\nEnd Sub')], None))
    report = analyze_bytes(simple_bytes, "planning.xlsm")
    assert {"vba_auto", "vba_risky"} <= ids(report)
    assert report["findings"][0]["severity"] == "critical"


def test_excel_table_totals_row_is_not_data():
    def build(wb):
        ws = wb.add_worksheet("Ventes")
        ws.add_table("A1:B5", {
            "name": "TVentes",
            "data": [["a", 1], ["b", 2], ["c", 3]],
            "total_row": True,
            "columns": [{"header": "Produit", "total_string": "Total"},
                        {"header": "Qté", "total_function": "sum"}],
        })

    report = analyze_bytes(xlsxwriter_bytes(build), "ventes.xlsx")
    entity = report["entities"][0]
    assert entity["name"] == "TVentes" and entity["source"] == "excel_table"
    assert entity["rows"] == 3 and entity["range"] == "A1:B4"
    assert entity["primary_key_candidate"] == "produit"  # « Total » n'est pas une donnée
