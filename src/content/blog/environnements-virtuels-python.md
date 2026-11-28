---
title: "Python : les environnements virtuels expliqués (venv, pip, requirements.txt)"
description: "Pourquoi isoler chaque projet Python, comment créer et activer un environnement virtuel sous Windows, macOS et Linux, et comment partager ses dépendances avec requirements.txt."
pubDate: 2026-11-28T07:50:00Z
category: dev
icon: code
tags: ["Python", "Guide", "Outils"]
---

Vous installez une bibliothèque Python pour un projet, et un autre projet cesse soudain de fonctionner ? Ou
votre système refuse carrément la commande `pip install` ? La solution tient en deux mots : **environnement
virtuel**. C'est un dossier qui contient une copie isolée de Python et des bibliothèques d'un seul projet. Voici
comment l'utiliser, en cinq minutes.

## Pourquoi isoler chaque projet

Sans environnement virtuel, toutes les bibliothèques s'installent au même endroit, pour tout l'ordinateur. Cela
pose trois problèmes :

- **les conflits de versions** : un projet a besoin de la version 1 d'une bibliothèque, un autre de la
  version 2, et les deux ne peuvent pas cohabiter ;
- **le système lui-même** : sur de nombreuses distributions Linux récentes, Python est utilisé par le système,
  et `pip install` hors d'un environnement virtuel est bloqué par l'erreur `externally-managed-environment` ;
- **le partage** : impossible de savoir précisément de quoi votre projet a besoin pour fonctionner ailleurs.

Avec un environnement virtuel par projet, chaque projet a ses propres versions, et rien ne déborde sur le reste
de la machine.

## Créer et activer un environnement

Le module `venv` est inclus dans Python : rien à installer. Placez-vous dans le dossier de votre projet, puis :

```bash
python -m venv .venv
```

Sous Windows, si la commande `python` n'est pas reconnue, utilisez le lanceur `py` : `py -m venv .venv`. Sur
certaines distributions Linux, le module s'installe à part (paquet `python3-venv` sur Debian et Ubuntu), et la
commande s'appelle souvent `python3`.

Il faut ensuite **activer** l'environnement, avec une commande qui dépend du système :

| Système | Commande d'activation |
|---|---|
| Linux et macOS | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (invite de commandes) | `.venv\Scripts\activate.bat` |

Une fois activé, le nom de l'environnement s'affiche généralement au début de la ligne de commande, par exemple
`(.venv)`. Les commandes `python` et `pip` utilisent alors la copie isolée. Pour en sortir, tapez simplement :

```bash
deactivate
```

Sous PowerShell, si un message indique que l'exécution de scripts est désactivée, autorisez les scripts locaux
pour votre compte, une fois pour toutes :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Installer et partager ses dépendances

Environnement activé, installez ce dont votre projet a besoin, comme d'habitude :

```bash
pip install pandas openpyxl
```

Pour que quelqu'un d'autre (ou vous, sur un autre ordinateur) puisse recréer exactement le même environnement,
enregistrez la liste des bibliothèques et de leurs versions :

```bash
pip freeze > requirements.txt
```

Ce fichier texte se partage avec le code. Pour tout réinstaller d'un coup dans un nouvel environnement :

```bash
pip install -r requirements.txt
```

## Les bonnes pratiques

1. **Un environnement par projet**, créé dans le dossier du projet. Le nom `.venv` est une convention répandue,
   reconnue par la plupart des éditeurs de code, dont Visual Studio Code.
2. **Ne versionnez jamais le dossier de l'environnement** : il est lourd et propre à chaque machine. Seul
   `requirements.txt` va dans Git. Depuis Python 3.13, `venv` ajoute de lui-même un fichier `.gitignore` dans
   le dossier créé ; avec une version plus ancienne, ajoutez la ligne `.venv/` au `.gitignore` du projet, le fichier
   qui liste ce que Git doit ignorer (pour le reste, voir notre
   [guide des commandes Git](/blog/git-commandes-essentielles/)).
3. **Ne déplacez pas un environnement** : il contient des chemins absolus. En cas de déménagement du projet,
   supprimez le dossier `.venv` et recréez-le à partir de `requirements.txt`.
4. **Vérifiez où vous êtes** : en cas de doute, `python -c "import sys; print(sys.prefix)"` affiche le dossier
   de l'environnement actif.

Pour aller plus loin, des outils comme [uv](https://docs.astral.sh/uv/) automatisent la création des
environnements et l'installation des dépendances, avec une grande rapidité. Mais `venv` et `pip`, fournis avec
Python, suffisent largement pour commencer. La [documentation officielle de venv](https://docs.python.org/fr/3/library/venv.html)
détaille toutes les options.

## Ce que ça change pour vous

1. **Une commande pour démarrer** : `python -m venv .venv`, puis l'activation adaptée à votre système.
2. **`requirements.txt` rend votre projet reproductible** : c'est lui qu'on partage, pas le dossier `.venv`.
3. **Fini les conflits** : chaque projet garde ses versions. Idéal pour suivre notre tutoriel
   [Automatiser ses fichiers Excel avec Python](/blog/automatiser-excel-avec-python/) sans toucher au reste de
   votre machine.

*Informations à jour au 28 novembre 2026.*
