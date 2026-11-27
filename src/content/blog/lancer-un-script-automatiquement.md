---
title: "Lancer un script automatiquement à heure fixe : cron et le Planificateur de tâches"
description: "Exécuter un script chaque matin ou chaque lundi sans y penser : la marche à suivre sous Linux, macOS et Windows, avec les pièges à éviter."
pubDate: 2026-11-27T23:14:00Z
category: dev
icon: rocket
tags: ["Automatisation", "Python", "Guide"]
---

Vous avez écrit un script qui vous fait gagner du temps, par exemple pour
[consolider vos fichiers Excel](/blog/automatiser-excel-avec-python/). Dernière étape : qu'il se lance **tout
seul**, chaque jour ou chaque semaine. Tous les systèmes savent le faire.

## Sous Linux et macOS : cron

`cron` exécute des commandes selon un calendrier. On édite sa liste de tâches avec :

```bash
crontab -e
```

Chaque ligne suit le format `minute heure jour-du-mois mois jour-de-la-semaine commande` :

```text
# Chaque lundi à 8 h 00
0 8 * * 1 /usr/bin/python3 /home/moi/scripts/rapport.py >> /home/moi/scripts/rapport.log 2>&1

# Tous les jours à 18 h 30
30 18 * * * /home/moi/scripts/sauvegarde.sh

# Toutes les 15 minutes
*/15 * * * * /home/moi/scripts/verifier.sh
```

| Champ | Valeurs | Exemple |
|---|---|---|
| Minute | 0 à 59 | `0` |
| Heure | 0 à 23 | `8` |
| Jour du mois | 1 à 31 | `*` (tous) |
| Mois | 1 à 12 | `*` |
| Jour de la semaine | 0 à 7 (0 et 7 = dimanche) | `1` (lundi) |

`crontab -l` affiche les tâches en place. Sur macOS récent, il peut falloir autoriser l'accès au disque pour que
cron puisse lire certains dossiers.

## Sous Windows : le Planificateur de tâches

Le plus simple est l'interface graphique : menu Démarrer, « Planificateur de tâches », puis **Créer une tâche
de base** et laissez-vous guider (déclencheur, puis action « Démarrer un programme »).

On peut aussi tout faire en une commande, dans un terminal :

```powershell
schtasks /Create /SC DAILY /TN "Rapport quotidien" /TR "C:\Python312\python.exe C:\scripts\rapport.py" /ST 08:00
```

Et pour vérifier ou supprimer :

```powershell
schtasks /Query /TN "Rapport quotidien"
schtasks /Delete /TN "Rapport quotidien" /F
```

## Les pièges qui font échouer une tâche planifiée

1. **Les chemins relatifs.** La tâche ne démarre pas dans le dossier de votre script. Utilisez des chemins
   **absolus**, pour le programme comme pour les fichiers lus et écrits.
2. **L'environnement différent.** cron démarre avec un environnement minimal : la commande `python` peut ne pas
   être trouvée. Indiquez le chemin complet (`/usr/bin/python3`) ; `which python3` vous le donne.
3. **Aucune trace des erreurs.** Redirigez la sortie vers un fichier journal (`>> fichier.log 2>&1`), sinon un
   échec passe inaperçu.
4. **L'ordinateur éteint ou en veille.** Une tâche prévue à 8 h ne s'exécute pas si la machine dort. Sous Windows,
   l'option « Exécuter la tâche dès que possible si un démarrage planifié est manqué » rattrape le coup.

## Ce que ça change pour vous

1. **cron** sous Linux et macOS, le **Planificateur de tâches** sous Windows : quelques minutes de configuration,
   des heures gagnées ensuite.
2. **Chemins absolus et fichier journal** : les deux réflexes qui évitent 90 % des problèmes.
3. Pour un script plus complexe à déployer, pensez à l'emballer avec [Docker](/blog/docker-explique-simplement/).

*Informations à jour au 27 novembre 2026.*
