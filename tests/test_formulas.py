import pytest

from app.analyzer.formulas import FormulaStats, analyze_formula, clean_function_name


def test_functions_are_extracted_and_prefixes_removed():
    info = analyze_formula("=IFERROR(_xlfn.XLOOKUP(A1,B:B,C:C),SUM(D1:D3))")
    assert info.functions == ["IFERROR", "XLOOKUP", "SUM"]
    assert info.depth == 2


@pytest.mark.parametrize("raw,expected", [("SUM(", "SUM"), ("_xlfn.CONCAT(", "CONCAT"), ("_xlws.FILTER(", "FILTER")])
def test_clean_function_name(raw, expected):
    assert clean_function_name(raw) == expected


def test_cross_sheet_references_with_quotes():
    info = analyze_formula("='Ma Feuille'!A1+Données!B2+'L''équipe'!C3")
    assert info.referenced_sheets == {"Ma Feuille", "Données", "L'équipe"}
    assert not info.external_refs


def test_external_references_are_detected():
    info = analyze_formula("=[1]Feuil1!B2+'[Budget 2018.xlsx]Budget'!$B$2")
    assert info.external_refs == {"[1]", "[Budget 2018.xlsx]"}
    # Une feuille d'un autre classeur n'est pas une dépendance interne.
    assert not info.referenced_sheets


def test_defined_names_and_structured_references():
    info = analyze_formula("=TauxTVA*Ventes[[#This Row],[Montant]]")
    assert info.defined_names == {"TauxTVA"}
    assert info.structured_refs == {"Ventes"}


def test_signature_is_position_independent_for_copied_formulas():
    a = analyze_formula("=A2*B2+$C$1", row=2, col=4)
    b = analyze_formula("=A3*B3+$C$1", row=3, col=4)
    c = analyze_formula("=A2*B2+$C$2", row=2, col=4)
    assert a.signature == b.signature
    assert a.signature != c.signature


def test_absolute_column_relative_row():
    a = analyze_formula("=$A2", row=2, col=2)
    b = analyze_formula("=$A9", row=9, col=5)
    assert a.signature == b.signature == "=R[0]C1"


@pytest.mark.parametrize(
    "formula,flagged",
    [
        ("=A1*0.2", True),
        ("=IF(A1>5000,\"Oui\",\"Non\")", True),
        ("=A1*-0.5", True),
        ("=VLOOKUP(A1,B:D,3,FALSE)", False),
        ("=ROUND(A1,2)", False),
        ("=A1*1", False),
        ("=A1/100", False),
        ("=LEFT(A1,3)", False),
    ],
)
def test_hardcoded_business_constants(formula, flagged):
    assert bool(analyze_formula(formula).hardcoded_numbers) is flagged


def test_error_literals():
    info = analyze_formula("=SUM(#REF!)+A1")
    assert "#REF!" in info.error_literals


def test_unparsable_formula_does_not_crash():
    info = analyze_formula('=SUM(A1,"non fermé')
    assert info.signature  # une signature de repli existe toujours


def test_cell_like_strings_in_text_are_not_rewritten():
    info = analyze_formula('="Réf A1"&B2', row=2, col=3)
    assert '"Réf A1"' in info.signature


def test_stats_aggregation():
    stats = FormulaStats()
    for r in range(2, 12):
        stats.add("Commandes", f"C{r}", f"=A{r}*B{r}", r, 3)
    stats.add("Synthèse", "B2", "=SUM(Commandes!C2:C11)", 2, 2)
    stats.add("Synthèse", "B3", "=TODAY()", 3, 2)
    stats.add("Synthèse", "B4", "=B2*0.2", 4, 2)
    d = stats.to_dict()
    assert d["total"] == 13
    assert d["unique"] == 4
    assert d["sheet_dependencies"] == [{"from": "Synthèse", "to": "Commandes", "formulas": 1}]
    assert d["volatile_formulas"] == 1 and d["volatile_examples"] == ["Synthèse!B3"]
    assert d["hardcoded_constants_formulas"] == 1
    assert d["per_sheet"] == {"Commandes": 10, "Synthèse": 3}


def test_same_formula_on_two_sheets_counts_twice():
    stats = FormulaStats()
    stats.add("A", "B2", "=A2*2", 2, 2)
    stats.add("B", "B2", "=A2*2", 2, 2)
    assert stats.unique_count == 2
