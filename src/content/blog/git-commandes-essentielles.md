---
title: "Git : les 10 commandes qui sauvent la mise"
description: "Annuler une erreur, retrouver un fichier supprimé, mettre son travail de côté : les commandes Git à garder sous la main."
pubDate: 2026-11-22
category: dev
icon: branch
tags: ["Git", "Outils"]
---

Git fait peur parce qu'on a l'impression qu'une mauvaise commande peut tout casser. En réalité, Git garde
presque tout en mémoire : il suffit de connaître les bonnes commandes pour réparer ses erreurs.

## Voir où on en est

```bash
git status                 # fichiers modifiés, ajoutés, non suivis
git log --oneline --graph  # historique compact, avec les branches
git diff                   # modifications pas encore ajoutées
```

## Annuler des modifications

```bash
git restore fichier.py            # annule les modifications non ajoutées d'un fichier
git restore --staged fichier.py   # retire un fichier de l'index (sans perdre les modifications)
```

## Corriger le dernier commit

Oublié un fichier, ou une faute dans le message ?

```bash
git add fichier_oublie.py
git commit --amend -m "Message corrigé"
```

> Ne modifiez un commit qu'**avant** de l'avoir partagé avec `git push`. Après, préférez un nouveau commit.

## Mettre son travail de côté

Une urgence tombe alors que votre travail n'est pas prêt à être commité :

```bash
git stash push -m "travail en cours sur le formulaire"
# ... on règle l'urgence ...
git stash pop
```

## Revenir sur un commit déjà partagé

`git revert` crée un *nouveau* commit qui annule un ancien. L'historique reste intact, c'est donc sans danger
sur une branche partagée :

```bash
git revert a1b2c3d
```

## Retrouver « l'irretrouvable »

`git reflog` liste tous les endroits où votre branche est passée, même après un `reset` malheureux :

```bash
git reflog
# a1b2c3d HEAD@{3}: commit: Ajoute l'export PDF
git switch -c sauvetage a1b2c3d   # nouvelle branche à partir de ce point
```

## Le récapitulatif

| Besoin | Commande |
|---|---|
| Où en suis-je ? | `git status` |
| Annuler un fichier modifié | `git restore fichier` |
| Corriger le dernier commit | `git commit --amend` |
| Mettre de côté | `git stash` / `git stash pop` |
| Annuler un commit partagé | `git revert <commit>` |
| Retrouver un état perdu | `git reflog` |

Gardez ce tableau sous la main : la plupart des « catastrophes » Git se réparent en une commande.
