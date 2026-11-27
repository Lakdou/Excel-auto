---
title: "Automatiser ses fichiers Excel avec Python"
description: "Lire, nettoyer et consolider des classeurs Excel avec pandas et openpyxl : le guide pratique pour arrêter les copier-coller."
pubDate: 2026-11-24
tags: ["Python", "Automatisation", "Excel"]
---

Chaque semaine, vous ouvrez les mêmes fichiers Excel, vous copiez les mêmes colonnes, vous refaites les mêmes
totaux. Bonne nouvelle : **Python sait faire tout ça en quelques lignes**, sans erreur et en quelques secondes.

## Les deux bibliothèques à connaître

- **pandas** : pour manipuler les *données* (filtrer, regrouper, calculer). C'est l'outil principal.
- **openpyxl** : pour contrôler le *fichier* lui-même (mise en forme, formules, largeur des colonnes).

```bash
pip install pandas openpyxl
```

## Lire un classeur

```python
import pandas as pd

# Une feuille précise, en sautant les deux lignes de titre au-dessus du tableau
ventes = pd.read_excel("ventes_2024.xlsx", sheet_name="Ventes", skiprows=2)

print(ventes.head())          # les 5 premières lignes
print(ventes.dtypes)          # le type détecté pour chaque colonne
```

> Si une colonne de montants est détectée comme du texte (`object`), c'est souvent qu'une cellule contient
> « n/a » ou un espace. On s'en occupe juste après.

## Nettoyer les données

```python
# Montants : les valeurs non numériques deviennent vides (NaN) au lieu de faire planter les calculs
ventes["Montant"] = pd.to_numeric(ventes["Montant"], errors="coerce")

# Dates au format français (jour/mois/année)
ventes["Date"] = pd.to_datetime(ventes["Date"], dayfirst=True, errors="coerce")

# Espaces parasites et majuscules incohérentes
ventes["Région"] = ventes["Région"].str.strip().str.title()

# Lignes entièrement vides et doublons
ventes = ventes.dropna(how="all").drop_duplicates()
```

## Consolider plusieurs fichiers

Le cas classique : un fichier par agence, à fusionner en un seul.

```python
from pathlib import Path

fichiers = sorted(Path("agences").glob("*.xlsx"))
tableaux = []
for fichier in fichiers:
    df = pd.read_excel(fichier)
    df["Agence"] = fichier.stem      # garde la trace de l'origine de chaque ligne
    tableaux.append(df)

consolide = pd.concat(tableaux, ignore_index=True)
print(f"{len(fichiers)} fichiers, {len(consolide)} lignes")
```

## Calculer une synthèse

L'équivalent d'un tableau croisé dynamique, en une instruction :

```python
synthese = (
    consolide
    .groupby(["Agence", "Région"], as_index=False)
    .agg(chiffre_affaires=("Montant", "sum"), commandes=("Montant", "size"))
    .sort_values("chiffre_affaires", ascending=False)
)
```

## Écrire le résultat proprement

```python
from openpyxl.styles import Font

with pd.ExcelWriter("synthese.xlsx", engine="openpyxl") as writer:
    consolide.to_excel(writer, sheet_name="Données", index=False)
    synthese.to_excel(writer, sheet_name="Synthèse", index=False)

    feuille = writer.sheets["Synthèse"]
    for cellule in feuille[1]:                     # ligne d'en-tête en gras
        cellule.font = Font(bold=True)
    feuille.column_dimensions["A"].width = 24
    feuille.freeze_panes = "A2"                    # en-tête toujours visible
```

## Pour aller plus loin

1. **Planifier le script** : le Planificateur de tâches (Windows) ou `cron` (Linux, macOS) peut le lancer
   chaque lundi matin.
2. **Vérifier avant d'écrire** : un simple `assert consolide["Montant"].notna().all()` évite d'envoyer un
   rapport faux.
3. **Garder les fichiers d'origine intacts** : écrivez toujours le résultat dans un *nouveau* fichier.

Le premier script prend une heure à écrire. Ensuite, il vous rend cette heure chaque semaine.
