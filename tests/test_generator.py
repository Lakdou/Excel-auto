import datetime as dt

import pytest

from app.analyzer import AnalysisError
from app.generator.generate import build_application, values_equal

from .conftest import openpyxl_bytes, xlsxwriter_bytes


def fields_of(app, entity):
    es = next(e for e in app.spec["entities"] if e["name"] == entity)
    return {f["name"]: f for f in es["fields"]}


@pytest.fixture(scope="module")
def complex_app(complex_bytes):
    return build_application(complex_bytes, "suivi_achats_2019.xlsm")


def test_complex_entities_and_import(complex_app):
    spec = complex_app.spec
    assert [e["name"] for e in spec["entities"]] == ["parametres", "tfournisseurs", "commandes", "archives"]
    assert spec["generation"]["rows"] == 2 + 5 + 60 + 2
    assert len(complex_app.rows["commandes"]) == 60
    assert any("Synthèse" in w for w in spec["generation"]["warnings"])  # vue non générée, signalée


def test_complex_rules_all_verified(complex_app):
    assert complex_app.spec["generation"]["rules"] == {
        "verified": 4, "partial": 0, "volatile": 0, "unverified": 0, "unsupported": 0}
    f = fields_of(complex_app, "commandes")
    assert f["montant_ttc"]["rule"]["display"] == "[Montant HT] + [TVA]"
    assert f["fournisseur"]["rule"]["depends_on"]["entities"] == ["tfournisseurs"]
    assert f["livraison_prevue"]["rule"]["verification"] == {"checked": 60, "matches": 60, "examples": []}


def test_hardcoded_rate_becomes_parameter(complex_app):
    assert complex_app.spec["parameters"] == [{
        "name": "tva_valeur", "label": "Valeur fixe de « TVA »", "value": 0.2, "type": "decimal",
        "source": "valeur saisie dans la formule Excel"}]
    assert "tva_valeur" in fields_of(complex_app, "commandes")["tva"]["rule"]["depends_on"]["params"]


def test_complex_field_constraints(complex_app):
    f = fields_of(complex_app, "commandes")
    assert f["n_commande"]["unique"] and f["n_commande"]["required"]
    # Listes déroulantes Excel (dont une définie par un nom : =ListeServices) -> listes strictes
    assert f["service"]["strict_choices"] and f["service"]["choices"] == ["Achats", "Finance", "Informatique", "Logistique", "RH"]
    assert f["statut"]["choices"] == ["Brouillon", "En attente", "Validée", "Refusée"]
    assert f["code_fournisseur"]["references"] == {"entity": "tfournisseurs", "field": "code"}
    assert f["montant_ht"]["type"] == "currency" and f["date"]["type"] == "date"
    assert not f["tva"]["required"]  # calculé : jamais saisi
    assert "anomalies" not in f["valide_par"]  # type texte : tout est accepté


def _table_book(rows, formula, cached, extra=None):
    """Tableau Excel « Lignes » : Qté, PU, Total (formule fournie, avec valeurs en cache)."""
    def build(wb):
        ws = wb.add_worksheet("Lignes")
        ws.write_row(0, 0, ["Réf", "Qté", "PU", "Total"])
        for i, (q, pu) in enumerate(rows, start=1):
            ws.write_row(i, 0, [f"L{i}", q, pu])
            value = cached(i, q, pu)
            if value is None:
                ws.write_formula(i, 3, formula(i + 1))
            else:
                ws.write_formula(i, 3, formula(i + 1), None, value)
        ws.add_table(0, 0, len(rows), 3, {"name": "TLignes", "columns": [
            {"header": "Réf"}, {"header": "Qté"}, {"header": "PU"}, {"header": "Total"}]})
        if extra:
            extra(wb, ws)
    return xlsxwriter_bytes(build)


ROWS = [(2, 10.0), (3, 2.5), (1, 99.0), (4, 0.5)]


def test_structured_references():
    data = _table_book(ROWS, lambda n: "=TLignes[@Qté]*TLignes[@PU]", lambda i, q, pu: q * pu)
    app = build_application(data, "t.xlsx")
    rule = fields_of(app, "tlignes")["total"]["rule"]
    assert rule["status"] == "verified" and rule["display"] == "[Qté] * [PU]"


def test_cumulative_formula_is_not_converted_and_values_are_kept():
    def formula(n):
        return f"=B{n}" if n == 2 else f"=D{n - 1}+B{n}"
    totals = [2, 5, 6, 10]
    data = _table_book(ROWS, formula, lambda i, q, pu: totals[i - 1])
    app = build_application(data, "cumul.xlsx")
    rule = fields_of(app, "tlignes")["total"]["rule"]
    assert rule["status"] == "unsupported"
    assert [r["total"] for r in app.rows["tlignes"]] == totals  # données d'origine conservées


def test_stale_excel_cache_gives_partial_rule():
    def cached(i, q, pu):
        return 0 if i == 4 else q * pu  # une valeur périmée sur 4 lignes... (75 %) -> rejet
    app = build_application(_table_book(ROWS, lambda n: f"=B{n}*C{n}", cached), "p.xlsx")
    assert fields_of(app, "tlignes")["total"]["rule"]["status"] == "unsupported"

    rows = ROWS * 3  # 1 valeur périmée sur 12 lignes (92 %) -> règle partielle, écarts listés
    app = build_application(_table_book(rows, lambda n: f"=B{n}*C{n}",
                                        lambda i, q, pu: 0 if i == 4 else q * pu), "p2.xlsx")
    rule = fields_of(app, "tlignes")["total"]["rule"]
    assert rule["status"] == "partial"
    assert rule["verification"]["examples"] == [{"row": 5, "excel": 0, "app": 2.0}]
    assert app.rows["tlignes"][3]["total"] == 2.0  # l'application applique la règle


def test_volatile_rule():
    def extra(wb, ws):
        pass
    data = _table_book(ROWS, lambda n: f"=TODAY()-B{n}", lambda i, q, pu: 45000 - q, extra)
    app = build_application(data, "v.xlsx", today=dt.date(2024, 1, 1))
    rule = fields_of(app, "tlignes")["total"]["rule"]
    assert rule["status"] == "volatile"


def test_file_never_recalculated_is_unverified():
    def build(wb):
        ws = wb.active
        ws.title = "Data"
        ws.append(["Réf", "Qté", "PU", "Total"])
        for i, (q, pu) in enumerate(ROWS, start=2):
            ws.append([f"L{i}", q, pu, f"=B{i}*C{i}"])
    app = build_application(openpyxl_bytes(build), "o.xlsx")
    rule = fields_of(app, "data")["total"]["rule"]
    assert rule["status"] == "unverified"
    assert [r["total"] for r in app.rows["data"]] == [q * pu for q, pu in ROWS]  # calculé par l'application


def test_named_cell_becomes_labelled_parameter_and_constants_dedup():
    def build(wb):
        ws = wb.add_worksheet("Ventes")
        ws.write_row(0, 0, ["Réf", "HT", "TVA", "Remise"])
        for i in range(1, 4):
            ws.write_row(i, 0, [f"V{i}", 100 * i])
            ws.write_formula(i, 2, f"=B{i + 1}*TauxTVA", None, 100 * i * 0.2)
            ws.write_formula(i, 3, f"=IF(B{i + 1}>150,B{i + 1}*0.05,0)", None, 100 * i * 0.05 if 100 * i > 150 else 0)
        p = wb.add_worksheet("Réglages")
        p.write_row(0, 0, ["Taux TVA", 0.2])
        wb.define_name("TauxTVA", "=Réglages!$B$1")
    app = build_application(xlsxwriter_bytes(build), "n.xlsx")
    params = {p["name"]: p for p in app.spec["parameters"]}
    assert params["tauxtva"]["value"] == 0.2 and params["tauxtva"]["source"] == "Réglages!B1"
    assert {"remise_valeur", "remise_valeur_2"} <= set(params)  # seuil 150 et taux 5 %
    assert app.spec["generation"]["rules"]["verified"] == 2


def test_cell_parameter_labelled_by_neighbour():
    def build(wb):
        ws = wb.add_worksheet("Calcul")
        ws.write_row(0, 0, ["Réf", "Poids", "Coût"])
        for i in range(1, 4):
            ws.write_row(i, 0, [f"C{i}", i * 2])
            ws.write_formula(i, 2, f"=B{i + 1}*$G$1", None, i * 2 * 1.5)
        ws.write(0, 5, "Prix au kilo")
        ws.write(0, 6, 1.5)
    app = build_application(xlsxwriter_bytes(build), "c.xlsx")
    assert app.spec["parameters"][0]["label"] == "Prix au kilo"


def test_circular_dependency_is_rejected():
    def build(wb):
        ws = wb.add_worksheet("Boucle")
        ws.write_row(0, 0, ["Réf", "A", "B", "Saisie"])
        for i in range(1, 4):
            ws.write(i, 0, f"R{i}")
            ws.write_formula(i, 1, f"=C{i + 1}+1", None, 0)
            ws.write_formula(i, 2, f"=B{i + 1}+1", None, 0)
            ws.write(i, 3, i)
    app = build_application(xlsxwriter_bytes(build), "b.xlsx")
    f = fields_of(app, "boucle")
    assert f["a"]["rule"]["status"] == f["b"]["rule"]["status"] == "unsupported"
    assert "circulaire" in f["a"]["rule"]["reason"]


def test_type_anomalies_are_flagged_not_lost():
    def build(wb):
        ws = wb.active
        ws.title = "Stock"
        ws.append(["Article", "Quantité"])
        for i in range(1, 21):
            ws.append([f"A{i}", "n/a" if i == 7 else i])
    app = build_application(openpyxl_bytes(build), "s.xlsx")
    q = fields_of(app, "stock")["quantite"]
    assert q["type"] == "integer"
    assert q["anomalies"] == {"count": 1, "examples": [{"row": 8, "value": "n/a"}]}
    assert app.rows["stock"][6]["quantite"] == "n/a"


def test_legacy_xls_generates_data_only_app(legacy_bytes):
    app = build_application(legacy_bytes, "inventaire_2004.xls")
    f = fields_of(app, "inventaire")
    assert len(app.rows["inventaire"]) == 30
    assert f["dernier_inventaire"]["type"] == "date"
    assert isinstance(app.rows["inventaire"][0]["dernier_inventaire"], dt.datetime)
    assert not any("rule" in x for x in f.values())


def test_workbook_without_table_is_refused():
    with pytest.raises(AnalysisError, match="Aucun tableau"):
        build_application(openpyxl_bytes(lambda wb: wb.active.cell(1, 1, "Rapport")), "vide.xlsx")


def test_external_reference_rule_is_unsupported():
    def build(wb):
        ws = wb.add_worksheet("Budget")
        ws.write_row(0, 0, ["Poste", "Réel", "Écart"])
        for i in range(1, 4):
            ws.write_row(i, 0, [f"P{i}", 10 * i])
            ws.write_formula(i, 2, f"=B{i + 1}-'[Budget_2018.xlsx]Feuil1'!B{i + 1}", None, 0)
    app = build_application(xlsxwriter_bytes(build), "e.xlsx")
    rule = fields_of(app, "budget")["ecart"]["rule"]
    assert rule["status"] == "unsupported" and "autre fichier" in rule["reason"]


@pytest.mark.parametrize("a,b,equal", [
    (1, 1.0, True), (0.1 + 0.2, 0.3, True), (None, "", True), ("a", "A", False),
    (dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 1, 0, 0, 0, 500), True), (True, 1, False), (1, "1", False),
])
def test_values_equal(a, b, equal):
    assert values_equal(a, b) is equal
