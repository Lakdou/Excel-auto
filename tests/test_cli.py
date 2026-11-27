import csv
import json

from app import cli


def test_batch_folder_to_csv_and_json(samples_dir, tmp_path, capsys):
    (samples_dir / "~$verrou.xlsx").write_bytes(b"temp")  # fichier verrou Office : ignoré
    (samples_dir / "notes.txt").write_text("ignoré")
    broken = tmp_path / "abime.xlsx"
    broken.write_bytes(b"pas un excel")
    out_csv, out_json = tmp_path / "inv.csv", tmp_path / "all.json"

    code = cli.main([str(samples_dir), str(broken), "--csv", str(out_csv), "--json", str(out_json)])
    assert code == 0

    with open(out_csv, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    assert len(rows) == 4
    assert rows[0]["fichier"].endswith("suivi_achats_2019.xlsm")  # trié par score décroissant
    assert rows[-1]["statut"] == "erreur" and rows[-1]["message"]
    assert "," in rows[0]["effort_max_j"] or rows[0]["effort_max_j"].isdigit()
    assert "." not in rows[0]["taille_ko"]
    assert len(json.loads(out_json.read_text(encoding="utf-8"))) == 3
    out = capsys.readouterr().out
    assert "[CRITIQUE]" in out and "4 fichier(s) analysé(s), 1 en erreur." in out


def test_single_file_json(samples_dir, tmp_path):
    out = tmp_path / "r.json"
    assert cli.main([str(samples_dir / "planning_equipe.xlsx"), "--json", str(out), "--quiet"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["file"]["name"] == "planning_equipe.xlsx"


def test_nothing_found(tmp_path):
    assert cli.main([str(tmp_path)]) == 2
