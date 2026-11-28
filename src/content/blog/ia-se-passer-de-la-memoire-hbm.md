---
title: "Face à la pénurie de HBM, l'IA cherche à se passer de la mémoire la plus chère"
description: "Nvidia et Kioxia transforment 144 SSD en mémoire pour GPU, Intel mise sur de la LPDDR5X : l'industrie teste des alternatives à la HBM. Ce que ça peut changer, et ses limites."
pubDate: 2026-11-28T00:50:00Z
category: ia
icon: ram
tags: ["IA", "Pénurie de RAM", "HBM"]
---

La HBM, cette mémoire ultra-rapide empilée à côté des puces d'IA, est au cœur de la
[pénurie de mémoire](/blog/penurie-de-ram-pourquoi-la-memoire-coute-si-cher/) : chère, difficile à produire, et
grande consommatrice de lignes de production. Résultat, l'industrie commence à chercher comment en utiliser
moins. Deux pistes viennent d'être présentées : des **SSD** utilisés comme extension de mémoire, et de la
**mémoire de téléphone** à la place de la HBM.

## Nvidia et Kioxia : 144 SSD branchés comme de la mémoire

Le 26 novembre, Kioxia et Nvidia ont présenté une **preuve de concept** : faire utiliser par des GPU des SSD
comme s'il s'agissait de mémoire supplémentaire. D'après
[TechPowerUp](https://www.techpowerup.com/355250/kioxia-and-nvidia-collaborate-to-expand-effective-high-bandwidth-memory-capacity-with-ssds),
[TweakTown](https://www.tweaktown.com/news/114898/nvidia-and-kioxia-combine-high-bandwidth-memory-with-fast-ssds-to-push-memory-capacity-beyond-1-petabyte/index.html)
et [HotHardware](https://hothardware.com/news/kioxia-nvidia-tap-144-ssds-stretch-gpu-memory-1-petabyte), le
dispositif repose sur :

| Élément | Détail |
|---|---|
| Serveur | Une baie Nvidia GB200 NVL72, avec 18 nœuds de serveurs |
| Stockage | 144 SSD Kioxia de la gamme XD8, de 7,68 To chacun |
| Capacité totale | Environ **1,1 pétaoctet** de mémoire flash brute |
| Logiciel | SCADA, de Nvidia, qui permet aux GPU d'accéder directement aux SSD, par blocs de 512 octets |
| Test | Une base de 2 000 milliards de « vecteurs » (les données qu'utilisent les IA pour retrouver des informations) |

L'idée est simple : un SSD est bien plus lent que la HBM, mais il coûte beaucoup moins cher par gigaoctet et
offre des capacités gigantesques. Pour certaines tâches, comme la recherche dans d'immenses bases de données,
la capacité compte davantage que la vitesse pure.

Prudence toutefois : il s'agit d'une démonstration, pas d'un produit. Les deux entreprises disent encore évaluer
la faisabilité et les performances, et l'annonce ne donne ni débit ni latence mesurés.

## Intel : de la mémoire de smartphone à la place de la HBM

Intel prend une autre route avec sa puce d'IA baptisée Crescent Island, commercialisée sous le nom
**Intel GPU D-series**. Au lieu de la HBM, elle utilise de la **LPDDR5X**, la mémoire basse consommation des
smartphones et des ordinateurs portables. Selon
[Tom's Hardware](https://www.tomshardware.com/pc-components/gpus/intel-details-long-awaited-crescent-island-ai-gpu-at-computex-boasts-up-to-480-gb-of-lpddr5x-to-combat-memory-shortages-company-shares-more-details-of-its-xe3p-inference-accelerator-at-computex)
et [ServeTheHome](https://www.servethehome.com/intel-crescent-island-160gb-to-480gb-lpddr5x-ai-gpu-at-hot-chips-2026/) :

- la carte d'Intel embarque **160 Go** de mémoire, et les cartes de ses partenaires pourront monter jusqu'à
  **480 Go** ;
- la bande passante annoncée est de 1,5 To/s, pour une consommation de 350 watts avec un simple
  refroidissement par air ;
- elle vise l'**inférence**, c'est-à-dire l'utilisation des modèles d'IA déjà entraînés, plutôt que leur
  entraînement.

La LPDDR5X est nettement moins rapide que la HBM des puces d'IA les plus puissantes. Le pari d'Intel : pour
faire tourner des modèles, beaucoup de mémoire à un coût raisonnable vaut mieux que peu de mémoire très rapide.

## Une bonne nouvelle pour les prix ?

Pas forcément, et pas tout de suite. Ces deux approches pourraient, à terme, réduire un peu la pression sur la
HBM. Mais elles déplacent aussi la demande vers d'autres mémoires, fabriquées par la même industrie : la
**mémoire flash des SSD**, dont TrendForce prévoyait déjà une hausse des prix contrats de 15 à 20 % au
quatrième trimestre ([TrendForce](https://www.trendforce.com/presscenter/news/20260930-13258.html)), et la
**LPDDR5X**, également utilisée dans les téléphones et les ordinateurs portables.

## Ce que ça change pour vous

1. **Rien dans l'immédiat** : la démonstration de Kioxia et Nvidia n'est pas un produit, et la puce d'Intel vise
   les centres de données.
2. **Les SSD ne sont pas à l'abri** : si l'IA se met à consommer davantage de mémoire flash, leurs prix pourraient
   rester élevés. Si vous en avez besoin, notre [guide pour choisir son SSD](/blog/choisir-son-ssd-pour-jouer/)
   vous aide à ne pas payer pour des performances inutiles.
3. **Une tendance à suivre** : la mémoire est devenue le principal goulot d'étranglement de l'IA, et chaque
   alternative crédible à la HBM aura des effets sur tout le marché.

*Informations à jour au 28 novembre 2026.*
