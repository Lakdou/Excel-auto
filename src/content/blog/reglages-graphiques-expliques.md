---
title: "Réglages graphiques expliqués : DLSS, FSR, ray tracing, que faut-il activer ?"
description: "Mise à l'échelle, génération d'images, ray tracing, textures, ombres : ce que font vraiment les options graphiques des jeux PC, et lesquelles sacrifier en premier pour gagner des images par seconde."
pubDate: 2026-11-28T01:50:00Z
category: gaming
icon: gamepad
tags: ["Gaming", "Réglages", "Guide"]
---

Le menu « Graphismes » des jeux PC ressemble souvent à un tableau de bord d'avion : DLSS, FSR, ray tracing,
occlusion ambiante, anticrénelage… Bonne nouvelle : quelques options pèsent bien plus que les autres. Bien
choisies, elles font gagner beaucoup d'images par seconde sans dégrader visiblement l'image.

## La mise à l'échelle : le réglage le plus rentable

Le principe : le jeu calcule l'image dans une **définition plus basse**, puis un algorithme l'agrandit jusqu'à
la définition de votre écran en reconstruisant les détails. Le gain de fluidité est souvent spectaculaire.

| Technologie | Éditeur | Compatibilité |
|---|---|---|
| **DLSS** | NVIDIA | Cartes NVIDIA RTX uniquement |
| **FSR** | AMD | La plupart des cartes graphiques, y compris NVIDIA et Intel |
| **XeSS** | Intel | Cartes Intel, et de nombreuses autres cartes récentes |

Ces technologies proposent plusieurs modes, du plus beau au plus rapide (par exemple « Qualité », « Équilibré »,
« Performance »). En pratique :

- en **1440p et en 4K**, le mode « Qualité » est souvent difficile à distinguer de l'image native, pour un gain
  net de fluidité ;
- en **1080p**, l'image de départ est plus petite : restez en « Qualité », les modes plus agressifs se voient
  davantage.

## La génération d'images : plus fluide, mais pas plus réactif

Certaines cartes récentes peuvent **inventer des images intermédiaires** entre deux images réellement calculées
(la fonction s'appelle « génération d'images » ou *frame generation*). Le compteur d'images par seconde grimpe et
l'animation paraît plus fluide.

Mais attention : ces images supplémentaires ne tiennent pas compte de vos actions, et la technique ajoute un peu
de latence. Elle fonctionne bien quand le jeu tourne déjà correctement (au moins une soixantaine d'images par
seconde avant activation), et beaucoup moins pour sauver un jeu qui rame. Associez-la à NVIDIA Reflex ou AMD
Anti-Lag pour limiter la latence, comme expliqué dans notre guide pour
[réduire la latence en jeu](/blog/reduire-la-latence-en-jeu/). Pour les jeux compétitifs, mieux vaut souvent la
désactiver.

## Le ray tracing : magnifique, mais très gourmand

Le **ray tracing** (lancer de rayons) simule le trajet de la lumière : reflets réalistes, ombres douces,
éclairage indirect. Le rendu peut être superbe, mais c'est l'option la plus coûteuse : l'activer peut diviser le
nombre d'images par seconde de façon importante sur de nombreuses cartes.

Conseil : si vous tenez au ray tracing, activez en même temps la mise à l'échelle (DLSS, FSR ou XeSS). Les deux
sont pensés pour fonctionner ensemble.

## Les autres réglages, par ordre d'impact

| Réglage | Impact sur les performances | Notre conseil |
|---|---|---|
| Ombres | Élevé | Passez de « Ultra » à « Élevé » : la différence se voit à peine |
| Brouillard et effets volumétriques | Élevé | Une des premières options à baisser |
| Occlusion ambiante | Moyen | Gardez un niveau moyen, elle donne de la profondeur à l'image |
| Qualité des textures | Faible, **si** la mémoire vidéo suffit | Montez-la tant que la VRAM le permet ; au-delà, saccades |
| Anticrénelage | Variable | Souvent géré par la mise à l'échelle, pas besoin de le doubler |
| Flou de mouvement, grain | Faible | Question de goût : beaucoup de joueurs les désactivent |

Les **textures** sont un cas à part : elles consomment surtout de la **mémoire vidéo**. Si votre carte en manque,
le jeu se met à saccader, même si le nombre d'images par seconde moyen paraît correct. Beaucoup de jeux affichent
une jauge d'utilisation de la mémoire vidéo dans leurs options : surveillez-la.

## La bonne méthode, en quatre étapes

1. **Partez du préréglage « Élevé »** plutôt que « Ultra » : l'écart visuel est faible, l'écart de performances
   souvent important.
2. **Activez la mise à l'échelle** en mode « Qualité ».
3. **Baissez les ombres et les effets volumétriques** si vous manquez encore de fluidité.
4. **Gardez les textures élevées** tant que la mémoire vidéo suit.

Et pensez aux pilotes : les mises à jour des fabricants de cartes graphiques apportent régulièrement des
optimisations pour les nouveaux jeux.

## Ce que ça change pour vous

1. **La mise à l'échelle (DLSS, FSR, XeSS)** est le réglage le plus rentable : activez-la en priorité.
2. **La génération d'images** rend l'image plus fluide, pas le jeu plus réactif.
3. **« Élevé » plutôt qu'« Ultra »** : c'est souvent le meilleur compromis. Et si votre carte graphique montre ses
   limites, notre [guide pour monter son PC pendant la pénurie](/blog/monter-son-pc-gamer-pendant-la-penurie/)
   vous aide à choisir quoi améliorer.

*Informations à jour au 28 novembre 2026.*
