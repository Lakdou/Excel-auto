---
title: "Faire tourner une IA sur son PC : de quoi a-t-on vraiment besoin ?"
description: "Mémoire vidéo, quantification, outils comme Ollama ou LM Studio : le guide pour utiliser un modèle d'IA en local, sans abonnement et sans envoyer ses données."
pubDate: 2026-11-27T23:10:00Z
category: ia
icon: neural
tags: ["IA", "LLM", "Guide"]
---

Faire tourner un modèle d'IA **directement sur son ordinateur**, sans connexion et sans abonnement, c'est
possible depuis quelques années. Vos données ne quittent pas votre machine, et ça marche même hors ligne. Mais
tout dépend d'une ressource devenue précieuse avec la [pénurie de mémoire](/blog/penurie-de-ram-pourquoi-la-memoire-coute-si-cher/) :
la mémoire de votre carte graphique.

## Le facteur clé : la mémoire vidéo (VRAM)

Un modèle de langage est d'abord un énorme fichier de « paramètres » (des milliards de nombres). Pour répondre
vite, il doit tenir **entièrement dans la mémoire de la carte graphique**. S'il déborde, une partie passe dans la
RAM classique et tout ralentit fortement.

Bonne nouvelle : grâce à la **quantification**, on stocke chaque paramètre sur 4 bits au lieu de 16, ce qui
divise la taille par quatre environ, pour une perte de qualité modérée. Ordres de grandeur avec une quantification
4 bits (il faut ajouter un peu de marge pour la conversation en cours) :

| Taille du modèle | Mémoire nécessaire (environ) | Matériel typique |
|---|---|---|
| 3 à 4 milliards de paramètres | 2 à 3 Go | Presque toutes les cartes récentes, voire le processeur seul |
| 7 à 8 milliards | 4 à 6 Go | Carte graphique avec 8 Go de VRAM |
| 13 à 14 milliards | 8 à 10 Go | Carte avec 12 Go de VRAM |
| 70 milliards | 35 à 45 Go | Plusieurs cartes, ou une machine très haut de gamme |

> Pour un usage quotidien (résumer, reformuler, aider à coder), un modèle de 7 à 8 milliards de paramètres sur
> une carte de 8 Go donne déjà de bons résultats.

Sans carte graphique adaptée, le processeur peut faire le travail, mais beaucoup plus lentement : comptez
quelques mots par seconde au lieu d'une réponse fluide.

## Les outils pour démarrer

- **[Ollama](https://ollama.com)** : le plus simple en ligne de commande. On installe, puis une seule commande
  télécharge et lance un modèle.
- **[LM Studio](https://lmstudio.ai)** : une application avec une interface de discussion, idéale si vous
  préférez cliquer plutôt que taper des commandes.
- **[llama.cpp](https://github.com/ggml-org/llama.cpp)** : le moteur open source sur lequel reposent beaucoup
  d'outils, pour ceux qui veulent tout régler eux-mêmes.

Avec Ollama, une fois installé :

```bash
ollama run mistral      # télécharge le modèle au premier lancement, puis ouvre la discussion
ollama list             # modèles déjà installés et leur taille sur le disque
```

## Local ou en ligne : que choisir ?

| | IA locale | IA en ligne |
|---|---|---|
| Confidentialité | Tout reste sur votre PC | Les données partent chez le fournisseur |
| Coût | Gratuit après l'achat du matériel | Abonnement ou paiement à l'usage |
| Qualité | Bonne pour les tâches courantes | Meilleure sur les tâches complexes |
| Hors ligne | Oui | Non |

Les meilleurs modèles en ligne restent nettement plus performants sur les tâches difficiles. L'IA locale brille
pour les données sensibles, les usages fréquents et répétitifs, ou simplement pour apprendre comment ces modèles
fonctionnent.

## Ce que ça change pour vous

1. **Vérifiez votre VRAM** avant tout : c'est elle qui détermine la taille de modèle utilisable.
2. **Commencez petit** : un modèle de 7 à 8 milliards de paramètres en 4 bits est le meilleur point de départ.
3. **Gardez les bons réflexes** : même en local, relisez ce que l'IA produit. Nos
   [7 règles pour coder avec une IA](/blog/bien-coder-avec-une-ia/) s'appliquent aussi ici.

*Informations à jour au 27 novembre 2026.*
