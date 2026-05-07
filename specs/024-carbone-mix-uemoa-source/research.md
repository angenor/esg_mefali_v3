# Phase 0 — Research : F17 Carbone Mix UEMOA + Facteurs Sourcés

Date : 2026-05-07
Branche : `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `024-carbone-mix-uemoa-source`)

## Décisions et alternatives

### Décision 1 — Stockage de l'année du facteur d'émission

- **Décision** : Ajouter une colonne `year: Integer NOT NULL` à la table `emission_factors`. Index composite `(category, country, year)` pour le lookup. Contrainte `UNIQUE (category, country, year)` pour l'unicité métier.
- **Rationale** : Performance des requêtes (lookup en O(log n) sur index B-tree composite vs parsing de chaîne O(n)). Validation de schéma facile via Pydantic. Évolutivité : permet d'ajouter de nouvelles colonnes (`valid_from`, `valid_to`, `version`) sans casser le format `code`.
- **Alternatives considérées** :
  - *Encoder l'année dans `code` (snake_case `electricity_ci_2024`)* : rejeté car parsing fragile, pas d'index efficace, validation difficile.
  - *Ajouter `valid_from: Date NOT NULL` et `valid_to: Date NULL`* : trop riche pour le MVP, F04 introduira ce versioning Money/Period plus tard.

### Décision 2 — Source des conversions FCFA → tonnes/litres

- **Décision** : Réutiliser la table `simulation_factors` créée par F01 pour stocker les ratios économiques (prix moyen ciment FCFA/t, prix électricité CIE FCFA/kWh, etc.). Le tool `save_emission_entry` interroge `simulation_factors` quand l'utilisateur fournit un montant FCFA.
- **Rationale** : Séparation des dimensions (`emission_factors` = facteurs physiques d'émission ; `simulation_factors` = paramètres économiques). Cohérent avec l'architecture F01.
- **Alternatives considérées** :
  - *Ajouter des entrées `prices_*` dans `emission_factors`* : rejeté car pollue la sémantique de la table avec des unités économiques (FCFA/t vs kgCO2e/L).
  - *Hardcoder les conversions FCFA dans `app/modules/carbon/emission_factors.py`* : rejeté car viole l'invariant de sourçage F01.

### Décision 3 — Stratégie de backfill des entries historiques

- **Décision** : Pour chaque `carbon_emission_entries` existante : (1) tenter un matching strict `subcategory` ↔ `emission_factors.code` (ex. `electricity_ci` matche `electricity_ci_2024`). (2) Si pas de match, lier au facteur générique global de la catégorie (`<category>_global_2024`) + une `Source` ADEME générique seedée par F01. (3) Si la catégorie elle-même est inconnue (cas exotique), logguer et ne pas backfiller (la migration n'échoue pas, mais l'entrée garde NULL et un warning est émis).
- **Rationale** : Préserve les données historiques sans perte. Le matching strict évite les erreurs sémantiques. Le fallback générique permet au moins un sourçage minimal.
- **Alternatives considérées** :
  - *Supprimer les entries non matchées* : rejeté (perte de données utilisateur).
  - *Bloquer la migration si une seule entry n'est pas matchée* : rejeté (rendrait la migration impossible sur des données réelles).
  - *Créer une `Source` « legacy F17 backfill »* : envisagé puis rejeté car les sources doivent être documentaires réelles ; on préfère une source ADEME générique (par exemple « ADEME Base Carbone v23 — facteur générique catégorie »).

### Décision 4 — Schéma JSON canonique du `reduction_plan`

- **Décision** : Chaque action du `reduction_plan` (champ JSON sur `CarbonAssessment`) suit le schéma : `{title: str (≤ 200), description: str (≤ 1000), estimated_reduction_tco2e: float ≥ 0, cost_estimate_fcfa: int ≥ 0 | null, timeline: str (ex: "0-3 mois", "3-12 mois"), source_id: str (UUID) | null, unsourced: bool}`.
- **Rationale** : Permet validation Pydantic backend (`ReductionPlanAction`) et type TypeScript frontend (`ReductionPlanAction`). Compatible avec l'invariant F01 (source_id optionnel + flag explicit unsourced).
- **Alternatives considérées** :
  - *Format libre laissé au LLM* : rejeté (imprévisible, casse les composants UI).
  - *Stockage en table dédiée `reduction_actions`* : rejeté pour le MVP (pas de besoin de requêter individuellement les actions ; rester en JSON économise une migration).

### Décision 5 — Sort de la colonne `source_description` legacy

- **Décision** : Conservation de `source_description: String(500) | NULL` telle quelle. La migration F17 n'efface ni ne renomme cette colonne. Suppression planifiée dans une migration ultérieure (≥ 2 sprints) une fois la stabilisation acquise.
- **Rationale** : Réversibilité de la migration (down possible sans perdre l'historique du texte libre). Décision orchestrateur par défaut. Coût technique minimal.
- **Alternatives considérées** :
  - *DROP immédiat* : rejeté (perd l'historique texte libre, moins réversible).
  - *Renommage en `source_description_legacy`* : rejeté car ajoute du bruit pour un bénéfice marginal ; le commentaire SQLAlchemy `# TODO(F17+1): drop after stabilisation` suffit.

### Décision 6 — Sources des valeurs des facteurs UEMOA

- **Décision** :
  - *Mix électrique 8 pays UEMOA* : utiliser **IEA Africa Energy Outlook 2024** (chapitre Sub-Saharan Africa Power Generation Mix) ; valeurs estimées : CI ~0.456, SN ~0.540, BF ~0.640, ML ~0.580, NE ~0.620, BJ ~0.670, TG ~0.585, GW ~0.700 kgCO2e/kWh. Validés à la rédaction du seed contre la dernière publication IEA disponible.
  - *Combustibles (diesel/essence/butane)* : **ADEME Base Carbone v23** (page 45-50, valeurs combustion stationnaire/mobile).
  - *Transport* : **ADEME Base Carbone v23** (chapitre Transport, page ~65-80).
  - *Déchets* : **ADEME Base Carbone v23** (chapitre Déchets, page ~95-105) + **IPCC AR6 WG3 chapitre 10** (méthane décharge).
  - *Achats matières premières* : **ADEME Base Carbone v23** (chapitre Matériaux, page ~120-140 : ciment ~0.9 kgCO2e/kg, acier ~1.85 kgCO2e/kg, papier ~1.3 kgCO2e/kg, plastique PE ~2.1 kgCO2e/kg, alimentation moyenne ~3.5 kgCO2e/kg).
- **Rationale** : Sources publiques, gratuites, déjà seedées par F01 en statut `verified`. IEA Africa pour électricité = données spécifiques au continent ; ADEME pour le reste = catalogue le plus détaillé en français.
- **Alternatives considérées** : Sources nationales (CIE Côte d'Ivoire, SENELEC Sénégal) : envisagées pour CI/SN mais leurs grilles publiques manquent de granularité par usage ; à intégrer post-MVP.

### Décision 7 — Pas de cache LRU sur `get_emission_factor`

- **Décision** : Ne pas mettre de cache LRU/Redis sur `get_emission_factor` au MVP.
- **Rationale** : Volume de la table très faible (~50 lignes), index composite suffit. Lookup < 5 ms en pratique. Ajouter un cache complexifie l'invalidation lors du seed.
- **Alternatives considérées** : `functools.lru_cache(maxsize=128)` : rejeté car invalidation manuelle nécessaire après seed admin ; bénéfice marginal.

### Décision 8 — Backfill dans la migration Alembic vs script séparé

- **Décision** : Backfill effectué directement dans la migration Alembic via `op.execute()` (SQL) et/ou `op.get_bind()` + SQLAlchemy session pour les cas complexes (matching subcategory).
- **Rationale** : Cohérence transactionnelle (rollback inclut le backfill). Une seule étape pour le déploiement.
- **Alternatives considérées** : Script `app/scripts/backfill_carbon_entries.py` séparé : rejeté car nécessiterait une coordination déploiement → backfill → switch contrainte NOT NULL en plusieurs étapes manuelles.

### Décision 9 — Idempotence du seed

- **Décision** : Le seed utilise `INSERT ... ON CONFLICT (code) DO NOTHING` (PostgreSQL `ON CONFLICT`) pour garantir l'idempotence sur re-exécution.
- **Rationale** : Permet de re-lancer le seed sans risque de doublon ou d'erreur.
- **Alternatives considérées** : `INSERT ... ON CONFLICT DO UPDATE` : rejeté car la mise à jour de facteurs déjà utilisés par des entries casserait la traçabilité historique. La mise à jour passe par un endpoint admin dédié (hors scope F17).

### Décision 10 — Tests E2E avec backend mocké

- **Décision** : Le test Playwright `F17-carbone-mix-uemoa-source.spec.ts` mocke les routes API backend (`POST /api/chat/messages`, `GET /api/carbon/...`, `GET /api/sources/{id}`) avec `page.route()` Playwright pour des scénarios déterministes.
- **Rationale** : Convention projet « Mock par défaut, vrai LLM uniquement pour `tests/llm_eval/` ». Tests rapides, fiables, sans dépendance LLM externe.
- **Alternatives considérées** : Vrai backend + LLM en E2E : rejeté (coût, flakiness, dépendance OpenRouter).

## Synthèse

Toutes les NEEDS CLARIFICATION du spec ont été résolues lors de la session de clarification 2026-05-07. Aucun unknown ne reste. Le plan technique est cohérent avec les invariants ESG Mefali (F01 sourçage, F02 multi-tenant, dark mode, français) et utilise exclusivement la stack imposée (Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Nuxt 4 / TailwindCSS / Playwright).
