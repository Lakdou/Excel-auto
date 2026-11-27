"""Score de complexité, points de vigilance et plan de migration.

Les pondérations sont volontairement simples et explicables : chaque point du
score est rattaché à un facteur affiché dans le rapport. L'estimation d'effort
est indicative (jours-homme pour reconstruire le fichier en application web).
"""

from __future__ import annotations

import math

LEVELS = [
    (20, "simple", "Simple"),
    (45, "moderate", "Modéré"),
    (70, "complex", "Complexe"),
    (101, "very_complex", "Très complexe"),
]

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _cap(value: float, cap: float) -> float:
    return min(cap, value)


def compute_complexity(report: dict) -> dict:
    s = report["summary"]
    f = report["formulas"]
    vba = report["vba"]
    feats = report.get("features") or {}
    factors: list[tuple[str, float]] = []

    def add(label: str, points: float) -> None:
        if points > 0:
            factors.append((label, round(points, 1)))

    add(f"{s['unique_formulas']} règles de calcul distinctes", _cap(s["unique_formulas"] / 6, 25))
    add(f"{f['lookup_calls']} recherches (RECHERCHEV, INDEX/EQUIV…)", _cap(f["lookup_calls"] / 10, 8))
    add("Formules très imbriquées", 4 if f["max_nesting_depth"] >= 5 else 0)
    add("Fonctions volatiles", 3 if f["volatile_formulas"] else 0)
    add(f"{len(f['sheet_dependencies'])} dépendances entre feuilles", _cap(len(f["sheet_dependencies"]) * 1.5, 8))
    add(f"{s['external_links']} lien(s) vers d'autres classeurs", _cap(s["external_links"] * 4, 10))
    add(f"{vba['lines_of_code']} lignes de macros VBA", _cap(vba["lines_of_code"] / 15, 25))
    add("Macros déclenchées automatiquement", 3 if vba["auto_triggers"] else 0)
    add(f"{s['sheets']} feuilles", _cap(max(0, s["sheets"] - 1) * 1.0, 6))
    add(f"{s['tables_detected']} tableau(x) de données", _cap(s["tables_detected"] * 1.5, 6))
    add("Power Query / modèle de données", 5 if feats.get("power_query") or feats.get("data_model") else 0)
    add("Connexions à des sources externes", 3 if feats.get("data_connections") else 0)
    add(f"{s['pivot_tables']} TCD / {s['charts']} graphiques", _cap(s["pivot_tables"] * 1.5 + s["charts"] * 0.5, 5))
    add("Contrôles de formulaire / ActiveX",
        3 if feats.get("form_controls") or feats.get("activex_controls") else 0)

    score = int(round(min(100, sum(p for _, p in factors))))
    level, label = next((lvl, lab) for limit, lvl, lab in LEVELS if score < limit)

    # Estimation d'effort (jours-homme) : socle + reconstruction de chaque composant.
    effort = (
        1.0
        + s["unique_formulas"] / 40
        + vba["lines_of_code"] / 120
        + s["tables_detected"] * 0.5
        + s["external_links"] * 0.5
        + max(0, s["sheets"] - 1) * 0.25
        + (s["pivot_tables"] + s["charts"]) * 0.25
        + (1.5 if feats.get("power_query") or feats.get("data_model") else 0)
    )
    low = max(0.5, math.floor(effort * 0.8 * 2) / 2)
    high = max(low + 0.5, math.ceil(effort * 1.5 * 2) / 2)

    return {
        "score": score,
        "level": level,
        "level_label": label,
        "factors": [{"label": lab, "points": pts} for lab, pts in sorted(factors, key=lambda x: -x[1])],
        "effort_days": {"low": low, "high": high},
    }


def _finding(fid: str, severity: str, title: str, detail: str, examples: list[str] | None = None) -> dict:
    return {"id": fid, "severity": severity, "title": title, "detail": detail, "examples": examples or []}


def build_findings(report: dict) -> list[dict]:
    f, vba = report["formulas"], report["vba"]
    feats = report.get("features") or {}
    out: list[dict] = []

    if f["error_examples"] or f.get("computed_errors"):
        examples = list(dict.fromkeys(f["error_examples"] + f.get("computed_error_examples", [])))[:10]
        out.append(_finding(
            "formula_errors", "critical", "Erreurs dans les formules",
            f"{f.get('computed_errors', 0)} cellule(s) affichent une erreur (#REF!, #N/A, #DIV/0!…) "
            "ou des formules contiennent des références cassées. Les résultats actuels du fichier "
            "sont donc peut-être faux : à corriger avant la migration.",
            examples,
        ))
    if report["external_links"] or f["external_references"]:
        targets = [e["target"] for e in report["external_links"]] or [r["link"] for r in f["external_references"]]
        out.append(_finding(
            "external_links", "critical", "Dépendances vers d'autres fichiers",
            "Le classeur lit des données dans d'autres fichiers Excel. Ces liens cassent dès qu'un "
            "fichier est renommé ou déplacé, et chaque source devra être migrée ou connectée.",
            targets[:10],
        ))
    risky = [i for i in vba["intents"] if i["risk"] == "high"]
    if risky:
        out.append(_finding(
            "vba_risky", "critical", "Macros à risque",
            "Des macros exécutent des programmes, appellent le web ou l'API Windows. À auditer en priorité "
            "(sécurité) et à remplacer par des services contrôlés.",
            [f"{i['label']} ({', '.join(i['modules'])})" for i in risky],
        ))
    if vba["auto_triggers"]:
        out.append(_finding(
            "vba_auto", "warning", "Macros qui se lancent automatiquement",
            "Certaines macros s'exécutent sans action de l'utilisateur. Leur logique est souvent "
            "invisible et doit être documentée avec le métier.",
            [f"{t['module']}.{t['procedure']} : {t['when']}" for t in vba["auto_triggers"]][:10],
        ))
    if vba.get("error"):
        out.append(_finding("vba_unreadable", "warning", "Macros illisibles", vba["error"]))
    if feats.get("power_query") or feats.get("data_model") or feats.get("data_connections"):
        parts = [p for p, ok in (("Power Query", feats.get("power_query")),
                                 ("Modèle de données Power Pivot", feats.get("data_model")),
                                 ("Connexions de données", feats.get("data_connections"))) if ok]
        out.append(_finding(
            "data_sources", "warning", "Sources de données externes",
            "Le classeur importe des données depuis d'autres systèmes. Il faudra identifier ces sources "
            "et les brancher directement sur l'application.",
            parts,
        ))
    if f["hardcoded_constants_formulas"]:
        out.append(_finding(
            "hardcoded", "warning", "Valeurs en dur dans les formules",
            f"{f['hardcoded_constants_formulas']} formule(s) contiennent des nombres saisis directement "
            "(taux, seuils, coefficients…). Dans l'application, ils deviendront des paramètres modifiables.",
            f["hardcoded_examples"],
        ))
    if f["volatile_formulas"]:
        out.append(_finding(
            "volatile", "warning", "Fonctions volatiles",
            f"{f['volatile_formulas']} formule(s) utilisent INDIRECT, DECALER, AUJOURDHUI… Elles se "
            "recalculent en permanence, ralentissent le fichier et rendent la logique difficile à suivre.",
            f["volatile_examples"],
        ))
    if f["max_nesting_depth"] >= 5:
        out.append(_finding(
            "nesting", "warning", "Formules très imbriquées",
            f"Une formule imbrique {f['max_nesting_depth']} fonctions. Ces règles sont difficiles à "
            "maintenir : elles seront découpées en étapes claires.",
            [f["deepest_formula"]] if f["deepest_formula"] else [],
        ))
    mixed = [f"{e['name']} › {c['name']}" for e in report["entities"] for c in e["columns"] if c["type"] == "mixed"]
    if mixed:
        out.append(_finding(
            "mixed_columns", "warning", "Colonnes au contenu hétérogène",
            "Ces colonnes mélangent des types (texte, nombres, dates…). Les données devront être "
            "nettoyées lors de la reprise.",
            mixed[:10],
        ))
    broken_names = [n["name"] for n in report["names"] if n["broken"]]
    if broken_names:
        out.append(_finding(
            "broken_names", "warning", "Noms définis cassés",
            "Des plages nommées pointent vers des cellules supprimées (#REF!).", broken_names[:10],
        ))
    very_hidden = [sh["name"] for sh in report["sheets"] if sh["state"] == "veryHidden"]
    if very_hidden:
        out.append(_finding(
            "very_hidden", "warning", "Feuilles super-masquées",
            "Ces feuilles sont invisibles même via le menu « Afficher » d'Excel (masquées par macro). "
            "Elles contiennent souvent des paramètres ou des données de référence.",
            very_hidden,
        ))
    hidden = [sh["name"] for sh in report["sheets"] if sh["state"] == "hidden"]
    if hidden:
        out.append(_finding(
            "hidden", "info", "Feuilles masquées",
            "Ces feuilles sont masquées. À examiner : elles servent souvent de tables de paramètres.", hidden,
        ))
    protected = [sh["name"] for sh in report["sheets"] if sh["protected"]]
    if protected or report.get("workbook_protected"):
        out.append(_finding(
            "protection", "info", "Protections en place",
            "Le fichier utilise des protections pour limiter les modifications. Dans l'application, "
            "elles seront remplacées par des droits par utilisateur et un historique des modifications.",
            protected + (["Structure du classeur"] if report.get("workbook_protected") else []),
        ))
    if feats.get("activex_controls"):
        out.append(_finding(
            "activex", "warning", "Contrôles ActiveX",
            "Les contrôles ActiveX ne fonctionnent que sous Windows et sont souvent bloqués par la "
            "sécurité : à remplacer par des formulaires web.",
        ))
    if report["file"]["format"] in {"xls", "xlt"}:
        out.append(_finding(
            "legacy_format", "info", "Format ancien (.xls)",
            "Format Excel 97-2003. L'analyse est partielle : enregistrez le fichier en .xlsx/.xlsm pour "
            "un diagnostic complet des formules.",
        ))
    if not report["entities"]:
        out.append(_finding(
            "no_table", "info", "Aucun tableau de données détecté",
            "Le classeur ne contient pas de tableau structuré reconnaissable (en-têtes + lignes). Il s'agit "
            "peut-être d'un formulaire ou d'un rapport mis en page : la modélisation se fera avec le métier.",
        ))
    out.sort(key=lambda x: SEVERITY_ORDER[x["severity"]])
    return out


def build_migration_plan(report: dict) -> list[dict]:
    s, f, vba = report["summary"], report["formulas"], report["vba"]
    plan: list[dict] = []

    if report["entities"]:
        items = [
            (f"Table « {e['entity']} » ({len(e['columns'])} champs, {e['rows']} ligne(s)) — source : {e['name']}"
             if e.get("kind") != "view" else
             f"Vue calculée « {e['entity']} » (rapport recalculé automatiquement) — source : {e['name']}")
            for e in report["entities"]
        ]
        items += [f"Relation : {r['label']}" for r in report.get("relations", [])]
        plan.append({"step": "Modèle de données", "icon": "database",
                     "description": "Chaque tableau devient une table de base de données, avec des types contrôlés.",
                     "items": items})

    form_items = []
    for e in report["entities"]:
        if e.get("kind") == "view":
            continue
        enums = [c["name"] for c in e["columns"] if c["type"] == "enum"]
        inputs = [c for c in e["columns"] if not c["computed"] and c["type"] != "empty"]
        if inputs:
            line = f"Formulaire « {e['name']} » : {len(inputs)} champ(s) de saisie"
            if enums:
                line += f", listes déroulantes : {', '.join(enums[:5])}"
            form_items.append(line)
    if report["validations"]:
        form_items.append(f"{len(report['validations'])} règle(s) de validation Excel reprises comme contrôles de saisie")
    if form_items:
        plan.append({"step": "Formulaires de saisie", "icon": "form",
                     "description": "La saisie se fait dans des formulaires web qui empêchent les erreurs.",
                     "items": form_items})

    if f["total"]:
        top = ", ".join(x["name"] for x in f["top_functions"][:6])
        items = [f"{f['unique']} règle(s) de calcul distinctes (sur {f['total']} formules)"]
        if top:
            items.append(f"Fonctions principales : {top}")
        if f["hardcoded_constants_formulas"]:
            items.append("Les valeurs en dur deviennent des paramètres administrables")
        items.append("Chaque règle est testée automatiquement contre les résultats actuels du fichier Excel")
        plan.append({"step": "Règles de calcul", "icon": "calc",
                     "description": "Les formules sont réécrites en calculs serveur fiables et testés.",
                     "items": items})

    if vba["intents"]:
        plan.append({"step": "Automatisations", "icon": "bolt",
                     "description": "Les macros VBA sont remplacées par des automatisations web.",
                     "items": [f"{i['label']} → {i['web_equivalent']}" for i in vba["intents"]]})
    elif vba["lines_of_code"]:
        plan.append({"step": "Automatisations", "icon": "bolt",
                     "description": "Les macros VBA sont remplacées par des automatisations web.",
                     "items": [f"{vba['lines_of_code']} lignes de VBA à analyser avec le métier"]})

    if s["charts"] or s["pivot_tables"]:
        plan.append({"step": "Tableaux de bord", "icon": "chart",
                     "description": "Les graphiques et TCD deviennent des tableaux de bord à jour en temps réel.",
                     "items": [f"{s['charts']} graphique(s) et {s['pivot_tables']} tableau(x) croisé(s) dynamique(s)"]})

    plan.append({"step": "Droits, historique et sécurité", "icon": "shield",
                 "description": "Ce qu'Excel ne sait pas faire : qui peut voir et modifier quoi, et qui a changé quoi.",
                 "items": ["Connexion via l'annuaire de l'entreprise (SSO)",
                           "Rôles : lecture, saisie, validation, administration",
                           "Journal d'audit de chaque modification",
                           "Export Excel conservé pour les utilisateurs"]})

    rows_to_import = sum(e["rows"] for e in report["entities"] if e.get("kind") != "view")
    reprise = [f"Import des {rows_to_import} ligne(s) existantes"] if rows_to_import else []
    if any(c["type"] == "mixed" for e in report["entities"] for c in e["columns"]):
        reprise.append("Nettoyage des colonnes hétérogènes")
    if f.get("computed_errors"):
        reprise.append("Correction des cellules en erreur")
    if reprise:
        plan.append({"step": "Reprise des données", "icon": "upload",
                     "description": "Les données actuelles sont importées et contrôlées.", "items": reprise})
    return plan
