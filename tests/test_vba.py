from app.analyzer.vba import VBAModule, analyze_vba, strip_attributes, summarize_module

from .conftest import openpyxl_bytes, xlsxwriter_bytes

LEGACY_MACRO = '''Attribute VB_Name = "ThisWorkbook"
' Macro écrite en 2009 par le contrôle de gestion
Private Sub Workbook_Open()
    Call MiseAJour
End Sub

Public Sub MiseAJour()
    Dim wb As Workbook
    Set wb = Workbooks.Open("\\\\serveur\\partage\\export_sap.xlsx")
    wb.Sheets(1).Range("A1:F500").Copy
    ThisWorkbook.Sheets("Données").Range("A2").PasteSpecial xlPasteValues
    wb.Close False
    ThisWorkbook.Sheets("Rapport").ExportAsFixedFormat Type:=xlTypePDF, Filename:="C:\\rapport.pdf"
    Set ol = CreateObject("Outlook.Application")
    Set mail = ol.CreateItem(0)
    mail.Send
    Shell "C:\\outils\\sync.exe"
    MsgBox "Terminé"
End Sub

Function Marge(ht As Double) As Double
    Marge = ht * 0.35
End Function
'''


def test_strip_attributes_and_comments():
    lines = strip_attributes(LEGACY_MACRO)
    assert not any(l.startswith("Attribute") or l.strip().startswith("'") for l in lines)
    assert lines[0].strip() == "Private Sub Workbook_Open()"


def test_summarize_module():
    s = summarize_module(VBAModule("ThisWorkbook", LEGACY_MACRO))
    assert s["procedures"] == ["Workbook_Open", "MiseAJour", "Marge"]
    assert s["triggers"] == [{"procedure": "Workbook_Open", "when": "À l'ouverture du classeur"}]
    ids = {i["id"] for i in s["intents"]}
    assert {"file_import", "copy_data", "pdf_print", "email", "shell", "message"} <= ids
    assert "web" not in ids and "database" not in ids
    assert next(i for i in s["intents"] if i["id"] == "shell")["risk"] == "high"


def test_preview_is_truncated():
    code = "\n".join(f"x = {i}" for i in range(100))
    s = summarize_module(VBAModule("M", code))
    assert s["truncated"] and s["preview"].count("\n") == 39


def test_real_vba_project_is_extracted():
    data = xlsxwriter_bytes(lambda wb: wb.add_worksheet().write("A1", "x"), vba=True)
    result = analyze_vba(data, "macro.xlsm")
    assert result["present"]
    assert result["module_count"] == 1  # les modules vides (feuilles) ne sont pas listés
    module = result["modules"][0]
    assert module["name"] == "Module1"
    assert module["procedures"] == ["say_hello"]
    assert [i["id"] for i in result["intents"]] == ["message"]


def test_file_without_macros():
    data = openpyxl_bytes(lambda wb: None)
    result = analyze_vba(data, "vide.xlsx")
    assert not result["present"] and result["modules"] == [] and result["error"] is None


def test_garbage_does_not_crash():
    result = analyze_vba(b"pas un fichier office" * 50, "faux.xlsm")
    assert result["present"] is False
