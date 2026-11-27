---
title: "Docker expliqué simplement : lancer une application en une commande"
description: "Image, conteneur, Dockerfile, Compose : les notions essentielles de Docker et les commandes pour empaqueter une application qui marche partout."
pubDate: 2026-11-27T23:13:00Z
category: dev
icon: code
tags: ["Docker", "DevOps", "Guide"]
---

« Ça marche sur ma machine » : c'est la phrase que Docker a rendue obsolète. L'idée est simple : on emballe une
application **avec tout ce dont elle a besoin** (langage, bibliothèques, réglages) dans une boîte standard, qui
fonctionne de la même façon sur n'importe quel ordinateur ou serveur.

## Les trois notions à connaître

| Notion | Analogie | Rôle |
|---|---|---|
| **Image** | Une recette | Le modèle figé : système, dépendances, code |
| **Conteneur** | Le plat préparé | Une image en cours d'exécution, isolée du reste |
| **Dockerfile** | La fiche recette | Le fichier texte qui décrit comment construire l'image |

Un conteneur n'est pas une machine virtuelle complète : il partage le noyau du système hôte, ce qui le rend
léger et rapide à démarrer.

## Premiers pas

Après avoir installé Docker (Docker Desktop sur Windows et macOS, le paquet `docker` sur Linux) :

```bash
docker run hello-world            # vérifie que tout fonctionne
docker run -d -p 8080:80 nginx    # lance un serveur web, accessible sur http://localhost:8080
docker ps                         # conteneurs en cours d'exécution
docker stop <id-du-conteneur>     # arrête un conteneur
```

L'option `-p 8080:80` relie le port 8080 de votre ordinateur au port 80 du conteneur, et `-d` le lance en
arrière-plan.

## Empaqueter sa propre application

Pour une petite application Python, un `Dockerfile` à la racine du projet suffit :

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

Puis :

```bash
docker build -t mon-app .     # construit l'image à partir du Dockerfile
docker run --rm mon-app       # la lance (--rm supprime le conteneur à l'arrêt)
```

> Copier `requirements.txt` et installer les dépendances **avant** de copier le reste du code permet à Docker de
> réutiliser cette étape tant que les dépendances ne changent pas : les reconstructions sont bien plus rapides.

## Plusieurs services ensemble : Docker Compose

Une vraie application a souvent une base de données à côté. Docker Compose décrit l'ensemble dans un fichier
`compose.yaml` :

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
  db:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: change-moi
    volumes:
      - donnees:/var/lib/postgresql/data
volumes:
  donnees:
```

```bash
docker compose up -d     # démarre tous les services
docker compose down      # les arrête (les données du volume sont conservées)
```

Le **volume** `donnees` est important : sans lui, le contenu de la base disparaîtrait à chaque suppression du
conteneur.

## Les erreurs classiques

- **Mettre des mots de passe dans l'image** : utilisez des variables d'environnement ou un fichier `.env` non
  versionné.
- **Oublier le fichier `.dockerignore`** : sans lui, vous copiez dans l'image des dossiers inutiles
  (`node_modules`, `.git`…), qui l'alourdissent.
- **Stocker des données dans le conteneur** : tout ce qui doit survivre va dans un volume.

## Ce que ça change pour vous

1. **Un Dockerfile** et votre application démarre à l'identique partout, de votre PC au serveur.
2. **Docker Compose** pour lancer application et base de données en une commande.
3. Pour tout le reste, la [documentation officielle](https://docs.docker.com/) est très complète. Et pour
   versionner tout ça proprement, gardez nos [commandes Git essentielles](/blog/git-commandes-essentielles/)
   sous la main.

*Informations à jour au 27 novembre 2026.*
