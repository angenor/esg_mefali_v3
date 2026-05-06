# F17 — Carbone : Mix UEMOA 8 Pays + Facteurs ADEME/IPCC Sourcés + Catégorie Achats

**Module(s) source(s)** : Module 4 (Calculateur d'Empreinte Carbone)
**Priorité** : P1 — crédibilité scientifique du calcul carbone
**Dépendances** : F01 (sources, emission_factors table)
**Estimation** : 1.5 sprints

## Contexte & motivation

Module 4.2 du brainstorming :
- Source primaire : **ADEME Base Carbone v23** (français, gratuit, contient facteurs Afrique) + **IPCC AR6** + **IEA Africa Energy Outlook**
- Mix électrique par pays UEMOA stocké en table de constantes versionnée (**8 pays principaux**)
- Affichage utilisateur : "Facteur utilisé : 0,456 kgCO2e/kWh (mix Côte d'Ivoire 2024, source ADEME Base Carbone v23, page 87)" + lien source cliquable

**État actuel** :
- `EMISSION_FACTORS` codé en Python (`backend/app/modules/carbon/emission_factors.py:7-26`) avec **un seul facteur électricité** : `electricity_ci` pour la Côte d'Ivoire
- Aucune référence à ADEME v23, IPCC AR6, IEA Africa
- Mention textuelle uniquement dans le commentaire ligne 3 ("grilles ADEME adaptees Afrique de l'Ouest")
- **Catégorie "Achats" / matières premières absente** (Module 4.1 cite : Énergie, Transport, Déchets, Achats)
- Pas de catégorisation pays UEMOA sur les facteurs
- Le `source_description: String(500)` sur `CarbonEmissionEntry` est texte libre, pas FK vers `Source`
- Recommandations du plan de réduction non sourcées

## User stories

- **PME en Côte d'Ivoire** : « Quand je saisis ma consommation électrique, le facteur d'émission utilisé est 0,456 kgCO2e/kWh (mix CI 2024, ADEME). »
- **PME au Sénégal** : « Quand je saisis ma consommation électrique, le facteur utilisé est différent (mix SN 2024, ~0,540 kgCO2e/kWh) — selon ma localisation déclarée dans le profil entreprise. »
- **PME** : « Quand je vois le total tCO2e affiché, je peux cliquer sur le picto Source à côté pour voir : ADEME Base Carbone v23, p. 87, dernière capture le 15/03/2026, statut vérifié. »
- **Auditeur** : « Le rapport carbone PDF inclut une annexe Sources avec toutes les références utilisées (ADEME / IPCC / IEA / mix UEMOA par pays). »

## Périmètre fonctionnel

### Migration `EMISSION_FACTORS` Python → table `emission_factors` (F01)

Table créée par F01, peuplée ici via seed admin (F09) :
- `id: UUID PK`
- `category: enum('electricity', 'fuel_diesel', 'fuel_gasoline', 'fuel_butane', 'transport_personal', 'transport_freight', 'waste_landfill', 'waste_incineration', 'waste_compost', 'purchases_steel', 'purchases_cement', 'purchases_paper', 'purchases_food', ...)`
- `country_code: str(2) | null` (ISO 3166-1 alpha-2 ; null = facteur global)
- `year: int`
- `factor_value: Numeric(20, 10)`
- `unit: str` (ex : `kgCO2e/kWh`, `kgCO2e/L`, `kgCO2e/tonne`)
- `source_id: UUID FK sources.id NOT NULL` (F01)
- `version: str`, `valid_from`, `valid_to` (F04)
- `notes: text | null`

Seed initial (~50 lignes) :
- Mix électrique 8 pays UEMOA : Côte d'Ivoire, Sénégal, Burkina Faso, Mali, Niger, Bénin, Togo, Guinée-Bissau (avec sources IEA Africa Energy Outlook 2024 ou équivalent national)
- Diesel, essence, butane (ADEME Base Carbone v23)
- Transport (ADEME, par catégorie véhicule)
- Déchets : enfouissement, incinération, compostage (ADEME + IPCC AR6 chap.10)
- Achats : matières premières principales (acier, ciment, papier, alimentaire, plastiques)

### Catégorie Achats

Ajouter au schéma `CarbonEmissionEntry` :
- `category` enum élargi avec `purchases_*`
- Les questions chat (carbon_node) demandent les volumes annuels d'achats en tonnes ou en valeur monétaire (avec ratio par défaut)

### Affichage Source dans le chat

Quand un facteur est utilisé :
```
Empreinte calculée : 12,3 tCO2e
- Électricité : 6,5 tCO2e (15 000 kWh × 0,456 kgCO2e/kWh) [📋 Source]
  Facteur : Mix Côte d'Ivoire 2024 — ADEME Base Carbone v23, p.87
- Diesel générateurs : 4,2 tCO2e (1 600 L × 2,68 kgCO2e/L) [📋 Source]
  Facteur : ADEME Base Carbone v23, p.45
- ...
```

Le picto `[📋 Source]` est le composant `<SourceLink>` (F01) cliquable qui ouvre `<SourceModal>`.

### Refactor `CarbonEmissionEntry`

- Remplacer `source_description: String(500)` par `source_id: UUID FK sources.id NOT NULL`
- Ajouter `factor_id: UUID FK emission_factors.id NOT NULL`
- Refactor `compute_emissions_tco2e` (`backend/app/modules/carbon/emission_factors.py:141-143`) pour requêter dynamiquement la table

### Sélection du facteur selon le pays

```python
async def get_emission_factor(category: str, country: str | None, year: int) -> EmissionFactor:
    # Priorité : factor pays + année exacte > pays + année antérieure > global + année exacte > global + antérieure
    candidates = await db.query(EmissionFactor).filter(
        EmissionFactor.category == category,
        EmissionFactor.year <= year,
        (EmissionFactor.country_code == country) | (EmissionFactor.country_code.is_(None)),
        EmissionFactor.valid_to.is_(None) | (EmissionFactor.valid_to > today),
    ).order_by(
        # priorité pays exact
        EmissionFactor.country_code == country,
        EmissionFactor.year.desc()
    ).limit(1)
    return candidates.first()
```

### Plan de réduction sourcé

Refactor `app/modules/carbon/service.py:reduction_plan` :
- Chaque action de réduction a un `source_id` (FK vers `Source` ADEME / IEA / BOAD policies)
- Affichage UI avec `<SourceLink>`

### Rapport carbone PDF (lien F21)

Endpoint `POST /api/reports/carbon/{assessment_id}/generate` (F21 le couvre) :
- Inclut l'annexe Sources auto-générée (F01)
- Pour chaque facteur utilisé, citation complète

## Hors-scope (post-MVP)

- Mix horaire (variations selon heure)
- Facteurs custom par PME (validés admin)
- Détection automatique du pays à partir de l'adresse IP
- Calcul Scope 3 complet (achats indirects upstream/downstream)
- Reporting GHG Protocol formel
- Intégration plateforme carbone Verra/GoldStandard

## Exigences techniques

### Backend

- Lien F01 : table `emission_factors` créée
- Seed admin (F09) : ~50 lignes pour MVP
- Refactor `app/modules/carbon/emission_factors.py` :
  - Plus de constantes Python
  - Service `get_emission_factor(category, country, year)` qui requête la BDD
- Modifications schéma `CarbonEmissionEntry` :
  - `source_id` (FK), `factor_id` (FK)
- Migration backfill : pour chaque entry existante, lier au facteur le plus probable
- Modifications `app/prompts/carbon.py` : enseigner au LLM à utiliser `country` du profil + appeler `cite_source` (F01) sur chaque facteur affiché
- Tool LangChain (mise à jour) : `save_emission_entry` retourne le facteur utilisé + source_id pour que le LLM puisse citer
- Tests :
  - Test sélection facteur : profil CI → factor electricity_ci ; profil SN → factor electricity_sn
  - Test fallback : si pays non couvert → facteur global
  - Test sourcing : entry sans `source_id` rejetée
  - Test catégorie Achats : nouvelle catégorie reconnue dans les questions LLM

### Frontend

- Mise à jour `pages/carbon/results.vue` : afficher `<SourceLink>` sur chaque facteur dans le breakdown
- Composant `<EmissionFactorBadge>` qui combine factor + source + label
- Dark mode

### Base de données

- Table `emission_factors` (créée par F01)
- ~50 rows initiales seedées
- Index : `(category, country_code, year, valid_to)`
- Modifications `carbon_emission_entries` : ajout `source_id`, `factor_id`

## Critères d'acceptation

- [ ] Table `emission_factors` peuplée avec ~50 facteurs (8 pays UEMOA × électricité, fuels, déchets, achats)
- [ ] Toutes sources liées à ADEME / IPCC / IEA (statut `verified` ou `pending`)
- [ ] Catégorie Achats fonctionnelle dans le calcul carbone
- [ ] Sélection de facteur dépend du pays du profil entreprise
- [ ] `CarbonEmissionEntry` lié à `factor_id` et `source_id`
- [ ] `<SourceLink>` cliquable sur chaque facteur dans le chat et l'UI
- [ ] Plan de réduction : recommandations sourcées
- [ ] Test : profil CI → électricité = 0,456 ; profil SN → différent
- [ ] Test : ajout d'un achat de ciment → catégorie purchases_cement reconnue + facteur appliqué
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : facteurs ADEME pas tous applicables à l'Afrique (ex : mix électrique différent). **Garde-fou** : prioriser IEA Africa Energy Outlook pour mix électrique, ADEME pour le reste, documenter les choix.
- **Risque** : 8 pays UEMOA n'ont pas tous des données récentes. **Garde-fou** : fallback sur pays voisin ou global, signal explicite "factor approximatif".
- **Risque** : changement de version ADEME casse les anciens calculs. **Garde-fou** : versioning F04, snapshot factor_id sur les entries (factor utilisé au moment du calcul).
