"""Génère des classeurs de démonstration réalistes (« vieux fichiers de grande entreprise »).

Usage :  python samples/generate_samples.py [dossier_de_sortie]

Fichiers produits :
- suivi_achats_2019.xlsm : classeur complexe (macros, liens externes, erreurs, feuilles masquées…)
- planning_equipe.xlsx   : classeur simple (un tableau, quelques validations)
- inventaire_2004.xls    : ancien format Excel 97-2003
"""

from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path

import xlsxwriter

ROOT = Path(__file__).resolve().parent.parent
VBA_BIN = ROOT / "tests" / "fixtures" / "vbaProject.bin"

SERVICES = ["Achats", "Finance", "Informatique", "Logistique", "RH"]
STATUTS = ["Brouillon", "En attente", "Validée", "Refusée"]
FOURNISSEURS = [
    ("F001", "Dupont Industrie", "France", 10),
    ("F002", "Bureau Plus", "France", 3),
    ("F003", "TechNord GmbH", "Allemagne", 15),
    ("F004", "Iberia Log", "Espagne", 7),
    ("F005", "Nordic Paper", "Suède", 21),
]


def build_complex(path: Path, rows: int = 60, seed: int = 42) -> Path:
    """Classeur « suivi des achats » typique : beaucoup de dette technique."""
    rnd = random.Random(seed)
    wb = xlsxwriter.Workbook(str(path))
    bold = wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1})
    euro = wb.add_format({"num_format": "#,##0.00 €"})
    date_fmt = wb.add_format({"num_format": "dd/mm/yyyy"})
    pct = wb.add_format({"num_format": "0.0%"})

    # --- Paramètres (masquée) -------------------------------------------------
    params = wb.add_worksheet("Paramètres")
    params.write_row(0, 0, ["Paramètre", "Valeur"], bold)
    params.write_row(1, 0, ["Taux TVA", 0.2])
    params.write_row(2, 0, ["Seuil validation DAF", 5000])
    params.write(4, 0, "Services", bold)
    for i, s in enumerate(SERVICES):
        params.write(5 + i, 0, s)
    params.hide()
    wb.define_name("TauxTVA", "=Paramètres!$B$2")
    wb.define_name("SeuilDAF", "=Paramètres!$B$3")
    wb.define_name("ListeServices", "=Paramètres!$A$6:$A$10")
    wb.define_name("AncienneZone", "=#REF!$A$1:$B$4")

    # --- Fournisseurs (tableau Excel officiel) ---------------------------------
    fourn = wb.add_worksheet("Fournisseurs")
    fourn.add_table(0, 0, len(FOURNISSEURS), 3, {
        "name": "TFournisseurs",
        "data": [list(f) for f in FOURNISSEURS],
        "columns": [{"header": h} for h in ("Code", "Raison sociale", "Pays", "Délai (jours)")],
    })

    # --- Commandes (zone de saisie principale) ----------------------------------
    cmd = wb.add_worksheet("Commandes")
    headers = ["N° commande", "Date", "Service", "Code fournisseur", "Fournisseur",
               "Montant HT", "TVA", "Montant TTC", "Statut", "Validé par", "Livraison prévue"]
    cmd.write_row(0, 0, headers, bold)
    cmd.set_column(0, 10, 16)
    start = dt.date(2019, 1, 7)
    delays = {f[0]: f[3] for f in FOURNISSEURS}
    totals = {s: [0, 0.0] for s in SERVICES}
    for r in range(1, rows + 1):
        n = r + 1  # numéro de ligne Excel
        code = FOURNISSEURS[rnd.randrange(len(FOURNISSEURS))][0]
        ht = round(rnd.uniform(80, 12000), 2)
        cmd.write(r, 0, f"CMD-2019-{r:04d}")
        cmd.write_datetime(r, 1, dt.datetime.combine(start + dt.timedelta(days=3 * r), dt.time()), date_fmt)
        service = SERVICES[rnd.randrange(len(SERVICES))]
        totals[service][0] += 1
        totals[service][1] += ht
        cmd.write(r, 2, service)
        cmd.write(r, 3, code)
        cmd.write_formula(r, 4, f"=IFERROR(VLOOKUP(D{n},Fournisseurs!$A:$D,2,FALSE),\"Inconnu\")", None,
                          dict((f[0], f[1]) for f in FOURNISSEURS)[code])
        cmd.write_number(r, 5, ht, euro)
        # Dette typique : le taux est codé en dur au lieu d'utiliser TauxTVA.
        cmd.write_formula(r, 6, f"=F{n}*0.2", euro, ht * 0.2)
        cmd.write_formula(r, 7, f"=F{n}+G{n}", euro, ht + ht * 0.2)
        cmd.write(r, 8, STATUTS[rnd.randrange(len(STATUTS))])
        # Colonne « fourre-tout » : noms, initiales, dates, nombres…
        valideur = rnd.choice(["M. Martin", "S. Bernard", "DAF", 12, dt.datetime(2019, 3, 1), "ok"])
        if isinstance(valideur, dt.datetime):
            cmd.write_datetime(r, 9, valideur, date_fmt)
        else:
            cmd.write(r, 9, valideur)
        order_date = start + dt.timedelta(days=3 * r)
        serial = (order_date - dt.date(1899, 12, 30)).days + delays[code]
        cmd.write_formula(r, 10, f"=B{n}+VLOOKUP(D{n},TFournisseurs[#All],4,FALSE)", date_fmt, serial)
    last = rows + 1
    cmd.data_validation(1, 2, rows, 2, {"validate": "list", "source": "=ListeServices"})
    cmd.data_validation(1, 8, rows, 8, {"validate": "list", "source": STATUTS})
    cmd.data_validation(1, 5, rows, 5, {"validate": "decimal", "criteria": ">=", "value": 0})
    cmd.conditional_format(1, 7, rows, 7, {"type": "cell", "criteria": ">", "value": "SeuilDAF",
                                           "format": wb.add_format({"bg_color": "#FFC7CE"})})
    cmd.write_comment("F1", "Montant hors taxes saisi par l'acheteur")
    cmd.freeze_panes(1, 0)
    cmd.activate()  # une feuille masquée ne peut pas être la feuille active

    # --- Synthèse (rapport) --------------------------------------------------
    syn = wb.add_worksheet("Synthèse")
    syn.write_row(0, 0, ["Service", "Nb commandes", "Total HT", "Part du total", "Écart budget"], bold)
    grand_total = sum(t[1] for t in totals.values()) or 1.0
    for i, s in enumerate(SERVICES, start=1):
        n = i + 1
        count, total = totals[s]
        syn.write(i, 0, s)
        syn.write_formula(i, 1, f"=COUNTIF(Commandes!$C$2:$C${last},A{n})", None, count)
        syn.write_formula(i, 2, f"=SUMIFS(Commandes!$F$2:$F${last},Commandes!$C$2:$C${last},A{n})", euro,
                          round(total, 2))
        syn.write_formula(i, 3, f"=C{n}/SUM($C$2:$C$6)", pct, round(total / grand_total, 4))
        syn.write_formula(i, 4, f"=C{n}-'[Budget_2018.xlsx]Budget'!$B${n}", euro, round(total - 50000, 2))
    syn.write(8, 0, "Mise à jour")
    syn.write_formula(8, 1, "=TODAY()", date_fmt, 43800)
    syn.write(9, 0, "Alerte")
    syn.write_formula(
        9, 1,
        '=IF(SUM(C2:C6)>SeuilDAF*10,IF(COUNTIF(Commandes!I:I,"Refusée")>5,'
        'IF(AND(B2>0,B3>0),IF(OR(C2>C3,C4>C5),IF(ISNUMBER(E2),"Revoir budget","Données manquantes"),"OK"),'
        '"Vide"),"OK"),"OK")',
        None, "OK",
    )
    syn.write(10, 0, "Ancien total")
    syn.write_formula(10, 1, "=SUM(#REF!)+INDIRECT(\"Commandes!F2\")", None, "#REF!")
    chart = wb.add_chart({"type": "column"})
    chart.add_series({"name": "Total HT", "categories": "=Synthèse!$A$2:$A$6", "values": "=Synthèse!$C$2:$C$6"})
    chart.set_title({"name": "Achats par service"})
    syn.insert_chart("G2", chart)
    syn.protect("1234")

    # --- Archives (super-masquée) ------------------------------------------------
    arch = wb.add_worksheet("Archives")
    arch.write_row(0, 0, ["Année", "Total"], bold)
    arch.write_row(1, 0, [2017, 410200.5])
    arch.write_row(2, 0, [2018, 455900.0])
    arch.very_hidden()

    if VBA_BIN.exists():
        wb.add_vba_project(str(VBA_BIN))
    wb.close()
    return path


def build_simple(path: Path) -> Path:
    """Petit planning d'équipe : un seul tableau, propre."""
    wb = xlsxwriter.Workbook(str(path))
    bold = wb.add_format({"bold": True})
    date_fmt = wb.add_format({"num_format": "dd/mm/yyyy"})
    ws = wb.add_worksheet("Planning")
    ws.write_row(0, 0, ["Matricule", "Nom", "Équipe", "Début", "Fin", "Jours"], bold)
    people = [("E100", "Alice Robert", "Matin"), ("E101", "Bruno Petit", "Soir"),
              ("E102", "Chloé Durand", "Matin"), ("E103", "David Leroy", "Nuit"),
              ("E104", "Emma Moreau", "Soir"), ("E105", "Félix Simon", "Matin"),
              ("E106", "Gaëlle Michel", "Nuit"), ("E107", "Hugo Laurent", "Soir")]
    for i, (mat, nom, eq) in enumerate(people, start=1):
        d = dt.datetime(2024, 1, 1) + dt.timedelta(days=7 * i)
        ws.write(i, 0, mat)
        ws.write(i, 1, nom)
        ws.write(i, 2, eq)
        ws.write_datetime(i, 3, d, date_fmt)
        ws.write_datetime(i, 4, d + dt.timedelta(days=4), date_fmt)
        ws.write_formula(i, 5, f"=E{i + 1}-D{i + 1}+1", None, 5)
    ws.data_validation(1, 2, len(people), 2, {"validate": "list", "source": ["Matin", "Soir", "Nuit"]})
    wb.close()
    return path


def build_legacy(path: Path) -> Path:
    """Ancien inventaire au format .xls (Excel 97-2003)."""
    import xlwt

    book = xlwt.Workbook(encoding="utf-8")
    sh = book.add_sheet("Inventaire")
    date_style = xlwt.easyxf(num_format_str="DD/MM/YYYY")
    for c, h in enumerate(["Référence", "Désignation", "Entrepôt", "Quantité", "Prix unitaire", "Dernier inventaire"]):
        sh.write(0, c, h)
    entrepots = ["Lyon", "Lille", "Nantes"]
    for r in range(1, 31):
        sh.write(r, 0, f"REF-{1000 + r}")
        sh.write(r, 1, f"Article {r}")
        sh.write(r, 2, entrepots[r % 3])
        sh.write(r, 3, (r * 7) % 50)
        sh.write(r, 4, round(3.5 + r * 1.25, 2))
        sh.write(r, 5, dt.datetime(2004, 1, 1) + dt.timedelta(days=r), date_style)
    sh.write(31, 3, xlwt.Formula("SUM(D2:D31)"))
    hidden = book.add_sheet("Codes")
    hidden.write(0, 0, "Code")
    hidden.write(1, 0, "LYO")
    hidden.visibility = 1  # 1 = masquée (champ BOUNDSHEET)
    book.save(str(path))
    return path


def main(out_dir: str | None = None) -> list[Path]:
    out = Path(out_dir) if out_dir else ROOT / "samples" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    return [
        build_complex(out / "suivi_achats_2019.xlsm"),
        build_simple(out / "planning_equipe.xlsx"),
        build_legacy(out / "inventaire_2004.xls"),
    ]


if __name__ == "__main__":
    for p in main(sys.argv[1] if len(sys.argv) > 1 else None):
        print(f"Créé : {p}")
