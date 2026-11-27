"""API des applications générées : création depuis un fichier Excel, données, paramètres, historique."""

from __future__ import annotations

import hmac
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from .. import config
from ..analyzer import AnalysisError
from .generate import build_application
from .store import ProjectStore, StoreError, ValidationError

logger = logging.getLogger("excel_auto")
router = APIRouter(prefix="/api/projects", tags=["applications"])
store = ProjectStore(config.DATA_DIR)


def check_access(request: Request) -> None:
    code = config.ACCESS_CODE
    if code is None:
        return
    given = request.headers.get("x-access-code", "")
    if not hmac.compare_digest(given.encode(), code.encode()):
        raise HTTPException(status_code=401, detail="Code d'accès requis.")


def store_error_response(exc: StoreError) -> JSONResponse:
    body: dict[str, Any] = {"detail": str(exc)}
    if isinstance(exc, ValidationError):
        body["errors"] = exc.errors
    return JSONResponse(body, status_code=exc.status)


@router.get("")
def list_projects(request: Request) -> dict:
    check_access(request)
    return {"items": store.list(), "protected": config.ACCESS_CODE is not None}


@router.post("", status_code=201)
def create_project(request: Request, file: UploadFile = File(...)) -> dict:
    check_access(request)
    filename = Path(file.filename or "classeur.xlsx").name
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (maximum {config.MAX_UPLOAD_MB} Mo).")
    try:
        app = build_application(data, filename)
        project_id = store.create(app)
    except AnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Échec de la génération pour %s", filename)
        raise HTTPException(status_code=500, detail="La génération de l'application a échoué de manière inattendue.")
    return {"id": project_id, "title": app.spec["title"], "generation": app.spec["generation"]}


@router.get("/{project_id}")
def get_project(request: Request, project_id: str) -> dict:
    check_access(request)
    project = store.open(project_id)
    return {"spec": project.public_spec(), "counts": project.counts()}


@router.delete("/{project_id}", status_code=204)
def delete_project(request: Request, project_id: str) -> Response:
    check_access(request)
    store.delete(project_id)
    return Response(status_code=204)


@router.get("/{project_id}/entities/{entity}/rows")
def list_rows(request: Request, project_id: str, entity: str, q: str = Query("", max_length=200),
              sort: str | None = None, desc: bool = False, offset: int = Query(0, ge=0),
              limit: int = Query(50, ge=1, le=200)) -> dict:
    check_access(request)
    return store.open(project_id).list_rows(entity, q=q, sort=sort, desc=desc, offset=offset, limit=limit)


@router.get("/{project_id}/entities/{entity}/rows/{row_id}")
def get_row(request: Request, project_id: str, entity: str, row_id: int) -> dict:
    check_access(request)
    return store.open(project_id).get_row(entity, row_id)


@router.post("/{project_id}/entities/{entity}/rows", status_code=201)
def create_row(request: Request, project_id: str, entity: str, data: dict = Body(...)) -> dict:
    check_access(request)
    return store.open(project_id).insert(entity, data)


@router.patch("/{project_id}/entities/{entity}/rows/{row_id}")
def update_row(request: Request, project_id: str, entity: str, row_id: int, data: dict = Body(...)) -> dict:
    check_access(request)
    return store.open(project_id).update(entity, row_id, data)


@router.delete("/{project_id}/entities/{entity}/rows/{row_id}", status_code=204)
def delete_row(request: Request, project_id: str, entity: str, row_id: int) -> Response:
    check_access(request)
    store.open(project_id).delete(entity, row_id)
    return Response(status_code=204)


@router.get("/{project_id}/parameters")
def get_parameters(request: Request, project_id: str) -> dict:
    check_access(request)
    return {"items": store.open(project_id).parameters()}


@router.put("/{project_id}/parameters/{name}")
def set_parameter(request: Request, project_id: str, name: str, data: dict = Body(...)) -> dict:
    check_access(request)
    return store.open(project_id).set_parameter(name, data.get("value"))


@router.get("/{project_id}/history")
def history(request: Request, project_id: str, entity: str | None = None, offset: int = Query(0, ge=0),
            limit: int = Query(50, ge=1, le=200)) -> dict:
    check_access(request)
    return store.open(project_id).history(entity=entity, offset=offset, limit=limit)


@router.get("/{project_id}/export.xlsx")
def export(request: Request, project_id: str) -> Response:
    check_access(request)
    project = store.open(project_id)
    filename = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.spec["title"]) or "application"
    return Response(
        project.export_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )
