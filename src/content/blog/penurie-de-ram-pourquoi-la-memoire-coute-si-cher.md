---
title: "Pénurie de RAM : pourquoi la mémoire coûte si cher"
description: "L'IA engloutit la production de mémoire et les prix de la RAM ont explosé. Ce qui se passe vraiment, les chiffres, et quand espérer une accalmie."
pubDate: 2026-11-25
category: hardware
featured: true
tags: ["Hardware", "Pénurie de RAM", "IA"]
---

En un an, une barrette de RAM est devenue l'un des composants les plus chers d'un PC. Un kit de 32 Go de DDR5,
qu'on trouvait autour de **72 $** à son prix le plus bas, ne descend plus sous les **375 $** chez les revendeurs
suivis par PCPartPicker, selon [Tom's Hardware](https://www.tomshardware.com/pc-components/ddr5/32gb-of-ddr5-now-costs-usd375-minimum-ai-shortage-continues-to-squeeze-pc-building).
Comment en est-on arrivé là ?

## La cause : l'IA a besoin d'une mémoire très particulière

Les puces qui entraînent et font tourner les modèles d'IA (les accélérateurs des centres de données) utilisent
de la **HBM** (*High Bandwidth Memory*) : des puces de mémoire empilées les unes sur les autres, collées au
processeur, pour obtenir un débit énorme.

Le problème, c'est que la HBM est fabriquée **dans les mêmes usines et sur les mêmes plaques de silicium** que
la mémoire de nos PC, consoles et téléphones. Or :

- la HBM consomme beaucoup plus de surface de silicium **par gigaoctet** que la DDR5 classique ;
- elle se vend nettement plus cher, donc les fabricants ont tout intérêt à lui donner la priorité.

Comme l'explique [Tom's Hardware](https://www.tomshardware.com/pc-components/ram/hbm-is-eating-your-ram), chaque
plaque de silicium réservée à l'IA, c'est autant de mémoire en moins pour le grand public.

> Trois fabricants se partagent l'essentiel de la production mondiale de DRAM : Samsung, SK hynix et Micron.
> Quand ils réorientent leurs usines, tout le marché le ressent.

## Les chiffres

Les hausses diffèrent selon les sources et les produits, mais la tendance est nette :

| Indicateur | Ce qu'on observe |
|---|---|
| Kit 32 Go DDR5 (prix le plus bas suivi) | environ 72 $ il y a un an, au moins 375 $ aujourd'hui ([Tom's Hardware](https://www.tomshardware.com/pc-components/ddr5/32gb-of-ddr5-now-costs-usd375-minimum-ai-shortage-continues-to-squeeze-pc-building)) |
| Prix contrats DRAM, 4e trimestre 2026 | encore **+10 à 15 %** sur un trimestre pour la DRAM classique ([TrendForce](https://www.trendforce.com/presscenter/news/20260930-13258.html)) |
| Mémoire et stockage des consoles Xbox | coût « multiplié par plus de 2,5 », selon Microsoft ([Xbox Wire](https://news.xbox.com/en-us/2026/06/25/xbox-console-price-update/)) |

Bonne nouvelle relative : les hausses **ralentissent**. Après des trimestres de flambée, TrendForce explique
que les augmentations de fin d'année sont plus modérées parce qu'une grande partie de la hausse est déjà
« dans les prix ». Mais ralentir ne veut pas dire baisser.

## Qui est touché ?

À peu près tout ce qui contient de la mémoire :

- **les PC** : RAM, SSD, mais aussi les cartes graphiques, dont la mémoire vidéo (GDDR) vient des mêmes
  fabricants ;
- **les consoles** : Sony et Microsoft ont relevé leurs prix en 2026, Microsoft citant explicitement le coût
  de la mémoire et du stockage ;
- **les téléphones, ordinateurs portables et objets connectés**, dont les fabricants doivent arbitrer entre
  prix plus élevés et configurations moins généreuses.

## Quand les prix vont-ils baisser ?

Probablement pas tout de suite. Construire une usine de mémoire prend plusieurs années, et la demande liée à
l'IA ne faiblit pas. Plusieurs acteurs du secteur évoquent une tension qui durera **au moins jusqu'en 2027**, et
certains parlent de bien plus longtemps. Les fabricants agrandissent leurs capacités, mais ces nouvelles lignes
de production serviront en priorité… à la HBM.

Côté consommateurs, le marché commence à réagir : selon
[TechRadar](https://www.techradar.com/pro/good-news-ram-prices-seem-to-have-finally-stabilized-bad-news-its-probably-because-memory-prices-are-so-high-that-its-forcing-most-of-us-to-give-up-buying-anything),
les prix de détail se stabilisent… surtout parce que beaucoup d'acheteurs renoncent à acheter.

## Ce qu'il faut retenir

1. La pénurie n'est pas un accident : c'est une **réallocation** de la production vers l'IA, plus rentable.
2. Les hausses ralentissent, mais un retour aux prix de 2024 n'est pas en vue.
3. Si vous comptez acheter de la RAM, mieux vaut **acheter ce dont vous avez besoin** que d'attendre une baisse
   qui pourrait tarder. Pour les joueurs, on détaille tout dans notre
   [guide pour monter son PC pendant la pénurie](/blog/monter-son-pc-gamer-pendant-la-penurie/).

*Chiffres à jour au 25 novembre 2026. Les prix évoluent vite : vérifiez avant d'acheter.*
