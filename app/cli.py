"""Analyse en ligne de commande, fichier par fichier ou tout un parc de classeurs.

Exemples :
    python -m app.cli classeur.xlsm                     # résumé lisible
    python -m app.cli classeur.xlsm --json rapport.json # rapport complet
    python -m app.cli //serveur/partage/finance --csv inventaire.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .analyzer import SUPPORTED_EXTENSIONS, AnalysisError, analyze_bytes

CSV_COLUMNS = [
    "fichier", "format", "taille_ko", "statut", "score", "niveau", "effort_min_j", "effort_max_j",
    "feuilles", "formules", "regles_distinctes", "tableaux", "lignes_macros", "liens_externes",
    "cellules_en_erreur", "points_critiques", "points_attention", "message",
]


def iter_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(
                f for f in sorted(p.rglob("*"))
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS and not f.name.startswith("~$")
            )
        else:
            files.append(p)
    return files


def row_for(path: Path, report: dict | None, error: str | None) -> dict:
    if report is None:
        return {"fichier": str(path), "statut": "erreur", "message": error,
                "taille_ko": round(path.stat().st_size / 1024, 1) if path.exists() else ""}
    s, c = report["summary"], report["complexity"]
    sev = [f["severity"] for f in report["findings"]]
    return {
        "fichier": str(path),
        "format": report["file"]["format"],
        "taille_ko": round(report["file"]["size_bytes"] / 1024, 1),
        "statut": "ok",
        "score": c["score"],
        "niveau": c["level_label"],
        "effort_min_j": c["effort_days"]["low"],
        "effort_max_j": c["effort_days"]["high"],
        "feuilles": s["sheets"],
        "formules": s["formulas"],
        "regles_distinctes": s["unique_formulas"],
        "tableaux": s["tables_detected"],
        "lignes_macros": s["vba_lines"],
        "liens_externes": s["external_links"],
        "cellules_en_erreur": report["formulas"].get("computed_errors", 0),
        "points_critiques": sev.count("critical"),
        "points_attention": sev.count("warning"),
        "message": "; ".join(report["limitations"]),
    }


def _fr(value):
    """Décimales à la française pour qu'Excel FR lise 4,5 comme un nombre (et pas une date)."""
    return f"{value:g}".replace(".", ",") if isinstance(value, float) else value


def print_summary(path: Path, report: dict) -> None:
    s, c = report["summary"], report["complexity"]
    print(f"\n{path}")
    print(f"  {report['file']['format_label']} — complexité {c['score']}/100 ({c['level_label']}), "
          f"effort estimé {_fr(c['effort_days']['low'])} à {_fr(c['effort_days']['high'])} j")
    print(f"  {s['sheets']} feuille(s), {s['formulas']} formule(s) dont {s['unique_formulas']} distincte(s), "
          f"{s['tables_detected']} tableau(x), {s['vba_lines']} ligne(s) de VBA")
    for f in report["findings"]:
        marker = {"critical": "[CRITIQUE]", "warning": "[ATTENTION]", "info": "[INFO]"}[f["severity"]]
        print(f"  {marker} {f['title']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="excel-auto", description="Diagnostic de classeurs Excel.")
    parser.add_argument("paths", nargs="+", help="Fichiers ou dossiers à analyser")
    parser.add_argument("--json", metavar="FICHIER", help="Rapport complet JSON (un fichier) ou liste (plusieurs)")
    parser.add_argument("--csv", metavar="FICHIER", help="Inventaire CSV (une ligne par classeur)")
    parser.add_argument("--quiet", action="store_true", help="N'affiche pas le résumé")
    args = parser.parse_args(argv)

    files = iter_files(args.paths)
    if not files:
        print("Aucun classeur Excel trouvé.", file=sys.stderr)
        return 2

    reports, rows, failures = [], [], 0
    for path in files:
        try:
            report = analyze_bytes(path.read_bytes(), path.name)
            error = None
        except (AnalysisError, OSError) as exc:
            report, error = None, str(exc)
            failures += 1
        rows.append(row_for(path, report, error))
        if report is not None:
            report["file"]["path"] = str(path)
            reports.append(report)
            if not args.quiet:
                print_summary(path, report)
        elif not args.quiet:
            print(f"\n{path}\n  [ERREUR] {error}")

    if args.json:
        payload = reports[0] if len(files) == 1 and reports else reports
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv:
        rows.sort(key=lambda r: -(r.get("score") or -1))
        # utf-8-sig + « ; » : s'ouvre directement et correctement dans Excel en français.
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, delimiter=";")
            writer.writeheader()
            writer.writerows({k: _fr(v) for k, v in r.items()} for r in rows)

    if not args.quiet:
        print(f"\n{len(files)} fichier(s) analysé(s), {failures} en erreur.")
    return 1 if failures == len(files) else 0


if __name__ == "__main__":
    raise SystemExit(main())
