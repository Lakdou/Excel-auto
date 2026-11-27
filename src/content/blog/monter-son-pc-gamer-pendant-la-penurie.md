---
title: "Monter ou améliorer son PC gamer pendant la pénurie de RAM"
description: "Combien de RAM pour jouer, DDR4 ou DDR5, occasion, réglages oubliés : le guide pratique pour avoir un bon PC de jeu sans se ruiner en pleine crise de la mémoire."
pubDate: 2026-11-26T18:00:00Z
category: hardware
icon: tower
tags: ["Gaming", "Hardware", "Guide"]
---

Avec la [flambée des prix de la mémoire](/blog/penurie-de-ram-pourquoi-la-memoire-coute-si-cher/), monter un PC
de jeu demande de faire des choix. Bonne nouvelle : avec les bons arbitrages, on peut encore avoir une très bonne
machine sans vider son compte en banque.

## 1. Combien de RAM faut-il vraiment pour jouer ?

| Quantité | Pour qui ? |
|---|---|
| 8 Go | Insuffisant pour les jeux récents : saccades et chargements à rallonge |
| **16 Go** | Le minimum confortable pour la grande majorité des jeux |
| **32 Go** | Le confort : jeu + navigateur + Discord + streaming en même temps |
| 64 Go et plus | Montage vidéo, 3D, IA en local… rarement utile pour le jeu seul |

En pleine pénurie, **16 Go en double canal** (2 × 8 Go) reste un très bon point de départ. Vous pourrez ajouter
une seconde paire plus tard, si votre carte mère a quatre emplacements.

## 2. Vérifiez d'abord ce que vous avez déjà

Avant d'acheter, regardez combien de mémoire vos jeux utilisent réellement. Sous Windows, dans PowerShell :

```powershell
# Mémoire installée, par barrette (capacité en Go et vitesse)
Get-CimInstance Win32_PhysicalMemory |
  Select-Object Manufacturer, PartNumber,
    @{n="Go"; e={$_.Capacity / 1GB}}, ConfiguredClockSpeed
```

Sous Linux :

```bash
free -h                      # mémoire totale, utilisée, disponible
sudo dmidecode -t memory | grep -E "Size|Speed|Part Number"
```

Lancez votre jeu le plus gourmand, puis regardez le Gestionnaire des tâches (onglet *Performances*). Si vous
restez sous 75 % d'utilisation, **la RAM n'est pas votre problème** : investissez plutôt dans la carte graphique
ou le SSD.

## 3. Le réglage oublié : XMP / EXPO

Beaucoup de PC tournent avec leur RAM **bien en dessous de sa vitesse nominale**, parce que le profil
d'usine n'a jamais été activé. Dans le BIOS, activez **XMP** (Intel) ou **EXPO** (AMD) : c'est gratuit, et le
gain peut être sensible dans les jeux qui dépendent du processeur.

```text
Vitesse annoncée sur la barrette : DDR5-6000
Vitesse réelle sans profil XMP/EXPO : souvent DDR5-4800
```

Vérifiez la vitesse réelle avec la commande PowerShell ci-dessus (colonne `ConfiguredClockSpeed`).

## 4. DDR4 ou DDR5 ?

La DDR5 est plus rapide, mais c'est aussi elle qui a le plus augmenté. Si vous avez déjà une plateforme DDR4
(par exemple une carte mère AM4 chez AMD), **la garder est souvent le choix le plus rentable** : un processeur
plus récent compatible et votre RAM actuelle offrent un vrai gain sans racheter de mémoire.

Pour un PC entièrement neuf, la DDR5 reste l'avenir : achetez simplement la quantité dont vous avez besoin
maintenant, sans surdimensionner.

## 5. Acheter d'occasion sans se faire avoir

Le marché de l'occasion est une bonne piste, mais les arnaques se multiplient avec la hausse des prix :

- **testez** la mémoire dès réception avec MemTest86 (quelques passes suffisent) ;
- **comparez la référence exacte** (le *Part Number*) avec les photos de l'annonce ;
- **méfiez-vous des prix trop bas** et des vendeurs sans historique ;
- **privilégiez des paires identiques** : mélanger des barrettes différentes cause souvent des instabilités.

## 6. Et si la console était plus raisonnable ?

Pour jouer sur un téléviseur, une console reste souvent plus simple, même si
[ses prix augmentent aussi](/blog/gaming-ce-que-la-penurie-de-memoire-change/). Le jeu en nuage (cloud gaming)
est une autre piste : pas de matériel à acheter, mais un abonnement et une bonne connexion internet.

## En résumé

1. **16 Go suffisent** pour la plupart des jeux ; 32 Go si vous faites autre chose en même temps.
2. **Mesurez avant d'acheter** : la RAM n'est peut-être pas ce qui vous limite.
3. **Activez XMP/EXPO**, c'est gratuit.
4. **Gardez votre plateforme DDR4** si elle vous convient encore.
5. **Achetez ce dont vous avez besoin**, plutôt que d'attendre une baisse qui pourrait tarder.
