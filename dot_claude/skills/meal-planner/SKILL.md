---
name: meal-planner
description: >-
  Generate biweekly meal plans (lunch + dinner) as Obsidian Markdown files with recipes, grocery lists,
  and pantry tracking. Adapted for a French diet with weight-loss focus. Use when Claude needs to:
  (1) generate a new 2-week meal plan, (2) create or update recipe files in Obsidian,
  (3) generate a grocery shopping list, (4) update the pantry inventory, or
  (5) any meal planning task involving the Projets/Meal-Plan/ Obsidian folder.
---

# Meal Planner

Générer des plans repas bihebdomadaires sous forme de fichiers Obsidian Markdown, avec fiches recettes, listes de courses et suivi du fonds de placard.

## Fichiers de référence

| Fichier                               | Contenu                                      | Quand le lire                                      |
| ------------------------------------- | -------------------------------------------- | -------------------------------------------------- |
| `references/profil.md`                | Profil utilisateur, contraintes, préférences | Toujours, en début de génération                   |
| `references/nutrition-guide.md`       | Recommandations PNNS/ANSES/OMS/HAS           | Toujours, pour calibrer les menus                  |
| `references/generation-guidelines.md` | Règles de conception des menus et courses    | Toujours, pour respecter les contraintes pratiques |
| `references/obsidian-conventions.md`  | Formats de fichiers, frontmatter, structure  | Toujours, pour produire les fichiers au bon format |

Lire les 4 fichiers de référence avant toute génération.

## Répertoire du projet

```
/home/vincent/Documents/Perso/Projets/Meal-Plan/
├── CLAUDE.md                # Contexte projet (logistique, données caloriques, leçons)
├── Recettes/                # Fiches recettes complètes (technique, sources Ciqual)
├── Assemblages/             # Fiches d'assemblage légères (ingrédients + 3-4 étapes)
├── Archive/
├── Fonds-de-placard.md
├── Semaine-YYYY-WNN.md
└── Courses-YYYY-WNN.md
```

## Workflow principal — Générer un nouveau plan

### Étape 1 : Collecter le contexte

1. Lire les 4 fichiers de référence
2. Lire `CLAUDE.md` dans le dossier du projet pour le contexte spécifique (logistique courses, données caloriques vérifiées, leçons des cycles précédents)
3. Lire `Fonds-de-placard.md` pour connaître le stock actuel
4. Lire les recettes existantes dans `Recettes/` et les assemblages dans `Assemblages/` — noter les `note:` pour favoriser les bien notés (≥ 4) et exclure les mal notés (≤ 2)
5. Identifier la saison courante (date du jour)
6. Identifier les numéros de semaine ISO à planifier

### Étape 2 : Concevoir les menus

Concevoir 2 semaines de déjeuners et dîners (14 déjeuners + 14 dîners) en respectant :

- **Profil** : contraintes caloriques et macros de `profil.md`
- **Nutrition** : recommandations de `nutrition-guide.md`
- **Conception** : règles de `generation-guidelines.md` (variété protéines, végétarien, saisonnalité, interchangeabilité, jour de sport)
- **Répétitions acceptées** : surtout pour les déjeuners, 2-3 types en rotation par semaine
- **Interchangeabilité** : chaque repas autonome, interchangeable au sein de sa catégorie

### Étape 3 : Générer les fichiers

Dans cet ordre :

1. **Archiver** les plans et courses précédents dans `Archive/`
2. **Créer les fiches manquantes** — réutiliser les recettes et assemblages bien notés quand pertinent. Pour chaque nouveau plat :
   - **Recette complète** (vraie technique) → fichier dans `Recettes/`, avec source en ligne dans `# Sources` (voir `generation-guidelines.md` § Source References).
   - **Assemblage** (procédure simple, aide-mémoire) → fichier dans `Assemblages/`, format réduit (voir `obsidian-conventions.md` § Format des Fiches d'Assemblage).
   - **Repas trivial** (composition évidente) → pas de fichier, juste lister les composants dans le plan hebdomadaire.
3. **Créer les 2 fichiers de plan hebdomadaire** (`Semaine-YYYY-WNN.md`)
4. **Créer le fichier de courses** (`Courses-YYYY-WNN.md`) couvrant les 2 semaines
5. **Mettre à jour `Fonds-de-placard.md`** si des articles du fonds de placard manquent

Respecter scrupuleusement les formats définis dans `obsidian-conventions.md`.

### Étape 4 : Validation nutritionnelle

Spot-checker 5-6 recettes représentatives contre Ciqual (voir `generation-guidelines.md` § Nutritional Validation). Ajuster les estimations si un écart > 20 % est constaté.

### Étape 5 : Résumé

Présenter à l'utilisateur :

- Le plan des 2 semaines (tableau récapitulatif)
- Les points nutritionnels clés (calories approximatives, répartition protéines)
- Le nombre de recettes créées / réutilisées
- Les articles à acheter / vérifier
- **Rapport de validation Ciqual** : tableau des recettes vérifiées avec estimation initiale, valeur Ciqual de référence, écart, et ajustement éventuel

## Workflow secondaire — Modifier le plan

Si l'utilisateur demande de remplacer un repas :

1. Proposer 2-3 alternatives interchangeables (même catégorie déjeuner/dîner)
2. Créer la recette si elle n'existe pas
3. Mettre à jour le fichier de plan hebdomadaire concerné
4. Recalculer la liste de courses si les ingrédients changent

## Workflow secondaire — Mettre à jour le fonds de placard

Si l'utilisateur signale des changements de stock :

1. Mettre à jour les cases à cocher dans `Fonds-de-placard.md`
2. Ajouter les nouveaux articles si nécessaire

## Règles impératives

- **Langue** : tout en français
- **Pas d'abats** : jamais de foie, rognons, cervelle, tripes, etc.
- **Quantités** : la règle concerne les achats et les conserves/paquets indivisibles — ne pas laisser des fonds de boîtes ou des restes de paquet inutilisables. En revanche, les produits surgelés ou facilement portionnables (pommes duchesse, poissons panés, steaks hachés, etc.) peuvent être utilisés en portions libres sur plusieurs repas sans problème
- **Confection quotidienne** : 15-20 min en moyenne, 30 min maximum
- **Repas élaboré** : 1 par semaine (dîner), jusqu'à 60 min. Doit être un plat gratifiant et « digne d'être servi à des invités » — pas juste long et laborieux. Marqué 🍽️ dans le plan
- **Pas de batch cooking** : chaque repas se prépare indépendamment
- **Congélation** : limitée à quelques portions maximum
- **Jour de sport** : mercredi par défaut, marqué ⚡ dans le plan
- **Petit-déjeuner** : pris en compte dans le budget calorique (~400-500 kcal) mais non planifié
- **Collations** : fruits (raisin, clémentines, poires) ou oléagineux si mentionnés, non planifiés
