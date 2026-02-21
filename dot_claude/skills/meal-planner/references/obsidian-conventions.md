# Conventions Obsidian

## Emplacement des Fichiers

Base du vault : `/home/vincent/Documents/Perso/`
Base du projet : `Projets/Meal-Plan/`

Structure :
```
Projets/Meal-Plan/
├── Recettes/                    # Fiches recettes individuelles
├── Fonds-de-placard.md          # Inventaire des ingrédients de base
├── Semaine-YYYY-WNN.md          # Plan hebdomadaire (ex: Semaine-2026-W06.md)
├── Courses-YYYY-WNN.md          # Liste de courses pour cette période
└── Archive/                     # Plans précédents déplacés ici
```

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

- Section **Notes** : optionnelle, pour astuces de conservation, variantes, ou accompagnements alternatifs.
- Section **Sources** : obligatoire. Lien(s) vers la ou les recettes en ligne ayant servi de référence ou correspondance proche. Permet à l'utilisateur de consulter l'original et d'adapter.

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

```markdown
# Plan Semaine NN

| Jour     | Déjeuner                              | Dîner                                  |
| -------- | ------------------------------------- | -------------------------------------- |
| Lundi    | [[Salade de lentilles]]               | [[Poulet grillé aux légumes]]          |
| Mardi    | [[Wrap au thon]]                      | [[Soupe de légumes et tartine]]        |
| Mercredi | [[Salade de pâtes complètes]] ⚡      | [[Sauté de bœuf aux brocolis]] ⚡      |
| Jeudi    | [[Tartine avocat-œuf]]               | [[Filet de saumon et riz]]             |
| Vendredi | [[Soupe de pois chiches]]             | [[Omelette aux champignons]]           |
| Samedi   | [[Taboulé de quinoa]]                 | [[Gratin de courgettes]]               |
| Dimanche | [[Salade composée]]                   | [[Ratatouille et œuf au plat]]         |

⚡ = jour de sport (repas légèrement enrichis)
🍽️ = repas élaboré de la semaine (jusqu'à 60 min)
🌱 = repas végétarien
```

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

Le fichier courses couvre 2 semaines et comporte 4 sections :

```markdown
# Courses - Semaines NN et NN+1

## Stock longue durée (commande en ligne)
Produits secs, conserves, surgelés - une fois toutes les 2 semaines.

- [ ] 1 kg de riz complet
- [ ] 500 g de pâtes complètes
- [ ] ...

## Semaine 1 - Produits frais
Fruits, légumes, viandes, produits laitiers pour la première semaine.

- [ ] 4 blancs de poulet (~600 g)
- [ ] 1 kg de courgettes
- [ ] ...

## Semaine 2 - Produits frais
Idem pour la deuxième semaine.

- [ ] 2 pavés de saumon (~300 g)
- [ ] ...

## Fonds de placard - À vérifier
Éléments normalement déjà en stock. Vérifier et cocher ce qui manque.
Consulter [[Fonds-de-placard]] pour l'inventaire complet.

- [ ] Huile d'olive
- [ ] Moutarde de Dijon
- [ ] ...
```

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

| Produit                | Quantité | Détail          |
| ---------------------- | -------- | --------------- |
| Carottes râpées        | 2        | barquettes 320g |
| Œufs                   | 12       | unités          |
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
