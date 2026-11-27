---
title: "Bienvenue sur Octet"
description: "Pourquoi ce blog, ce que vous y trouverez, et comment il est construit : Astro, Markdown et zéro serveur."
pubDate: 2026-11-20
tags: ["Meta", "Astro"]
---

Bienvenue ! **Octet** est un blog sur le développement, l'intelligence artificielle, le matériel PC et le gaming.
La promesse est simple : des articles **concrets**, avec du code qui fonctionne, que vous pouvez réutiliser
le jour même.

## Ce que vous trouverez ici

- **Des tutoriels pas à pas** : Python, JavaScript, Git, automatisation de tâches répétitives.
- **De l'IA pratique** : comment utiliser les assistants de code sans perdre la main sur son projet.
- **Du matériel et du gaming** : l'actualité décryptée (prix, pénuries, sorties) et des guides pour monter son PC.
- **Des astuces** pour gagner quelques minutes chaque jour, qui deviennent des heures à la fin du mois.

## Comment ce blog est construit

Chaque article est un simple fichier texte au format [Markdown](https://commonmark.org/help/). Le site est
généré par [Astro](https://astro.build), qui transforme ces fichiers en pages HTML statiques :

| Avantage | Pourquoi c'est important |
|---|---|
| Aucun serveur | Rien à maintenir, rien à pirater |
| Pages statiques | Affichage quasi instantané |
| Hébergement gratuit | GitHub Pages suffit largement |
| Fichiers texte | Historique complet grâce à Git |

Écrire un nouvel article revient à créer un fichier dans `src/content/blog/` :

```markdown
---
title: "Mon nouvel article"
description: "Une phrase qui donne envie de lire la suite."
pubDate: 2026-12-01
tags: ["Python"]
---

Le contenu de l'article, en **Markdown**.
```

> Astuce : ajoutez `draft: true` dans l'en-tête pour travailler sur un brouillon sans le publier.

Bonne lecture, et n'hésitez pas à vous abonner au flux RSS pour ne rien manquer.
