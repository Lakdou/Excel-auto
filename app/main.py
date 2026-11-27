"""API web d'Excel Auto.

Lancement local :  uvicorn app.main:app --reload
Les fichiers sont analysés en mémoire et ne sont jamais enregistrés sur le serveur.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .analyzer import SUPPORTED_EXTENSIONS, AnalysisError, analyze_bytes

logger = logging.getLogger("excel_auto")

MAX_UPLOAD_MB = int(os.environ.get("EXCEL_AUTO_MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Excel Auto",
    version=__version__,
    description="Diagnostic de classeurs Excel en vue de leur transformation en application web.",
)


APP_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
# La documentation interactive (Swagger / ReDoc) charge ses fichiers depuis un CDN avec du script inline.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "worker-src blob:; frame-ancestors 'none'; base-uri 'none'"
)
DOCS_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    csp = DOCS_CSP if request.url.path in DOCS_PATHS else APP_CSP
    response.headers.setdefault("Content-Security-Policy", csp)
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/config")
def config() -> dict:
    return {"max_upload_mb": MAX_UPLOAD_MB, "extensions": sorted(SUPPORTED_EXTENSIONS)}


@app.post("/api/analyze")
def analyze(file: UploadFile = File(...)) -> JSONResponse:
    # Fonction synchrone : FastAPI l'exécute dans un thread, l'analyse ne bloque pas le serveur.
    filename = Path(file.filename or "classeur.xlsx").name
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (maximum {MAX_UPLOAD_MB} Mo).")
    try:
        report = analyze_bytes(data, filename)
    except AnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:  # Ne jamais renvoyer de trace technique à l'utilisateur.
        logger.exception("Échec inattendu de l'analyse de %s", filename)
        raise HTTPException(
            status_code=500,
            detail="L'analyse a échoué de manière inattendue. Le fichier est peut-être endommagé.",
        )
    return JSONResponse(report)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
