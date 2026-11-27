"""Moteur de formules : analyse syntaxique et évaluation sûre (sans eval) de formules Excel.

Une formule est transformée en arbre (AST) dont les feuilles ne sont plus des
cellules mais des champs de l'enregistrement courant (FieldRef), des paramètres
(ParamRef) ou des colonnes d'une autre table (EntityCol). La correspondance
cellule -> champ est faite par un « résolveur » fourni par l'appelant
(voir translate.py) ; ce module ne connaît rien des classeurs.

Sémantique Excel reproduite : cellule vide = 0 dans un calcul et "" dans un
texte, arithmétique sur les dates (date + jours), comparaisons insensibles à
la casse, erreurs (#DIV/0!, #N/A…) propagées et rattrapées par SIERREUR.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Any, Callable, Iterable

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import Token, TokenizerError
from openpyxl.utils.datetime import from_excel, to_excel

from ..analyzer.formulas import TRIVIAL_CONSTANTS, _in_arithmetic, clean_function_name


class Unsupported(Exception):
    """La formule utilise une construction que le moteur ne sait pas (encore) convertir."""


class XLError(Exception):
    """Erreur Excel (#DIV/0!, #N/A…) pendant l'évaluation."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# --------------------------------------------------------------------------- #
# Arbre syntaxique
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Lit:
    value: Any


@dataclass(frozen=True)
class Missing:
    """Argument omis : RECHERCHEV(a;b;2;)."""


@dataclass(frozen=True)
class FieldRef:
    field: str


@dataclass(frozen=True)
class ParamRef:
    name: str


@dataclass(frozen=True)
class EntityCol:
    """Une ou plusieurs colonnes (dans l'ordre de la plage Excel) d'une table."""

    entity: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Neg:
    operand: Any


@dataclass(frozen=True)
class Percent:
    operand: Any


Resolver = Callable[[str], Any]
ConstantHook = Callable[[float], Any]

_COMPARE = ("=", "<>", "<", ">", "<=", ">=")
_LEVELS = [_COMPARE, ("&",), ("+", "-"), ("*", "/"), ("^",)]


def parse(formula: str, resolve: Resolver, on_constant: ConstantHook | None = None) -> Any:
    """Analyse une formule. `resolve(texte_plage)` renvoie le nœud d'une référence ;
    `on_constant(nombre)` peut transformer une valeur en dur (dans un calcul) en paramètre."""
    text = formula if formula.startswith("=") else "=" + formula
    try:
        tokens = [t for t in Tokenizer(text).items if t.type != Token.WSPACE]
    except (TokenizerError, ValueError, IndexError) as exc:
        raise Unsupported("formule illisible") from exc
    parser = _Parser(tokens, resolve, on_constant)
    node = parser.expression()
    if parser.pos != len(tokens):
        raise Unsupported(f"syntaxe non prise en charge près de « {tokens[parser.pos].value} »")
    return node


class _Parser:
    def __init__(self, tokens: list, resolve: Resolver, on_constant: ConstantHook | None):
        self.tokens = tokens
        self.pos = 0
        self.resolve = resolve
        self.on_constant = on_constant

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self):
        tok = self.peek()
        if tok is None:
            raise Unsupported("formule incomplète")
        self.pos += 1
        return tok

    def expression(self, level: int = 0):
        if level == len(_LEVELS):
            return self.unary()
        node = self.expression(level + 1)
        while True:
            tok = self.peek()
            if tok is not None and tok.type == Token.OP_IN and tok.value in _LEVELS[level]:
                self.pos += 1
                node = BinOp(tok.value, node, self.expression(level + 1))
            else:
                return node

    def unary(self):
        tok = self.peek()
        if tok is not None and tok.type == Token.OP_PRE:
            self.pos += 1
            operand = self.unary()
            return Neg(operand) if tok.value == "-" else operand
        return self.postfix()

    def postfix(self):
        node = self.primary()
        while (tok := self.peek()) is not None and tok.type == Token.OP_POST and tok.value == "%":
            self.pos += 1
            node = Percent(node)
        return node

    def primary(self):
        index = self.pos
        tok = self.take()
        if tok.type == Token.OPERAND:
            if tok.subtype == Token.NUMBER:
                value = float(tok.value)
                if value.is_integer() and "." not in tok.value and "e" not in tok.value.lower():
                    value = int(value)
                if (self.on_constant is not None and float(value) not in TRIVIAL_CONSTANTS
                        and _in_arithmetic(self.tokens, index)):
                    return self.on_constant(value)
                return Lit(value)
            if tok.subtype == Token.TEXT:
                return Lit(tok.value[1:-1].replace('""', '"'))
            if tok.subtype == Token.LOGICAL:
                return Lit(tok.value.upper() == "TRUE")
            if tok.subtype == Token.ERROR:
                return Call("__ERROR__", (Lit(tok.value.upper()),))
            if tok.subtype == Token.RANGE:
                return self.resolve(tok.value)
        if tok.type == Token.PAREN and tok.subtype == Token.OPEN:
            node = self.expression()
            close = self.take()
            if close.type != Token.PAREN or close.subtype != Token.CLOSE:
                raise Unsupported("parenthèse non fermée")
            return node
        if tok.type == Token.FUNC and tok.subtype == Token.OPEN:
            name = clean_function_name(tok.value)
            if name not in FUNCTIONS:
                raise Unsupported(f"fonction {name} non prise en charge")
            args: list = []
            nxt = self.peek()
            if nxt is not None and nxt.type == Token.FUNC and nxt.subtype == Token.CLOSE:
                self.pos += 1
                return Call(name, ())
            while True:
                nxt = self.peek()
                if nxt is not None and (nxt.type == Token.SEP or
                                        (nxt.type == Token.FUNC and nxt.subtype == Token.CLOSE)):
                    args.append(Missing())
                else:
                    args.append(self.expression())
                sep = self.take()
                if sep.type == Token.SEP and sep.subtype == Token.ARG:
                    continue
                if sep.type == Token.FUNC and sep.subtype == Token.CLOSE:
                    return Call(name, tuple(args))
                raise Unsupported("séparateur inattendu")
        if tok.type == Token.ARRAY:
            raise Unsupported("constantes matricielles {…} non prises en charge")
        raise Unsupported(f"élément « {tok.value} » non pris en charge")


# --------------------------------------------------------------------------- #
# Analyse de l'arbre
# --------------------------------------------------------------------------- #


def walk(node) -> Iterable:
    yield node
    if isinstance(node, Call):
        for a in node.args:
            yield from walk(a)
    elif isinstance(node, BinOp):
        yield from walk(node.left)
        yield from walk(node.right)
    elif isinstance(node, (Neg, Percent)):
        yield from walk(node.operand)


def dependencies(node) -> dict[str, set]:
    """Champs, paramètres, tables et fonctions utilisés par une règle."""
    deps = {"fields": set(), "params": set(), "entities": set(), "functions": set()}
    for n in walk(node):
        if isinstance(n, FieldRef):
            deps["fields"].add(n.field)
        elif isinstance(n, ParamRef):
            deps["params"].add(n.name)
        elif isinstance(n, EntityCol):
            deps["entities"].add(n.entity)
        elif isinstance(n, Call):
            deps["functions"].add(n.name)
    return deps


def render(node, field_label: Callable[[str], str], param_label: Callable[[str], str],
           entity_label: Callable[[str, tuple], str]) -> str:
    """Affiche une règle lisible par un humain : [Montant HT] * [Taux TVA]."""

    def r(n, parent_prec: int = 0) -> str:
        if isinstance(n, Lit):
            if isinstance(n.value, str):
                return '"' + n.value.replace('"', '""') + '"'
            if isinstance(n.value, bool):
                return "VRAI" if n.value else "FAUX"
            return _number_text(n.value).replace(".", ",")
        if isinstance(n, Missing):
            return ""
        if isinstance(n, FieldRef):
            return f"[{field_label(n.field)}]"
        if isinstance(n, ParamRef):
            return f"{{{param_label(n.name)}}}"
        if isinstance(n, EntityCol):
            return entity_label(n.entity, n.fields)
        if isinstance(n, Call):
            if n.name == "__ERROR__":
                return n.args[0].value
            return f"{n.name}(" + " ; ".join(r(a) for a in n.args) + ")"
        if isinstance(n, Neg):
            return "-" + r(n.operand, 9)
        if isinstance(n, Percent):
            return r(n.operand, 9) + "%"
        if isinstance(n, BinOp):
            prec = next(i for i, ops in enumerate(_LEVELS) if n.op in ops) + 1
            text = f"{r(n.left, prec)} {n.op} {r(n.right, prec + 1)}"
            return f"({text})" if prec < parent_prec else text
        return "?"

    return r(node)


# --------------------------------------------------------------------------- #
# Évaluation
# --------------------------------------------------------------------------- #


class Context:
    """Données disponibles pendant l'évaluation d'une règle."""

    def __init__(self, row: dict, params: dict, rows_of: Callable[[str], list[dict]],
                 today: dt.date | None = None):
        self.row = row
        self.params = params
        self.rows_of = rows_of
        self.today = today or dt.date.today()
        self._index: dict = {}

    def lookup_index(self, entity: str, field: str) -> dict:
        key = (entity, field)
        if key not in self._index:
            index: dict = {}
            for i, row in enumerate(self.rows_of(entity)):
                index.setdefault(_key(row.get(field)), i)
            self._index[key] = index
        return self._index[key]


def evaluate(node, ctx: Context) -> Any:
    """Évalue une règle. Les erreurs Excel sont renvoyées sous forme de texte ('#DIV/0!')."""
    try:
        value = _eval(node, ctx)
    except XLError as err:
        return err.code
    except RecursionError:
        return "#NUM!"
    if isinstance(value, EntityCol):
        return "#VALUE!"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "#NUM!"
    return value


def _eval(node, ctx: Context):
    if isinstance(node, Lit):
        return node.value
    if isinstance(node, Missing):
        return None
    if isinstance(node, FieldRef):
        value = ctx.row.get(node.field)
        if isinstance(value, str) and value in ERROR_CODES:
            raise XLError(value)
        return value
    if isinstance(node, ParamRef):
        return ctx.params.get(node.name)
    if isinstance(node, EntityCol):
        return node  # évalué par la fonction qui le reçoit
    if isinstance(node, Neg):
        return -to_number(_eval(node.operand, ctx))
    if isinstance(node, Percent):
        return to_number(_eval(node.operand, ctx)) / 100
    if isinstance(node, BinOp):
        return _binop(node.op, _eval(node.left, ctx), _eval(node.right, ctx))
    if isinstance(node, Call):
        return FUNCTIONS[node.name](node.args, ctx)
    raise XLError("#VALUE!")


ERROR_CODES = frozenset({"#REF!", "#N/A", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!", "#NULL!", "#SPILL!", "#CALC!"})


def _number_text(v) -> str:
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.15g}"
    return str(v)


def to_number(v) -> float | int:
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (dt.datetime, dt.date)):
        return to_excel(v)
    if isinstance(v, str):
        if v in ERROR_CODES:
            raise XLError(v)
        try:
            return float(v.replace(",", ".")) if v.strip() else 0
        except ValueError:
            raise XLError("#VALUE!") from None
    if isinstance(v, EntityCol):
        raise XLError("#VALUE!")
    raise XLError("#VALUE!")


def to_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "VRAI" if v else "FAUX"
    if isinstance(v, (int, float)):
        return _number_text(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return _number_text(to_excel(v))
    return str(v)


def to_bool(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        if v.upper() in ("TRUE", "VRAI"):
            return True
        if v.upper() in ("FALSE", "FAUX"):
            return False
        if v in ERROR_CODES:
            raise XLError(v)
    raise XLError("#VALUE!")


def _as_date(serial: float) -> dt.datetime:
    try:
        return from_excel(serial)
    except (ValueError, OverflowError):
        raise XLError("#NUM!") from None


def _binop(op: str, a, b):
    if op in _COMPARE:
        return _compare(op, a, b)
    if op == "&":
        return to_text(a) + to_text(b)
    is_date = (dt.datetime, dt.date)
    x, y = to_number(a), to_number(b)
    if op == "+":
        result = x + y
        return _as_date(result) if isinstance(a, is_date) != isinstance(b, is_date) else result
    if op == "-":
        result = x - y
        return _as_date(result) if isinstance(a, is_date) and not isinstance(b, is_date) else result
    if op == "*":
        return x * y
    if op == "/":
        if y == 0:
            raise XLError("#DIV/0!")
        return x / y
    if op == "^":
        try:
            return float(x) ** float(y)
        except (OverflowError, ZeroDivisionError, ValueError):
            raise XLError("#NUM!") from None
    raise XLError("#VALUE!")


def _rank(v):
    """Ordre Excel : nombres < textes < booléens."""
    if isinstance(v, bool):
        return 2, v
    if isinstance(v, str):
        return 1, v.lower()
    return 0, to_number(v)


def _compare(op: str, a, b) -> bool:
    for v in (a, b):
        if isinstance(v, str) and v in ERROR_CODES:
            raise XLError(v)
    if a is None:
        a = "" if isinstance(b, str) else (False if isinstance(b, bool) else 0)
    if b is None:
        b = "" if isinstance(a, str) else (False if isinstance(a, bool) else 0)
    ra, rb = _rank(a), _rank(b)
    return {"=": ra == rb, "<>": ra != rb, "<": ra < rb, ">": ra > rb, "<=": ra <= rb, ">=": ra >= rb}[op]


def _key(v):
    """Clé de recherche (RECHERCHEV) : insensible à la casse, 2 == 2.0."""
    if isinstance(v, str):
        return ("s", v.strip().lower())
    if isinstance(v, bool):
        return ("b", v)
    if v is None:
        return ("n", None)
    try:
        return ("d", float(to_number(v)))
    except XLError:
        return ("s", str(v))


# --------------------------------------------------------------------------- #
# Fonctions
# --------------------------------------------------------------------------- #


def _arg(args, i, ctx, default=None):
    if i >= len(args) or isinstance(args[i], Missing):
        return default
    return _eval(args[i], ctx)


def _values(args, ctx) -> list:
    """Valeurs « à plat » : scalaires et colonnes de tables (pour SOMME, MAX…)."""
    out = []
    for a in args:
        if isinstance(a, Missing):
            continue
        v = _eval(a, ctx)
        if isinstance(v, EntityCol):
            for row in ctx.rows_of(v.entity):
                out.extend(row.get(f) for f in v.fields)
        else:
            out.append(v)
    return out


def _numbers(args, ctx) -> list:
    nums = []
    for a in args:
        if isinstance(a, Missing):
            continue
        v = _eval(a, ctx)
        if isinstance(v, EntityCol):
            for row in ctx.rows_of(v.entity):
                for f in v.fields:
                    x = row.get(f)
                    if isinstance(x, str) and x in ERROR_CODES:
                        raise XLError(x)
                    if isinstance(x, (int, float, dt.date)) and not isinstance(x, bool):
                        nums.append(to_number(x))
        else:
            nums.append(to_number(v))
    return nums


def _require(args, n_min, n_max=None):
    if len(args) < n_min or (n_max is not None and len(args) > n_max):
        raise XLError("#VALUE!")


def _round(value, digits, mode):
    d = int(to_number(digits))
    q = Decimal(1).scaleb(-d)
    x = Decimal(repr(float(to_number(value))))
    rounded = abs(x).quantize(q, rounding=mode)
    result = float(rounded if x >= 0 else -rounded)
    return int(result) if d <= 0 else result


def _single_col(v) -> EntityCol:
    if not isinstance(v, EntityCol) or len(v.fields) != 1:
        raise XLError("#N/A")
    return v


def _criterion(crit) -> Callable[[Any], bool]:
    """Critère de NB.SI / SOMME.SI : 'Validée', '>100', '<>Refusée', 'A*'…"""
    if isinstance(crit, str):
        m = re.match(r"^(<=|>=|<>|<|>|=)?(.*)$", crit, re.S)
        op, rest = m.group(1) or "=", m.group(2)
        try:
            target: Any = float(rest.replace(",", ".")) if rest.strip() else rest
        except ValueError:
            target = rest
        if isinstance(target, str) and op in ("=", "<>") and any(c in target for c in "*?"):
            pattern = re.compile("^" + re.escape(target).replace(r"\*", ".*").replace(r"\?", ".") + "$", re.I | re.S)
            matches = lambda v: isinstance(v, str) and bool(pattern.match(v))  # noqa: E731
            return matches if op == "=" else (lambda v: not matches(v))
        if isinstance(target, str) and target == "" and op in ("=", "<>"):
            return (lambda v: v in (None, "")) if op == "=" else (lambda v: v not in (None, ""))
    else:
        op, target = "=", crit

    def check(v):
        if isinstance(target, (int, float)) and not isinstance(target, bool):
            if v is None or isinstance(v, bool) or (isinstance(v, str) and v.strip() == ""):
                return op == "<>"
            try:
                x = to_number(v)
            except XLError:
                return op == "<>"
            return _compare(op, x, target)
        if v is None or isinstance(v, (int, float)):
            return op == "<>" if not isinstance(target, bool) else _compare(op, v, target)
        return _compare(op, v, target)

    return check


def _conditional(args, ctx, sum_index: int | None, pairs_from: int):
    """Moteur commun de SOMME.SI(.ENS) et NB.SI(.ENS) sur les lignes d'une table."""
    pairs = []
    for i in range(pairs_from, len(args) - 1, 2):
        rng = _single_col(_eval(args[i], ctx))
        pairs.append((rng, _criterion(_eval(args[i + 1], ctx))))
    if not pairs:
        raise XLError("#VALUE!")
    entity = pairs[0][0].entity
    if any(r.entity != entity for r, _ in pairs):
        raise XLError("#VALUE!")
    sum_col = None
    if sum_index is not None:
        sum_col = _single_col(_eval(args[sum_index], ctx))
        if sum_col.entity != entity:
            raise XLError("#VALUE!")
    total, count = 0.0, 0
    for row in ctx.rows_of(entity):
        if all(check(row.get(r.fields[0])) for r, check in pairs):
            count += 1
            if sum_col is not None:
                v = row.get(sum_col.fields[0])
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    total += v
    return total if sum_col is not None else count


def _vlookup(args, ctx):
    _require(args, 3, 4)
    key = _eval(args[0], ctx)
    table = _eval(args[1], ctx)
    if not isinstance(table, EntityCol):
        raise XLError("#N/A")
    col = int(to_number(_eval(args[2], ctx)))
    if col < 1 or col > len(table.fields):
        raise XLError("#REF!")
    approximate = to_bool(_arg(args, 3, ctx, True))
    rows = ctx.rows_of(table.entity)
    first, target = table.fields[0], table.fields[col - 1]
    if isinstance(key, str) and key in ERROR_CODES:
        raise XLError(key)
    if not approximate:
        i = ctx.lookup_index(table.entity, first).get(_key(key))
        if i is None:
            raise XLError("#N/A")
        return rows[i].get(target)
    # Recherche approchée (données triées) : dernière ligne dont la clé est <= à la valeur cherchée.
    found = None
    for row in rows:
        v = row.get(first)
        if v is None:
            continue
        if _rank(v)[0] == _rank(key)[0] and _rank(v) <= _rank(key):
            found = row
        elif _rank(v)[0] == _rank(key)[0]:
            break
    if found is None:
        raise XLError("#N/A")
    return found.get(target)


def _match(args, ctx):
    _require(args, 2, 3)
    key = _eval(args[0], ctx)
    col = _single_col(_eval(args[1], ctx))
    mode = int(to_number(_arg(args, 2, ctx, 1)))
    if mode != 0:
        raise XLError("#N/A")  # seule la recherche exacte est fiable sur des données non triées
    i = ctx.lookup_index(col.entity, col.fields[0]).get(_key(key))
    if i is None:
        raise XLError("#N/A")
    return i + 1


def _index(args, ctx):
    _require(args, 2, 3)
    table = _eval(args[0], ctx)
    if not isinstance(table, EntityCol):
        raise XLError("#REF!")
    row_n = int(to_number(_eval(args[1], ctx)))
    col_n = int(to_number(_arg(args, 2, ctx, 1)))
    rows = ctx.rows_of(table.entity)
    if len(table.fields) == 1 and len(args) == 2:
        col_n = 1
    if not (1 <= row_n <= len(rows)) or not (1 <= col_n <= len(table.fields)):
        raise XLError("#REF!")
    return rows[row_n - 1].get(table.fields[col_n - 1])


def _xlookup(args, ctx):
    _require(args, 3, 6)
    key = _eval(args[0], ctx)
    look = _single_col(_eval(args[1], ctx))
    ret = _eval(args[2], ctx)
    if not isinstance(ret, EntityCol) or ret.entity != look.entity:
        raise XLError("#VALUE!")
    i = ctx.lookup_index(look.entity, look.fields[0]).get(_key(key))
    if i is None:
        if len(args) > 3 and not isinstance(args[3], Missing):
            return _eval(args[3], ctx)
        raise XLError("#N/A")
    return ctx.rows_of(ret.entity)[i].get(ret.fields[0])


def _if(args, ctx):
    _require(args, 1, 3)
    cond = to_bool(_eval(args[0], ctx))
    if cond:
        return _arg(args, 1, ctx, True) if len(args) > 1 else True
    return _arg(args, 2, ctx, False) if len(args) > 2 else False


def _iferror(args, ctx, only_na=False):
    _require(args, 2, 2)
    try:
        v = _eval(args[0], ctx)
        if isinstance(v, str) and v in ERROR_CODES:
            raise XLError(v)
        return v
    except XLError as err:
        if only_na and err.code != "#N/A":
            raise
        return _arg(args, 1, ctx, "")


def _is_error(args, ctx, only_na=False):
    try:
        v = _eval(args[0], ctx)
        return isinstance(v, str) and v in ERROR_CODES and (not only_na or v == "#N/A")
    except XLError as err:
        return not only_na or err.code == "#N/A"


def _is_kind(args, ctx, kind: str) -> bool:
    try:
        v = _eval(args[0], ctx)
    except XLError:
        return False
    if kind == "number":
        return isinstance(v, (int, float, dt.date)) and not isinstance(v, bool)
    return isinstance(v, str) and v not in ERROR_CODES


def _date_arg(v) -> dt.datetime:
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    return _as_date(to_number(v))


def _make_date(args, ctx):
    _require(args, 3, 3)
    y, m, d = (int(to_number(_eval(a, ctx))) for a in args)
    if 0 <= y < 1900:
        y += 1900
    # Excel normalise les débordements : DATE(2020;13;1) = 1er janvier 2021.
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    try:
        return dt.datetime(y, m, 1) + dt.timedelta(days=d - 1)
    except (ValueError, OverflowError):
        raise XLError("#NUM!") from None


def _text_fn(fn):
    return lambda args, ctx: fn(to_text(_eval(args[0], ctx)), *[_eval(a, ctx) for a in args[1:]])


def _mid(s, start, length):
    start, length = int(to_number(start)), int(to_number(length))
    if start < 1 or length < 0:
        raise XLError("#VALUE!")
    return s[start - 1:start - 1 + length]


def _sum(args, ctx):
    return sum(_numbers(args, ctx))


def _average(args, ctx):
    nums = _numbers(args, ctx)
    if not nums:
        raise XLError("#DIV/0!")
    return sum(nums) / len(nums)


FUNCTIONS: dict[str, Callable] = {
    "__ERROR__": lambda args, ctx: (_ for _ in ()).throw(XLError(args[0].value)),
    # Logique
    "IF": _if,
    "IFERROR": _iferror,
    "IFNA": lambda args, ctx: _iferror(args, ctx, only_na=True),
    "AND": lambda args, ctx: all(to_bool(v) for v in _values(args, ctx) if v is not None),
    "OR": lambda args, ctx: any(to_bool(v) for v in _values(args, ctx) if v is not None),
    "NOT": lambda args, ctx: not to_bool(_eval(args[0], ctx)),
    "TRUE": lambda args, ctx: True,
    "FALSE": lambda args, ctx: False,
    "ISBLANK": lambda args, ctx: _eval(args[0], ctx) in (None, ""),
    "ISNUMBER": lambda args, ctx: _is_kind(args, ctx, "number"),
    "ISTEXT": lambda args, ctx: _is_kind(args, ctx, "text"),
    "ISERROR": _is_error,
    "ISNA": lambda args, ctx: _is_error(args, ctx, only_na=True),
    # Calcul
    "SUM": _sum,
    "MIN": lambda args, ctx: min(_numbers(args, ctx), default=0),
    "MAX": lambda args, ctx: max(_numbers(args, ctx), default=0),
    "AVERAGE": _average,
    "COUNT": lambda args, ctx: len([v for v in _values(args, ctx) if isinstance(v, (int, float, dt.date)) and not isinstance(v, bool)]),
    "COUNTA": lambda args, ctx: len([v for v in _values(args, ctx) if v not in (None, "")]),
    "ROUND": lambda args, ctx: _round(_eval(args[0], ctx), _arg(args, 1, ctx, 0), ROUND_HALF_UP),
    "ROUNDUP": lambda args, ctx: _round(_eval(args[0], ctx), _arg(args, 1, ctx, 0), ROUND_UP),
    "ROUNDDOWN": lambda args, ctx: _round(_eval(args[0], ctx), _arg(args, 1, ctx, 0), ROUND_DOWN),
    "INT": lambda args, ctx: math.floor(to_number(_eval(args[0], ctx))),
    "ABS": lambda args, ctx: abs(to_number(_eval(args[0], ctx))),
    "MOD": lambda args, ctx: _mod(to_number(_eval(args[0], ctx)), to_number(_eval(args[1], ctx))),
    "POWER": lambda args, ctx: _binop("^", _eval(args[0], ctx), _eval(args[1], ctx)),
    "SUMIF": lambda args, ctx: _sumif(args, ctx),
    "SUMIFS": lambda args, ctx: _conditional(args, ctx, sum_index=0, pairs_from=1),
    "COUNTIF": lambda args, ctx: _conditional(args, ctx, sum_index=None, pairs_from=0),
    "COUNTIFS": lambda args, ctx: _conditional(args, ctx, sum_index=None, pairs_from=0),
    # Texte
    "CONCATENATE": lambda args, ctx: "".join(to_text(v) for v in _values(args, ctx)),
    "CONCAT": lambda args, ctx: "".join(to_text(v) for v in _values(args, ctx)),
    "LEFT": _text_fn(lambda s, n=1: s[: int(to_number(n))]),
    "RIGHT": _text_fn(lambda s, n=1: s[len(s) - int(to_number(n)):] if int(to_number(n)) else ""),
    "MID": _text_fn(_mid),
    "LEN": _text_fn(len),
    "UPPER": _text_fn(str.upper),
    "LOWER": _text_fn(str.lower),
    "PROPER": _text_fn(str.title),
    "TRIM": _text_fn(lambda s: re.sub(" +", " ", s.strip(" "))),
    "VALUE": lambda args, ctx: to_number(to_text(_eval(args[0], ctx))),
    # Dates
    "TODAY": lambda args, ctx: dt.datetime.combine(ctx.today, dt.time()),
    "YEAR": lambda args, ctx: _date_arg(_eval(args[0], ctx)).year,
    "MONTH": lambda args, ctx: _date_arg(_eval(args[0], ctx)).month,
    "DAY": lambda args, ctx: _date_arg(_eval(args[0], ctx)).day,
    "DATE": _make_date,
    # Recherche
    "VLOOKUP": _vlookup,
    "MATCH": _match,
    "INDEX": _index,
    "XLOOKUP": _xlookup,
}

VOLATILE = frozenset({"TODAY"})


def _mod(a, b):
    if b == 0:
        raise XLError("#DIV/0!")
    return a - b * math.floor(a / b)


def _sumif(args, ctx):
    _require(args, 2, 3)
    rng = _single_col(_eval(args[0], ctx))
    check = _criterion(_eval(args[1], ctx))
    sum_col = _single_col(_eval(args[2], ctx)) if len(args) == 3 else rng
    total = 0.0
    for row in ctx.rows_of(rng.entity):
        if check(row.get(rng.fields[0])):
            v = row.get(sum_col.fields[0])
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                total += v
    return total


# --------------------------------------------------------------------------- #
# Sérialisation (la règle est stockée dans la description de l'application)
# --------------------------------------------------------------------------- #


def to_json(node) -> Any:
    if isinstance(node, Lit):
        v = node.value
        if isinstance(v, (dt.datetime, dt.date)):
            return {"t": "date", "v": v.isoformat()}
        return {"t": "lit", "v": v}
    if isinstance(node, Missing):
        return {"t": "missing"}
    if isinstance(node, FieldRef):
        return {"t": "field", "f": node.field}
    if isinstance(node, ParamRef):
        return {"t": "param", "p": node.name}
    if isinstance(node, EntityCol):
        return {"t": "cols", "e": node.entity, "f": list(node.fields)}
    if isinstance(node, Call):
        return {"t": "call", "n": node.name, "a": [to_json(a) for a in node.args]}
    if isinstance(node, BinOp):
        return {"t": "op", "o": node.op, "l": to_json(node.left), "r": to_json(node.right)}
    if isinstance(node, Neg):
        return {"t": "neg", "x": to_json(node.operand)}
    if isinstance(node, Percent):
        return {"t": "pct", "x": to_json(node.operand)}
    raise TypeError(f"nœud inconnu : {node!r}")


def from_json(data: dict) -> Any:
    t = data["t"]
    if t == "lit":
        return Lit(data["v"])
    if t == "date":
        return Lit(dt.datetime.fromisoformat(data["v"]))
    if t == "missing":
        return Missing()
    if t == "field":
        return FieldRef(data["f"])
    if t == "param":
        return ParamRef(data["p"])
    if t == "cols":
        return EntityCol(data["e"], tuple(data["f"]))
    if t == "call":
        if data["n"] not in FUNCTIONS:
            raise ValueError(f"fonction inconnue : {data['n']}")
        return Call(data["n"], tuple(from_json(a) for a in data["a"]))
    if t == "op":
        if data["o"] not in {op for ops in _LEVELS for op in ops}:
            raise ValueError("opérateur inconnu")
        return BinOp(data["o"], from_json(data["l"]), from_json(data["r"]))
    if t == "neg":
        return Neg(from_json(data["x"]))
    if t == "pct":
        return Percent(from_json(data["x"]))
    raise ValueError(f"type de nœud inconnu : {t}")
