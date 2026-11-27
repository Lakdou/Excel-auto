"""Lecture rapide des cellules d'un classeur OpenXML (.xlsx/.xlsm).

openpyxl construit un objet Python par cellule et doit charger le classeur deux
fois (formules puis valeurs) : trop lent sur les gros fichiers. Ce module :

- lit chaque feuille en flux (un seul passage) et renvoie, pour chaque cellule,
  sa formule ET sa dernière valeur calculée ;
- fabrique une copie du classeur sans les cellules, qu'openpyxl charge
  instantanément pour les métadonnées (tableaux, validations, graphiques…).

Le XML est lu avec defusedxml (protection contre les entités malveillantes).
"""

from __future__ import annotations

import datetime as dt
import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Any, Iterator

from defusedxml.ElementTree import iterparse
from openpyxl.styles.numbers import BUILTIN_FORMATS, is_date_format
from openpyxl.utils.cell import column_index_from_string
from openpyxl.utils.datetime import from_excel

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_SHEET_DATA_RE = re.compile(
    rb"<(?P<p>[A-Za-z0-9_]+:)?sheetData(?:\s[^>]*)?(?:/>|>.*?</(?P=p)?sheetData>)", re.DOTALL
)
_COORD_RE = re.compile(r"^([A-Z]{1,3})([0-9]+)$")


try:  # lxml (C) est nettement plus rapide ; repli sur la bibliothèque standard sinon.
    from lxml import etree as _lxml
except ImportError:  # pragma: no cover - dépend de l'environnement
    _lxml = None

_MAIN_NS = ("http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "http://purl.oclc.org/ooxml/spreadsheetml/main")
_CELL_TAGS = tuple(f"{{{ns}}}c" for ns in _MAIN_NS)
_LOCAL_CACHE: dict[str, str] = {}


def _local(tag: str) -> str:
    name = _LOCAL_CACHE.get(tag)
    if name is None:
        name = _LOCAL_CACHE[tag] = tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""
    return name


def _cell_elements(source) -> Iterator[tuple[Any, int, bool]]:
    """Renvoie (élément <c>, n° de ligne, nouvelle_ligne) en mémoire bornée.

    Le n° de ligne vient de l'attribut r du <row>, ou est déduit (ligne précédente + 1).
    """
    row_num = 0
    if _lxml is not None:
        context = _lxml.iterparse(source, events=("end",), tag=_CELL_TAGS, resolve_entities=False,
                                  no_network=True, load_dtd=False)
        current_parent = None
        for _, el in context:
            parent = el.getparent()
            new_row = parent is not current_parent
            if new_row:
                current_parent = parent
                r = parent.get("r") if parent is not None else None
                row_num = int(r) if r else row_num + 1
            yield el, row_num, new_row
            el.clear()
            while el.getprevious() is not None:
                del parent[0]
        return
    new_row = False
    for event, el in iterparse(source, events=("start", "end")):
        tag = _local(el.tag)
        if tag == "row":
            if event == "start":
                r = el.get("r")
                row_num = int(r) if r else row_num + 1
                new_row = True
            else:
                el.clear()
        elif tag == "c" and event == "end":
            yield el, row_num, new_row
            new_row = False
            el.clear()


@dataclass(slots=True)
class RawCell:
    row: int
    col: int
    value: Any  # valeur (ou dernier résultat calculé pour une formule)
    formula: str | None  # texte de la formule sans '=' (None si cellule de saisie)
    formula_kind: str | None  # None | "normal" | "array" | "shared" | "dataTable"
    shared_index: str | None  # identifiant de formule partagée
    style: int
    is_error: bool


def strip_sheet_data(data: bytes, sheet_parts: list[str]) -> bytes:
    """Copie du package où le contenu des cellules des feuilles est vidé."""
    out = io.BytesIO()
    targets = set(sheet_parts)
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            content = src.read(info)
            if info.filename in targets:
                content = _SHEET_DATA_RE.sub(b"<sheetData/>", content, count=1)
            dst.writestr(info, content)
    return out.getvalue()


def sheet_parts(archive: zipfile.ZipFile) -> dict[str, str]:
    """Nom de feuille -> chemin de la partie XML (ex. 'xl/worksheets/sheet1.xml')."""
    rels: dict[str, str] = {}
    for _, el in iterparse(io.BytesIO(archive.read("xl/_rels/workbook.xml.rels"))):
        if _local(el.tag) == "Relationship":
            target = el.get("Target", "")
            if target.startswith("/"):
                path = target.lstrip("/")
            else:
                path = posixpath.normpath(posixpath.join("xl", target))
            rels[el.get("Id")] = path
    parts: dict[str, str] = {}
    for _, el in iterparse(io.BytesIO(archive.read("xl/workbook.xml"))):
        if _local(el.tag) == "sheet":
            rid = el.get(f"{{{_REL_NS}}}id")
            if rid in rels:
                parts[el.get("name")] = rels[rid]
    return parts


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    strings: list[str] = []
    parts: list[str] = []
    in_phonetic = 0
    for event, el in iterparse(io.BytesIO(archive.read("xl/sharedStrings.xml")), events=("start", "end")):
        tag = _local(el.tag)
        if event == "start":
            if tag == "rPh":
                in_phonetic += 1
            continue
        if tag == "rPh":
            in_phonetic -= 1
        elif tag == "t" and not in_phonetic:
            parts.append(el.text or "")
        elif tag == "si":
            strings.append("".join(parts))
            parts = []
            el.clear()
    return strings


class StyleResolver:
    """Index de style -> format de nombre, et détection des formats de date."""

    def __init__(self, workbook: Any):
        self._styles = getattr(workbook, "_cell_styles", [])
        self._custom = list(getattr(workbook, "_number_formats", []))
        self.epoch = getattr(workbook, "epoch", None)
        self._cache: dict[int, tuple[str, bool]] = {}

    def resolve(self, index: int) -> tuple[str, bool]:
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        fmt = "General"
        if 0 <= index < len(self._styles):
            num_id = self._styles[index].numFmtId
            if num_id in BUILTIN_FORMATS:
                fmt = BUILTIN_FORMATS[num_id]
            elif num_id >= 164 and num_id - 164 < len(self._custom):
                fmt = self._custom[num_id - 164]
        result = (fmt, is_date_format(fmt))
        self._cache[index] = result
        return result


def _number(text: str) -> int | float:
    try:
        if "." not in text and "E" not in text and "e" not in text:
            return int(text)
        return float(text)
    except ValueError:
        return float("nan")


def iter_cells(xml: bytes | io.BufferedIOBase, strings: list[str], styles: StyleResolver) -> Iterator[RawCell]:
    """Parcourt les cellules d'une feuille, dans l'ordre, en mémoire constante."""
    source = io.BytesIO(xml) if isinstance(xml, bytes) else xml
    row_num = 0
    col_num = 0
    epoch = styles.epoch
    for el, row_from_xml, new_row in _cell_elements(source):
        if new_row:
            row_num, col_num = row_from_xml, 0
        ref = el.get("r")
        if ref:
            m = _COORD_RE.match(ref)
            if m:
                col_num = column_index_from_string(m.group(1))
                row_num = int(m.group(2))
            else:
                col_num += 1
        else:
            col_num += 1
        ctype = el.get("t", "n")
        style = int(el.get("s", "0") or 0)
        v_text = None
        formula = None
        f_kind = None
        shared = None
        inline = None
        for child in el:
            ctag = _local(child.tag)
            if ctag == "v":
                v_text = child.text
            elif ctag == "f":
                f_kind = child.get("t", "normal")
                formula = child.text
                shared = child.get("si")
            elif ctag == "is":
                inline = "".join(t.text or "" for t in child.iter() if _local(t.tag) == "t")

        if formula is None and f_kind is None and v_text is None and inline is None:
            continue  # cellule seulement mise en forme

        value: Any = None
        is_error = False
        if ctype == "s":
            if v_text is not None:
                try:
                    value = strings[int(v_text)]
                except (ValueError, IndexError):
                    value = None
        elif ctype == "inlineStr":
            value = inline
        elif ctype == "str":
            value = v_text if v_text is not None else None
        elif ctype == "b":
            value = v_text == "1" if v_text is not None else None
        elif ctype == "e":
            value = v_text
            is_error = v_text is not None
        elif ctype == "d":
            try:
                value = dt.datetime.fromisoformat(v_text) if v_text else None
            except ValueError:
                value = v_text
        elif v_text is not None:
            value = _number(v_text)
            if style and styles.resolve(style)[1] and isinstance(value, (int, float)) and value == value:
                try:
                    value = from_excel(value, epoch) if epoch else from_excel(value)
                except (ValueError, OverflowError):
                    pass

        if value == "" and formula is None and f_kind is None:
            continue
        yield RawCell(row_num, col_num, value, formula, f_kind, shared, style, is_error)
