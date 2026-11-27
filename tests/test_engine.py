import datetime as dt

import pytest

from app.generator.engine import (
    Context, EntityCol, FieldRef, ParamRef, Unsupported, dependencies, evaluate, from_json, parse, render, to_json,
)

FOURNISSEURS = [
    {"code": "F1", "nom": "Alpha", "delai": 10},
    {"code": "F2", "nom": "Beta", "delai": 3},
    {"code": "f3", "nom": "Gamma", "delai": 7},
]
COMMANDES = [
    {"ref": "A", "statut": "Validée", "montant": 100.0, "four": "F1"},
    {"ref": "B", "statut": "Refusée", "montant": 50.0, "four": "F2"},
    {"ref": "C", "statut": "validée", "montant": 25.0, "four": "F1"},
    {"ref": "D", "statut": None, "montant": None, "four": "F2"},
]
TABLES = {"four": FOURNISSEURS, "cmd": COMMANDES}


def resolver(text):
    """Résolveur de test : A..E = champs de la ligne, TAUX = paramètre, plages = tables."""
    mapping = {"A1": "a", "B1": "b", "C1": "c", "D1": "d", "E1": "e"}
    if text in mapping:
        return FieldRef(mapping[text])
    if text == "TAUX":
        return ParamRef("taux")
    if text == "Four!A:C":
        return EntityCol("four", ("code", "nom", "delai"))
    if text == "Four!A:A":
        return EntityCol("four", ("code",))
    if text == "Four!B:B":
        return EntityCol("four", ("nom",))
    if text.startswith("Cmd!"):
        col = {"B": "statut", "C": "montant", "D": "four"}[text[4]]
        return EntityCol("cmd", (col,))
    raise Unsupported(text)


def run(formula, row=None, params=None, today=None):
    ast = parse(formula, resolver)
    return evaluate(ast, Context(row or {}, params or {"taux": 0.2}, lambda e: TABLES[e], today))


@pytest.mark.parametrize("formula,expected", [
    ("=1+2*3", 7),
    ("=(1+2)*3", 9),
    ("=-2^2", 4.0),  # en Excel, la négation est prioritaire sur la puissance
    ("=2^3^2", 64.0),  # associativité gauche, comme Excel
    ("=50%", 0.5),
    ("=10/4", 2.5),
    ('="a"&1&TRUE', "a1VRAI"),
    ('="ABC"="abc"', True),  # comparaison insensible à la casse
    ("=1<\"a\"", True),  # nombres < textes
    ("=A1+1", 1),  # cellule vide = 0
    ('=A1&"x"', "x"),  # cellule vide = ""
    ("=ROUND(2.5,0)", 3),
    ("=ROUND(-2.5,0)", -3),
    ("=ROUND(1.005,2)", 1.01),
    ("=ROUNDDOWN(1.99,1)", 1.9),
    ("=ROUNDUP(1.01,0)", 2),
    ("=INT(-1.5)", -2),
    ("=MOD(-3,2)", 1),
    ('=LEFT("Bonjour",3)&RIGHT("Bonjour",2)&MID("Bonjour",2,3)', "Bon" + "ur" + "onj"),
    ('=LEN(TRIM("  a   b  "))', 3),
    ('=UPPER("é")&LOWER("A")', "Éa"),
    ("=IF(1>2,\"oui\",\"non\")", "non"),
    ("=IF(FALSE,1)", False),
    ("=IFERROR(1/0,\"div\")", "div"),
    ("=IFERROR(1/0,)", ""),
    ("=ISERROR(1/0)", True),
    ("=ISNUMBER(\"1\")", False),
    ("=AND(TRUE,1)", True),
    ("=OR(FALSE,0)", False),
    ("=NOT(0)", True),
])
def test_scalar_semantics(formula, expected):
    result = run(formula)
    if isinstance(expected, float):
        assert result == pytest.approx(expected)
    else:
        assert result == expected


def test_errors_are_returned_as_codes():
    assert run("=1/0") == "#DIV/0!"
    assert run('="a"+1') == "#VALUE!"
    assert run("=A1*2", row={"a": "#N/A"}) == "#N/A"
    assert run("=#REF!+1") == "#REF!"


def test_if_is_lazy():
    assert run('=IF(TRUE,"ok",1/0)') == "ok"


def test_dates():
    row = {"a": dt.datetime(2019, 1, 10), "b": 5, "c": dt.datetime(2019, 1, 1)}
    assert run("=A1+B1", row) == dt.datetime(2019, 1, 15)
    assert run("=B1+A1", row) == dt.datetime(2019, 1, 15)
    assert run("=A1-C1", row) == 9
    assert run("=A1-B1", row) == dt.datetime(2019, 1, 5)
    assert run("=YEAR(A1)*100+MONTH(A1)", row) == 201901
    assert run("=DATE(2020,13,1)") == dt.datetime(2021, 1, 1)
    assert run("=DATE(2020,3,0)") == dt.datetime(2020, 2, 29)
    assert run("=A1>C1", row) is True
    assert run("=TODAY()", today=dt.date(2024, 5, 1)) == dt.datetime(2024, 5, 1)


def test_parameters():
    assert run("=A1*TAUX", row={"a": 100}) == pytest.approx(20)
    assert run("=A1*TAUX", row={"a": 100}, params={"taux": 0.055}) == pytest.approx(5.5)


def test_vlookup_exact_and_errors():
    assert run('=VLOOKUP("F2",Four!A:C,2,FALSE)') == "Beta"
    assert run('=VLOOKUP("F3",Four!A:C,3,FALSE)') == 7  # insensible à la casse
    assert run('=VLOOKUP("X",Four!A:C,2,FALSE)') == "#N/A"
    assert run('=IFERROR(VLOOKUP("X",Four!A:C,2,FALSE),"?")') == "?"
    assert run('=VLOOKUP("F1",Four!A:C,9,FALSE)') == "#REF!"
    assert run('=VLOOKUP(A1,Four!A:C,2,0)', row={"a": "F1"}) == "Alpha"


def test_vlookup_approximate():
    TABLES["bareme"] = [{"seuil": 0, "taux": 0.0}, {"seuil": 1000, "taux": 0.05}, {"seuil": 5000, "taux": 0.1}]
    ast = parse("=VLOOKUP(A1,X,2)", lambda t: FieldRef("a") if t == "A1" else EntityCol("bareme", ("seuil", "taux")))
    rows_of = lambda e: TABLES[e]  # noqa: E731
    assert evaluate(ast, Context({"a": 2500}, {}, rows_of)) == 0.05
    assert evaluate(ast, Context({"a": 9999}, {}, rows_of)) == 0.1
    assert evaluate(ast, Context({"a": -1}, {}, rows_of)) == "#N/A"


def test_index_match_and_xlookup():
    assert run('=INDEX(Four!B:B,MATCH("F2",Four!A:A,0))') == "Beta"
    assert run('=MATCH("ZZ",Four!A:A,0)') == "#N/A"
    assert run('=XLOOKUP("F1",Four!A:A,Four!B:B)') == "Alpha"
    assert run('=XLOOKUP("ZZ",Four!A:A,Four!B:B,"absent")') == "absent"


def test_conditional_aggregates():
    assert run('=SUMIF(Cmd!B:B,"Validée",Cmd!C:C)') == 125  # « validée » en minuscules compte aussi
    assert run('=COUNTIF(Cmd!B:B,"<>Refusée")') == 3
    assert run('=COUNTIF(Cmd!B:B,"Val*")') == 2
    assert run('=SUMIFS(Cmd!C:C,Cmd!D:D,"F1",Cmd!C:C,">50")') == 100
    assert run('=COUNTIFS(Cmd!D:D,"F2")') == 2
    assert run('=COUNTIF(Cmd!B:B,"")') == 1
    assert run("=SUM(Cmd!C:C)") == 175
    assert run("=AVERAGE(Cmd!C:C)") == pytest.approx(175 / 3)
    assert run("=MAX(Cmd!C:C)+MIN(Cmd!C:C)") == 125


def test_unsupported_constructs():
    with pytest.raises(Unsupported, match="OFFSET"):
        parse("=OFFSET(A1,1,1)", resolver)
    with pytest.raises(Unsupported):
        parse("=SUM({1,2,3})", resolver)
    with pytest.raises(Unsupported):
        parse("=Z99+1", resolver)


def test_constant_hook_only_for_business_values():
    seen = []

    def hook(v):
        seen.append(v)
        return ParamRef(f"k{len(seen)}")

    ast = parse('=IF(A1>5000,A1*0.2,ROUND(A1,2))', resolver, hook)
    assert seen == [5000, 0.2]  # pas l'argument « 2 » d'ARRONDI
    assert dependencies(ast)["params"] == {"k1", "k2"}


def test_json_roundtrip_and_render():
    ast = parse('=IFERROR(VLOOKUP(A1,Four!A:C,2,FALSE),"?")&" "&TEXTE', lambda t: (
        FieldRef("a") if t == "A1" else EntityCol("four", ("code", "nom", "delai")) if t.startswith("Four")
        else ParamRef("p")))
    assert from_json(to_json(ast)) == ast
    text = render(ast, lambda f: f.upper(), lambda p: "Param", lambda e, fs: f"{e}[{len(fs)}]")
    assert text == 'IFERROR(VLOOKUP([A] ; four[3] ; 2 ; FAUX) ; "?") & " " & {Param}'


def test_from_json_rejects_unknown_functions():
    with pytest.raises(ValueError):
        from_json({"t": "call", "n": "__import__", "a": []})
