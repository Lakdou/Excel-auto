"""Point d'entrée de l'analyse : ouvre un classeur et produit le rapport complet."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import re
import zipfile
from typing import Any

from openpyxl.utils.cell import range_boundaries

from .. import __version__
from .formulas import ERROR_LITERALS, FormulaStats
from .openxml_reader import StyleResolver, iter_cells, shared_strings, sheet_parts, strip_sheet_data
from .profiling import (
    HEADER_SCAN_ROWS,
    MAX_PROFILE_ROWS,
    CellData,
    TableRegion,
    build_sql,
    detect_region,
    detect_relations,
    profile_region,
)
from .scoring import build_findings, build_migration_plan, compute_complexity
from .vba import analyze_vba

OPENXML_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}
LEGACY_EXTENSIONS = {".xls", ".xlt"}
SUPPORTED_EXTENSIONS = OPENXML_EXTENSIONS | LEGACY_EXTENSIONS

FORMAT_LABELS = {
    "xlsx": "Classeur Excel (.xlsx)",
    "xlsm": "Classeur Excel avec macros (.xlsm)",
    "xltx": "Modèle Excel (.xltx)",
    "xltm": "Modèle Excel avec macros (.xltm)",
    "xls": "Classeur Excel 97-2003 (.xls)",
    "xlt": "Modèle Excel 97-2003 (.xlt)",
}

MAX_CELLS_SCANNED = 3_000_000
MAX_UNCOMPRESSED_BYTES = 400 * 1024 * 1024
MAX_ZIP_ENTRIES = 20_000
GRID_ROWS = HEADER_SCAN_ROWS + MAX_PROFILE_ROWS + 5

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK\x03\x04"


class AnalysisError(Exception):
    """Erreur présentable à l'utilisateur (message en français)."""


def _extension(filename: str) -> str:
    match = re.search(r"(\.[A-Za-z0-9]+)$", filename or "")
    return match.group(1).lower() if match else ""


def detect_format(data: bytes, filename: str) -> str:
    """Détermine le format réel à partir du contenu (pas seulement de l'extension)."""
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise AnalysisError(
            f"Extension « {ext or 'aucune'} » non prise en charge. "
            "Formats acceptés : .xlsx, .xlsm, .xltx, .xltm, .xls, .xlt."
        )
    if not data:
        raise AnalysisError("Le fichier est vide.")
    if data.startswith(ZIP_MAGIC):
        # Un .xls renommé qui est en réalité un .xlsx : on suit le contenu.
        if ext in OPENXML_EXTENSIONS:
            return ext[1:]
        return "xlsm" if b"xl/vbaProject.bin" in data else "xlsx"
    if data.startswith(OLE_MAGIC):
        if _is_encrypted_ooxml(data):
            raise AnalysisError(
                "Ce classeur est protégé par un mot de passe à l'ouverture. "
                "Retirez le mot de passe (Fichier › Informations › Protéger le classeur) puis réessayez."
            )
        return ext[1:] if ext in LEGACY_EXTENSIONS else "xls"
    head = data[:512].lstrip().lower()
    if head.startswith((b"<html", b"<!doctype", b"<table", b"<?xml")):
        raise AnalysisError(
            "Ce fichier n'est pas un vrai classeur Excel (c'est une page HTML/XML renommée en Excel, "
            "souvent produite par un ancien export). Ouvrez-le dans Excel et enregistrez-le au format .xlsx."
        )
    raise AnalysisError("Ce fichier n'est pas un classeur Excel valide ou il est endommagé.")


def _is_encrypted_ooxml(data: bytes) -> bool:
    try:
        import olefile

        with olefile.OleFileIO(io.BytesIO(data)) as ole:
            return ole.exists("EncryptionInfo")
    except Exception:
        return False


def inspect_package(data: bytes) -> dict:
    """Inspecte l'archive OpenXML : protection anti « zip bomb » et fonctionnalités avancées."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AnalysisError("Le fichier est endommagé (archive illisible).") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise AnalysisError("Le fichier contient un nombre anormal d'éléments internes.")
        total = sum(i.file_size for i in infos)
        if total > MAX_UNCOMPRESSED_BYTES:
            raise AnalysisError(
                "Le fichier est trop volumineux une fois décompressé "
                f"({total // (1024 * 1024)} Mo, maximum {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} Mo)."
            )
        names = [i.filename for i in infos]
        if "xl/workbook.xml" not in names and "xl/workbook.bin" not in names:
            raise AnalysisError("Ce fichier n'est pas un classeur Excel (archive Office d'un autre type).")
        if "xl/workbook.bin" in names:
            raise AnalysisError("Le format binaire .xlsb n'est pas encore pris en charge. Enregistrez-le en .xlsx.")
        power_query = False
        for info in infos:
            if info.filename.startswith("customXml/item") and info.file_size < 5 * 1024 * 1024:
                if b"DataMashup" in archive.read(info):
                    power_query = True
                    break
        features = {
            "vba_project": "xl/vbaProject.bin" in names,
            "power_query": power_query,
            "data_model": any(n.startswith("xl/model/") for n in names),
            "data_connections": "xl/connections.xml" in names,
            "query_tables": sum(1 for n in names if n.startswith("xl/queryTables/")),
            "form_controls": sum(1 for n in names if n.startswith("xl/ctrlProps/")),
            "activex_controls": sum(1 for n in names if n.startswith("xl/activeX/") and n.endswith(".xml")),
            "slicers": sum(1 for n in names if n.startswith("xl/slicers/")),
            "external_link_parts": sum(1 for n in names if n.startswith("xl/externalLinks/externalLink")),
        }
    return {"uncompressed_bytes": total, "features": features}


# --------------------------------------------------------------------------- #
# Format OpenXML (.xlsx / .xlsm / .xltx / .xltm)
# --------------------------------------------------------------------------- #


def _analyze_openxml(data: bytes, limitations: list[str]) -> dict:
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = sheet_parts(archive)
            strings = shared_strings(archive)
        # openpyxl ne lit que les métadonnées : les cellules sont lues en flux ci-dessous.
        wb = load_workbook(io.BytesIO(strip_sheet_data(data, list(parts.values()))), keep_links=True)
    except AnalysisError:
        raise
    except Exception as exc:
        raise AnalysisError(f"Impossible d'ouvrir le classeur : {exc}") from exc
    styles = StyleResolver(wb)

    stats = FormulaStats()
    sheets: list[dict] = []
    entities: list[dict] = []
    validations: list[dict] = []
    computed_errors: list[str] = []
    computed_error_count = 0
    cells_budget = MAX_CELLS_SCANNED
    missing_cache = 0

    package = zipfile.ZipFile(io.BytesIO(data))
    names_in_package = set(package.namelist())
    for ws in wb.worksheets:
        part = parts.get(ws.title)
        non_empty = 0
        formula_cells = 0
        truncated = False
        max_row = max_col = 0
        grid_rows: dict[int, dict[int, CellData]] = {}
        shared_masters: dict[str, Any] = {}
        if part and part in names_in_package:
            with package.open(part) as stream:
                for cell in iter_cells(stream, strings, styles):
                    if cells_budget <= 0:
                        truncated = True
                        break
                    cells_budget -= 1
                    non_empty += 1
                    max_row = max(max_row, cell.row)
                    max_col = max(max_col, cell.col)
                    is_formula = cell.formula_kind not in (None, "dataTable")
                    if is_formula:
                        formula_cells += 1
                        coord = f"{get_column_letter(cell.col)}{cell.row}"
                        if cell.formula_kind == "shared" and not cell.formula and cell.shared_index in shared_masters:
                            # Copie d'une formule partagée : même règle que la formule maître.
                            stats.record(ws.title, coord, shared_masters[cell.shared_index])
                        elif cell.formula:
                            info = stats.add(ws.title, coord, "=" + cell.formula, cell.row, cell.col,
                                             is_array=cell.formula_kind == "array")
                            if cell.formula_kind == "shared" and cell.shared_index is not None:
                                shared_masters[cell.shared_index] = info
                        else:
                            formula_cells -= 1
                            is_formula = False
                        if is_formula and cell.value is None:
                            missing_cache += 1
                    if cell.is_error or (is_formula and isinstance(cell.value, str) and cell.value.upper() in ERROR_LITERALS):
                        computed_error_count += 1
                        if len(computed_errors) < 10:
                            computed_errors.append(f"{ws.title}!{get_column_letter(cell.col)}{cell.row}")
                    if cell.row <= GRID_ROWS:
                        fmt = styles.resolve(cell.style)[0] if cell.style else ""
                        grid_rows.setdefault(cell.row, {})[cell.col] = CellData(cell.value, is_formula, fmt)
        elif cells_budget <= 0:
            truncated = True

        grid_height = min(max_row, GRID_ROWS)
        grid_width = max((max(r) for r in grid_rows.values()), default=0)
        grid: list[list[CellData]] = []
        empty = CellData(None)
        for r in range(1, grid_height + 1):
            cols = grid_rows.get(r, {})
            grid.append([cols.get(c, empty) for c in range(1, grid_width + 1)])
        comments = sum(1 for c in ws._cells.values() if c.comment is not None)
        hyperlinks = sum(1 for c in ws._cells.values() if c.hyperlink is not None)
        dimensions = f"A1:{get_column_letter(max_col)}{max_row}" if max_row else None

    # Tableaux Excel officiels (Insertion › Tableau)
        table_names = []
        regions: list[TableRegion] = []
        # NB : ws.tables.items() renvoie (nom, plage texte) ; .values() donne les objets Table.
        for table in ws.tables.values():
            name = table.displayName or table.name
            table_names.append(name)
            try:
                min_col, min_row, max_c, max_r = range_boundaries(table.ref)
            except (TypeError, ValueError):
                continue
            if table.totalsRowCount:
                max_r -= int(table.totalsRowCount)
            if table.headerRowCount == 0:
                continue
            regions.append(TableRegion(name, min_row, min_col, max_c, max_r, "excel_table", ws.title))
        if not regions and grid:
            region = detect_region(grid, ws.title, max_row)
            if region:
                regions.append(region)
        for region in regions:
            if region.header_row <= len(grid):
                entities.append(profile_region(grid, region))
            else:
                limitations.append(f"Tableau « {region.name} » trop bas dans la feuille pour être profilé.")

        for dv in ws.data_validations.dataValidation:
            entry = {"sheet": ws.title, "range": str(dv.sqref), "type": dv.type or "any"}
            f1 = dv.formula1 or ""
            if dv.type == "list" and f1.startswith('"') and f1.endswith('"'):
                entry["choices"] = [c.strip() for c in f1.strip('"').split(",") if c.strip()]
            elif f1:
                entry["rule"] = f1
            validations.append(entry)

        cf_rules = sum(len(cf.rules) for cf in ws.conditional_formatting)
        sheets.append({
            "name": ws.title,
            "kind": "worksheet",
            "state": ws.sheet_state,
            "protected": bool(ws.protection.sheet),
            "dimensions": dimensions,
            "rows": max_row,
            "columns": max_col,
            "non_empty_cells": non_empty,
            "formulas": formula_cells,
            "tables": table_names,
            "charts": len(getattr(ws, "_charts", [])),
            "images": len(getattr(ws, "_images", [])),
            "pivot_tables": len(getattr(ws, "_pivots", [])),
            "merged_ranges": len(ws.merged_cells.ranges),
            "data_validations": len(ws.data_validations.dataValidation),
            "conditional_formats": cf_rules,
            "comments": comments,
            "hyperlinks": hyperlinks,
            "truncated": truncated,
        })
        if truncated:
            limitations.append(f"Feuille « {ws.title} » : analyse partielle (trop de cellules).")

    package.close()

    for cs in wb.chartsheets:
        sheets.append({
            "name": cs.title, "kind": "chartsheet", "state": cs.sheet_state, "protected": False,
            "dimensions": None, "rows": 0, "columns": 0, "non_empty_cells": 0, "formulas": 0,
            "tables": [], "charts": 1, "images": 0, "pivot_tables": 0, "merged_ranges": 0,
            "data_validations": 0, "conditional_formats": 0, "comments": 0, "hyperlinks": 0,
            "truncated": False,
        })

    if missing_cache and missing_cache == stats.total:
        limitations.append(
            "Les résultats des formules ne sont pas enregistrés dans le fichier (il n'a jamais été "
            "recalculé par Excel) : les erreurs de calcul ne peuvent pas être détectées."
        )

    names = []
    for name, dn in wb.defined_names.items():
        names.append(_name_entry(name, "Classeur", dn))
    for ws in wb.worksheets:
        for name, dn in ws.defined_names.items():
            names.append(_name_entry(name, ws.title, dn))

    external_links = []
    for idx, link in enumerate(getattr(wb, "_external_links", []), start=1):
        target = getattr(getattr(link, "file_link", None), "Target", None)
        external_links.append({"id": f"[{idx}]", "target": target or "inconnu"})
    target_by_id = {e["id"]: e["target"] for e in external_links}
    formulas = stats.to_dict()
    for ref in formulas["external_references"]:
        ref["target"] = target_by_id.get(ref["link"], ref["link"].strip("[]"))
    formulas["available"] = True
    formulas["computed_errors"] = computed_error_count
    formulas["computed_error_examples"] = computed_errors

    return {
        "sheets": sheets,
        "entities": entities,
        "formulas": formulas,
        "names": names,
        "validations": validations,
        "external_links": external_links,
        "workbook_protected": bool(getattr(wb, "security", None) and wb.security.lockStructure),
    }


def _name_entry(name: str, scope: str, dn: Any) -> dict:
    refers = dn.attr_text or ""
    return {
        "name": name,
        "scope": scope,
        "refers_to": refers,
        "hidden": bool(dn.hidden),
        "broken": "#REF!" in refers.upper(),
        "external": bool(re.match(r"^'?\[", refers)),
    }


# --------------------------------------------------------------------------- #
# Ancien format binaire (.xls / .xlt)
# --------------------------------------------------------------------------- #


def _analyze_legacy(data: bytes, limitations: list[str]) -> dict:
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=data, on_demand=False, logfile=io.StringIO())
    except xlrd.biffh.XLRDError as exc:
        if "encrypt" in str(exc).lower():
            raise AnalysisError("Ce classeur .xls est protégé par un mot de passe à l'ouverture.") from exc
        raise AnalysisError(f"Impossible de lire ce fichier .xls : {exc}") from exc
    except Exception as exc:
        raise AnalysisError(f"Impossible de lire ce fichier .xls : {exc}") from exc

    limitations.append(
        "Format .xls (Excel 97-2003) : le texte des formules, les graphiques, les validations et la mise "
        "en forme ne sont pas lisibles. Pour une analyse complète, enregistrez le fichier en .xlsx/.xlsm."
    )
    states = {0: "visible", 1: "hidden", 2: "veryHidden"}
    sheets, entities = [], []
    computed_errors: list[str] = []
    computed_error_count = 0
    cells_budget = MAX_CELLS_SCANNED
    from openpyxl.utils import get_column_letter

    for sh in book.sheets():
        grid: list[list[CellData]] = []
        non_empty = 0
        truncated = False
        for r in range(sh.nrows):
            if cells_budget <= 0:
                truncated = True
                break
            cells_budget -= sh.ncols
            keep = r < GRID_ROWS
            row_cells: list[CellData] = []
            for c in range(sh.ncols):
                ctype = sh.cell_type(r, c)
                raw = sh.cell_value(r, c)
                value: Any
                if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    value = None
                elif ctype == xlrd.XL_CELL_DATE:
                    try:
                        value = xlrd.xldate.xldate_as_datetime(raw, book.datemode)
                    except Exception:
                        value = raw
                elif ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(raw)
                elif ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code.get(raw, "#ERREUR")
                    computed_error_count += 1
                    if len(computed_errors) < 10:
                        computed_errors.append(f"{sh.name}!{get_column_letter(c + 1)}{r + 1}")
                else:
                    value = raw
                if value is not None and not (isinstance(value, str) and not value.strip()):
                    non_empty += 1
                if keep:
                    row_cells.append(CellData(value))
            if keep:
                grid.append(row_cells)
        region = detect_region(grid, sh.name, sh.nrows) if grid else None
        if region:
            entities.append(profile_region(grid, region))
        sheets.append({
            "name": sh.name, "kind": "worksheet", "state": states.get(sh.visibility, "visible"),
            "protected": bool(getattr(sh, "protected", False)),
            "dimensions": f"A1:{get_column_letter(max(1, sh.ncols))}{max(1, sh.nrows)}" if sh.nrows else None,
            "rows": sh.nrows, "columns": sh.ncols, "non_empty_cells": non_empty, "formulas": None,
            "tables": [], "charts": None, "images": None, "pivot_tables": None, "merged_ranges": None,
            "data_validations": None, "conditional_formats": None, "comments": None, "hyperlinks": None,
            "truncated": truncated,
        })

    names = []
    for nobj in book.name_obj_list:
        refers = ""
        try:
            refers = nobj.formula_text or ""
        except Exception:
            pass
        names.append({
            "name": nobj.name, "scope": "Classeur" if nobj.scope < 0 else book.sheet_names()[nobj.scope]
            if 0 <= nobj.scope < book.nsheets else "Classeur",
            "refers_to": refers, "hidden": bool(nobj.hidden), "broken": "#REF!" in refers.upper(),
            "external": False,
        })

    formulas = FormulaStats().to_dict()
    formulas["available"] = False
    formulas["computed_errors"] = computed_error_count
    formulas["computed_error_examples"] = computed_errors
    return {
        "sheets": sheets,
        "entities": entities,
        "formulas": formulas,
        "names": names,
        "validations": [],
        "external_links": [],
        "workbook_protected": False,
    }


# --------------------------------------------------------------------------- #
# Rapport
# --------------------------------------------------------------------------- #


def analyze_bytes(data: bytes, filename: str) -> dict:
    """Analyse un classeur fourni en mémoire. Lève AnalysisError si le fichier est inexploitable."""
    fmt = detect_format(data, filename)
    limitations: list[str] = []
    package = {"uncompressed_bytes": None, "features": {}}
    if fmt in {"xls", "xlt"}:
        body = _analyze_legacy(data, limitations)
    else:
        package = inspect_package(data)
        body = _analyze_openxml(data, limitations)

    vba = analyze_vba(data, filename) if (fmt in {"xls", "xlt", "xlsm", "xltm"} or package["features"].get("vba_project")) else analyze_vba_absent()

    sheets = body["sheets"]
    body["relations"] = detect_relations(body["entities"])
    external_count = max(len(body["external_links"]), len(body["formulas"]["external_references"]))
    summary = {
        "sheets": len(sheets),
        "hidden_sheets": sum(1 for s in sheets if s["state"] != "visible"),
        "very_hidden_sheets": sum(1 for s in sheets if s["state"] == "veryHidden"),
        "protected_sheets": sum(1 for s in sheets if s["protected"]),
        "non_empty_cells": sum(s["non_empty_cells"] or 0 for s in sheets),
        "formulas": body["formulas"]["total"],
        "unique_formulas": body["formulas"]["unique"],
        "tables_detected": len(body["entities"]),
        "data_rows": sum(e["rows"] for e in body["entities"]),
        "charts": sum(s["charts"] or 0 for s in sheets),
        "pivot_tables": sum(s["pivot_tables"] or 0 for s in sheets),
        "data_validations": len(body["validations"]),
        "defined_names": len(body["names"]),
        "external_links": external_count,
        "relations": len(body["relations"]),
        "vba_modules": vba["module_count"],
        "vba_lines": vba["lines_of_code"],
    }

    report: dict[str, Any] = {
        "file": {
            "name": filename,
            "format": fmt,
            "format_label": FORMAT_LABELS.get(fmt, fmt),
            "size_bytes": len(data),
            "uncompressed_bytes": package["uncompressed_bytes"],
            "sha256": hashlib.sha256(data).hexdigest(),
            "analyzed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "analyzer_version": __version__,
        },
        "summary": summary,
        "sheets": sheets,
        "entities": body["entities"],
        "relations": body["relations"],
        "formulas": body["formulas"],
        "names": body["names"],
        "validations": body["validations"],
        "external_links": body["external_links"],
        "features": package["features"],
        "workbook_protected": body["workbook_protected"],
        "vba": vba,
        "limitations": limitations,
    }
    report["complexity"] = compute_complexity(report)
    report["findings"] = build_findings(report)
    report["migration_plan"] = build_migration_plan(report)
    report["sql_schema"] = build_sql(report["entities"]) if report["entities"] else ""
    return report


def analyze_vba_absent() -> dict:
    return {
        "present": False, "error": None, "module_count": 0, "empty_modules": 0, "lines_of_code": 0,
        "procedures": 0, "auto_triggers": [], "intents": [], "modules": [],
    }

