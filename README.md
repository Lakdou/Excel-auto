# Octet — tech, dev, IA & gaming

Un blog rapide et sans serveur, construit avec [Astro](https://astro.build). Chaque article est un simple fichier
Markdown ; le site est généré en pages statiques et publié gratuitement sur GitHub Pages.

**Ce qui est inclus** : accueil, liste des articles avec recherche instantanée, pages par tag, sommaire qui suit
la lecture, temps de lecture, code coloré avec bouton « Copier », thème clair / sombre (qui suit l'appareil et
se mémorise), flux RSS, sitemap, `robots.txt`, aperçus pour les réseaux sociaux, page 404, affichage mobile.

## Démarrer

```bash
npm install
npm run dev        # http://localhost:4321, rechargement automatique
```

## Écrire un article

Créez un fichier dans `src/content/blog/`, par exemple `mon-article.md`. Le nom du fichier devient l'adresse
(`/blog/mon-article/`).

````markdown
---
title: "Mon article"
description: "Une ou deux phrases qui donnent envie de lire (20 à 300 caractères)."
pubDate: 2026-12-01
tags: ["Python", "IA"]
draft: true        # facultatif : brouillon non publié
updatedDate: 2026-12-05   # facultatif
---

Le contenu en **Markdown**. Les titres `##` et `###` alimentent le sommaire.

```python
print("Le code est coloré automatiquement")
```
````

L'en-tête est vérifié : un champ manquant ou mal écrit bloque la publication avec un message clair.
Les images se placent dans `public/` et s'insèrent avec `![description](/mon-image.png)`.

## Personnaliser

Tout se règle dans [`src/config.ts`](src/config.ts) : nom du blog, accroche, description, auteur, liens.
Les couleurs sont définies en haut de [`src/styles/global.css`](src/styles/global.css).

## Publier sur GitHub Pages

1. Sur GitHub : **Settings › Pages › Source : GitHub Actions** (une seule fois).
2. Chaque push sur la branche `main` publie le site automatiquement. On peut aussi lancer la publication à la
   main : onglet **Actions › Déploiement GitHub Pages › Run workflow**.

L'adresse du site (`https://<utilisateur>.github.io/<dépôt>/`) est détectée automatiquement.

## Vérifications

```bash
npm test           # types (astro check) + build + vérification du site généré
npm run test:e2e   # tests dans un vrai navigateur (après npm run build && npx astro preview)
```

La vérification du site contrôle chaque page : liens internes et ancres, titre, description, un seul titre
principal, flux RSS, sitemap et `robots.txt`. Les tests navigateur couvrent l'accueil, les articles (sommaire,
bouton Copier), le thème sombre, la recherche, les tags, la page 404, l'accessibilité au clavier et l'affichage
mobile. La CI GitHub Actions lance l'ensemble à chaque push.

## Structure

```
src/
  config.ts              Réglages du blog
  content.config.ts      Format des articles (vérifié)
  content/blog/          Les articles (Markdown)
  layouts/               Mise en page générale et page d'article
  components/            En-tête, pied de page, carte d'article, liste de tags
  pages/                 Accueil, articles, tags, à propos, RSS, robots.txt, 404
  styles/global.css      Styles (thèmes clair et sombre)
scripts/check-site.mjs   Vérification du site généré
tests/e2e/               Tests navigateur (Playwright)
```
