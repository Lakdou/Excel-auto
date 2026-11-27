"""Extraction et analyse des macros VBA (via oletools).

Pour chaque module : lignes de code utiles, procédures, déclencheurs
automatiques, et « intentions » métier détectées (envoi d'e-mail, export PDF,
import de fichiers…) qui deviendront des automatisations dans l'application web.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CODE_PREVIEW_LINES = 40

_PROC_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend|Static)\s+)*(Sub|Function|Property\s+(?:Get|Let|Set))\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE | re.MULTILINE,
)

# Procédures exécutées automatiquement par Excel.
AUTO_TRIGGERS = {
    "workbook_open": "À l'ouverture du classeur",
    "auto_open": "À l'ouverture du classeur",
    "workbook_beforeclose": "À la fermeture du classeur",
    "auto_close": "À la fermeture du classeur",
    "workbook_beforesave": "Avant chaque enregistrement",
    "workbook_aftersave": "Après chaque enregistrement",
    "workbook_beforeprint": "Avant chaque impression",
    "workbook_sheetchange": "À chaque modification d'une feuille",
    "worksheet_change": "À chaque modification de cellule",
    "worksheet_selectionchange": "À chaque changement de sélection",
    "worksheet_activate": "À l'activation de la feuille",
    "worksheet_calculate": "À chaque recalcul",
    "userform_initialize": "À l'ouverture d'un formulaire",
}

# (motif, identifiant, libellé, équivalent web, risque)
INTENT_PATTERNS: list[tuple[re.Pattern[str], str, str, str, str]] = [
    (re.compile(r"Outlook\.Application|\.Send\b|MailItem|CDO\.Message", re.I),
     "email", "Envoi d'e-mails", "Notification e-mail automatique", "medium"),
    (re.compile(r"ExportAsFixedFormat|\.PrintOut\b", re.I),
     "pdf_print", "Export PDF / impression", "Génération de documents PDF", "low"),
    (re.compile(r"Workbooks\.Open|GetOpenFilename|Workbooks\.Add", re.I),
     "file_import", "Ouverture / import d'autres classeurs", "Import de fichiers ou connecteur de données", "medium"),
    (re.compile(r"\.SaveAs\b|\.SaveCopyAs\b|\.Save\b", re.I),
     "file_save", "Enregistrement de fichiers", "Export Excel/CSV et historique des versions", "low"),
    (re.compile(r"Scripting\.FileSystemObject|\bDir\(|\bKill\b|\bMkDir\b|Open .+ For (?:Input|Output|Append)", re.I),
     "filesystem", "Accès aux fichiers et dossiers", "Stockage de documents dans l'application", "medium"),
    (re.compile(r"ADODB\.|\bDAO\.|OpenRecordset|\.Execute\b|ODBC", re.I),
     "database", "Connexion à une base de données", "Intégration directe à la base de données", "medium"),
    (re.compile(r"MSXML2\.|WinHttp|XMLHTTP|InternetExplorer\.Application|URLDownloadToFile", re.I),
     "web", "Appels web / téléchargements", "Intégration API", "high"),
    (re.compile(r"\bShell\b|WScript\.Shell|CreateObject\(\s*\"Shell", re.I),
     "shell", "Exécution de programmes externes", "À remplacer par un service serveur contrôlé", "high"),
    (re.compile(r"\.AutoFilter\b|\.AdvancedFilter\b", re.I),
     "filter", "Filtres", "Filtres et recherche dans les tableaux", "low"),
    (re.compile(r"\.Sort\b|SortFields", re.I),
     "sort", "Tris", "Tri des tableaux", "low"),
    (re.compile(r"\.Copy\b|\.PasteSpecial\b|\.Cut\b|\.Value\s*=\s*\w+\.(?:Range|Cells)", re.I),
     "copy_data", "Copie de données entre zones/feuilles", "Traitement de données côté serveur", "low"),
    (re.compile(r"PivotTable|PivotCache", re.I),
     "pivot", "Tableaux croisés dynamiques", "Tableaux de bord et agrégations", "low"),
    (re.compile(r"ChartObjects|\.Chart\b|AddChart", re.I),
     "chart", "Graphiques", "Graphiques du tableau de bord", "low"),
    (re.compile(r"UserForm|\.Show\b|InputBox", re.I),
     "form", "Formulaires / saisie utilisateur", "Formulaires web avec validation", "low"),
    (re.compile(r"\bMsgBox\b", re.I),
     "message", "Messages à l'utilisateur", "Alertes et confirmations dans l'interface", "low"),
    (re.compile(r"Application\.OnTime", re.I),
     "schedule", "Exécution planifiée", "Tâche planifiée côté serveur", "medium"),
    (re.compile(r"\.Protect\b|\.Unprotect\b|Password\s*:?=", re.I),
     "protection", "Protection / mots de passe", "Gestion des droits par utilisateur", "medium"),
    (re.compile(r"\bDeclare\s+(?:PtrSafe\s+)?(?:Function|Sub)\b", re.I),
     "win_api", "Appels à l'API Windows", "À réécrire (non portable)", "high"),
]


@dataclass
class VBAModule:
    name: str
    code: str


def strip_attributes(code: str) -> list[str]:
    """Lignes de code utiles : sans les 'Attribute VB_…', lignes vides ni commentaires."""
    useful = []
    for line in code.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = line.strip()
        if not s or s.startswith("'") or s.upper().startswith("REM ") or s.startswith("Attribute VB_"):
            continue
        useful.append(line.rstrip())
    return useful


def summarize_module(module: VBAModule) -> dict:
    lines = strip_attributes(module.code)
    body = "\n".join(lines)
    procedures = [m.group(2) for m in _PROC_RE.finditer(body)]
    triggers = []
    for proc in procedures:
        label = AUTO_TRIGGERS.get(proc.lower())
        if label:
            triggers.append({"procedure": proc, "when": label})
    intents = []
    for pattern, ident, label, web, risk in INTENT_PATTERNS:
        if pattern.search(body):
            intents.append({"id": ident, "label": label, "web_equivalent": web, "risk": risk})
    return {
        "name": module.name,
        "lines_of_code": len(lines),
        "procedures": procedures,
        "triggers": triggers,
        "intents": intents,
        "preview": "\n".join(lines[:CODE_PREVIEW_LINES]),
        "truncated": len(lines) > CODE_PREVIEW_LINES,
    }


def extract_modules(data: bytes, filename: str) -> tuple[list[VBAModule], str | None]:
    """Extrait les modules VBA. Renvoie (modules, message d'erreur éventuel)."""
    try:
        from oletools.olevba import VBA_Parser
    except ImportError:  # pragma: no cover - dépendance déclarée
        return [], "oletools n'est pas installé"
    parser = None
    try:
        parser = VBA_Parser(filename, data=data)
        # oletools accepte aussi du texte brut comme « code VBA » : on ne garde que les vrais projets.
        if parser.type == "Text" or not parser.detect_vba_macros():
            return [], None
        modules: dict[str, VBAModule] = {}
        for _, _, vba_filename, code in parser.extract_macros():
            name = re.sub(r"\.(bas|cls|frm)$", "", vba_filename or "Module", flags=re.I)
            if isinstance(code, bytes):
                code = code.decode("latin-1", errors="replace")
            # Un même module peut apparaître deux fois (xlsm + copie) : on garde le plus long.
            if name not in modules or len(code) > len(modules[name].code):
                modules[name] = VBAModule(name=name, code=code or "")
        return list(modules.values()), None
    except Exception as exc:  # oletools peut lever des erreurs variées sur des fichiers abîmés
        logger.warning("Extraction VBA impossible pour %s : %s", filename, exc)
        return [], "Les macros n'ont pas pu être lues (fichier abîmé ou projet VBA protégé)."
    finally:
        if parser is not None:
            try:
                parser.close()
            except Exception:  # pragma: no cover
                pass


def analyze_vba(data: bytes, filename: str) -> dict:
    modules, error = extract_modules(data, filename)
    summaries = [summarize_module(m) for m in modules]
    # Les modules vides (uniquement des attributs) ne sont pas listés.
    meaningful = [s for s in summaries if s["lines_of_code"] > 0]
    intents: dict[str, dict] = {}
    for s in meaningful:
        for intent in s["intents"]:
            intents.setdefault(intent["id"], {**intent, "modules": []})["modules"].append(s["name"])
    return {
        "present": bool(modules),
        "error": error,
        "module_count": len(meaningful),
        "empty_modules": len(summaries) - len(meaningful),
        "lines_of_code": sum(s["lines_of_code"] for s in meaningful),
        "procedures": sum(len(s["procedures"]) for s in meaningful),
        "auto_triggers": [dict(t, module=s["name"]) for s in meaningful for t in s["triggers"]],
        "intents": list(intents.values()),
        "modules": meaningful,
    }
