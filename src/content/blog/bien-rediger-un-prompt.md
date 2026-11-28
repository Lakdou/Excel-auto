---
title: "Bien rédiger un prompt : la méthode pour obtenir de meilleures réponses d'une IA"
description: "Contexte, objectif, format, exemples, relances : une méthode simple en cinq étapes pour écrire des demandes claires à un assistant IA, avec des exemples avant et après."
pubDate: 2026-11-28T05:50:00Z
category: ia
icon: neural
tags: ["IA", "Prompt", "Guide"]
---

Face à un assistant IA, la qualité de la réponse dépend énormément de la qualité de la demande. Un modèle de
langage ne lit pas dans les pensées : il complète au mieux ce que vous lui donnez. Bonne nouvelle, il n'y a pas
de formule magique à connaître. Il suffit de demander comme on le ferait à un collègue compétent qui ne connaît
rien de votre situation. Voici une méthode en cinq étapes.

## 1. Donner le contexte

L'IA ne sait pas qui vous êtes, à qui s'adresse le résultat ni ce que vous avez déjà essayé. Dites-le.

- **Qui vous êtes** : « Je suis professeur de collège », « Je débute en Python ».
- **Pour qui** : « Le texte sera lu par des clients non techniciens ».
- **La situation** : « J'ai déjà essayé de redémarrer, sans succès ».

Plus le contexte est précis, moins le modèle a besoin de deviner, et moins il risque de partir dans une mauvaise
direction.

## 2. Formuler un objectif clair

Une demande vague donne une réponse vague. Comparez :

| Demande floue | Demande précise |
|---|---|
| « Parle-moi des SSD » | « Explique la différence entre un SSD NVMe et SATA pour quelqu'un qui veut accélérer ses chargements de jeux » |
| « Corrige mon mail » | « Corrige les fautes de ce mail sans changer le ton, et signale les phrases ambiguës » |
| « Fais-moi un plan d'entraînement » | « Propose un programme de course de 8 semaines pour passer de 5 à 10 km, à raison de 3 sorties par semaine » |

Un bon réflexe : un verbe d'action (explique, résume, compare, corrige, propose) et un résultat attendu.

## 3. Préciser le format

Dites à quoi doit ressembler la réponse : c'est l'un des leviers les plus simples et les plus efficaces.

- **La longueur** : « en cinq lignes », « en trois paragraphes ».
- **La forme** : liste à puces, tableau, étapes numérotées, e-mail prêt à envoyer.
- **Le ton** : formel, amical, pédagogique.
- **La langue** et le niveau de vocabulaire : « sans jargon », « niveau débutant ».

## 4. Montrer des exemples

Quand vous attendez un style ou une structure précise, un exemple vaut mieux qu'une longue description. Donnez un
ou deux modèles de ce que vous voulez, puis demandez la même chose pour votre cas.

```text
Voici deux descriptions de produits dans le style de ma boutique :
1. « Tasse en grès, 30 cl. Faite main, va au lave-vaisselle. »
2. « Bol en céramique, 50 cl. Émail mat, passe au micro-ondes. »

Écris la description d'une assiette plate en grès de 27 cm, dans le même style.
```

Le modèle reproduit alors la longueur, le ton et la structure, sans qu'il soit nécessaire de les décrire.

## 5. Relancer et affiner

La première réponse n'est pas forcément la bonne, et c'est normal. Une conversation se construit :

- **Corrigez précisément** : « Plus court », « Retire la deuxième partie », « Ajoute un exemple concret ».
- **Demandez des alternatives** : « Propose trois titres différents ».
- **Faites-le réfléchir par étapes** pour les problèmes complexes : « Avant de répondre, liste les hypothèses,
  puis raisonne étape par étape ».
- **Autorisez-le à poser des questions** : « Si des informations te manquent, pose-moi des questions avant de
  répondre ».

Sur une très longue conversation, il peut être utile de repartir de zéro avec une demande qui résume tout : la
[fenêtre de contexte](/blog/lexique-de-l-ia/) d'un modèle a ses limites.

## Les erreurs à éviter

1. **Tout mettre dans une seule demande géante** : découpez les tâches complexes en plusieurs étapes.
2. **Confier des informations sensibles** : mots de passe, données bancaires ou informations confidentielles
   n'ont rien à faire dans une conversation avec une IA, surtout en ligne.
3. **Croire la réponse sur parole** : un modèle peut se tromper avec assurance. Vérifiez les chiffres, les dates
   et les citations importants.
4. **Demander à l'IA ce qu'elle ne peut pas savoir** : sans accès à Internet, elle ignore les événements récents.

## Ce que ça change pour vous

1. **Contexte, objectif, format** : ces trois éléments suffisent à améliorer nettement la plupart des réponses.
2. **Un exemple vaut mieux qu'une longue explication** quand vous attendez un style précis.
3. **Dialoguez** : relancez, corrigez, affinez. Et si vous codez, nos
   [règles pour coder avec une IA](/blog/bien-coder-avec-une-ia/) appliquent la même logique au développement.

*Informations à jour au 28 novembre 2026.*
