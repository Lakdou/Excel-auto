"""Détection des tableaux de données et profilage des colonnes.

Travaille sur une grille abstraite (liste de lignes de `CellData`) pour être
commun aux formats .xlsx/.xlsm (openpyxl) et .xls (xlrd).
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, NamedTuple, Sequence

MAX_PROFILE_ROWS = 10_000  # lignes de données échantillonnées par tableau
HEADER_SCAN_ROWS = 25
ENUM_MAX_DISTINCT = 25
MIXED_THRESHOLD = 0.9  # en dessous, la colonne est considérée « mixte »
MAX_RELATION_VALUES = 20_000  # valeurs distinctes conservées pour détecter les relations


class CellData(NamedTuple):
    value: Any
    is_formula: bool = False
    number_format: str = ""


@dataclass
class TableRegion:
    """Zone tabulaire : en-tête + lignes de données (coordonnées 1-indexées, inclusives)."""

    name: str
    header_row: int
    first_col: int
    last_col: int
    last_row: int
    source: str  # "excel_table" | "detected"
    sheet: str = ""  # feuille contenant le tableau (par défaut : le nom du tableau)

    @property
    def data_rows(self) -> int:
        return max(0, self.last_row - self.header_row)


def is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


# Mots réservés PostgreSQL : interdits comme identifiants non échappés.
SQL_RESERVED = frozenset("""
all analyse analyze and any array as asc asymmetric both case cast check collate column constraint
create current_catalog current_date current_role current_time current_timestamp current_user default
deferrable desc distinct do else end except false fetch for foreign from grant group having in
initially intersect into lateral leading limit localtime localtimestamp not null offset on only or
order placing primary references returning select session_user some symmetric table then to trailing
true union unique user using variadic when where window with
""".split())


def slugify(label: str, fallback: str = "colonne") -> str:
    """'Montant TTC (€)' -> 'montant_ttc'. Identifiant SQL sûr."""
    text = unicodedata.normalize("NFKD", str(label)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    if not text:
        text = fallback
    if text[0].isdigit():
        text = "c_" + text
    text = text[:62]
    if text in SQL_RESERVED:
        text += "_"
    return text


def detect_header_row(grid: Sequence[Sequence[CellData]], first_row: int = 1) -> int | None:
    """Renvoie l'index (1-indexé, relatif à la feuille) de la ligne d'en-tête la plus probable.

    Heuristique : première ligne (parmi les 25 premières) contenant au moins
    2 libellés texte, où les libellés représentent ≥ 60 % des cellules remplies,
    et suivie d'une ligne non vide.
    """
    limit = min(len(grid), HEADER_SCAN_ROWS)
    for i in range(limit):
        row = grid[i]
        filled = [c for c in row if not is_empty(c.value)]
        labels = [c for c in filled if isinstance(c.value, str) and not c.is_formula]
        if len(labels) >= 2 and len(labels) / len(filled) >= 0.6:
            if i + 1 < len(grid) and any(not is_empty(c.value) for c in grid[i + 1]):
                return first_row + i
    return None


def detect_region(grid: Sequence[Sequence[CellData]], sheet_name: str, max_row: int) -> TableRegion | None:
    header = detect_header_row(grid)
    if header is None:
        return None
    header_cells = grid[header - 1]
    cols = [j for j, c in enumerate(header_cells) if not is_empty(c.value)]
    if len(cols) < 2:
        return None
    # On garde le bloc contigu de colonnes autour du premier libellé.
    first = cols[0]
    last = first
    for j in cols[1:]:
        if j - last > 1:
            break
        last = j
    # Fin du tableau : dernière ligne non vide avant 2 lignes vides consécutives.
    # Fin du tableau : deux lignes vides consécutives, ou une ligne vide suivie d'un
    # simple titre de section (une seule cellule texte), signe qu'un autre bloc commence.
    last_row = header
    blank_streak = 0
    width = last - first + 1
    for i in range(header, len(grid)):
        row = grid[i]
        filled = [row[j] for j in range(first, min(last + 1, len(row))) if not is_empty(row[j].value)]
        if filled:
            if blank_streak and width >= 2 and len(filled) == 1 and isinstance(filled[0].value, str):
                break
            last_row = i + 1
            blank_streak = 0
        else:
            blank_streak += 1
            if blank_streak >= 2:
                break
    if len(grid) < max_row and last_row == len(grid):
        # Grille tronquée pour l'échantillonnage : le tableau continue jusqu'à la fin de la feuille.
        last_row = max_row
    if last_row == header:
        return None
    return TableRegion(
        name=sheet_name,
        header_row=header,
        first_col=first + 1,
        last_col=last + 1,
        last_row=last_row,
        source="detected",
    )


def _value_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "integer" if value.is_integer() and abs(value) < 2**53 else "decimal"
    if isinstance(value, dt.datetime):
        return "datetime" if (value.hour, value.minute, value.second) != (0, 0, 0) else "date"
    if isinstance(value, dt.date):
        return "date"
    if isinstance(value, dt.time):
        return "time"
    if isinstance(value, dt.timedelta):
        return "duration"
    if isinstance(value, str):
        if value.startswith("#") and value.upper() in {
            "#REF!", "#N/A", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!", "#NULL!", "#SPILL!", "#CALC!"
        }:
            return "error"
        return "text"
    return "text"


SQL_TYPES = {
    "integer": "INTEGER",
    "decimal": "NUMERIC(18,4)",
    "currency": "NUMERIC(18,2)",
    "percent": "NUMERIC(9,6)",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "time": "TIME",
    "duration": "INTERVAL",
    "boolean": "BOOLEAN",
    "text": "TEXT",
    "enum": "TEXT",
    "mixed": "TEXT",
    "empty": "TEXT",
}

LABELS_FR = {
    "integer": "Nombre entier",
    "decimal": "Nombre décimal",
    "currency": "Montant",
    "percent": "Pourcentage",
    "date": "Date",
    "datetime": "Date et heure",
    "time": "Heure",
    "duration": "Durée",
    "boolean": "Oui / Non",
    "text": "Texte",
    "enum": "Liste de choix",
    "mixed": "Mixte (à nettoyer)",
    "empty": "Vide",
}

_CURRENCY_RE = re.compile(r"[€$£¥]|EUR|USD|\[\$")


def _jsonable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def profile_column(header: Any, cells: Sequence[CellData], index: int) -> dict:
    """Profil d'une colonne : type dominant, taux de remplissage, valeurs distinctes…"""
    label = str(header).strip() if not is_empty(header) else f"Colonne {index + 1}"
    total = len(cells)
    values = [c for c in cells if not is_empty(c.value)]
    kinds = Counter(_value_kind(c.value) for c in values)
    errors = kinds.pop("error", 0)
    formula_count = sum(1 for c in cells if c.is_formula)

    # Les entiers sont compatibles avec les décimaux.
    if kinds.get("integer") and kinds.get("decimal"):
        kinds["decimal"] += kinds.pop("integer")
    if kinds.get("date") and kinds.get("datetime"):
        kinds["datetime"] += kinds.pop("date")

    typed_total = sum(kinds.values())
    if typed_total == 0:
        kind = "empty"
        dominance = 1.0
    else:
        kind, dominant_count = kinds.most_common(1)[0]
        dominance = dominant_count / typed_total
        if dominance < MIXED_THRESHOLD:
            kind = "mixed"

    if kind in {"integer", "decimal"}:
        formats = Counter(c.number_format or "" for c in values)
        fmt = formats.most_common(1)[0][0] if formats else ""
        if "%" in fmt:
            kind = "percent"
        elif _CURRENCY_RE.search(fmt):
            kind = "currency"

    distinct_values = Counter(str(c.value).strip() for c in values if _value_kind(c.value) != "error")
    distinct = len(distinct_values)
    if (
        kind == "text"
        and formula_count == 0
        and 1 < distinct <= ENUM_MAX_DISTINCT
        and len(values) >= 2 * distinct
    ):
        kind = "enum"

    profile = {
        "name": label,
        "field": slugify(label, f"colonne_{index + 1}"),
        "type": kind,
        "type_label": LABELS_FR[kind],
        "sql_type": SQL_TYPES[kind],
        "fill_rate": round(len(values) / total, 3) if total else 0.0,
        "distinct": distinct,
        "unique": distinct == len(values) and len(values) > 1,
        "computed": formula_count > 0 and formula_count >= 0.5 * max(1, len(values)),
        "errors": errors,
        "type_consistency": round(dominance, 3),
        "samples": [_jsonable(c.value) for c in values[:3]],
    }
    if len(distinct_values) <= MAX_RELATION_VALUES:
        profile["_values"] = set(distinct_values)
    if kind == "enum":
        profile["choices"] = sorted(distinct_values)
    if kind in {"integer", "decimal", "currency", "percent"}:
        nums = [c.value for c in values if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
        if nums:
            profile["min"] = _jsonable(min(nums))
            profile["max"] = _jsonable(max(nums))
    return profile


def profile_region(grid: Sequence[Sequence[CellData]], region: TableRegion, grid_first_row: int = 1) -> dict:
    """Profile toutes les colonnes d'une zone. `grid` commence à la ligne `grid_first_row`."""
    hdr_idx = region.header_row - grid_first_row
    header_cells = grid[hdr_idx]
    end = min(region.last_row - grid_first_row + 1, hdr_idx + 1 + MAX_PROFILE_ROWS)
    data = grid[hdr_idx + 1 : end]
    data = [r for r in data if any(not is_empty(c.value) for c in r)]
    columns = []
    used_fields: Counter = Counter()
    for j in range(region.first_col - 1, region.last_col):
        header = header_cells[j].value if j < len(header_cells) else None
        cells = [r[j] if j < len(r) else CellData(None) for r in data]
        col = profile_column(header, cells, j)
        used_fields[col["field"]] += 1
        if used_fields[col["field"]] > 1:
            col["field"] = f"{col['field']}_{used_fields[col['field']]}"
        columns.append(col)
    # Proposition de clé primaire : première colonne unique et toujours remplie.
    primary_key = next(
        (c["field"] for c in columns if c["unique"] and c["fill_rate"] == 1.0 and c["type"] in {"integer", "text"}),
        None,
    )
    # Tableau « rapport » : toutes les colonnes sauf la première sont calculées -> vue.
    derived = len(columns) >= 2 and all(c["computed"] for c in columns[1:])
    return {
        "name": region.name,
        "entity": slugify(region.name, "table"),
        "sheet": region.sheet or region.name,
        "kind": "view" if derived else "table",
        "source": region.source,
        "range": _range_label(region),
        "rows": region.data_rows,
        "sampled_rows": len(data),
        "columns": columns,
        "primary_key_candidate": primary_key,
    }


def _range_label(region: TableRegion) -> str:
    from openpyxl.utils import get_column_letter

    return f"{get_column_letter(region.first_col)}{region.header_row}:{get_column_letter(region.last_col)}{region.last_row}"


def detect_relations(entities: list[dict]) -> list[dict]:
    """Détecte les clés étrangères probables : les valeurs d'une colonne sont toutes
    présentes dans la clé primaire candidate d'un autre tableau. Retire ensuite les
    ensembles de valeurs internes (non sérialisés dans le rapport)."""
    relations = []
    keys = []
    for e in entities:
        pk = e.get("primary_key_candidate")
        if pk and e.get("kind") != "view":
            col = next(c for c in e["columns"] if c["field"] == pk)
            if col.get("_values"):
                keys.append((e, col))
    for e in entities:
        if e.get("kind") == "view":
            continue
        for c in e["columns"]:
            values = c.get("_values")
            if not values or c["field"] == e.get("primary_key_candidate") or c["type"] in {"empty", "boolean"}:
                continue
            for target, pk_col in keys:
                if target is e or len(pk_col["_values"]) < 2:
                    continue
                if values <= pk_col["_values"]:
                    c["references"] = {"entity": target["entity"], "field": pk_col["field"]}
                    relations.append({
                        "from_entity": e["entity"], "from_field": c["field"],
                        "to_entity": target["entity"], "to_field": pk_col["field"],
                        "label": f"{e['name']}.{c['name']} → {target['name']}.{pk_col['name']}",
                    })
                    break
    for e in entities:
        for c in e["columns"]:
            c.pop("_values", None)
    return relations


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def build_sql(entities: Sequence[dict]) -> str:
    """Génère un schéma PostgreSQL proposé à partir des entités détectées."""
    lines = [
        "-- Schéma proposé par Excel Auto (à valider avec le métier)",
        "-- Généré automatiquement à partir de l'analyse du classeur.",
        "",
    ]
    seen: Counter = Counter()
    for entity in entities:
        name = entity["entity"]
        seen[name] += 1
        if seen[name] > 1:
            name = f"{name}_{seen[name]}"
        if entity.get("kind") == "view":
            computed = ", ".join(c["field"] for c in entity["columns"][1:])
            lines.append(f"-- Vue calculée « {name} » (source : {_one_line(entity['name'])}, {entity['range']})")
            lines.append(f"-- Regroupe par {entity['columns'][0]['field']} et calcule : {computed}")
            lines.append(f"-- CREATE VIEW {name} AS SELECT ... ;  -- à écrire à partir des formules Excel")
            lines.append("")
            continue
        cols = []
        pk = entity.get("primary_key_candidate")
        if not pk:
            cols.append("    id SERIAL PRIMARY KEY,")
        for c in entity["columns"]:
            if c["type"] == "empty":
                continue
            definition = f"    {c['field']} {c['sql_type']}"
            if c["field"] == pk:
                definition += " PRIMARY KEY"
            elif c["fill_rate"] == 1.0 and not c["computed"]:
                definition += " NOT NULL"
            comment = f"  -- {_one_line(c['name'])}"
            if c["computed"]:
                comment += " (calculé dans Excel)"
            if c.get("references"):
                ref = c["references"]
                definition += f" REFERENCES {ref['entity']}({ref['field']})"
            elif c["type"] == "enum":
                choices = ", ".join("'" + v.replace("'", "''") + "'" for v in c.get("choices", []))
                definition += f" CHECK ({c['field']} IN ({choices}))"
            cols.append(definition + "," + comment)
        if cols:
            last = cols[-1]
            # Retire la virgule de la dernière colonne (avant le commentaire éventuel).
            if ",  --" in last:
                head, tail = last.rsplit(",  --", 1)
                cols[-1] = head + "  --" + tail
            else:
                cols[-1] = last.rstrip(",")
        lines.append(f"CREATE TABLE {name} (  -- source : {_one_line(entity['name'])} ({entity['range']})")
        lines.extend(cols)
        lines.append(");")
        lines.append("")
    return "\n".join(lines)
