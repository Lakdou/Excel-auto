import datetime as dt
import sqlite3

import pytest

from app.analyzer.profiling import (
    CellData,
    TableRegion,
    build_sql,
    detect_header_row,
    detect_region,
    detect_relations,
    profile_column,
    profile_region,
    slugify,
)


def grid(rows):
    return [[c if isinstance(c, CellData) else CellData(c) for c in row] for row in rows]


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Montant TTC (€)", "montant_ttc"),
        ("N° commande", "n_commande"),
        ("Délai (jours)", "delai_jours"),
        ("2019", "c_2019"),
        ("   ", "colonne"),
        ("Order", "order_"),
        ("user", "user_"),
        ("x" * 100, "x" * 62),
    ],
)
def test_slugify(label, expected):
    assert slugify(label) == expected


def test_header_detection_skips_title_rows():
    g = grid([
        ["SUIVI DES ACHATS 2019", None, None],
        [None, None, None],
        ["Produit", "Quantité", "Prix"],
        ["A", 1, 2.5],
    ])
    assert detect_header_row(g) == 3


def test_header_needs_following_data():
    assert detect_header_row(grid([["A", "B"], [None, None]])) is None


def test_region_stops_at_two_blank_rows():
    g = grid([["Nom", "Âge"], ["a", 1], [None, None], ["b", 2], [None, None], [None, None], ["notes", "x"]])
    region = detect_region(g, "F", max_row=len(g))
    assert (region.header_row, region.last_row) == (1, 4)


def test_region_stops_at_section_title():
    g = grid([["Paramètre", "Valeur"], ["TVA", 0.2], [None, None], ["Services", None], ["Achats", None]])
    region = detect_region(g, "P", max_row=len(g))
    assert region.last_row == 2


def test_region_extends_to_sheet_end_when_grid_is_truncated():
    g = grid([["Nom", "Âge"]] + [["x", i] for i in range(10)])
    region = detect_region(g, "F", max_row=50_000)
    assert region.last_row == 50_000


def col(values, **kw):
    return [CellData(v, kw.get("formula", False), kw.get("fmt", "")) for v in values]


def test_profile_types():
    assert profile_column("n", col([1, 2, 3]), 0)["type"] == "integer"
    assert profile_column("n", col([1, 2.5, 3]), 0)["type"] == "decimal"
    assert profile_column("d", col([dt.datetime(2020, 1, 1)] * 2), 0)["type"] == "date"
    assert profile_column("d", col([dt.datetime(2020, 1, 1, 10, 30)] * 2), 0)["type"] == "datetime"
    assert profile_column("b", col([True, False, True]), 0)["type"] == "boolean"
    assert profile_column("m", col([1.5, 2], fmt="#,##0.00 €"), 0)["type"] == "currency"
    assert profile_column("p", col([0.1, 0.2], fmt="0.0%"), 0)["type"] == "percent"
    assert profile_column("e", col([None, None]), 0)["type"] == "empty"


def test_mixed_column_is_flagged():
    p = profile_column("Validé par", col(["M. Martin", 12, dt.datetime(2019, 3, 1), "ok", "DAF"]), 0)
    assert p["type"] == "mixed"
    assert p["type_consistency"] < 0.9


def test_enum_detection():
    values = ["Matin", "Soir", "Nuit"] * 4
    p = profile_column("Équipe", col(values), 0)
    assert p["type"] == "enum"
    assert p["choices"] == ["Matin", "Nuit", "Soir"]


def test_unique_text_is_not_enum():
    p = profile_column("Nom", col([f"nom {i}" for i in range(30)]), 0)
    assert p["type"] == "text" and p["unique"]


def test_errors_and_fill_rate():
    p = profile_column("x", col([1, None, "#N/A", 4]), 0)
    assert p["errors"] == 1
    assert p["fill_rate"] == 0.75
    assert p["type"] == "integer"


def test_computed_column():
    p = profile_column("TTC", col([1.2, 2.4], formula=True), 0)
    assert p["computed"]


def test_profile_region_primary_key_and_bounds():
    g = grid([["Code", "Nom"], ["A1", "x"], ["A2", "y"], [None, None], [None, None], ["parasite", "z"]])
    region = TableRegion("T", 1, 1, 2, 3, "detected")
    e = profile_region(g, region)
    assert e["rows"] == 2 and e["sampled_rows"] == 2
    assert e["primary_key_candidate"] == "code"
    assert e["kind"] == "table"


def test_duplicate_headers_get_unique_fields():
    g = grid([["Montant", "Montant"], [1, 2], [3, 4]])
    e = profile_region(g, TableRegion("T", 1, 1, 2, 3, "detected"))
    assert [c["field"] for c in e["columns"]] == ["montant", "montant_2"]


def test_report_like_table_is_a_view():
    g = grid([["Service", "Total"], ["A", CellData(10, True)], ["B", CellData(20, True)]])
    e = profile_region(g, TableRegion("Synthèse", 1, 1, 2, 3, "detected"))
    assert e["kind"] == "view"


def _entities():
    fourn = profile_region(
        grid([["Code", "Nom"], ["F1", "a"], ["F2", "b"], ["F3", "c"]]),
        TableRegion("Fournisseurs", 1, 1, 2, 4, "detected"),
    )
    cmd = profile_region(
        grid([["N°", "Fournisseur", "Statut", "Montant"],
              ["C1", "F1", "Validée", 10.5], ["C2", "F2", "Refusée", 20], ["C3", "F1", "Validée", 1],
              ["C4", "F1", "Refusée", 3]]),
        TableRegion("Commandes", 1, 1, 4, 5, "detected"),
    )
    return [fourn, cmd]


def test_relations_detected_and_private_values_removed():
    entities = _entities()
    rel = detect_relations(entities)
    assert [(r["from_field"], r["to_entity"]) for r in rel] == [("fournisseur", "fournisseurs")]
    assert all("_values" not in c for e in entities for c in e["columns"])


def test_relation_requires_subset():
    entities = _entities()
    entities[1]["columns"][1]["_values"].add("F99")
    assert detect_relations(entities) == []


def test_generated_sql_is_valid():
    entities = _entities()
    detect_relations(entities)
    entities.append(profile_region(
        grid([["Service", "Total"], ["A", CellData(10, True)], ["B", CellData(20, True)]]),
        TableRegion("Synthèse", 1, 1, 2, 3, "detected"),
    ))
    sql = build_sql(entities)
    assert "REFERENCES fournisseurs(code)" in sql
    assert "CHECK (statut IN ('Refusée', 'Validée'))" in sql
    assert "CREATE VIEW synthese" in sql  # en commentaire
    con = sqlite3.connect(":memory:")
    con.executescript(sql)  # SQLite accepte ces types : valide la syntaxe du script
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    assert tables == {"fournisseurs", "commandes"}


def test_sql_escapes_quotes_and_newlines():
    g = grid([["Avis\nclient", "Code"]] + [["l'avis", f"c{i}"] for i in range(3)] + [["bon", "c9"]] * 3)
    e = profile_region(g, TableRegion("T", 1, 1, 2, len(g), "detected"))
    sql = build_sql([e])
    sqlite3.connect(":memory:").executescript(sql)
    assert "'l''avis'" in sql
