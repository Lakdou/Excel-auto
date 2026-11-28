---
title: "Votre SSD s'use-t-il trop vite ? Comment vérifier sa santé"
description: "Un bug des pilotes NVIDIA a fait écrire des gigaoctets par heure sur des SSD au repos. L'occasion d'apprendre à lire l'usure de son SSD (TBW, SMART) et à repérer un logiciel qui écrit trop."
pubDate: 2026-11-28T06:50:00Z
category: hardware
icon: ram
tags: ["SSD", "NVIDIA", "Guide"]
---

Un SSD ne s'use pas comme un disque dur mécanique : ce sont les **écritures** qui le fatiguent, pas le temps qui
passe. En temps normal, un particulier est très loin des limites. Mais un logiciel défaillant peut changer la
donne, comme l'ont montré ces dernières semaines des pilotes graphiques NVIDIA. Voici comment vérifier où en est
votre SSD, et comment repérer un programme qui écrit beaucoup trop.

## Le cas des pilotes NVIDIA 621.14 et 621.24

Selon [Tom's Hardware](https://www.tomshardware.com/pc-components/gpu-drivers/nvidia-geforce-driver-bug-reportedly-hammers-ssds-with-up-to-30gb-of-writes-per-hour-users-trace-massive-idle-wear-to-background-service-newer-driver-reportedly-still-affected),
[Guru3D](https://www.guru3d.com/story/reports-indicate-recent-nvidia-geforce-drivers-may-generate-heavy-ssd-writes/)
et [Windows Latest](https://www.windowslatest.com/2026/11/20/first-amd-now-nvidia-your-gpu-driver-could-be-quietly-wearing-out-your-windows-11-pcs-ssd-and-nvidia-hasnt-even-admitted-it/),
des utilisateurs des pilotes GeForce **621.14** et **621.24** ont constaté que leur SSD travaillait sans arrêt,
même quand le PC ne faisait rien :

- le processus en cause est **NVDisplay.Container.exe**, un service d'arrière-plan des pilotes ;
- il réécrit en boucle un fichier journal, `nvlog.nvlgstg`, situé dans `C:\ProgramData\NVIDIA Corporation\` ;
- le volume signalé varie beaucoup selon les machines : de quelques gigaoctets jusqu'à environ **30 Go par
  heure** dans les cas les plus graves.

Côté correctif, [Notebookcheck](https://www.notebookcheck.net/Nvidia-releases-hotfix-for-GeForce-driver-bug-that-hammered-SSDs-with-up-to-30-GB-of-writes-an-hour.1456096.0.html)
rapporte la sortie d'un pilote correctif, et [TechRepublic](https://www.techrepublic.com/article/news-nvidia-621-40-ssd-write-bug-fix-affected-gpus/)
indique que la version **621.40** s'attaque au problème. Certains utilisateurs jugent toutefois la correction
incomplète : mieux vaut vérifier par vous-même, avec la méthode ci-dessous.

Pour se faire une idée : 30 Go par heure sur un PC allumé jour et nuit, cela représente environ 720 Go par jour,
soit plus de 250 To en un an. C'est énorme au regard de l'endurance d'un SSD grand public.

## Comprendre l'endurance d'un SSD : le TBW

Chaque fabricant annonce une **endurance**, exprimée en **TBW** (*terabytes written*, téraoctets écrits) : la
quantité totale de données que le SSD est garanti pouvoir écrire. Elle figure dans la fiche technique et
conditionne souvent la garantie (« 5 ans **ou** X TBW, au premier terme atteint »).

Pour un usage classique (jeux, bureautique, navigation), on écrit en général quelques dizaines de gigaoctets
par jour au plus : la plupart des SSD grand public tiendront alors bien plus longtemps que le reste du PC. Le
risque vient des écritures anormales et continues, comme dans le cas des pilotes NVIDIA.

## Vérifier l'état de son SSD

Tous les SSD tiennent un journal interne, les données **SMART**, qui indique leur état de santé.

| Outil | Système | Ce qu'il affiche |
|---|---|---|
| Paramètres de Windows 11 | Windows | « Santé du disque » et durée de vie restante estimée (SSD NVMe) |
| [CrystalDiskInfo](https://crystalmark.info/en/software/crystaldiskinfo/) | Windows | État de santé en pourcentage, total des écritures (*Host Writes*) |
| Logiciel du fabricant | Windows | Santé, mises à jour du firmware |
| [smartctl](https://www.smartmontools.org/) | Linux, macOS, Windows | Toutes les données SMART en ligne de commande |

Sous Windows 11, le chemin est : **Paramètres > Système > Stockage > Paramètres de stockage avancés > Disques et
volumes**, puis **Propriétés** sur le SSD.

Sous Linux, une commande suffit (le nom du disque peut varier) :

```bash
sudo smartctl -a /dev/nvme0
```

Les deux lignes à regarder sur un SSD NVMe : **Percentage Used** (le pourcentage de l'endurance déjà consommé)
et **Data Units Written** (le volume total écrit). Comparez ce volume à la valeur TBW de votre modèle.

## Repérer un programme qui écrit trop

Le total d'écritures augmente vite alors que vous ne faites rien ? Cherchez le coupable :

1. Ouvrez le **Moniteur de ressources** : touches Windows + R, tapez `resmon`, puis Entrée.
2. Allez dans l'onglet **Disque** et triez la liste par la colonne **Écriture (octets/s)**.
3. Laissez le PC au repos quelques minutes : un processus qui écrit en permanence plusieurs mégaoctets par
   seconde sans raison mérite une enquête. Le moniteur affiche aussi le **fichier** concerné.

Autre méthode simple : notez le total d'écritures dans CrystalDiskInfo, laissez le PC allumé une heure sans
l'utiliser, puis comparez.

## Ce que ça change pour vous

1. **Si vous avez une carte NVIDIA**, vérifiez la version de votre pilote et installez la plus récente. Puis
   contrôlez dans le Moniteur de ressources que `NVDisplay.Container.exe` n'écrit plus en boucle.
2. **Contrôlez la santé de votre SSD** une ou deux fois par an : le pourcentage d'usure et le total d'écritures
   suffisent.
3. **Pas de panique** : en usage normal, un SSD dure des années. Et si vous devez en changer, notre
   [guide pour choisir son SSD](/blog/choisir-son-ssd-pour-jouer/) et notre
   [point sur les prix de la mémoire](/blog/memoire-ssd-baisse-2027-ram-reste-chere/) vous aideront.

*Informations à jour au 28 novembre 2026.*
