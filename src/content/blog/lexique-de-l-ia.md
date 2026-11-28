---
title: "LLM, tokens, RAG, agents : le lexique de l'IA pour tout comprendre"
description: "Modèle de langage, paramètres, contexte, hallucination, RAG, agent, inférence : les mots de l'intelligence artificielle expliqués simplement, avec des exemples concrets."
pubDate: 2026-11-28T02:50:00Z
category: ia
icon: neural
tags: ["IA", "LLM", "Guide"]
---

L'intelligence artificielle s'accompagne d'un vocabulaire qui change vite et qu'on emploie souvent sans
l'expliquer. Voici les termes essentiels, regroupés par thème, pour suivre l'actualité (et nos articles) sans
se perdre.

## Les bases

**Modèle de langage (LLM).** Un programme entraîné sur d'énormes quantités de texte pour prédire la suite la plus
probable d'un texte. C'est le moteur des assistants conversationnels. « LLM » signifie *Large Language Model*,
grand modèle de langage.

**Paramètres.** Les milliards de nombres que le modèle ajuste pendant son entraînement : c'est sa « mémoire »
apprise. On parle d'un modèle « de 8 milliards de paramètres ». Plus il y en a, plus le modèle est capable en
général, mais plus il demande de mémoire et de puissance, ce qui explique en partie la
[pénurie de mémoire actuelle](/blog/ia-se-passer-de-la-memoire-hbm/).

**Entraînement et inférence.** L'**entraînement** est la phase, très coûteuse, où le modèle apprend à partir des
données. L'**inférence** est son utilisation au quotidien : chaque fois que vous posez une question, le modèle
fait de l'inférence.

**Multimodal.** Un modèle capable de traiter plusieurs types de contenus : texte, images, son, parfois vidéo.

## Comment le modèle lit et écrit

**Token.** L'unité de texte que manipule le modèle : un mot entier, un morceau de mot ou un signe de ponctuation.
En français, un mot correspond souvent à un ou deux tokens. La facturation des services d'IA et leurs limites
sont généralement exprimées en tokens.

**Fenêtre de contexte.** La quantité de texte (en tokens) que le modèle peut prendre en compte en même temps :
votre question, l'historique de la conversation, les documents fournis. Au-delà, les éléments les plus anciens
sont oubliés ou doivent être résumés.

**Prompt.** Le texte que vous donnez au modèle : la consigne, le contexte, les exemples. Sa qualité change
beaucoup le résultat, comme nous l'expliquons dans nos [règles pour coder avec une IA](/blog/bien-coder-avec-une-ia/).

**Température.** Un réglage qui dose le hasard dans les réponses : basse, le modèle choisit les suites les plus
probables (réponses régulières) ; haute, il varie davantage (réponses plus créatives, mais moins fiables).

## Les limites à connaître

**Hallucination.** Quand le modèle affirme avec assurance quelque chose de faux : une citation inventée, une
référence qui n'existe pas, une fonction de programmation imaginaire. C'est une conséquence de son
fonctionnement : il produit un texte *plausible*, pas forcément *vrai*. D'où la règle d'or : vérifier les faits
importants.

**Date de coupure (*cutoff*).** La date à laquelle s'arrêtent les données d'entraînement. Sans accès à des
sources extérieures, le modèle ne connaît pas ce qui s'est passé après.

**Biais.** Les déséquilibres présents dans les données d'entraînement peuvent se retrouver dans les réponses.

## Les techniques pour aller plus loin

| Terme | En une phrase | Exemple d'usage |
|---|---|---|
| **RAG** | Le modèle va chercher des passages dans vos documents avant de répondre | Un assistant qui répond à partir de la documentation interne d'une entreprise |
| **Embedding (vecteur)** | Une liste de nombres qui représente le sens d'un texte, pour retrouver des contenus proches | La recherche « par le sens » plutôt que par mots-clés |
| **Fine-tuning** | Un entraînement complémentaire sur des données spécialisées | Adapter un modèle au vocabulaire médical ou juridique |
| **Agent** | Un modèle qui enchaîne des actions avec des outils (recherche, code, applications) pour atteindre un objectif | Un assistant qui réserve, compare ou corrige du code en plusieurs étapes |
| **Quantification** | Stocker les paramètres avec moins de précision pour réduire la mémoire nécessaire | Faire tourner un modèle [en local sur son PC](/blog/faire-tourner-une-ia-en-local/) |

Le **RAG** (*Retrieval-Augmented Generation*, génération augmentée par la recherche) mérite une mention
particulière : en donnant au modèle les bons documents au moment de répondre, il réduit les hallucinations et
permet d'utiliser des informations récentes ou privées, sans réentraîner le modèle.

## Ce que ça change pour vous

1. **Un LLM prédit du texte plausible** : il peut se tromper avec aplomb. Vérifiez toujours ce qui compte.
2. **Pensez en tokens et en contexte** : une conversation très longue ou un document énorme dépassent vite la
   mémoire de travail du modèle.
3. **RAG, agents, quantification** : ces mots reviennent sans cesse dans l'actualité. Vous savez désormais ce
   qu'ils recouvrent.

*Informations à jour au 28 novembre 2026.*
