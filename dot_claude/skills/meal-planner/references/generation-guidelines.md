# Meal Plan Generation Guidelines

This reference defines the rules and constraints for generating meal plans, recipes, and grocery lists. Follow these instructions precisely.

---

## Assemblage vs Recette

Tous les repas n'ont pas besoin d'une fiche recette. Distinguer :

- **Repas d'assemblage** : combinaison simple de produits sans véritable préparation culinaire (cordon bleu + purée + légumes en conserve, salade de thon en boîte + pain, etc.). Pas de fichier recette — noter directement les composants et calories dans le plan hebdomadaire.
- **Recette** : plat nécessitant des étapes de préparation/cuisson (galette sarrasin, poulet papillote, gratin, curry, etc.). Créer un fichier dans `Recettes/`.

La majorité des repas quotidiens seront des assemblages. Ne créer des recettes que quand il y a une vraie valeur ajoutée (étapes, proportions, technique).

---

## Menu Design Principles

### Weekly Balance (Not Per-Meal)

- Target macro balance across the **week**, not each individual meal.
- **Rotate proteins** over the week: chicken, fish, beef, pork, eggs, legumes.
- Include **at least 2 vegetarian meals per week**, preferably at lunch.
- **Never repeat** the same main protein on consecutive dinner days.

### Lunches

- Favor **light, quick meals**: composed salads, soups, open sandwiches, wraps, bowls.
- It is acceptable to **repeat 2-3 lunch types** in rotation within a week.
- Target: **400-600 kcal** per lunch.
- Typical prep time: **10-15 min**.

### Dinners

- More substantial but reasonable portions.
- Structure: **one main dish + side** (vegetable + starch, or vegetable alone).
- Target: **600-800 kcal** per dinner.
- Typical prep time: **15-25 min**, 30 min maximum.

### Sport Day (Wednesday by Default)

- Add an **extra whole-grain starch** or increase starch portion size.
- Favor **lean proteins in slightly larger quantities**.
- Mark the day with ⚡ in the plan.

### Weekly Elaborate Meal (1 per week, dinner)

- **Once per week**, plan a more ambitious dinner: up to **60 min** of prep/cooking.
- Must be a **gratifying, guest-worthy dish** — not just something that takes long because it's tedious.
- Think: a proper *blanquette de veau*, a *poulet rôti aux herbes et légumes*, a *risotto aux champignons*, a *tajine*, a *gratin dauphinois avec son rôti* — dishes with depth of flavor that reward the effort.
- **Avoid**: anything that's long but bland, overly fussy plating, or restaurant-level techniques.
- Mark with 🍽️ in the plan.
- Still respects the calorie targets (600-800 kcal); the extra time is about flavor and technique, not extra calories.
- Prefer **weekend evenings** (vendredi, samedi) when there's more time and appetite for it.

### Composition Rules

- **Une seule protéine principale par repas.** Ne pas mélanger deux protéines animales (ex : pas de steak + poisson pané, pas de poulet + thon). Les œufs dans une galette sarrasin ne comptent pas comme doublon si c'est la protéine unique du plat.
- **Pas de combinaisons incohérentes.** Respecter les associations classiques de la cuisine française du quotidien. Exemples de combos à éviter : coquillettes + maïs en accompagnement, salade de thon + riz, purée + pâtes. En cas de doute, préférer les associations simples et éprouvées.
- **Ne pas forcer la consommation du stock.** Les surgelés se conservent des mois. Ne pas construire des repas artificiels juste pour « écouler » du stock. Intégrer naturellement les produits en stock dans des repas qui ont du sens.

### Interchangeability

- Design meals to be **swappable within the same category** (lunch ↔ lunch, dinner ↔ dinner).
- Elaborate meals (🍽️) are swappable with other elaborate meals or can be replaced by a standard dinner if the user doesn't feel like it.
- **Avoid dependency chains** between meals (e.g., do not rely on Monday's leftovers for Tuesday).
- Every recipe must be **self-contained**.

---

## Quantities and Grocery Management

### Fundamental Principle

**NEVER** use fractions of standard packaging that would leave unusable leftovers (e.g., 40% of a can of chickpeas).

**Exception**: Frozen or easily portionable items (fish sticks, steaks hachés, pommes duchesse, etc.) can be freely split across multiple meals. The rule targets cans, jars, and packages where a leftover partial amount would be awkward or wasted — not bulk frozen goods.

### Quantity Rules

1. **Meat/fish**: buy as individual portions (1 chicken breast, 1 salmon fillet, 1 ground beef patty).
2. **Fresh vegetables**: buy by unit or by the exact weight needed.
3. **Dry starches** (rice, pasta, lentils): standard packages (500 g, 1 kg) will be consumed over 2 weeks or beyond. Plan to **use the full package** when possible.
4. **Dairy**: one pot of fromage blanc, one carton of crème fraîche — plan **2-3 recipes** using it within the fortnight.
5. **Canned goods**: use the **entire can** in one recipe (e.g., one can of chickpeas = one recipe, not 40% of a can).
6. **Fresh herbs**: if a bunch of parsley is purchased, plan **2-3 recipes** using it within the week.

### Grocery Categorization

Organize the grocery list into these sections:

| Section                        | Contents                                              | Notes                                           |
| ------------------------------ | ----------------------------------------------------- | ----------------------------------------------- |
| **Long-shelf-life stock**      | Rice, pasta, canned goods, frozen items, sauces       | Can be ordered online                           |
| **Week 1 fresh**               | Meat, fish, vegetables, fresh dairy for days 1-7      | Buy at start of plan                            |
| **Week 2 fresh**               | Same categories for days 8-14                         | Buy at start of week 2                          |
| **Pantry staples to verify**   | Spices, oils, condiments                              | Normally already in stock; list those needed     |

### Grocery Aggregation

- Group items **by category** within each section (Meat, Fish, Vegetables, Fruit, Dairy, etc.).
- Show **total quantities needed**, not per-recipe quantities.
- If the same ingredient appears in multiple recipes, **sum the quantities**.

---

## Recipe Generation

### Structure

Each recipe is a **separate Obsidian file** in `Recettes/`. Follow the format defined in `obsidian-conventions.md`.

### Instruction Style

- Use **numbered steps**, kept concise.
- No filler text or difficulty commentary.
- Include **cooking times within the steps**.
- If a side is implied (e.g., green salad), **list it explicitly in the ingredients**.

### Naming

- Use **clear, descriptive French names**: "Poulet grillé aux courgettes", "Salade de lentilles au chèvre".
- **No numbering** in recipe names.

### Source References

For each recipe generated:

1. **Search** for a close match on French recipe sites (Marmiton, Cuisine AZ, Journal des Femmes Cuisine, 750g, etc.) using WebFetch.
2. **Include** the URL(s) in the recipe's `# Sources` section.
3. The recipe itself may be adapted (simplified, adjusted for portions/calories), but the source provides a reference point the user can consult.
4. If no close match is found online, note "Recette composée sans source directe" in the Sources section.

### Nutritional Validation (Ciqual)

After generating all recipes for the plan:

1. **Spot-check** the calorie estimates of 5-6 representative recipes against the ANSES Ciqual food composition database (https://ciqual.anses.fr/).
2. For each checked recipe, look up the main caloric contributors (protein source, starch, fat) and verify the `calories-approx` value is in the right ballpark (within ~20%).
3. If a recipe is off by more than 20%, adjust the portion or the estimate.
4. Report the validation results in the final summary (see SKILL.md Étape 4).

This is a sanity check, not a precise audit. The goal is to catch major errors (e.g., a recipe estimated at 500 kcal that's actually 800 kcal).

---

## Plan Renewal Process

When generating a new plan, follow these steps in order:

1. **Read** `Fonds-de-placard.md` to know current pantry stock.
2. **Read** existing recipes and their ratings (if present):
   - **Exclude** poorly rated recipes (rating ≤ 2).
   - **Favor** well-rated recipes (rating ≥ 4).
3. **Archive** previous plans and grocery lists into `Archive/`.
4. **Generate** the new plan, reusing existing recipes when possible and creating new ones only as needed.
5. **Generate** the new grocery list, accounting for current pantry stock.
6. **Update** `Fonds-de-placard.md` if any pantry staples need to be purchased.

---

## Seasonality

Adapt recipes to the **current season**:

| Season                  | Preferred Ingredients                                                  |
| ----------------------- | ---------------------------------------------------------------------- |
| **Winter** (Dec-Feb)    | Soups, gratins, light stews, root vegetables, cabbage, leeks           |
| **Spring** (Mar-May)    | Asparagus, peas, salads, artichokes                                    |
| **Summer** (Jun-Aug)    | Cold salads, gazpacho, tomatoes, zucchini, eggplant, bell peppers      |
| **Autumn** (Sep-Nov)    | Squash, mushrooms, broccoli, cauliflower                               |

**Prioritize seasonal vegetables** for both cost and flavor.
