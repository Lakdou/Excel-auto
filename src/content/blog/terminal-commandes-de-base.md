---
title: "Terminal : les commandes de base pour débuter (Windows, macOS, Linux)"
description: "Se déplacer dans les dossiers, créer, copier, déplacer et supprimer des fichiers, gagner du temps avec la touche Tab : les commandes essentielles du terminal, et leurs équivalents sous Windows."
pubDate: 2026-11-28T11:50:00Z
category: dev
icon: code
tags: ["Terminal", "Guide", "Outils"]
---

Le terminal fait peur : un écran noir, un curseur qui clignote, aucun bouton. Pourtant, une dizaine de commandes
suffit pour s'y sentir à l'aise, et beaucoup de tutoriels (dont ceux de ce blog) vous demanderont tôt ou tard
d'en taper une. Voici l'essentiel, avec les équivalents pour Windows.

## Ouvrir un terminal

| Système | Comment l'ouvrir |
|---|---|
| Windows | Menu Démarrer, tapez « Terminal » (ou « PowerShell ») |
| macOS | Application **Terminal**, dans Applications > Utilitaires |
| Linux | Raccourci Ctrl + Alt + T sur de nombreuses distributions |

Sous Windows, **PowerShell** comprend la plupart des commandes de ce guide, car il propose des alias (des
raccourcis) pour les noms Linux classiques. L'ancienne **invite de commandes** (`cmd`) utilise d'autres noms :
nous les indiquons quand ils diffèrent.

## Savoir où l'on est et se déplacer

Le terminal travaille toujours **dans un dossier**, appelé dossier courant.

```bash
pwd          # affiche le dossier courant
ls           # liste son contenu
cd Documents # entre dans le dossier Documents
cd ..        # remonte d'un niveau
cd ~         # revient au dossier personnel
```

Quelques repères :

- `..` désigne le dossier parent, `.` le dossier courant et `~` votre dossier personnel ;
- un nom contenant des espaces doit être placé **entre guillemets** : `cd "Mes projets"` ;
- dans l'invite de commandes Windows, `dir` remplace `ls`, et `cd` seul affiche le dossier courant.

## Créer, copier, déplacer

```bash
mkdir projet               # crée un dossier
cp notes.txt copie.txt     # copie un fichier
mv copie.txt archive.txt   # renomme (ou déplace) un fichier
mv archive.txt projet/     # déplace le fichier dans le dossier projet
cat notes.txt              # affiche le contenu d'un fichier texte
```

`mv` sert à la fois à **renommer** et à **déplacer** : c'est la même opération pour le système. Dans l'invite de
commandes Windows, les équivalents sont `copy`, `move` et `type`.

## Supprimer, avec prudence

```bash
rm archive.txt   # supprime un fichier
rm -r projet     # supprime un dossier et tout son contenu
```

Attention : **le terminal n'utilise pas la corbeille**. Un fichier supprimé avec `rm` est généralement perdu pour
de bon. Avant une suppression, vérifiez avec `ls` que vous êtes dans le bon dossier. Sous PowerShell, la
suppression d'un dossier s'écrit `Remove-Item projet -Recurse` ; dans l'invite de commandes, on utilise `del`
pour un fichier et `rmdir /s` pour un dossier.

## Les raccourcis qui changent tout

| Raccourci | Effet |
|---|---|
| **Tab** | Complète automatiquement un nom de fichier ou de dossier |
| **Flèche haut** | Rappelle les commandes précédentes |
| **Ctrl + C** | Interrompt la commande en cours |
| **Ctrl + L** ou `clear` | Efface l'écran (`cls` dans l'invite de commandes) |

La touche **Tab** est la plus précieuse : tapez les premières lettres d'un nom, appuyez sur Tab, et le terminal
complète le reste. Moins de frappe, et surtout moins de fautes. Notez aussi que, sous Linux, les noms de fichiers
**distinguent les majuscules** : `Notes.txt` et `notes.txt` sont deux fichiers différents (ce n'est pas le cas,
par défaut, sous Windows et macOS).

## Obtenir de l'aide

Inutile de tout retenir. Chaque commande a sa documentation intégrée :

- sous Linux et macOS : `man ls` (touche **q** pour quitter), ou souvent `ls --help` sous Linux ;
- sous PowerShell : `Get-Help Get-ChildItem` ;
- dans l'invite de commandes : `dir /?`.

Et si une commande trouvée sur Internet vous semble obscure, ne la lancez pas sans comprendre ce qu'elle fait,
surtout si elle contient `rm` ou demande des droits administrateur (`sudo`).

## Ce que ça change pour vous

1. **Cinq commandes pour commencer** : `pwd`, `ls`, `cd`, `mkdir` et `mv` couvrent la majorité des besoins.
2. **Tab et flèche haut** font gagner un temps considérable, dès le premier jour.
3. **Prochaine étape** : versionner son travail avec nos [commandes Git essentielles](/blog/git-commandes-essentielles/),
   ou isoler ses projets avec les [environnements virtuels Python](/blog/environnements-virtuels-python/).

*Informations à jour au 28 novembre 2026.*
