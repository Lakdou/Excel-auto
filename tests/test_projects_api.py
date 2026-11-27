import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.generator import api
from app.generator.store import ProjectStore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "store", ProjectStore(tmp_path))
    monkeypatch.setattr(config, "ACCESS_CODE", None)
    return TestClient(main.app)


@pytest.fixture()
def project_id(client, complex_bytes):
    res = client.post("/api/projects", files={"file": ("suivi_achats_2019.xlsm", complex_bytes)})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_create_and_list(client, project_id):
    items = client.get("/api/projects").json()["items"]
    assert [i["id"] for i in items] == [project_id]
    body = client.get(f"/api/projects/{project_id}").json()
    assert body["counts"]["commandes"] == 60
    assert body["spec"]["generation"]["rules"]["verified"] == 4


def test_create_refuses_bad_files(client):
    res = client.post("/api/projects", files={"file": ("notes.txt", b"bonjour")})
    assert res.status_code == 422
    res = client.post("/api/projects", files={"file": ("vide.xlsx", _empty_xlsx())})
    assert res.status_code == 422 and "Aucun tableau" in res.json()["detail"]


def _empty_xlsx():
    buf = io.BytesIO()
    openpyxl.Workbook().save(buf)
    return buf.getvalue()


def test_rows_crud(client, project_id):
    base = f"/api/projects/{project_id}/entities/commandes/rows"
    payload = {"n_commande": "CMD-X", "date": "2019-06-01", "service": "RH", "code_fournisseur": "F001",
               "montant_ht": 100, "statut": "Validée", "valide_par": "DAF"}
    created = client.post(base, json=payload)
    assert created.status_code == 201 and created.json()["montant_ttc"] == pytest.approx(120)
    rid = created.json()["_id"]
    assert client.patch(f"{base}/{rid}", json={"montant_ht": 50}).json()["tva"] == pytest.approx(10)
    assert client.get(f"{base}?q=CMD-X").json()["total"] == 1
    assert client.delete(f"{base}/{rid}").status_code == 204
    assert client.get(f"{base}/{rid}").status_code == 404


def test_validation_errors_are_structured(client, project_id):
    res = client.post(f"/api/projects/{project_id}/entities/commandes/rows", json={"montant_ht": "abc"})
    assert res.status_code == 422
    body = res.json()
    assert body["detail"] == "Saisie invalide"
    assert body["errors"]["montant_ht"] == "Nombre attendu"
    assert body["errors"]["n_commande"] == "Champ obligatoire"


def test_conflict_and_not_found(client, project_id):
    rows = client.get(f"/api/projects/{project_id}/entities/tfournisseurs/rows").json()["rows"]
    res = client.delete(f"/api/projects/{project_id}/entities/tfournisseurs/rows/{rows[0]['_id']}")
    assert res.status_code == 409
    assert client.get("/api/projects/AAAAAAAAAAAAAAAA").status_code == 404
    assert client.get(f"/api/projects/{project_id}/entities/inconnue/rows").status_code == 404
    assert client.get(f"/api/projects/{project_id}/entities/commandes/rows?sort=pirate").status_code == 400


def test_parameters_and_history(client, project_id):
    base = f"/api/projects/{project_id}"
    assert client.get(f"{base}/parameters").json()["items"][0]["value"] == 0.2
    res = client.put(f"{base}/parameters/tva_valeur", json={"value": "0,1"})
    assert res.json()["recomputed_rows"] == 60
    assert client.put(f"{base}/parameters/tva_valeur", json={"value": ""}).status_code == 422
    history = client.get(f"{base}/history").json()
    assert history["items"][0]["action"] == "parameter"


def test_export(client, project_id):
    res = client.get(f"/api/projects/{project_id}/export.xlsx")
    assert res.status_code == 200
    assert res.headers["content-disposition"] == 'attachment; filename="Suivi_achats_2019.xlsx"'
    assert "Commandes" in openpyxl.load_workbook(io.BytesIO(res.content)).sheetnames


def test_delete_project(client, project_id):
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_access_code(client, project_id, monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "s3cret")
    assert client.get("/api/projects").status_code == 401
    assert client.get(f"/api/projects/{project_id}", headers={"X-Access-Code": "faux"}).status_code == 401
    ok = client.get("/api/projects", headers={"X-Access-Code": "s3cret"})
    assert ok.status_code == 200 and ok.json()["protected"] is True
    assert client.get("/api/config").json()["access_code_required"] is True
    # Le diagnostic (sans stockage) reste accessible
    assert client.get("/api/health").status_code == 200


def test_application_page_served(client):
    res = client.get("/application.html")
    assert res.status_code == 200 and "application.js" in res.text
    assert client.get("/ui.js").status_code == 200
