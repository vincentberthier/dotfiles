---
name: meal-planner
description: >-
  Generate weekly meal plans (lunch + dinner) as Obsidian Markdown files with recipes, grocery lists,
  and pantry tracking. Adapted for a French diet with weight-loss focus. Use when Claude needs to:
  (1) generate a new weekly meal plan, (2) create or update recipe files in Obsidian,
  (3) generate a grocery shopping list, (4) update the pantry inventory, or
  (5) any meal planning task involving the Projets/Meal-Plan/ Obsidian folder.
---

# Meal Planner

Générer des plans repas hebdomadaires sous forme de fichiers Obsidian Markdown, avec fiches recettes, listes de courses et suivi du fonds de placard.

**Cycle** : du mercredi au mardi suivant, calé sur l'unique course hebdomadaire du mercredi.

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
├── Liste de courses.md      # Boîte de réception : notes d'achat libres de l'utilisateur
├── Semaine-YYYY-WNN.md
└── Courses-YYYY-WNN.md
```

## Workflow principal — Générer un nouveau plan

### Étape 1 : Collecter le contexte

1. Lire les 4 fichiers de référence
2. Lire `CLAUDE.md` dans le dossier du projet pour le contexte spécifique (logistique courses, données caloriques vérifiées, leçons des cycles précédents)
3. Lire `Fonds-de-placard.md` pour connaître le stock actuel
4. Lire `Liste de courses.md` — boîte de réception où l'utilisateur note au fil de l'eau ce qu'il veut acheter. Chaque ligne doit se retrouver dans la liste de courses du cycle (voir § _Notes d'achat de l'utilisateur_ dans `generation-guidelines.md`)
5. Lire `Matériel.md` — **aucune recette ne doit exiger un ustensile ou un appareil absent de cette liste**. Vérifier avant d'écrire une fiche, pas après. Un blender, un robot, une râpe, un fouet électrique, un mixeur plongeant ne sont acquis que s'ils y figurent
6. Lire les recettes existantes dans `Recettes/` et les assemblages dans `Assemblages/` — noter les `note:` pour favoriser les bien notés (≥ 4) et exclure les mal notés (≤ 2)
7. Identifier la saison courante (date du jour)
8. Identifier le mercredi de départ du cycle et le numéro de semaine ISO correspondant

### Étape 2 : Concevoir les menus

Concevoir un cycle mercredi → mardi de déjeuners et dîners (7 déjeuners + 7 dîners) en respectant :

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
3. **Créer le fichier de plan hebdomadaire** (`Semaine-YYYY-WNN.md`, `NN` = semaine ISO du mercredi de départ)
4. **Créer le fichier de courses** (`Courses-YYYY-WNN.md`) couvrant le cycle — une seule course, le mercredi. Y reporter les lignes de `Liste de courses.md` et le déjeuner du mercredi suivant
5. **Vider `Liste de courses.md`** — une fois chaque ligne reportée dans son rayon, remettre le fichier à vide (frontmatter conservé s'il en a un). C'est une boîte de réception : elle repart blanche pour le cycle suivant
6. **Mettre à jour `Fonds-de-placard.md`** si des articles du fonds de placard manquent

Respecter scrupuleusement les formats définis dans `obsidian-conventions.md`.

### Étape 4 : Validation nutritionnelle

Spot-checker 5-6 recettes représentatives contre Ciqual (voir `generation-guidelines.md` § Nutritional Validation). Ajuster les estimations si un écart > 20 % est constaté.

### Étape 5 : Résumé

Présenter à l'utilisateur :

- Le plan du cycle mercredi → mardi (tableau récapitulatif)
- Les points nutritionnels clés (calories approximatives, répartition protéines)
- Le nombre de recettes créées / réutilisées
- Les articles à acheter / vérifier
- Les lignes reprises de `Liste de courses.md` et le rayon où chacune a atterri (le fichier ayant été vidé, c'est la seule trace de ce qui a été repris)
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
- **Matériel** : ne jamais écrire une étape qui suppose un appareil ou un ustensile absent de `Matériel.md`. En cas de doute, choisir la méthode manuelle (fouet plutôt que blender, couteau plutôt que robot) ou changer de recette
- **Zéro jargon dans les étapes.** Une étape décrit un geste et son résultat visible, en français courant. Un mot de métier ne se met **jamais** à la place du geste — ni « nacrer le riz », ni « monter au beurre », ni « faire suer », ni « déglacer », ni « blanchir », ni « réserver ». Écrire ce qu'on fait et ce qu'on doit voir : « remuer le riz 2 min dans l'huile chaude, jusqu'à ce que les grains deviennent brillants et un peu transparents sur les bords ». Le terme de métier peut suivre entre parenthèses, jamais précéder. Voir `generation-guidelines.md` § _Langue des recettes_ pour la table de traduction. Cette règle prime sur toute considération de concision : une étape longue et claire vaut mieux qu'une étape courte et opaque
- **Pas d'abats** : jamais de foie, rognons, cervelle, tripes, etc.
- **Quantités** : la règle concerne les achats et les conserves/paquets indivisibles — ne pas laisser des fonds de boîtes ou des restes de paquet inutilisables. En revanche, les produits surgelés ou facilement portionnables (pommes duchesse, poissons panés, steaks hachés, etc.) peuvent être utilisés en portions libres sur plusieurs repas sans problème
- **Confection quotidienne** : 15-20 min en moyenne, 30 min maximum
- **Repas élaboré** : 1 par semaine (dîner), jusqu'à 60 min. Doit être un plat gratifiant et « digne d'être servi à des invités » — pas juste long et laborieux. Marqué 🍽️ dans le plan
- **Pas de batch cooking** : chaque repas se prépare indépendamment
- **Congélation** : limitée à quelques portions maximum
- **Jour de sport** : mercredi par défaut, marqué ⚡ dans le plan. Le mercredi cumule course + sport + début de cycle → prévoir un dîner rapide ce jour-là
- **Déjeuner du mercredi : avant la course.** La course se fait le mercredi après-midi ; le déjeuner du mercredi est donc pris **avant**. Il ne peut utiliser **aucun** ingrédient de la liste de courses du cycle en cours. Il se compose de surgelés, conserves, fonds de placard, ou d'un article robuste acheté la semaine précédente. En contrepartie, chaque liste de courses inclut de quoi couvrir le déjeuner du mercredi **suivant**, marqué `(déj. mercredi prochain)`
- **Fraîcheur** : deux points d'appro possibles selon le contexte projet (voir `CLAUDE.md`). Par défaut, avec la seule course du mercredi, les produits les plus périssables (poisson frais, salade, herbes) se placent en début de cycle (mer–ven) et la fin de cycle repose sur des ingrédients robustes (conserves, surgelés, œufs, féculents, légumes racines, fromage). Si `CLAUDE.md` documente un second point d'appro confirmé en cours de semaine (marché, producteur), la seconde moitié du cycle peut s'appuyer dessus et des repas peuvent en dépendre
- **Induction avec fryingSensor** : la plaque régule la température de la poêle. Les cuissons à la poêle exigeantes (saisie, réduction, sauce montée) sont réalistes — ne pas les éviter par prudence
- **Petit-déjeuner** : pris en compte dans le budget calorique (~400-500 kcal) mais non planifié
- **Collations** : fruits (raisin, clémentines, poires) ou oléagineux si mentionnés, non planifiés
