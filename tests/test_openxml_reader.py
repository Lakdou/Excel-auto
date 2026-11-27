import datetime as dt
import io
import zipfile

import pytest

from app.analyzer import analyze_bytes, openxml_reader
from app.analyzer.openxml_reader import StyleResolver, iter_cells, strip_sheet_data

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


class FakeWorkbook:
    """Styles minimaux : index 1 = format date."""

    class _Style:
        def __init__(self, num):
            self.numFmtId = num

    _cell_styles = [_Style(0), _Style(14)]
    _number_formats = []
    epoch = None


def cells(xml: str, strings=None):
    return list(iter_cells(xml.encode(), strings or [], StyleResolver(FakeWorkbook())))


@pytest.fixture(params=["lxml", "stdlib"])
def parser(request, monkeypatch):
    if request.param == "stdlib":
        monkeypatch.setattr(openxml_reader, "_lxml", None)
    elif openxml_reader._lxml is None:
        pytest.skip("lxml non installé")
    return request.param


def test_value_types(parser):
    xml = f"""<worksheet {NS}><sheetData>
      <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>42</v></c><c r="C1"><v>3.5</v></c>
        <c r="D1" t="b"><v>1</v></c><c r="E1" t="e"><v>#N/A</v></c><c r="F1" s="1"><v>43831</v></c>
        <c r="G1" t="inlineStr"><is><t>en ligne</t></is></c><c r="H1" s="1"/></row>
    </sheetData></worksheet>"""
    out = cells(xml, ["partagé"])
    assert [(c.col, c.value) for c in out] == [
        (1, "partagé"), (2, 42), (3, 3.5), (4, True), (5, "#N/A"), (6, dt.datetime(2020, 1, 1)), (7, "en ligne"),
    ]
    assert out[4].is_error  # H1 (mise en forme seule) est ignorée


def test_missing_coordinates(parser):
    xml = f"""<worksheet {NS}><sheetData>
      <row><c><v>1</v></c><c><v>2</v></c></row>
      <row><c><v>3</v></c></row>
      <row r="7"><c><v>4</v></c><c r="D7"><v>5</v></c><c><v>6</v></c></row>
    </sheetData></worksheet>"""
    assert [(c.row, c.col, c.value) for c in cells(xml)] == [
        (1, 1, 1), (1, 2, 2), (2, 1, 3), (7, 1, 4), (7, 4, 5), (7, 5, 6)]


def test_formulas_shared_and_array(parser):
    xml = f"""<worksheet {NS}><sheetData>
      <row r="2"><c r="C2"><f t="shared" ref="C2:C3" si="0">A2*B2</f><v>6</v></c>
                 <c r="D2" t="str"><f>A2&amp;"x"</f><v>1x</v></c></row>
      <row r="3"><c r="C3"><f t="shared" si="0"/><v>12</v></c>
                 <c r="D3"><f t="array" ref="D3">SUM(A2:A3*B2:B3)</f><v>18</v></c>
                 <c r="E3"><f>1/0</f></c></row>
    </sheetData></worksheet>"""
    out = cells(xml)
    assert [(c.formula, c.formula_kind, c.shared_index, c.value) for c in out] == [
        ("A2*B2", "shared", "0", 6), ('A2&"x"', "normal", None, "1x"), (None, "shared", "0", 12),
        ("SUM(A2:A3*B2:B3)", "array", None, 18), ("1/0", "normal", None, None)]


def test_rich_text_shared_strings_ignore_phonetic(parser):
    sst = f"""<sst {NS}><si><r><t>Bon</t></r><r><t>jour</t></r><rPh sb="0" eb="1"><t>X</t></rPh></si>
               <si><t>simple</t></si></sst>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
    with zipfile.ZipFile(buf) as z:
        assert openxml_reader.shared_strings(z) == ["Bonjour", "simple"]


def test_strip_sheet_data_handles_prefixes():
    buf = io.BytesIO()
    sheet = (b'<x:worksheet xmlns:x="ns"><x:dimension ref="A1"/><x:sheetData><x:row r="1"><x:c r="A1">'
             b'<x:v>1</x:v></x:c></x:row></x:sheetData><x:mergeCells/></x:worksheet>')
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("other.xml", b"<sheetData>garder</sheetData>")
    stripped = strip_sheet_data(buf.getvalue(), ["xl/worksheets/sheet1.xml"])
    with zipfile.ZipFile(io.BytesIO(stripped)) as z:
        out = z.read("xl/worksheets/sheet1.xml")
        assert b"<x:v>" not in out and b"<sheetData/>" in out and b"<x:mergeCells/>" in out
        assert z.read("other.xml") == b"<sheetData>garder</sheetData>"


def test_lxml_and_stdlib_give_identical_reports(complex_bytes, monkeypatch):
    if openxml_reader._lxml is None:
        pytest.skip("lxml non installé")
    fast = analyze_bytes(complex_bytes, "c.xlsm")
    monkeypatch.setattr(openxml_reader, "_lxml", None)
    slow = analyze_bytes(complex_bytes, "c.xlsm")
    for report in (fast, slow):
        report["file"].pop("analyzed_at")
    assert fast == slow


def test_shared_formulas_from_openpyxl_files():
    """openpyxl/Excel écrivent des formules partagées : elles comptent comme une seule règle."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Qté", "PU", "Total"])
    for r in range(2, 102):
        ws.append([r, 2, f"=A{r}*B{r}"])
    buf = io.BytesIO()
    wb.save(buf)
    report = analyze_bytes(buf.getvalue(), "t.xlsx")
    assert report["summary"]["formulas"] == 100
    assert report["summary"]["unique_formulas"] == 1
