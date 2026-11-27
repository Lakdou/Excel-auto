"""Génération d'une application à partir d'un classeur Excel.

Étapes : analyse du classeur -> tables et champs -> traduction des formules en
règles -> import des données -> recalcul de chaque règle sur chaque ligne et
comparaison avec les valeurs d'Excel (vérification) -> description de
l'application (spec) + lignes à enregistrer.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from openpyxl.utils.cell import range_boundaries

from ..analyzer import AnalysisError, analyze_bytes
from ..analyzer.formulas import analyze_formula
from .cells import MAX_IMPORT_ROWS, SheetCells
from .engine import VOLATILE, Context, Unsupported, dependencies, evaluate, parse, render, to_json
from .translate import EntityInfo, ParamRegistry, Translator

SPEC_VERSION = 1
FIELD_TYPES = {
    "integer": "integer", "decimal": "decimal", "currency": "currency", "percent": "percent",
    "date": "date", "datetime": "datetime", "boolean": "boolean",
    "text": "text", "enum": "text", "mixed": "text", "empty": "text", "time": "text", "duration": "text",
}
NUMERIC_TYPES = {"integer", "decimal", "currency", "percent"}
FORMULA_CONSISTENCY = 0.9  # part minimale des lignes partageant la même formule
PARTIAL_THRESHOLD = 0.8  # en dessous : règle rejetée


@dataclass
class GeneratedApp:
    spec: dict
    rows: dict[str, list[dict]]  # valeurs Python (dates en datetime) par table


# --------------------------------------------------------------------------- #
# Utilitaires de valeurs
# --------------------------------------------------------------------------- #


def jsonable(v: Any) -> Any:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def conforms(value: Any, ftype: str) -> bool:
    """La valeur importée respecte-t-elle le type du champ ?"""
    if value is None or value == "":
        return True
    if ftype in NUMERIC_TYPES:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if ftype in ("date", "datetime"):
        return isinstance(value, (dt.date, dt.datetime))
    if ftype == "boolean":
        return isinstance(value, bool)
    return True


def values_equal(app: Any, excel: Any) -> bool:
    """Comparaison tolérante (arrondis flottants, vide = chaîne vide, entiers = flottants)."""
    if app in (None, "") and excel in (None, ""):
        return True
    if isinstance(app, bool) or isinstance(excel, bool):
        return isinstance(app, bool) and isinstance(excel, bool) and app == excel
    if isinstance(app, (int, float)) and isinstance(excel, (int, float)):
        return math.isclose(app, excel, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(app, dt.datetime) and isinstance(excel, dt.datetime):
        return abs((app - excel).total_seconds()) < 1
    if isinstance(app, dt.date) and isinstance(excel, dt.date):
        return app == excel
    if isinstance(app, str) and isinstance(excel, str):
        return app == excel
    return False


def _title(filename: str) -> str:
    base = re.sub(r"\.[^.]+$", "", filename)
    return re.sub(r"[_\-]+", " ", base).strip().capitalize() or "Application"


def _topological(items: dict[str, set[str]]) -> tuple[list[str], set[str]]:
    """Tri topologique ; renvoie (ordre, éléments pris dans un cycle)."""
    order, done, cyclic = [], set(), set()

    def visit(node: str, stack: tuple[str, ...]):
        if node in done:
            return
        if node in stack:
            cyclic.update(stack[stack.index(node):])
            return
        for dep in sorted(items.get(node, ())):
            if dep in items:
                visit(dep, stack + (node,))
        if node not in done:
            done.add(node)
            order.append(node)

    for n in items:
        visit(n, ())
    return order, cyclic


# --------------------------------------------------------------------------- #
# Génération
# --------------------------------------------------------------------------- #


def build_application(data: bytes, filename: str, today: dt.date | None = None) -> GeneratedApp:
    report = analyze_bytes(data, filename)
    tables = [e for e in report["entities"] if e.get("kind") != "view"]
    if not tables:
        raise AnalysisError(
            "Aucun tableau de données exploitable n'a été trouvé dans ce classeur : impossible de générer "
            "une application. Il faut au moins un tableau avec une ligne d'en-têtes et des lignes de données."
        )
    cells = SheetCells(data, report["file"]["format"])
    warnings: list[str] = []

    infos: list[EntityInfo] = []
    for e in tables:
        min_col, min_row, max_col, max_row = range_boundaries(e["range"])
        info = EntityInfo(
            entity=e["entity"], label=e["name"], sheet=e["sheet"],
            table_name=e["name"] if e["source"] == "excel_table" else None,
            header_row=min_row, first_col=min_col, last_col=max_col, last_row=max_row,
        )
        for offset, col in enumerate(e["columns"]):
            info.col_to_field[min_col + offset] = col["field"]
            info.header_to_field[col["name"].strip().lower()] = col["field"]
        infos.append(info)
    # Deux tableaux peuvent produire le même identifiant : on les distingue.
    seen: Counter = Counter()
    for info, e in zip(infos, tables):
        seen[info.entity] += 1
        if seen[info.entity] > 1:
            info.entity = e["entity"] = f"{info.entity}_{seen[info.entity]}"

    names = {n["name"]: n["refers_to"] for n in report["names"] if n.get("refers_to")}
    params = ParamRegistry()
    translator = Translator(cells, infos, names, params)

    entity_specs: list[dict] = []
    rows_by_entity: dict[str, list[dict]] = {}
    source_rows: dict[str, list[int]] = {}
    rules: dict[tuple[str, str], Any] = {}

    for e, info in zip(tables, infos):
        sheet_rows = cells.sheet(info.sheet)
        if info.sheet in cells.truncated:
            warnings.append(f"« {info.label} » : seules les {MAX_IMPORT_ROWS} premières lignes sont importées.")
        rows: list[dict] = []
        formulas: dict[str, list[tuple[int, str | None]]] = {f: [] for f in info.col_to_field.values()}
        excel_rows: list[int] = []
        last = min(info.last_row, info.header_row + MAX_IMPORT_ROWS)
        for r in range(info.header_row + 1, last + 1):
            row_cells = sheet_rows.get(r)
            if not row_cells:
                continue
            values, any_value = {}, False
            for col, fname in info.col_to_field.items():
                value, formula = row_cells.get(col, (None, None))
                if isinstance(value, str) and not value.strip() and not formula:
                    value = None
                values[fname] = value
                formulas[fname].append((r, formula))
                any_value = any_value or value is not None or formula is not None
            if any_value:
                rows.append(values)
                excel_rows.append(r)
        rows_by_entity[info.entity] = rows
        source_rows[info.entity] = excel_rows

        fields = []
        validations = _validations_for(report["validations"], info, translator)
        pk = e.get("primary_key_candidate")
        for offset, col in enumerate(e["columns"]):
            fname = col["field"]
            ftype = FIELD_TYPES.get(col["type"], "text")
            fspec: dict[str, Any] = {
                "name": fname,
                "label": col["name"],
                "type": ftype,
                "required": col["fill_rate"] == 1.0 and not col["computed"] and col["type"] != "empty" and bool(rows),
                "unique": fname == pk,
            }
            if col.get("references"):
                fspec["references"] = col["references"]
            if fname in validations:
                fspec["choices"], fspec["strict_choices"] = validations[fname], True
            elif col.get("choices"):
                fspec["choices"], fspec["strict_choices"] = col["choices"], False
            if col["computed"]:
                rule = _translate_column(translator, info, fname, col["name"], info.first_col + offset,
                                         formulas[fname], params)
                fspec["rule"] = rule
                if rule.get("ast") is not None:
                    rules[(info.entity, fname)] = rule.pop("ast")
            fields.append(fspec)

        # Ordre de calcul dans la table ; une dépendance circulaire annule les règles concernées.
        graph = {f["name"]: dependencies(rules[(info.entity, f["name"])])["fields"]
                 for f in fields if (info.entity, f["name"]) in rules}
        order, cyclic = _topological(graph)
        for fname in cyclic:
            rules.pop((info.entity, fname), None)
            _reject(next(f for f in fields if f["name"] == fname), "dépendance circulaire entre colonnes calculées")
        entity_specs.append({
            "name": info.entity,
            "label": info.label,
            "source": f"{info.sheet}!{e['range']}",
            "primary_key": pk,
            "fields": fields,
            "compute_order": [f for f in order if f not in cyclic],
        })

    param_values = {p.name: p.value for p in params.params.values()}
    _verify_and_compute(entity_specs, rows_by_entity, source_rows, rules, param_values, today)

    labels = {(es["name"], f["name"]): f["label"] for es in entity_specs for f in es["fields"]}
    entity_labels = {es["name"]: es["label"] for es in entity_specs}
    summary = Counter()
    for es in entity_specs:
        for f in es["fields"]:
            rule = f.get("rule")
            if not rule:
                continue
            summary[rule["status"]] += 1
            ast = rules.get((es["name"], f["name"]))
            if ast is not None:
                rule["ast"] = to_json(ast)
                rule["display"] = render(
                    ast,
                    field_label=lambda name, ent=es["name"]: labels.get((ent, name), name),
                    param_label=lambda name: params.params[name].label if name in params.params else name,
                    entity_label=lambda ent, flds: f"{entity_labels.get(ent, ent)}["
                    + (" … ".join([labels.get((ent, flds[0]), flds[0]), labels.get((ent, flds[-1]), flds[-1])])
                       if len(flds) > 1 else labels.get((ent, flds[0]), flds[0])) + "]",
                )
                deps = dependencies(ast)
                rule["depends_on"] = {k: sorted(v) for k, v in deps.items() if k != "functions"}
                rule["functions"] = sorted(deps["functions"])
            else:
                f.pop("rule_status", None)
        _flag_anomalies(es, rows_by_entity[es["name"]], source_rows[es["name"]])

    views = [e["name"] for e in report["entities"] if e.get("kind") == "view"]
    if views:
        warnings.append("Rapports non générés (prochaine étape : tableaux de bord) : " + ", ".join(views) + ".")
    if report["vba"]["module_count"]:
        warnings.append("Les macros VBA ne sont pas converties automatiquement : voir le diagnostic.")

    spec = {
        "version": SPEC_VERSION,
        "title": _title(filename),
        "source": {
            "filename": filename,
            "format": report["file"]["format"],
            "sha256": report["file"]["sha256"],
        },
        "entities": entity_specs,
        "parameters": [
            {"name": p.name, "label": p.label, "value": jsonable(p.value), "type": _param_type(p.value),
             "source": p.source}
            for p in params.params.values() if _is_used(p.name, rules)
        ],
        "generation": {
            "entities": len(entity_specs),
            "rows": sum(len(r) for r in rows_by_entity.values()),
            "rules": {k: summary.get(k, 0) for k in ("verified", "partial", "volatile", "unverified", "unsupported")},
            "warnings": warnings,
        },
    }
    return GeneratedApp(spec=spec, rows=rows_by_entity)


def _is_used(param: str, rules: dict) -> bool:
    return any(param in dependencies(ast)["params"] for ast in rules.values())


def _param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "decimal"
    if isinstance(value, (dt.date, dt.datetime)):
        return "date"
    return "text"


def _reject(fspec: dict, reason: str) -> None:
    rule = fspec.setdefault("rule", {})
    rule.update({"status": "unsupported", "reason": reason})
    rule.pop("ast", None)


def _translate_column(translator: Translator, info: EntityInfo, fname: str, label: str, col: int,
                      formulas: list[tuple[int, str | None]], params: ParamRegistry) -> dict:
    present = [(r, f) for r, f in formulas if f]
    if not present:
        return {"status": "unsupported", "reason": "aucune formule trouvée"}
    signatures = Counter()
    first_row: dict[str, tuple[int, str]] = {}
    for r, f in present:
        sig = analyze_formula(f, r, col).signature
        signatures[sig] += 1
        first_row.setdefault(sig, (r, f))
    sig, count = signatures.most_common(1)[0]
    r0, formula = first_row[sig]
    rule: dict[str, Any] = {"excel": formula, "excel_row": r0}
    if count / len(present) < FORMULA_CONSISTENCY:
        rule.update(status="unsupported",
                    reason=f"la formule change d'une ligne à l'autre ({len(signatures)} variantes)")
        return rule
    snap = params.snapshot()
    try:
        rule["ast"] = parse(formula, translator.resolver(info, r0, label), translator.constant_hook(fname, label))
        rule["status"] = "pending"
    except Unsupported as exc:
        params.restore(snap)
        rule.update(status="unsupported", reason=str(exc))
    return rule


def _validations_for(validations: list[dict], info: EntityInfo, translator: Translator) -> dict[str, list[str]]:
    """Listes déroulantes Excel (validation de données) appliquées aux colonnes du tableau."""
    out: dict[str, list[str]] = {}
    for v in validations:
        if v["sheet"] != info.sheet or v["type"] != "list":
            continue
        for part in v["range"].split():
            try:
                c1, r1, c2, r2 = range_boundaries(part)
            except ValueError:
                continue
            if c1 != c2 or not info.contains_cols(c1, c1) or r2 <= info.header_row or r1 > info.last_row:
                continue
            choices = v.get("choices") or (translator.list_values(v["rule"], info.sheet) if v.get("rule") else None)
            if choices:
                out[info.col_to_field[c1]] = list(dict.fromkeys(choices))
    return out


def _verify_and_compute(entity_specs: list[dict], rows_by_entity: dict[str, list[dict]],
                        source_rows: dict[str, list[int]], rules: dict, params: dict,
                        today: dt.date | None) -> None:
    """Recalcule chaque règle et la compare aux valeurs enregistrées par Excel."""
    by_name = {es["name"]: es for es in entity_specs}
    graph = {
        es["name"]: {ent for (e_name, _), ast in rules.items() if e_name == es["name"]
                     for ent in dependencies(ast)["entities"] if ent != es["name"]}
        for es in entity_specs
    }
    order, _ = _topological(graph)

    def rows_of(entity: str) -> list[dict]:
        return rows_by_entity.get(entity, [])

    for ent in order:
        es = by_name[ent]
        rows = rows_by_entity[ent]
        fields = {f["name"]: f for f in es["fields"]}
        for fname in es["compute_order"]:
            ast = rules.get((ent, fname))
            if ast is None:
                continue
            rule = fields[fname]["rule"]
            ctx = Context({}, params, rows_of, today)
            computed, checked, matches, examples = [], 0, 0, []
            excel_cached = 0
            for i, row in enumerate(rows):
                ctx.row = row
                value = evaluate(ast, ctx)
                computed.append(value)
                excel_value = row.get(fname)
                if excel_value is not None:
                    excel_cached += 1
                checked += 1
                if values_equal(value, excel_value):
                    matches += 1
                elif len(examples) < 5:
                    examples.append({"row": source_rows[ent][i], "excel": jsonable(excel_value),
                                     "app": jsonable(value)})
            volatile = bool(VOLATILE & dependencies(ast)["functions"])
            rule["verification"] = {"checked": checked, "matches": matches, "examples": examples}
            if volatile:
                rule["status"] = "volatile"
            elif checked and excel_cached == 0:
                rule["status"] = "unverified"
            elif not checked or matches == checked:
                rule["status"] = "verified"
            elif matches / checked >= PARTIAL_THRESHOLD:
                rule["status"] = "partial"
            else:
                rule.update(status="unsupported",
                            reason=f"résultats différents d'Excel ({round(100 * matches / checked)} % identiques)")
                rules.pop((ent, fname))
                continue
            for row, value in zip(rows, computed):
                row[fname] = value


def _flag_anomalies(es: dict, rows: list[dict], source_rows: list[int]) -> None:
    """Valeurs importées qui ne respectent pas le type du champ : conservées mais signalées."""
    for f in es["fields"]:
        if f.get("rule", {}).get("status") not in (None, "unsupported"):
            continue
        bad = [(source_rows[i], row.get(f["name"])) for i, row in enumerate(rows) if not conforms(row.get(f["name"]), f["type"])]
        if bad:
            f["anomalies"] = {"count": len(bad), "examples": [{"row": r, "value": jsonable(v)} for r, v in bad[:5]]}
