"""Stockage et exécution des applications générées (SQLite, une base par application).

Chaque application est un dossier : spec.json (description) + app.db (données,
paramètres, historique). Toute écriture passe par ce module, qui contrôle les
saisies, recalcule les champs calculés (et, en cascade, ceux des tables qui en
dépendent) et trace chaque modification dans l'historique.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .engine import Context, dependencies, evaluate, from_json
from .generate import GeneratedApp, jsonable

DEFAULT_DIR = Path(os.environ.get("EXCEL_AUTO_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,32}$")
IDENT_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
MAX_PAGE = 200
MAX_TEXT = 10_000
NUMERIC = {"integer", "decimal", "currency", "percent"}

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


class StoreError(Exception):
    status = 400


class NotFound(StoreError):
    status = 404


class Conflict(StoreError):
    status = 409


class ValidationError(StoreError):
    status = 422

    def __init__(self, errors: dict[str, str]):
        super().__init__("Saisie invalide")
        self.errors = errors


def _lock(project_id: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(project_id, threading.RLock())


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Conversions de valeurs
# --------------------------------------------------------------------------- #


def to_db(value: Any, ftype: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if ftype == "date" else value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value) if ftype == "boolean" else ("VRAI" if value else "FAUX")
    if isinstance(value, (int, float)) and ftype == "text":
        return int(value) if isinstance(value, float) and value.is_integer() else value
    return value


def from_db(value: Any, ftype: str) -> Any:
    if value is None:
        return None
    if ftype in ("date", "datetime") and isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value)
        except ValueError:
            return value
    if ftype == "boolean" and isinstance(value, int):
        return bool(value)
    return value


def to_api(value: Any, ftype: str) -> Any:
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if ftype == "date" else value.isoformat()
    return jsonable(value)


def parse_input(raw: Any, field: dict) -> Any:
    """Valeur saisie (JSON) -> valeur Python typée. Lève ValueError avec un message clair."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    ftype = field["type"]
    if ftype == "integer":
        try:
            number = float(str(raw).replace(",", ".").replace(" ", "")) if not isinstance(raw, (int, float)) else raw
        except ValueError:
            raise ValueError("Nombre entier attendu") from None
        if isinstance(number, bool) or not float(number).is_integer():
            raise ValueError("Nombre entier attendu")
        return int(number)
    if ftype in NUMERIC:
        if isinstance(raw, bool):
            raise ValueError("Nombre attendu")
        try:
            number = float(raw) if isinstance(raw, (int, float)) else float(str(raw).replace(",", ".").replace(" ", ""))
        except ValueError:
            raise ValueError("Nombre attendu") from None
        if number != number or number in (float("inf"), float("-inf")):
            raise ValueError("Nombre attendu")
        return number
    if ftype in ("date", "datetime"):
        try:
            value = dt.datetime.fromisoformat(str(raw).strip())
        except ValueError:
            raise ValueError("Date attendue (AAAA-MM-JJ)") from None
        return value.replace(tzinfo=None)
    if ftype == "boolean":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in ("true", "1", "oui", "vrai"):
            return True
        if text in ("false", "0", "non", "faux"):
            return False
        raise ValueError("Oui ou non attendu")
    text = str(raw).strip()
    if len(text) > MAX_TEXT:
        raise ValueError(f"Texte trop long (maximum {MAX_TEXT} caractères)")
    return text


# --------------------------------------------------------------------------- #
# Magasin d'applications
# --------------------------------------------------------------------------- #


class ProjectStore:
    def __init__(self, base: Path | str = DEFAULT_DIR):
        self.base = Path(base)

    def _dir(self, project_id: str) -> Path:
        if not ID_RE.match(project_id or ""):
            raise NotFound("Application introuvable")
        return self.base / project_id

    def create(self, app: GeneratedApp) -> str:
        project_id = secrets.token_urlsafe(12)  # 16 caractères, impossible à deviner
        path = self.base / project_id
        path.mkdir(parents=True, exist_ok=False)
        spec = dict(app.spec, id=project_id, created_at=_now())
        try:
            _initialize(path, spec, app.rows)
        except Exception:
            shutil.rmtree(path, ignore_errors=True)
            raise
        return project_id

    def list(self) -> list[dict]:
        if not self.base.exists():
            return []
        items = []
        for d in self.base.iterdir():
            spec_file = d / "spec.json"
            if not (ID_RE.match(d.name) and spec_file.exists()):
                continue
            try:
                spec = json.loads(spec_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            items.append({
                "id": spec["id"], "title": spec["title"], "created_at": spec["created_at"],
                "source": spec["source"]["filename"], "entities": len(spec["entities"]),
                "rows": spec["generation"]["rows"],
            })
        return sorted(items, key=lambda x: x["created_at"], reverse=True)

    def open(self, project_id: str) -> "Project":
        path = self._dir(project_id)
        if not (path / "spec.json").exists():
            raise NotFound("Application introuvable")
        return Project(path)

    def delete(self, project_id: str) -> None:
        path = self._dir(project_id)
        if not path.exists():
            raise NotFound("Application introuvable")
        with _lock(project_id):
            shutil.rmtree(path)


def _table(entity: str) -> str:
    if not IDENT_RE.match(entity):
        raise StoreError(f"identifiant invalide : {entity}")
    return f'"e_{entity}"'


def _col(field: str) -> str:
    if not IDENT_RE.match(field):
        raise StoreError(f"identifiant invalide : {field}")
    return f'"f_{field}"'


def _initialize(path: Path, spec: dict, rows: dict[str, list[dict]]) -> None:
    con = sqlite3.connect(path / "app.db")
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE _params (name TEXT PRIMARY KEY, value TEXT)")
        con.execute("CREATE TABLE _audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, entity TEXT, "
                    "row_id INTEGER, action TEXT, summary TEXT, changes TEXT)")
        for p in spec["parameters"]:
            con.execute("INSERT INTO _params VALUES (?, ?)", (p["name"], json.dumps(p["value"])))
        for es in spec["entities"]:
            cols = ", ".join(_col(f["name"]) for f in es["fields"])
            con.execute(f"CREATE TABLE {_table(es['name'])} (_id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
            if es.get("primary_key"):
                con.execute(f"CREATE UNIQUE INDEX \"u_{es['name']}\" ON {_table(es['name'])} ({_col(es['primary_key'])})")
            types = {f["name"]: f["type"] for f in es["fields"]}
            names = [f["name"] for f in es["fields"]]
            placeholders = ", ".join("?" for _ in names)
            con.executemany(
                f"INSERT INTO {_table(es['name'])} ({', '.join(_col(n) for n in names)}) VALUES ({placeholders})",
                [[to_db(r.get(n), types[n]) for n in names] for r in rows.get(es["name"], [])],
            )
        con.execute("INSERT INTO _audit (ts, entity, row_id, action, summary, changes) VALUES (?, NULL, NULL, ?, ?, ?)",
                    (spec["created_at"], "import",
                     f"Application générée depuis « {spec['source']['filename']} » "
                     f"({spec['generation']['rows']} ligne(s) importée(s))", "{}"))
        con.commit()
    finally:
        con.close()
    (path / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Une application
# --------------------------------------------------------------------------- #


class Project:
    def __init__(self, path: Path):
        self.path = path
        self.id = path.name
        self.spec = json.loads((path / "spec.json").read_text(encoding="utf-8"))
        self.entities = {es["name"]: es for es in self.spec["entities"]}
        self.rules: dict[tuple[str, str], Any] = {}
        for es in self.spec["entities"]:
            for f in es["fields"]:
                rule = f.get("rule")
                if rule and rule.get("ast") and rule["status"] != "unsupported":
                    self.rules[(es["name"], f["name"])] = from_json(rule["ast"])
        # Tables qui doivent être recalculées quand une table (ou un paramètre) change.
        self.dependents: dict[str, set[str]] = {}
        self.param_users: dict[str, set[str]] = {}
        for (ent, _), ast in self.rules.items():
            deps = dependencies(ast)
            for target in deps["entities"]:
                self.dependents.setdefault(target, set()).add(ent)
            for p in deps["params"]:
                self.param_users.setdefault(p, set()).add(ent)

    # -- outils ---------------------------------------------------------------
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Connexion validée en fin de bloc, annulée en cas d'erreur, toujours fermée."""
        con = sqlite3.connect(self.path / "app.db", timeout=30)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def entity(self, name: str) -> dict:
        if name not in self.entities:
            raise NotFound(f"Table « {name} » introuvable")
        return self.entities[name]

    def is_computed(self, entity: str, field: str) -> bool:
        return (entity, field) in self.rules

    def _fields(self, entity: str) -> dict[str, dict]:
        return {f["name"]: f for f in self.entity(entity)["fields"]}

    def _decode(self, entity: str, row: sqlite3.Row) -> dict:
        types = {f["name"]: f["type"] for f in self.entity(entity)["fields"]}
        out = {"_id": row["_id"]}
        for name, ftype in types.items():
            out[name] = from_db(row[f"f_{name}"], ftype)
        return out

    def _all_rows(self, con, entity: str) -> list[dict]:
        cur = con.execute(f"SELECT * FROM {_table(entity)} ORDER BY _id")
        return [self._decode(entity, r) for r in cur]

    def _params(self, con) -> dict[str, Any]:
        types = {p["name"]: p["type"] for p in self.spec["parameters"]}
        values = {}
        for r in con.execute("SELECT name, value FROM _params"):
            value = json.loads(r["value"])
            values[r["name"]] = from_db(value, types.get(r["name"], "text"))
        return values

    def _audit(self, con, entity: str | None, row_id: int | None, action: str, summary: str, changes: dict) -> None:
        con.execute("INSERT INTO _audit (ts, entity, row_id, action, summary, changes) VALUES (?, ?, ?, ?, ?, ?)",
                    (_now(), entity, row_id, action, summary, json.dumps(changes, ensure_ascii=False)))

    def _label_of(self, entity: str, row: dict) -> str:
        es = self.entity(entity)
        key = es.get("primary_key") or es["fields"][0]["name"]
        value = row.get(key)
        return str(to_api(value, self._fields(entity)[key]["type"])) if value is not None else f"n°{row.get('_id')}"

    # -- lecture --------------------------------------------------------------
    def public_spec(self) -> dict:
        return self.spec

    def counts(self) -> dict[str, int]:
        with self._connect() as con:
            return {name: con.execute(f"SELECT COUNT(*) FROM {_table(name)}").fetchone()[0] for name in self.entities}

    def list_rows(self, entity: str, q: str = "", sort: str | None = None, desc: bool = False,
                  offset: int = 0, limit: int = 50) -> dict:
        fields = self._fields(entity)
        limit = max(1, min(int(limit), MAX_PAGE))
        offset = max(0, int(offset))
        where, args = "", []
        if q:
            terms = [t for t in q.split() if t][:5]
            clauses = []
            for term in terms:
                like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                clauses.append("(" + " OR ".join(f"CAST({_col(f)} AS TEXT) LIKE ? ESCAPE '\\'" for f in fields) + ")")
                args.extend([like] * len(fields))
            where = "WHERE " + " AND ".join(clauses)
        order = "_id"
        if sort:
            if sort not in fields:
                raise StoreError(f"Tri impossible : champ « {sort} » inconnu")
            order = f"{_col(sort)} IS NULL, {_col(sort)}"
        direction = "DESC" if desc else "ASC"
        with self._connect() as con:
            total = con.execute(f"SELECT COUNT(*) FROM {_table(entity)} {where}", args).fetchone()[0]
            cur = con.execute(
                f"SELECT * FROM {_table(entity)} {where} ORDER BY {order} {direction}, _id {direction} LIMIT ? OFFSET ?",
                args + [limit, offset],
            )
            rows = [self._serialize(entity, self._decode(entity, r)) for r in cur]
        return {"total": total, "offset": offset, "limit": limit, "rows": rows}

    def _serialize(self, entity: str, row: dict) -> dict:
        types = {f["name"]: f["type"] for f in self.entity(entity)["fields"]}
        return {"_id": row["_id"], **{k: to_api(row.get(k), t) for k, t in types.items()}}

    def get_row(self, entity: str, row_id: int) -> dict:
        with self._connect() as con:
            row = self._fetch(con, entity, row_id)
        return self._serialize(entity, row)

    def _fetch(self, con, entity: str, row_id: int) -> dict:
        r = con.execute(f"SELECT * FROM {_table(entity)} WHERE _id = ?", (int(row_id),)).fetchone()
        if r is None:
            raise NotFound("Ligne introuvable")
        return self._decode(entity, r)

    # -- écriture -------------------------------------------------------------
    def insert(self, entity: str, data: dict) -> dict:
        with _lock(self.id), self._connect() as con:
            row = self._validated(con, entity, data, current=None)
            self._compute_row(con, entity, row)
            names = [f["name"] for f in self.entity(entity)["fields"]]
            types = {f["name"]: f["type"] for f in self.entity(entity)["fields"]}
            cur = con.execute(
                f"INSERT INTO {_table(entity)} ({', '.join(_col(n) for n in names)}) "
                f"VALUES ({', '.join('?' for _ in names)})",
                [to_db(row.get(n), types[n]) for n in names],
            )
            row["_id"] = cur.lastrowid
            self._audit(con, entity, row["_id"], "create", f"Ajout de « {self._label_of(entity, row)} »",
                        {n: [None, to_api(row.get(n), types[n])] for n in names if row.get(n) is not None})
            self._cascade(con, {entity}, include_self=True)
            con.commit()
            return self._serialize(entity, self._fetch(con, entity, row["_id"]))

    def update(self, entity: str, row_id: int, data: dict) -> dict:
        with _lock(self.id), self._connect() as con:
            before = self._fetch(con, entity, row_id)
            row = self._validated(con, entity, data, current=before)
            self._compute_row(con, entity, row)
            types = {f["name"]: f["type"] for f in self.entity(entity)["fields"]}
            changes = {n: [to_api(before.get(n), t), to_api(row.get(n), t)]
                       for n, t in types.items() if to_db(before.get(n), t) != to_db(row.get(n), t)}
            if changes:
                sets = ", ".join(f"{_col(n)} = ?" for n in changes)
                con.execute(f"UPDATE {_table(entity)} SET {sets} WHERE _id = ?",
                            [to_db(row.get(n), types[n]) for n in changes] + [int(row_id)])
                self._audit(con, entity, int(row_id), "update",
                            f"Modification de « {self._label_of(entity, row)} »", changes)
                self._cascade(con, {entity}, include_self=True)
                con.commit()
            return self._serialize(entity, self._fetch(con, entity, row_id))

    def delete(self, entity: str, row_id: int) -> None:
        with _lock(self.id), self._connect() as con:
            row = self._fetch(con, entity, row_id)
            es = self.entity(entity)
            pk = es.get("primary_key")
            if pk and row.get(pk) is not None:
                for other in self.entities.values():
                    for f in other["fields"]:
                        ref = f.get("references")
                        if ref and ref["entity"] == entity and ref["field"] == pk:
                            n = con.execute(f"SELECT COUNT(*) FROM {_table(other['name'])} WHERE {_col(f['name'])} = ?",
                                            (to_db(row[pk], self._fields(entity)[pk]["type"]),)).fetchone()[0]
                            if n:
                                raise Conflict(f"Impossible de supprimer « {self._label_of(entity, row)} » : "
                                               f"utilisé par {n} ligne(s) de « {other['label']} ».")
            con.execute(f"DELETE FROM {_table(entity)} WHERE _id = ?", (int(row_id),))
            types = {f["name"]: f["type"] for f in es["fields"]}
            self._audit(con, entity, int(row_id), "delete", f"Suppression de « {self._label_of(entity, row)} »",
                        {n: [to_api(row.get(n), t), None] for n, t in types.items() if row.get(n) is not None})
            self._cascade(con, {entity}, include_self=True)
            con.commit()

    def _validated(self, con, entity: str, data: dict, current: dict | None) -> dict:
        if not isinstance(data, dict):
            raise ValidationError({"_": "Données invalides"})
        es = self.entity(entity)
        row = dict(current) if current else {f["name"]: None for f in es["fields"]}
        errors: dict[str, str] = {}
        for f in es["fields"]:
            name = f["name"]
            if self.is_computed(entity, name):
                continue  # calculé : jamais saisi
            if current is not None and name not in data:
                continue  # mise à jour partielle
            try:
                value = parse_input(data.get(name), f)
            except ValueError as exc:
                errors[name] = str(exc)
                continue
            if value is None and f.get("required"):
                errors[name] = "Champ obligatoire"
                continue
            if value is not None and f.get("strict_choices") and f.get("choices") and str(value) not in f["choices"]:
                errors[name] = "Valeur hors de la liste autorisée"
                continue
            if value is not None and f.get("references"):
                ref = f["references"]
                target_type = self._fields(ref["entity"])[ref["field"]]["type"]
                exists = con.execute(
                    f"SELECT 1 FROM {_table(ref['entity'])} WHERE {_col(ref['field'])} = ? LIMIT 1",
                    (to_db(parse_input(value, {"type": target_type}), target_type),),
                ).fetchone()
                if not exists:
                    errors[name] = f"« {value} » n'existe pas dans « {self.entity(ref['entity'])['label']} »"
                    continue
            if value is not None and f.get("unique"):
                clash = con.execute(
                    f"SELECT 1 FROM {_table(entity)} WHERE {_col(name)} = ? AND _id != ? LIMIT 1",
                    (to_db(value, f["type"]), current["_id"] if current else -1),
                ).fetchone()
                if clash:
                    errors[name] = "Cette valeur existe déjà"
                    continue
            row[name] = value
        if errors:
            raise ValidationError(errors)
        return row

    def _context(self, con, row: dict) -> Context:
        cache: dict[str, list[dict]] = {}

        def rows_of(ent: str) -> list[dict]:
            if ent not in cache:
                cache[ent] = self._all_rows(con, ent)
            return cache[ent]

        return Context(row, self._params(con), rows_of)

    def _compute_row(self, con, entity: str, row: dict) -> None:
        order = self.entity(entity).get("compute_order", [])
        ctx = self._context(con, row)
        for name in order:
            ast = self.rules.get((entity, name))
            if ast is not None:
                row[name] = evaluate(ast, ctx)

    def _cascade(self, con, changed: set[str], include_self: bool = False) -> None:
        """Recalcule toutes les lignes des tables qui dépendent des tables modifiées."""
        todo: list[str] = []
        queue = list(changed)
        while queue:
            ent = queue.pop(0)
            for dep in sorted(self.dependents.get(ent, ())):
                if dep not in todo and (include_self or dep not in changed):
                    todo.append(dep)
                    queue.append(dep)
        for ent in todo:
            self._recompute_all(con, ent)

    def _recompute_all(self, con, entity: str) -> int:
        order = [n for n in self.entity(entity).get("compute_order", []) if (entity, n) in self.rules]
        if not order:
            return 0
        types = {f["name"]: f["type"] for f in self.entity(entity)["fields"]}
        rows = self._all_rows(con, entity)
        ctx = self._context(con, {})
        updates = []
        for row in rows:
            ctx.row = row
            before = {n: to_db(row.get(n), types[n]) for n in order}
            for n in order:
                row[n] = evaluate(self.rules[(entity, n)], ctx)
            after = {n: to_db(row.get(n), types[n]) for n in order}
            if after != before:
                updates.append([after[n] for n in order] + [row["_id"]])
        if updates:
            sets = ", ".join(f"{_col(n)} = ?" for n in order)
            con.executemany(f"UPDATE {_table(entity)} SET {sets} WHERE _id = ?", updates)
        return len(updates)

    # -- paramètres -----------------------------------------------------------
    def parameters(self) -> list[dict]:
        with self._connect() as con:
            values = self._params(con)
        return [dict(p, value=to_api(values.get(p["name"]), p["type"])) for p in self.spec["parameters"]]

    def set_parameter(self, name: str, raw: Any) -> dict:
        spec = next((p for p in self.spec["parameters"] if p["name"] == name), None)
        if spec is None:
            raise NotFound("Paramètre introuvable")
        try:
            value = parse_input(raw, {"type": spec["type"]})
        except ValueError as exc:
            raise ValidationError({"value": str(exc)}) from None
        if value is None:
            raise ValidationError({"value": "Valeur obligatoire"})
        with _lock(self.id), self._connect() as con:
            old = self._params(con).get(name)
            con.execute("UPDATE _params SET value = ? WHERE name = ?", (json.dumps(to_api(value, spec["type"])), name))
            self._audit(con, None, None, "parameter", f"Paramètre modifié : {spec['label']}",
                        {name: [to_api(old, spec["type"]), to_api(value, spec["type"])]})
            recomputed = 0
            users = sorted(self.param_users.get(name, ()))
            for ent in users:
                recomputed += self._recompute_all(con, ent)
            self._cascade(con, set(users))
            con.commit()
        return {"name": name, "value": to_api(value, spec["type"]), "recomputed_rows": recomputed}

    # -- historique et export ---------------------------------------------------
    def history(self, entity: str | None = None, offset: int = 0, limit: int = 50) -> dict:
        limit = max(1, min(int(limit), MAX_PAGE))
        where, args = ("WHERE entity = ?", [entity]) if entity else ("", [])
        with self._connect() as con:
            total = con.execute(f"SELECT COUNT(*) FROM _audit {where}", args).fetchone()[0]
            cur = con.execute(f"SELECT * FROM _audit {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                              args + [limit, max(0, int(offset))])
            items = [{"id": r["id"], "ts": r["ts"], "entity": r["entity"], "row_id": r["row_id"],
                      "action": r["action"], "summary": r["summary"], "changes": json.loads(r["changes"] or "{}")}
                     for r in cur]
        return {"total": total, "items": items}

    def export_xlsx(self) -> bytes:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        formats = {"date": "dd/mm/yyyy", "datetime": "dd/mm/yyyy hh:mm", "currency": '#,##0.00 "€"',
                   "percent": "0.00%", "decimal": "#,##0.####", "integer": "0"}
        wb = Workbook()
        wb.remove(wb.active)
        used: set[str] = set()
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1F7A4D")
        with self._connect() as con:
            for es in self.spec["entities"]:
                title = re.sub(r"[\[\]:*?/\\]", " ", es["label"])[:31] or es["name"]
                while title in used:
                    title = title[:28] + f"_{len(used)}"
                used.add(title)
                ws = wb.create_sheet(title)
                ws.append([f["label"] for f in es["fields"]])
                for cell in ws[1]:
                    cell.font, cell.fill = header_font, header_fill
                for row in self._all_rows(con, es["name"]):
                    ws.append([row.get(f["name"]) for f in es["fields"]])
                    for cell in ws[ws.max_row]:
                        if isinstance(cell.value, str) and cell.value.startswith("="):
                            cell.data_type = "s"  # un texte saisi n'est jamais exporté comme formule
                for i, f in enumerate(es["fields"], start=1):
                    fmt = formats.get(f["type"])
                    letter = ws.cell(row=1, column=i).column_letter
                    ws.column_dimensions[letter].width = max(12, min(40, len(f["label"]) + 4))
                    if fmt:
                        for (cell,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                            cell.number_format = fmt
                ws.freeze_panes = "A2"
                ws.auto_filter.ref = ws.dimensions
            if self.spec["parameters"]:
                title = "Paramètres de calcul"
                while title in used:
                    title = title[:28] + f"_{len(used)}"
                ws = wb.create_sheet(title)
                ws.append(["Paramètre", "Valeur", "Origine"])
                for cell in ws[1]:
                    cell.font, cell.fill = header_font, header_fill
                values = self._params(con)
                for p in self.spec["parameters"]:
                    ws.append([p["label"], values.get(p["name"]), p["source"]])
                ws.column_dimensions["A"].width = 40
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
