"""Accès complet aux cellules d'un classeur (valeurs + texte des formules) pour la génération."""

from __future__ import annotations

import io
import zipfile
from typing import Any

from openpyxl.formula.translate import Translator as FormulaTranslator
from openpyxl.utils import get_column_letter

from ..analyzer.openxml_reader import StyleResolver, iter_cells, shared_strings, sheet_parts, strip_sheet_data

MAX_IMPORT_ROWS = 100_000

Cell = tuple[Any, str | None]  # (valeur ou dernier résultat, formule avec '=' ou None)


class SheetCells:
    """Charge les feuilles à la demande : {ligne: {colonne: (valeur, formule)}}."""

    def __init__(self, data: bytes, fmt: str):
        self.data = data
        self.fmt = fmt
        self._sheets: dict[str, dict[int, dict[int, Cell]]] = {}
        self.truncated: set[str] = set()
        self._xls = None
        if fmt in {"xls", "xlt"}:
            import xlrd

            self._xls = xlrd.open_workbook(file_contents=data, logfile=io.StringIO())
        else:
            from openpyxl import load_workbook

            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self._parts = sheet_parts(archive)
                self._strings = shared_strings(archive)
            meta = load_workbook(io.BytesIO(strip_sheet_data(data, list(self._parts.values()))))
            self._styles = StyleResolver(meta)

    def sheet(self, name: str) -> dict[int, dict[int, Cell]]:
        if name not in self._sheets:
            self._sheets[name] = self._load_xls(name) if self._xls is not None else self._load_openxml(name)
        return self._sheets[name]

    def get(self, sheet: str, row: int, col: int) -> Cell:
        return self.sheet(sheet).get(row, {}).get(col, (None, None))

    def has_sheet(self, name: str) -> bool:
        if self._xls is not None:
            return name in self._xls.sheet_names()
        return name in self._parts

    def _load_openxml(self, name: str) -> dict[int, dict[int, Cell]]:
        rows: dict[int, dict[int, Cell]] = {}
        part = self._parts.get(name)
        if not part:
            return rows
        masters: dict[str, tuple[str, str]] = {}
        with zipfile.ZipFile(io.BytesIO(self.data)) as archive, archive.open(part) as stream:
            for cell in iter_cells(stream, self._strings, self._styles):
                if cell.row > MAX_IMPORT_ROWS + 50:
                    self.truncated.add(name)
                    break
                formula = None
                coord = f"{get_column_letter(cell.col)}{cell.row}"
                if cell.formula_kind in ("normal", "array") and cell.formula:
                    formula = "=" + cell.formula
                elif cell.formula_kind == "shared":
                    if cell.formula:
                        formula = "=" + cell.formula
                        if cell.shared_index is not None:
                            masters[cell.shared_index] = (formula, coord)
                    elif cell.shared_index in masters:
                        text, origin = masters[cell.shared_index]
                        formula = FormulaTranslator(text, origin=origin).translate_formula(coord)
                rows.setdefault(cell.row, {})[cell.col] = (cell.value, formula)
        return rows

    def _load_xls(self, name: str) -> dict[int, dict[int, Cell]]:
        import xlrd

        sh = self._xls.sheet_by_name(name)
        rows: dict[int, dict[int, Cell]] = {}
        for r in range(min(sh.nrows, MAX_IMPORT_ROWS + 50)):
            for c in range(sh.ncols):
                ctype, raw = sh.cell_type(r, c), sh.cell_value(r, c)
                if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    continue
                if ctype == xlrd.XL_CELL_DATE:
                    try:
                        raw = xlrd.xldate.xldate_as_datetime(raw, self._xls.datemode)
                    except Exception:
                        pass
                elif ctype == xlrd.XL_CELL_BOOLEAN:
                    raw = bool(raw)
                elif ctype == xlrd.XL_CELL_ERROR:
                    raw = xlrd.error_text_from_code.get(raw, "#VALUE!")
                elif ctype == xlrd.XL_CELL_NUMBER and float(raw).is_integer():
                    raw = int(raw)
                rows.setdefault(r + 1, {})[c + 1] = (raw, None)
        if sh.nrows > MAX_IMPORT_ROWS + 50:
            self.truncated.add(name)
        return rows
