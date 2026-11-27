---
title: "Coder avec une IA : 7 règles pour rester aux commandes"
description: "Les assistants de code font gagner un temps fou, à condition de bien les utiliser. Sept règles simples pour obtenir du code fiable."
pubDate: 2026-11-26
tags: ["IA", "Productivité"]
---

Les assistants de code basés sur l'IA écrivent des fonctions entières en quelques secondes. Le risque ? Accepter
du code qu'on ne comprend pas, et le payer plus tard. Voici sept règles pour en tirer le meilleur.

## 1. Donnez du contexte, pas seulement une consigne

« Écris une fonction de tri » donne un résultat générique. Précisez le langage, les contraintes et le cas
d'usage :

> En Python 3.12, écris une fonction qui trie une liste de commandes (dictionnaires avec les clés `date` et
> `montant`) par date décroissante, puis par montant. Les dates sont des chaînes au format `JJ/MM/AAAA`.

## 2. Demandez des tests en même temps que le code

Les tests sont votre filet de sécurité. Demandez-les explicitement, puis **lisez-les** : ils décrivent ce que
le code est censé faire.

```python
def test_tri_par_date_puis_montant():
    commandes = [
        {"date": "02/01/2024", "montant": 10},
        {"date": "03/01/2024", "montant": 5},
        {"date": "02/01/2024", "montant": 20},
    ]
    assert [c["montant"] for c in trier(commandes)] == [5, 10, 20]
```

## 3. Avancez par petites étapes

Une grosse demande produit un gros bloc de code difficile à vérifier. Découpez : d'abord la structure, puis
chaque fonction, puis la gestion des erreurs. Après chaque étape, lancez les tests.

## 4. Lisez tout ce que vous acceptez

Si vous ne pourriez pas expliquer une ligne à un collègue, ne la gardez pas. Demandez à l'IA de l'expliquer, ou
de proposer une version plus simple.

## 5. Méfiez-vous des détails inventés

Une IA peut citer avec assurance une fonction ou une option qui n'existe pas. Vérifiez dans la documentation
officielle dès qu'un nom ne vous dit rien, et laissez les tests trancher.

## 6. Ne collez jamais de secrets

Mots de passe, clés d'API, données clients : rien de tout cela ne doit apparaître dans une conversation.
Remplacez-les par des valeurs factices comme `API_KEY="xxx"`.

## 7. Gardez Git comme filet de sécurité

Faites un commit avant chaque modification importante générée par l'IA. Si le résultat ne convient pas,
revenir en arrière prend une seconde :

```bash
git add -A && git commit -m "Avant refactorisation"
# ... l'IA modifie le code ...
git diff            # voir exactement ce qui a changé
git restore .       # tout annuler si besoin
```

## En résumé

L'IA est un excellent **copilote**, mais c'est vous qui tenez le manche : contexte précis, petites étapes,
tests systématiques et relecture. Avec ces réflexes, vous codez plus vite *et* mieux.
