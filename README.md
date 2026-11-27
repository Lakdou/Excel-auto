# Excel Auto

**Diagnostic de classeurs Excel avant leur transformation en application web.**

Les grandes entreprises tournent sur des centaines de fichiers Excel critiques (budgets, suivis d'achats,
plannings, costing…) : macros VBA écrites il y a quinze ans, liens vers d'autres fichiers, feuilles masquées,
formules imbriquées, aucun historique ni contrôle d'accès. Excel Auto analyse un classeur (ou tout un parc de
classeurs) et produit :

- un **score de complexité** (0-100) expliqué facteur par facteur, et une **estimation d'effort** de migration ;
- les **points de vigilance** : erreurs `#REF!`, liens externes, macros à risque ou auto-exécutées, valeurs en dur,
  fonctions volatiles, colonnes hétérogènes, noms cassés, feuilles super-masquées, Power Query… ;
- le **modèle de données** détecté : tableaux, types de colonnes, listes de choix, clés primaires et **relations**
  entre tableaux, avec un **schéma SQL PostgreSQL** prêt à l'emploi ;
- l'inventaire des **formules** (règles distinctes, fonctions, dépendances entre feuilles) ;
- l'analyse des **macros VBA** : ce qu'elles font (e-mails, export PDF, import de fichiers, appels système…) et
  leur équivalent dans une application web ;
- un **plan de migration** étape par étape.

Les fichiers sont analysés **en mémoire** et ne sont jamais enregistrés sur le serveur.

## Démarrage rapide

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Puis ouvrir <http://127.0.0.1:8000> et déposer un fichier. Pour des fichiers de démonstration réalistes :

```bash
pip install -r requirements-dev.txt
python samples/generate_samples.py      # crée samples/demo/*.xlsm, *.xlsx, *.xls
```

## Analyser un parc de fichiers (ligne de commande)

```bash
python -m app.cli "//serveur/partage/Finance" --csv inventaire.csv
python -m app.cli classeur.xlsm --json rapport.json
```

Le CSV (séparateur `;`, s'ouvre directement dans Excel en français) contient une ligne par classeur, triée par
score de complexité : c'est la base d'une proposition commerciale (« voici vos 200 fichiers, voici par où
commencer »). Les fichiers verrous Office (`~$…`) sont ignorés.

## Formats pris en charge

| Format | Analyse |
|---|---|
| `.xlsx`, `.xlsm`, `.xltx`, `.xltm` | Complète |
| `.xls`, `.xlt` (Excel 97-2003) | Données, feuilles, noms, macros VBA. Le texte des formules n'est pas lisible dans ce format : le rapport le signale et conseille d'enregistrer en `.xlsx`. |

Cas gérés avec un message clair : fichier protégé par mot de passe, page HTML renommée en `.xls` (vieux exports),
`.xlsb`, archive corrompue, fichier vide, « zip bomb ». Un `.xlsx` renommé en `.xls` est détecté par son contenu.

## API

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/analyze` | Formulaire multipart avec un champ `file`. Renvoie le rapport JSON. `413` si trop gros, `422` si inexploitable. |
| `GET` | `/api/health` | État et version |
| `GET` | `/api/config` | Taille maximale et extensions acceptées |

Documentation interactive : `/docs`. Variable d'environnement : `EXCEL_AUTO_MAX_UPLOAD_MB` (50 par défaut).

## Architecture

```
app/
  main.py                 API FastAPI + en-têtes de sécurité (CSP stricte) + interface statique
  cli.py                  Analyse en ligne de commande / par lots
  analyzer/
    workbook.py           Orchestration : détection du format réel, garde-fous, assemblage du rapport
    openxml_reader.py     Lecture en flux des cellules (formules + valeurs en un seul passage)
    formulas.py           Découpage des formules, signatures de règles, dépendances, valeurs en dur
    profiling.py          Détection des tableaux, typage des colonnes, relations, schéma SQL
    vba.py                Extraction (oletools) et interprétation des macros
    scoring.py            Score, points de vigilance, plan de migration
  static/                 Interface web (HTML/CSS/JS sans dépendance, mode sombre, impression PDF)
samples/generate_samples.py   Classeurs de démonstration
tests/                    Tests unitaires, d'intégration, d'API et de bout en bout (Playwright)
```

Quelques choix techniques :

- **Performance** : openpyxl ne sert qu'aux métadonnées, sur une copie du classeur vidée de ses cellules ; les
  cellules sont lues en flux (lxml si disponible). Les formules recopiées ne sont analysées qu'une fois. Ordre de
  grandeur : 600 000 cellules en ~6 s et moins de 110 Mo de mémoire. Au-delà de 3 millions de cellules, l'analyse
  est partielle et le rapport le signale.
- **Règles distinctes** : chaque formule est convertie en notation relative (style R1C1) : `=A2*B2` recopiée sur
  10 000 lignes compte pour **une** règle de calcul, ce qui reflète l'effort réel de réécriture.
- **Sécurité** : XML lu sans résolution d'entités (defusedxml / lxml), limites de taille compressée et
  décompressée, rendu de l'interface exclusivement via `textContent` (aucune injection HTML possible depuis le
  contenu d'un fichier), CSP sans script inline, aucune trace technique renvoyée à l'utilisateur.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest                       # 105 tests : moteur, formats, sécurité, API, CLI

# Tests de bout en bout dans un vrai navigateur
npm install && npx playwright install chromium
python samples/generate_samples.py
uvicorn app.main:app --port 8765 &
npm run test:e2e                       # parcours complet, exports, mobile, mode sombre, anti-XSS
```

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute les deux suites à chaque push.

## Déploiement

```bash
docker build -t excel-auto .
docker run -p 8000:8000 excel-auto
```

L'image tourne sans privilèges (utilisateur dédié) et expose un healthcheck. Elle se déploie telle quelle sur
Render, Railway, Fly.io, Scaleway ou un serveur interne (pour les clients qui refusent le cloud).

## Limites connues

- La détection des tableaux est heuristique quand le classeur n'utilise pas de « Tableaux » Excel officiels
  (un tableau principal par feuille).
- Les valeurs des formules proviennent du dernier calcul enregistré par Excel ; un fichier jamais recalculé
  (généré par un programme) ne permet pas de détecter les erreurs de calcul, ce que le rapport signale.
- L'estimation d'effort est indicative : elle sert à prioriser, pas à chiffrer un devis.

## Suite prévue

1. **Générateur d'application** : à partir du rapport, générer la base de données, les formulaires de saisie
   et les écrans de consultation.
2. **Moteur de règles** : réécrire les formules en calculs serveur testés automatiquement contre les valeurs
   du fichier Excel d'origine.
3. **Plateforme** : comptes, SSO (Azure AD), rôles, journal d'audit, import/export Excel.
