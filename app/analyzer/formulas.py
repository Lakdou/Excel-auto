"""Analyse des formules Excel.

Chaque formule est découpée avec le tokenizer d'openpyxl pour en extraire :
les fonctions utilisées, les feuilles référencées, les liens externes,
les erreurs écrites en dur, les constantes numériques et une « signature »
indépendante de la position (style R1C1) qui permet de compter les formules
réellement distinctes (une formule recopiée sur 1 000 lignes = 1 règle).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import Token, TokenizerError
from openpyxl.utils.cell import column_index_from_string

VOLATILE_FUNCTIONS = frozenset(
    {"INDIRECT", "OFFSET", "NOW", "TODAY", "RAND", "RANDBETWEEN", "RANDARRAY", "CELL", "INFO"}
)
LOOKUP_FUNCTIONS = frozenset(
    {"VLOOKUP", "HLOOKUP", "LOOKUP", "INDEX", "MATCH", "XLOOKUP", "XMATCH", "CHOOSE", "GETPIVOTDATA"}
)
ERROR_LITERALS = ("#REF!", "#N/A", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!", "#NULL!", "#SPILL!", "#CALC!")
# Constantes considérées comme « normales » dans une formule (pas des valeurs métier en dur).
TRIVIAL_CONSTANTS = frozenset({0.0, 1.0, -1.0, 2.0, 100.0})

_FUNCTION_PREFIXES = ("_xlfn._xlws.", "_xlfn.", "_xlws.", "_xll.")
_CELL_REF_RE = re.compile(r"(?<![A-Za-z0-9_.])(\$?)([A-Za-z]{1,3})(\$?)([0-9]{1,7})(?![0-9A-Za-z_(])")
_NAME_RE = re.compile(r"^[A-Za-z_\\][A-Za-z0-9_.\\]*$")
_EXTERNAL_RE = re.compile(r"\[[^\]]+\]")


@dataclass
class FormulaInfo:
    """Résultat de l'analyse d'une formule."""

    functions: list[str] = field(default_factory=list)
    referenced_sheets: set[str] = field(default_factory=set)
    external_refs: set[str] = field(default_factory=set)
    defined_names: set[str] = field(default_factory=set)
    structured_refs: set[str] = field(default_factory=set)
    error_literals: set[str] = field(default_factory=set)
    hardcoded_numbers: list[float] = field(default_factory=list)
    depth: int = 0
    signature: str = ""
    parse_error: bool = False


def clean_function_name(raw: str) -> str:
    """'_xlfn.XLOOKUP(' -> 'XLOOKUP'."""
    name = raw.rstrip("(").upper()
    for prefix in _FUNCTION_PREFIXES:
        if name.startswith(prefix.upper()):
            name = name[len(prefix):]
            break
    return name


def _split_sheet(operand: str) -> tuple[str | None, str]:
    """Sépare 'Feuille'!A1 en ('Feuille', 'A1'). Gère les guillemets et '' échappés."""
    if "!" not in operand:
        return None, operand
    # Le '!' peut apparaître dans un nom de feuille entre guillemets : on coupe au dernier.
    sheet, ref = operand.rsplit("!", 1)
    if sheet.startswith("'") and sheet.endswith("'") and len(sheet) >= 2:
        sheet = sheet[1:-1].replace("''", "'")
    return sheet, ref


def _relative_ref(ref: str, row: int, col: int) -> str:
    """Convertit les références A1 relatives en décalages (R[x]C[y]) pour la signature."""

    def repl(match: re.Match[str]) -> str:
        col_abs, col_letters, row_abs, row_digits = match.groups()
        try:
            c = column_index_from_string(col_letters.upper())
        except ValueError:
            return match.group(0)
        r = int(row_digits)
        if c > 16384 or r > 1048576:
            return match.group(0)
        rpart = f"R{r}" if row_abs else f"R[{r - row}]"
        cpart = f"C{c}" if col_abs else f"C[{c - col}]"
        return rpart + cpart

    return _CELL_REF_RE.sub(repl, ref)


_CACHE_MAX = 50_000
_formula_cache: dict[str, FormulaInfo] = {}


def _cache_key(text: str, row: int, col: int) -> str | None:
    """Clé indépendante de la position : '=F2*G2' en ligne 2 et '=F3*G3' en ligne 3 donnent
    la même clé. Les formules contenant du texte entre guillemets ne sont pas mises en cache
    (une référence apparente dans une chaîne ne doit pas être réécrite)."""
    if '"' in text:
        return None
    return _relative_ref(text, row, col)


def analyze_formula(formula: str, row: int = 1, col: int = 1) -> FormulaInfo:
    """Analyse une formule (avec ou sans '=' initial) située en (row, col).

    Les formules recopiées (même règle, autre ligne) sont servies depuis un cache.
    """
    text = formula if formula.startswith("=") else "=" + formula
    key = _cache_key(text, row, col)
    if key is not None:
        cached = _formula_cache.get(key)
        if cached is not None:
            return cached
    info = _analyze_formula_uncached(text, row, col)
    if key is not None:
        if len(_formula_cache) >= _CACHE_MAX:
            _formula_cache.clear()
        _formula_cache[key] = info
    return info


def _analyze_formula_uncached(formula: str, row: int, col: int) -> FormulaInfo:
    info = FormulaInfo()
    text = formula if formula.startswith("=") else "=" + formula

    for literal in ERROR_LITERALS:
        if literal in text.upper():
            info.error_literals.add(literal)

    try:
        tokens = Tokenizer(text).items
    except (TokenizerError, ValueError, IndexError):
        info.parse_error = True
        info.signature = text
        return info

    depth = 0
    parts: list[str] = []
    for idx, tok in enumerate(tokens):
        if tok.type == Token.FUNC and tok.subtype == Token.OPEN:
            name = clean_function_name(tok.value)
            info.functions.append(name)
            depth += 1
            info.depth = max(info.depth, depth)
            parts.append(name + "(")
        elif tok.type == Token.FUNC and tok.subtype == Token.CLOSE:
            depth = max(0, depth - 1)
            parts.append(")")
        elif tok.type == Token.OPERAND and tok.subtype == Token.RANGE:
            parts.append(_analyze_range_operand(tok.value, row, col, info))
        elif tok.type == Token.OPERAND and tok.subtype == Token.NUMBER:
            try:
                number = float(tok.value)
            except ValueError:
                number = None
            if number is not None and number not in TRIVIAL_CONSTANTS and _in_arithmetic(tokens, idx):
                info.hardcoded_numbers.append(number)
            parts.append(tok.value)
        else:
            parts.append(tok.value)
    info.signature = "=" + "".join(parts)
    return info


_ARITHMETIC_OPERATORS = frozenset({"+", "-", "*", "/", "^", ">", "<", ">=", "<=", "=", "<>"})


def _in_arithmetic(tokens: list[Token], idx: int) -> bool:
    """Vrai si le nombre participe à un calcul ou une comparaison (ex. =A1*0.2, =B2>5000).

    Les arguments « techniques » (n° de colonne de RECHERCHEV, nb de décimales d'ARRONDI…)
    ne sont pas des valeurs métier en dur et sont ignorés.
    """
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(tokens):
            t = tokens[j]
            if t.type == Token.OP_IN and t.value in _ARITHMETIC_OPERATORS:
                return True
            if j == idx - 1 and t.type == Token.OP_PRE and t.value == "-" and idx - 2 >= 0:
                if tokens[idx - 2].type == Token.OP_IN and tokens[idx - 2].value in _ARITHMETIC_OPERATORS:
                    return True
    return False


def _analyze_range_operand(value: str, row: int, col: int, info: FormulaInfo) -> str:
    sheet, ref = _split_sheet(value)
    external = None
    if sheet is not None:
        ext = _EXTERNAL_RE.search(sheet)
        if ext:
            external = ext.group(0)
            sheet = _EXTERNAL_RE.sub("", sheet) or None
    elif _EXTERNAL_RE.match(value) and "!" not in value and not _looks_structured(value):
        # Nom défini d'un autre classeur : [1]!Nom
        external = _EXTERNAL_RE.match(value).group(0)

    if external:
        info.external_refs.add(external)
    elif sheet:
        info.referenced_sheets.add(sheet)

    if _looks_structured(ref):
        info.structured_refs.add(ref.split("[", 1)[0] or "(table courante)")
        return value
    if not _CELL_REF_RE.search(ref) and ":" not in ref and _NAME_RE.match(ref) and ref.upper() not in {"TRUE", "FALSE"}:
        info.defined_names.add(ref)
        return value

    prefix = value[: len(value) - len(ref)]
    return prefix + _relative_ref(ref, row, col)


def _looks_structured(ref: str) -> bool:
    return "[" in ref and ref.rstrip().endswith("]") and not ref.startswith("[")


@dataclass
class FormulaStats:
    """Agrégation de toutes les formules d'un classeur."""

    total: int = 0
    signatures: set[tuple[str, str]] = field(default_factory=set)
    functions: Counter = field(default_factory=Counter)
    max_depth: int = 0
    deepest_location: str | None = None
    sheet_edges: Counter = field(default_factory=Counter)  # (source, cible) -> nb de formules
    external_refs: Counter = field(default_factory=Counter)
    error_locations: list[str] = field(default_factory=list)
    hardcoded_locations: list[str] = field(default_factory=list)
    hardcoded_count: int = 0
    volatile_locations: list[str] = field(default_factory=list)
    volatile_count: int = 0
    defined_names_used: Counter = field(default_factory=Counter)
    structured_refs: Counter = field(default_factory=Counter)
    array_formulas: int = 0
    parse_errors: int = 0
    per_sheet: Counter = field(default_factory=Counter)

    MAX_LOCATIONS = 10

    def add(self, sheet: str, coordinate: str, formula: str, row: int, col: int, is_array: bool = False) -> FormulaInfo:
        info = analyze_formula(formula, row, col)
        self.record(sheet, coordinate, info, is_array)
        return info

    def record(self, sheet: str, coordinate: str, info: FormulaInfo, is_array: bool = False) -> None:
        """Enregistre une formule déjà analysée (ex. copie d'une formule partagée)."""
        location = f"{sheet}!{coordinate}"
        self.total += 1
        self.per_sheet[sheet] += 1
        self.signatures.add((sheet, info.signature))
        self.functions.update(info.functions)
        if is_array:
            self.array_formulas += 1
        if info.parse_error:
            self.parse_errors += 1
        if info.depth > self.max_depth:
            self.max_depth = info.depth
            self.deepest_location = location
        for target in info.referenced_sheets:
            if target != sheet:
                self.sheet_edges[(sheet, target)] += 1
        for ext in info.external_refs:
            self.external_refs[ext] += 1
        if info.error_literals:
            self._note(self.error_locations, location)
        if info.hardcoded_numbers:
            self.hardcoded_count += 1
            self._note(self.hardcoded_locations, location)
        if VOLATILE_FUNCTIONS.intersection(info.functions):
            self.volatile_count += 1
            self._note(self.volatile_locations, location)
        self.defined_names_used.update(info.defined_names)
        self.structured_refs.update(info.structured_refs)

    def _note(self, bucket: list[str], location: str) -> None:
        if len(bucket) < self.MAX_LOCATIONS:
            bucket.append(location)

    @property
    def unique_count(self) -> int:
        return len(self.signatures)

    @property
    def lookup_count(self) -> int:
        return sum(n for f, n in self.functions.items() if f in LOOKUP_FUNCTIONS)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "unique": self.unique_count,
            "per_sheet": dict(self.per_sheet),
            "array_formulas": self.array_formulas,
            "top_functions": [{"name": n, "count": c} for n, c in self.functions.most_common(15)],
            "distinct_functions": len(self.functions),
            "lookup_calls": self.lookup_count,
            "volatile_formulas": self.volatile_count,
            "volatile_examples": self.volatile_locations,
            "max_nesting_depth": self.max_depth,
            "deepest_formula": self.deepest_location,
            "hardcoded_constants_formulas": self.hardcoded_count,
            "hardcoded_examples": self.hardcoded_locations,
            "error_examples": self.error_locations,
            "sheet_dependencies": [
                {"from": s, "to": t, "formulas": n} for (s, t), n in sorted(self.sheet_edges.items())
            ],
            "external_references": [{"link": k, "formulas": v} for k, v in self.external_refs.items()],
            "defined_names_used": sorted(self.defined_names_used),
            "structured_references": sorted(self.structured_refs),
            "unparsable": self.parse_errors,
        }
