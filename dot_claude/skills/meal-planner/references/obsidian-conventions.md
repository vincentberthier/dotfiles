# Conventions Obsidian

## Emplacement des Fichiers

Base du vault : `/home/vincent/Documents/Perso/`
Base du projet : `Projets/Meal-Plan/`

Structure :

```
Projets/Meal-Plan/
├── Recettes/                    # Fiches recettes complètes (technique, sources)
├── Assemblages/                 # Fiches d'assemblage légères (ingrédients + 3-4 étapes)
├── Fonds-de-placard.md          # Inventaire des ingrédients de base
├── Liste de courses.md          # Boîte de réception : notes d'achat libres de l'utilisateur
├── Semaine-YYYY-WNN.md          # Plan hebdomadaire (ex: Semaine-2026-W06.md)
├── Courses-YYYY-WNN.md          # Liste de courses pour cette période
└── Archive/                     # Plans précédents déplacés ici
```

Voir `generation-guidelines.md` § _Trois types de repas_ pour la distinction entre trivial (pas de fichier), assemblage (fiche légère dans `Assemblages/`) et recette (fiche complète dans `Recettes/`).

## Frontmatter - Fileclass "recette"

Chaque fiche recette utilise la fileclass `recette` avec ce frontmatter :

```yaml
---
catégorie: recette
création: YYYY-MM-DD
tags:
  - Projet/Meal-Plan
type-repas: déjeuner | dîner | les-deux
protéine-principale: poulet | bœuf | porc | poisson | œufs | légumineuses | tofu | aucune
temps-confection: 10 | 15 | 20 | 25 | 30
portions: 1
calories-approx: <number>
saison: printemps | été | automne | hiver | toutes
note: <1-5 or empty>
terminée: true
---
```

Notes :

- `type-repas` : `les-deux` si la recette convient aux deux
- `protéine-principale` : la protéine dominante
- `temps-confection` : en minutes, arrondi au multiple de 5
- `calories-approx` : calories approximatives par portion
- `saison` : saison optimale pour les ingrédients, `toutes` si pas de saisonnalité
- `note` : vide à la création, rempli par l'utilisateur après dégustation (1=bof, 5=excellent)
- `terminée` : toujours `true` à la création (la recette est complète)

## Format des Recettes

```markdown
# Ingrédients

- 150 g de blanc de poulet
- 1 courgette
- ...

# Préparation

1. Étape 1...
2. Étape 2...

# Notes

- Variante possible : ...
- Se conserve X jours au frigo

# Sources

- [Nom de la recette de référence - NomDuSite](https://url-de-la-recette)
```

- **Langue des étapes** : français courant, zéro terme de métier employé seul. Voir
  `generation-guidelines.md` § _Langue des recettes — zéro jargon_ et sa table de traduction. Une
  étape se lit et s'exécute sans ouvrir `Lexique cuisine.md`.
- Section **Notes** : optionnelle, pour astuces de conservation, variantes, ou accompagnements alternatifs.
- **Niveaux de cuisson** : toute étape à la poêle indique le niveau **fryingSensor** (1 à 5) plutôt
  qu'un « feu moyen-vif » vague — le niveau de la table aliment → niveau du matériel fait foi. Les
  étapes sans correspondance (cuisson à l'eau, four, cuisson à couvert, sauce montée sous 120 °C) le
  disent explicitement : « pas de fryingSensor ». Voir la note `Matériel` du projet pour la table et
  les contraintes (poêle vide au départ, aliment au bip, pas de couvercle, beurre et huile d'olive
  vierge extra plafonnés au niveau 2).
- Section **Sources** : obligatoire. Lien(s) vers la ou les recettes en ligne ayant servi de référence ou correspondance proche. Permet à l'utilisateur de consulter l'original et d'adapter.

## Format des Fiches d'Assemblage (dans `Assemblages/`)

Frontmatter identique aux recettes (fileclass `recette`), mais contenu réduit :

```markdown
# Ingrédients

- 2 tranches de pain complet
- ½ avocat mûr
- 1 œuf
- Tomates cerises, citron, huile d'olive, sel, poivre

# Préparation

1. Toaster le pain.
2. Écraser l'avocat avec citron, sel.
3. Cuire l'œuf (au plat, mollet ou poché).
4. Monter et arroser d'huile.
```

Règles :

- Limité à **2 sections** : `# Ingrédients` et `# Préparation`.
- Ingrédients : liste sans quantités précises (ou très approximatives), pas de kcal par ligne.
- Préparation : **3-4 étapes** maximum, courtes (max ~15 mots).
- Niveau de cuisson en forme courte : `**fryingSensor 3**` inséré dans l'étape, sans citer la
  température ni la ligne de la notice — les explications restent dans les fiches recette complètes.
- **Pas** de section Notes, Sources, ni validation Ciqual détaillée.
- `calories-approx` dans le frontmatter reste indicatif (estimation globale, pas validée Ciqual).

## Format du Plan Hebdomadaire (Semaine-YYYY-WNN.md)

```yaml
---
catégorie: Note-Projet
tags:
  - Projet/Meal-Plan
création: YYYY-MM-DD
statut: En cours
terminée: false
---
```

Corps du fichier : tableau Markdown avec liens vers les recettes.

Le cycle va du **mercredi au mardi suivant**. `NN` est la semaine ISO du mercredi de départ. Les lignes suivent l'ordre du cycle, pas l'ordre lundi→dimanche.

```markdown
# Plan Semaine NN (mercredi DD/MM → mardi DD/MM)

| Jour     | Déjeuner                         | Dîner                              |
| -------- | -------------------------------- | ---------------------------------- |
| Mercredi | [[Salade de pâtes complètes]] ⚡ | [[Sauté de bœuf aux brocolis]] ⚡  |
| Jeudi    | [[Tartine avocat-œuf]]           | [[Filet de saumon et riz]]         |
| Vendredi | [[Soupe de pois chiches]]        | [[Omelette aux champignons]]       |
| Samedi   | [[Taboulé de quinoa]]            | [[Gratin de courgettes]] 🍽️        |
| Dimanche | [[Salade composée]]              | [[Ratatouille et œuf au plat]]     |
| Lundi    | [[Salade de lentilles]]          | [[Poulet grillé aux légumes]]      |
| Mardi    | [[Wrap au thon]]                 | [[Gratin de coquillettes au thon]] |

⚡ = jour de sport (repas légèrement enrichis)
🍽️ = repas élaboré de la semaine (jusqu'à 60 min)
🌱 = repas végétarien
```

Le mercredi est à la fois jour de course, jour de sport et premier jour du cycle → son dîner doit être rapide.

**Le déjeuner du mercredi se prend avant la course** (faite l'après-midi) : il ne peut donc utiliser aucun ingrédient de la liste de courses du cycle. Il repose sur le congélateur, les conserves ou le fonds de placard. Ses ingrédients ont été achetés la semaine précédente, marqués `(déj. mercredi prochain)` dans la liste de courses du cycle précédent.

Les produits très périssables (poisson frais, salade, herbes fraîches) se placent sur **mercredi–vendredi**. La fin de cycle repose sur des ingrédients robustes (conserves, surgelés, œufs, féculents, légumes racines, fromage) — sauf si `CLAUDE.md` documente un second point d'appro confirmé en cours de semaine, auquel cas la seconde moitié du cycle peut s'appuyer sur du frais racheté.

Notes sur le format du plan :

- Les **calories approximatives** sont indiquées entre parenthèses après chaque repas : `Salade de thon + pain (445)`.
- Pour les repas d'assemblage (sans fiche recette), lister les composants séparés par `+` : `Cordon bleu + purée 1 portion + haricots verts (665)`.
- Pour les repas avec fiche recette, utiliser un wikilink : `[[Galette sarrasin complète]] + compote 🌱 (415)`.
- Les marqueurs (⚡, 🍽️, 🌱) se placent après le contenu du repas, avant les calories.

## Format de la Liste de Courses (Courses-YYYY-WNN.md)

```yaml
---
catégorie: Note-Projet
tags:
  - Projet/Meal-Plan
création: YYYY-MM-DD
statut: En cours
terminée: false
---
```

Le fichier courses couvre **un seul cycle de 7 jours** et **une seule course**, le mercredi, en supermarché. Il n'y a plus de commande en ligne ni de second passage en magasin : tout est acheté en une fois.

Structure : les articles sont regroupés **par rayon**, dans l'ordre d'un parcours de supermarché, pour une course en une passe.

Pas de section « fonds de placard à vérifier ». Croiser directement avec `Fonds-de-placard.md` pendant la génération et ajouter à la liste ce qui manque réellement, dans le rayon correspondant.

Deux catégories d'articles s'ajoutent aux ingrédients des repas du cycle, toutes deux placées **dans leur rayon normal**, jamais dans une rubrique à part :

- Les lignes reprises de `Liste de courses.md`, telles quelles, sans marqueur de vérification.
- Ce qui couvre le **déjeuner du mercredi suivant** (pris avant la course de la semaine d'après), suffixé `(déj. mercredi prochain)`.

```markdown
# Courses — Semaine NN (mercredi DD/MM)

## Fruits & légumes

- [ ] Poireaux × 2
- [ ] Salade verte × 1
- [ ] ...

## Boucherie / volaille

- [ ] 4 blancs de poulet (~600 g)
- [ ] Filet de porc ~250 g

## Poissonnerie

- [ ] 1 pavé de saumon ~180 g

## Crèmerie

- [ ] 1 pot de fromage blanc 500 g
- [ ] ...

## Épicerie salée

- [ ] 1 boîte de pois chiches 400 g
- [ ] 500 g de pâtes complètes
- [ ] ...

## Surgelés

- [ ] 1 sachet de haricots verts 750 g
- [ ] 1 sachet de poisson pané (déj. mercredi prochain)
- [ ] ...

## Boulangerie

- [ ] 1 pain complet
```

Omettre les rayons vides. Ne pas créer de rubrique pour un rayon sans article.

## Format de `Liste de courses.md`

Fichier libre, tenu par l'utilisateur entre deux cycles. Pas de frontmatter imposé, pas de rayons, pas de quantités : une idée d'achat par ligne, écrite au fil de l'eau.

```markdown
Thym
Huile d'olive
Moutarde à l'ancienne
Farines
```

- **Lecture obligatoire** à chaque génération. Chaque ligne part dans le rayon correspondant de `Courses-YYYY-WNN.md`, sans marqueur `(placard ?)` : la demande est explicite, donc confirmée.
- **Vider le fichier** une fois les lignes reportées (conserver le frontmatter s'il y en a un). C'est une boîte de réception, pas un historique.
- Ne jamais y écrire soi-même : c'est le canal de l'utilisateur vers le planificateur, pas l'inverse.

## Format du Fonds de Placard (Fonds-de-placard.md)

```yaml
---
catégorie: Note-Projet
tags:
  - Projet/Meal-Plan
création: YYYY-MM-DD
statut: En cours
terminée: false
---
```

Le fichier comporte deux parties :

### Partie 1 — Stock actuel (tables)

Trois sections (Réfrigérateur, Congélateur, Garde-manger) sous forme de **tableaux Markdown**, triés alphabétiquement :

```markdown
## Réfrigérateur

| Produit         | Quantité | Détail          |
| --------------- | -------- | --------------- |
| Carottes râpées | 2        | barquettes 320g |
| Œufs            | 12       | unités          |
```

- Mettre à jour les quantités ou supprimer les lignes au fur et à mesure de la consommation.
- Tri alphabétique par produit.

### Partie 2 — Fonds de placard permanent (checklists)

Ingrédients de base à toujours avoir, sous forme de cases à cocher :

```markdown
## Épices et aromates

- [x] Sel, poivre
- [x] Paprika
- [ ] Curry (à acheter)
```

Cases cochées = en stock. Cases non cochées = à acheter / réapprovisionner.

## Conventions Générales

- Noms de fichiers : titre en français, espaces autorisés, pas de date dans le nom des recettes
- Liens internes : utiliser `[[Nom de la recette]]` (wikilinks Obsidian)
- Listes de courses : utiliser les cases à cocher `- [ ]` pour pouvoir les cocher dans Obsidian
- Langue : tout en français
- Pas d'émoji dans les noms de fichiers, émojis acceptés dans le contenu (⚡ pour sport)
