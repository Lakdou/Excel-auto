"""Traduction des références Excel (cellules, plages, noms, tableaux) en éléments de l'application.

Exemples, pour une formule située en ligne 5 de la feuille « Commandes » :
    F5                     -> champ « montant_ht » de la ligne courante
    Commandes[@[Qté]]      -> champ « qte » de la ligne courante
    Fournisseurs!$A:$D     -> colonnes (code, raison_sociale, pays, delai) de la table fournisseurs
    TauxTVA / Paramètres!$B$2 -> paramètre modifiable « Taux TVA »
    F4 (ligne précédente)  -> non pris en charge (calcul cumulatif)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from openpyxl.utils.cell import column_index_from_string

from ..analyzer.formulas import _split_sheet
from ..analyzer.profiling import slugify
from .cells import SheetCells
from .engine import EntityCol, FieldRef, ParamRef, Unsupported

_CELL_RE = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)([0-9]{1,7})$")
_COLS_RE = re.compile(r"^\$?([A-Za-z]{1,3}):\$?([A-Za-z]{1,3})$")
_RANGE_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([0-9]{1,7}):\$?([A-Za-z]{1,3})\$?([0-9]{1,7})$")
_STRUCT_RE = re.compile(r"^(?P<table>[A-Za-z_\\][\w.]*)?\[(?P<spec>.*)\]$", re.S)
_NAME_RE = re.compile(r"^[A-Za-z_\\][A-Za-z0-9_.\\]*$")


@dataclass
class EntityInfo:
    entity: str  # identifiant technique (table SQL)
    label: str
    sheet: str
    table_name: str | None  # nom du tableau Excel officiel, si c'en est un
    header_row: int
    first_col: int
    last_col: int
    last_row: int
    col_to_field: dict[int, str] = field(default_factory=dict)
    header_to_field: dict[str, str] = field(default_factory=dict)

    def contains_cols(self, c1: int, c2: int) -> bool:
        return self.first_col <= c1 <= c2 <= self.last_col

    def fields_between(self, c1: int, c2: int) -> tuple[str, ...]:
        return tuple(self.col_to_field[c] for c in range(c1, c2 + 1))


@dataclass
class Parameter:
    name: str
    label: str
    value: Any
    source: str


class ParamRegistry:
    """Paramètres de l'application : cellules de référence, noms définis et valeurs en dur."""

    def __init__(self):
        self.params: dict[str, Parameter] = {}
        self._by_key: dict[Any, str] = {}

    def _unique(self, base: str) -> str:
        name, i = base, 2
        while name in self.params:
            name, i = f"{base}_{i}", i + 1
        return name

    def add(self, key: Any, base_name: str, label: str, value: Any, source: str) -> str:
        if key in self._by_key:
            return self._by_key[key]
        name = self._unique(slugify(base_name, "parametre"))
        self.params[name] = Parameter(name, label, value, source)
        self._by_key[key] = name
        return name

    def snapshot(self) -> tuple[dict, dict]:
        return dict(self.params), dict(self._by_key)

    def restore(self, snap: tuple[dict, dict]) -> None:
        self.params, self._by_key = dict(snap[0]), dict(snap[1])


class Translator:
    def __init__(self, cells: SheetCells, entities: list[EntityInfo], defined_names: dict[str, str],
                 params: ParamRegistry):
        self.cells = cells
        self.entities = entities
        self.by_table = {e.table_name.lower(): e for e in entities if e.table_name}
        self.names = {k.lower(): v for k, v in defined_names.items()}
        self.params = params

    # -- API ------------------------------------------------------------------
    def resolver(self, entity: EntityInfo, row: int, field_label: str):
        """Fonction de résolution pour une formule de la colonne `field_label`, ligne `row`."""

        def resolve(text: str, via_name: str | None = None):
            return self._resolve(text, entity, row, via_name, resolve)

        return resolve

    def constant_hook(self, field_name: str, field_label: str):
        def hook(value):
            name = self.params.add(
                ("const", field_name, value), f"{field_name}_valeur",
                f"Valeur fixe de « {field_label} »", value, "valeur saisie dans la formule Excel",
            )
            return ParamRef(name)

        return hook

    # -- Résolution -----------------------------------------------------------
    def _resolve(self, text: str, entity: EntityInfo, row: int, via_name: str | None, resolve):
        if "!" not in text:
            m = _STRUCT_RE.match(text)
            if m and not text.startswith("["):
                return self._structured(m.group("table"), m.group("spec"), entity)
            if text.startswith("[") and text.endswith("]") and not re.match(r"^\[\d+\]", text):
                return self._structured(None, text[1:-1], entity)

        sheet, ref = _split_sheet(text)
        if (sheet and "[" in sheet) or re.match(r"^\[\d+\]", text):
            raise Unsupported("référence à un autre fichier Excel")
        if sheet is None and _NAME_RE.match(ref) and not _CELL_RE.match(ref):
            target = self.names.get(ref.lower())
            if target is None:
                if ref.lower() in self.by_table:
                    return self._structured(ref, "#Data", entity)
                raise Unsupported(f"nom « {ref} » inconnu")
            if "#REF!" in target.upper():
                raise Unsupported(f"le nom « {ref} » est cassé (#REF!)")
            return resolve(target.lstrip("="), via_name=ref)
        target_sheet = sheet or entity.sheet
        if not self.cells.has_sheet(target_sheet):
            raise Unsupported(f"feuille « {target_sheet} » introuvable")

        cm = _CELL_RE.match(ref)
        if cm:
            col_abs, col_letters, row_abs, row_digits = cm.groups()
            col, r = column_index_from_string(col_letters.upper()), int(row_digits)
            if target_sheet == entity.sheet and entity.contains_cols(col, col) and not row_abs:
                if r == row:
                    return FieldRef(entity.col_to_field[col])
                if entity.header_row < r <= entity.last_row:
                    raise Unsupported("référence à une autre ligne du tableau (calcul cumulatif)")
            return self._param_cell(target_sheet, r, col, via_name)

        bounds = None
        if (cm := _COLS_RE.match(ref)):
            c1, c2 = sorted((column_index_from_string(cm.group(1).upper()), column_index_from_string(cm.group(2).upper())))
            bounds = (c1, c2, None, None)
        elif (rm := _RANGE_RE.match(ref)):
            c1, c2 = sorted((column_index_from_string(rm.group(1).upper()), column_index_from_string(rm.group(3).upper())))
            r1, r2 = sorted((int(rm.group(2)), int(rm.group(4))))
            bounds = (c1, c2, r1, r2)
        if bounds is None:
            raise Unsupported(f"référence « {text} » non prise en charge")
        c1, c2, r1, r2 = bounds
        for target in self.entities:
            if target.sheet != target_sheet or not target.contains_cols(c1, c2):
                continue
            if r1 is None or (r1 <= target.header_row + 1 and r2 >= target.last_row):
                return EntityCol(target.entity, target.fields_between(c1, c2))
        raise Unsupported(f"la plage « {text} » ne correspond pas à un tableau de données complet")

    @staticmethod
    def _structured_items(spec: str) -> tuple[list[str], bool]:
        """Découpe la partie entre crochets d'une référence structurée.

        'Qté' -> ['Qté'] ; '@Qté' / '@[Qté HT]' -> ['#This Row', ...] ;
        '[#This Row],[Qté]' -> ['#This Row', 'Qté'] ; '[A]:[C]' -> (['A', 'C'], plage)
        """
        if not spec.startswith("["):
            if spec.startswith("@"):
                rest = spec[1:]
                if rest.startswith("[") and rest.endswith("]"):
                    rest = rest[1:-1]
                return ["#This Row"] + ([rest] if rest else []), False
            return [spec], False
        return re.findall(r"\[((?:'.|[^\[\]])*)\]", spec), "]:[" in spec

    def _structured(self, table: str | None, spec: str, entity: EntityInfo):
        target = entity if table is None else self.by_table.get(table.lower())
        if target is None:
            raise Unsupported(f"tableau « {table} » inconnu")
        items, is_span = self._structured_items(spec)
        this_row = False
        columns: list[str] = []
        for raw in items:
            item = re.sub(r"'(.)", r"\1", raw).strip()  # caractère d'échappement d'Excel
            low = item.lower()
            if low == "#this row":
                this_row = True
            elif low in ("#all", "#data"):
                continue
            elif low in ("#headers", "#totals"):
                raise Unsupported("ligne d'en-tête ou de total d'un tableau non prise en charge")
            elif item:
                columns.append(item)
        fields: list[str] = []
        for col in columns:
            f = target.header_to_field.get(col.lower())
            if f is None:
                raise Unsupported(f"colonne « {col} » inconnue dans le tableau")
            fields.append(f)
        if is_span and len(fields) == 2:
            index = {f: c for c, f in target.col_to_field.items()}
            fields = list(target.fields_between(*sorted((index[fields[0]], index[fields[1]]))))
        if not fields:
            fields = [target.col_to_field[c] for c in sorted(target.col_to_field)]
        if this_row:
            if target is not entity or len(fields) != 1:
                raise Unsupported("référence à la ligne courante d'un autre tableau")
            return FieldRef(fields[0])
        return EntityCol(target.entity, tuple(fields))

    def _param_cell(self, sheet: str, row: int, col: int, via_name: str | None):
        value, formula = self.cells.get(sheet, row, col)
        if formula:
            raise Unsupported("dépend d'une cellule calculée en dehors des tableaux")
        from openpyxl.utils import get_column_letter

        coord = f"{get_column_letter(col)}{row}"
        label = via_name or self._label_near(sheet, row, col) or f"{sheet} {coord}"
        return ParamRef(self.params.add(("cell", sheet, row, col), via_name or label, label, value,
                                        f"{sheet}!{coord}"))

    def _label_near(self, sheet: str, row: int, col: int) -> str | None:
        """Un paramètre est souvent étiqueté par la cellule à sa gauche (« Taux TVA | 20 % »)."""
        for r, c in ((row, col - 1), (row - 1, col)):
            if r >= 1 and c >= 1:
                v, f = self.cells.get(sheet, r, c)
                if isinstance(v, str) and v.strip() and not f:
                    return v.strip()
        return None

    def list_values(self, rule: str, sheet: str) -> list[str] | None:
        """Valeurs d'une liste de validation : '=ListeServices' ou '=Paramètres!$A$6:$A$10'."""
        text = rule.lstrip("=").strip()
        if text.lower() in self.names:
            text = self.names[text.lower()].lstrip("=")
        target_sheet, ref = _split_sheet(text)
        target_sheet = target_sheet or sheet
        m = _RANGE_RE.match(ref)
        if not m or not self.cells.has_sheet(target_sheet):
            return None
        c1, c2 = sorted((column_index_from_string(m.group(1).upper()), column_index_from_string(m.group(3).upper())))
        r1, r2 = sorted((int(m.group(2)), int(m.group(4))))
        if (r2 - r1 + 1) * (c2 - c1 + 1) > 1000:
            return None
        values = []
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                v, _ = self.cells.get(target_sheet, r, c)
                if v not in (None, ""):
                    values.append(str(v).strip())
        return values or None
