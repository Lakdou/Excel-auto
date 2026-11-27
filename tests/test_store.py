import io

import openpyxl
import pytest

from app.generator.generate import build_application
from app.generator.store import Conflict, NotFound, ProjectStore, StoreError, ValidationError

NEW_ORDER = {
    "n_commande": "CMD-2019-0999", "date": "2019-06-01", "service": "RH", "code_fournisseur": "F003",
    "montant_ht": "1 000,50", "statut": "Validée", "valide_par": "DAF",
}


@pytest.fixture()
def project(tmp_path, complex_bytes):
    store = ProjectStore(tmp_path)
    pid = store.create(build_application(complex_bytes, "suivi_achats_2019.xlsm"))
    return store.open(pid)


def supplier(project, code):
    return next(r for r in project.list_rows("tfournisseurs")["rows"] if r["code"] == code)


def test_created_project_contents(project, tmp_path):
    assert project.counts() == {"parametres": 2, "tfournisseurs": 5, "commandes": 60, "archives": 2}
    store = ProjectStore(tmp_path)
    [item] = store.list()
    assert item["title"] == "Suivi achats 2019" and item["rows"] == 69
    first = project.list_rows("commandes", limit=1)["rows"][0]
    assert first["date"] == "2019-01-10" and first["fournisseur"] == "Dupont Industrie"


def test_insert_computes_fields(project):
    row = project.insert("commandes", NEW_ORDER)
    assert row["montant_ht"] == 1000.5
    assert row["fournisseur"] == "TechNord GmbH"
    assert row["tva"] == pytest.approx(200.1)
    assert row["montant_ttc"] == pytest.approx(1200.6)
    assert row["livraison_prevue"] == "2019-06-16"  # 1er juin + 15 jours de délai fournisseur


def test_computed_fields_cannot_be_forced(project):
    row = project.insert("commandes", dict(NEW_ORDER, tva=999999, montant_ttc=1))
    assert row["tva"] == pytest.approx(200.1)


def test_validation_errors(project):
    with pytest.raises(ValidationError) as exc:
        project.insert("commandes", {
            "n_commande": "CMD-2019-0001", "date": "31/02/2019", "service": "Compta",
            "code_fournisseur": "F999", "montant_ht": "abc", "statut": "Validée", "valide_par": " ",
        })
    assert exc.value.errors == {
        "n_commande": "Cette valeur existe déjà",
        "date": "Date attendue (AAAA-MM-JJ)",
        "service": "Valeur hors de la liste autorisée",
        "code_fournisseur": "« F999 » n'existe pas dans « TFournisseurs »",
        "montant_ht": "Nombre attendu",
        "valide_par": "Champ obligatoire",
    }
    assert project.counts()["commandes"] == 60  # rien n'a été écrit


def test_partial_update_and_recompute(project):
    row = project.insert("commandes", NEW_ORDER)
    updated = project.update("commandes", row["_id"], {"montant_ht": 2000})
    assert updated["tva"] == pytest.approx(400) and updated["statut"] == "Validée"
    same = project.update("commandes", row["_id"], {"n_commande": "CMD-2019-0999"})  # sa propre valeur : pas un doublon
    assert same["n_commande"] == "CMD-2019-0999"


def test_cascade_when_referenced_table_changes(project):
    row = project.insert("commandes", NEW_ORDER)
    project.update("tfournisseurs", supplier(project, "F003")["_id"], {"raison_sociale": "TechNord AG", "delai_jours": 30})
    after = project.get_row("commandes", row["_id"])
    assert after["fournisseur"] == "TechNord AG" and after["livraison_prevue"] == "2019-07-01"


def test_delete_protected_by_references(project):
    with pytest.raises(Conflict, match="utilisé par 1[0-9] ligne"):
        project.delete("tfournisseurs", supplier(project, "F003")["_id"])
    row = project.insert("tfournisseurs", {"code": "F009", "raison_sociale": "Neuf", "pays": "France", "delai_jours": 2})
    project.delete("tfournisseurs", row["_id"])
    with pytest.raises(NotFound):
        project.get_row("tfournisseurs", row["_id"])


def test_lookup_follows_renamed_supplier(project):
    project.insert("tfournisseurs", {"code": "F010", "raison_sociale": "Temp", "pays": "France", "delai_jours": 1})
    order = project.insert("commandes", dict(NEW_ORDER, code_fournisseur="F010"))
    assert order["fournisseur"] == "Temp"
    project.update("tfournisseurs", supplier(project, "F010")["_id"], {"raison_sociale": "Renommé"})
    assert project.get_row("commandes", order["_id"])["fournisseur"] == "Renommé"


def test_parameter_change_recomputes_everything(project):
    res = project.set_parameter("tva_valeur", "0,055")
    assert res == {"name": "tva_valeur", "value": 0.055, "recomputed_rows": 60}
    row = project.list_rows("commandes", limit=1)["rows"][0]
    assert row["tva"] == pytest.approx(row["montant_ht"] * 0.055)
    assert row["montant_ttc"] == pytest.approx(row["montant_ht"] * 1.055)  # recalcul en chaîne
    with pytest.raises(ValidationError):
        project.set_parameter("tva_valeur", "beaucoup")
    with pytest.raises(NotFound):
        project.set_parameter("inconnu", 1)


def test_search_sort_paginate(project):
    res = project.list_rows("commandes", q="TechNord", sort="montant_ht", desc=True, limit=5)
    assert res["total"] == sum(1 for r in project.list_rows("commandes", limit=200)["rows"] if r["code_fournisseur"] == "F003")
    amounts = [r["montant_ht"] for r in res["rows"]]
    assert amounts == sorted(amounts, reverse=True) and len(amounts) == 5
    page2 = project.list_rows("commandes", offset=50, limit=50)
    assert page2["total"] == 60 and len(page2["rows"]) == 10
    assert project.list_rows("commandes", q="%")["total"] == 0  # les jokers SQL sont échappés
    assert project.list_rows("commandes", q="' OR 1=1 --")["total"] == 0
    with pytest.raises(StoreError):
        project.list_rows("commandes", sort="_id; DROP TABLE x")


def test_history_records_every_change(project):
    row = project.insert("commandes", NEW_ORDER)
    project.update("commandes", row["_id"], {"statut": "Refusée"})
    project.set_parameter("tva_valeur", 0.1)
    project.delete("commandes", row["_id"])
    items = project.history()["items"]
    assert [i["action"] for i in items] == ["delete", "parameter", "update", "create", "import"]
    assert items[2]["changes"]["statut"] == ["Validée", "Refusée"]
    assert items[1]["changes"]["tva_valeur"] == [0.2, 0.1]
    assert project.history(entity="commandes")["total"] == 3


def test_export_xlsx(project):
    project.insert("commandes", dict(NEW_ORDER, valide_par="=HYPERLINK(\"http://x\")"))
    wb = openpyxl.load_workbook(io.BytesIO(project.export_xlsx()))
    assert wb.sheetnames == ["Paramètres", "TFournisseurs", "Commandes", "Archives", "Paramètres de calcul"]
    ws = wb["Commandes"]
    assert ws.max_row == 62
    assert [c.value for c in ws[1]][:3] == ["N° commande", "Date", "Service"]
    last = [c for c in ws[62]]
    assert last[9].value == '=HYPERLINK("http://x")' and last[9].data_type == "s"  # texte, pas une formule
    assert ws["B2"].number_format == "dd/mm/yyyy"


def test_unknown_ids_are_rejected(tmp_path):
    store = ProjectStore(tmp_path)
    for bad in ["../etc", "x", "a" * 40, "..%2F..%2Fpasswd"]:
        with pytest.raises(NotFound):
            store.open(bad)
    with pytest.raises(NotFound):
        store.delete("AAAAAAAAAAAAAAAA")


def test_unknown_entity(project):
    with pytest.raises(NotFound):
        project.list_rows("utilisateurs")


def test_delete_project(tmp_path, simple_bytes):
    store = ProjectStore(tmp_path)
    pid = store.create(build_application(simple_bytes, "planning.xlsx"))
    store.delete(pid)
    assert store.list() == []
