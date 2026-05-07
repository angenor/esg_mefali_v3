# Phase 0 — Research : F07 Entité Offre = Couple Fonds × Intermédiaire

**Date** : 2026-05-07
**Branch** : `feat/F07-entite-offre-fonds-intermediaire`

## Décisions techniques

### 1. Stratégie de migration backfill : transactionnelle + idempotente

**Décision** : la migration `028_offers_and_enrich_fund_intermediary.py` est composée de plusieurs phases enchaînées dans une seule transaction Alembic :
1. **DDL non-destructif** : création des nouvelles colonnes nullable, des nouveaux enums, de la table `offers`.
2. **Seed du singleton DIRECT** : insertion conditionnelle (`INSERT ... WHERE NOT EXISTS`) de l'intermédiaire `code='DIRECT'`.
3. **Backfill `offers`** : pour chaque paire `(fund_id, intermediary_id)` dans `fund_intermediaries`, insertion `(fund_id, intermediary_id, name=fund.name + ' via ' + intermediary.name, is_active=false, publication_status='draft')`. Pour chaque fonds avec `access_type='direct'`, idem avec `intermediary_id=DIRECT.id`. **Idempotence** garantie par index unique `(fund_id, intermediary_id, version)`.
4. **Backfill `fund_applications.offer_id`** : `UPDATE fund_applications fa SET offer_id = (SELECT o.id FROM offers o WHERE o.fund_id = fa.fund_id AND o.intermediary_id = COALESCE(fa.intermediary_id, DIRECT.id))`.
5. **Renommage enum `fund_type`** : création nouveau type `fund_type_v2_enum` avec valeurs `multilateral|bilateral|regional|national|private|carbon_marketplace`, `ALTER TABLE funds ALTER COLUMN fund_type TYPE fund_type_v2_enum USING (CASE fund_type WHEN 'international' THEN 'multilateral' WHEN 'regional' THEN 'regional' WHEN 'national' THEN 'national' WHEN 'carbon_market' THEN 'carbon_marketplace' WHEN 'local_bank_green_line' THEN 'private' END)::fund_type_v2_enum)`, drop ancien type.
6. **NOT NULL** sur `funds.source_id`, `intermediaries.source_id`, `fund_intermediaries.accredited_from`, `fund_applications.offer_id` (post-backfill).

**Alternative considérée** : 2 migrations séparées (DDL + DML). Rejetée car cela double le coût opérationnel et complique le rollback.

**Tests** :
- `pytest tests/migrations/test_alembic_028.py` : verify counts pre/post migration, count `offers` ≥ count `fund_intermediaries` + count `funds where access_type='direct'`, `SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL = 0`.
- Idempotence : `alembic upgrade head` deux fois consécutives → même résultat.
- Réversibilité : `alembic downgrade -1` ne casse pas les données pre-migration.

### 2. Algorithme `compute_effective_offer`

**Décision** : implémenter un service stateless dans `app/modules/offers/calculator.py` :

```python
def compute_effective_offer(
    fund: Fund, intermediary: Intermediary, fund_intermediary: FundIntermediary | None,
) -> OfferDraft:
    # Étape 1 : intersection critères
    effective_criteria = _intersect_criteria(
        fund.eligibility_criteria,  # JSONB dict
        intermediary.eligibility_for_sme,  # JSONB dict
    )
    # Étape 2 : union documents avec déduplication exacte
    effective_required_documents = _union_documents(
        fund.required_documents + intermediary.required_documents,
    )
    # Étape 3 : somme frais Money typed (conversion XOF si devises différentes)
    effective_fees = _combine_fees(
        fund_fees=_extract_fund_fees(fund),  # potentiellement vide
        intermediary_fees=intermediary.fees_structured,
    )
    # Étape 4 : somme délais
    fund_timeline_days = (fund.typical_timeline_months or 0) * 30
    effective_processing_time_days_min = fund_timeline_days + (intermediary.processing_time_days_min or 0)
    effective_processing_time_days_max = fund_timeline_days + (intermediary.processing_time_days_max or 0)
    effective_disbursement_time_days_min = (intermediary.disbursement_time_days_min or 0)
    effective_disbursement_time_days_max = (intermediary.disbursement_time_days_max or 0)
    # Étape 5 : hint langue
    accepted_languages_hint = _infer_languages_from_country(intermediary.country)
    # Étape 6 : warnings
    notes = _detect_inconsistencies(fund, intermediary, fund_intermediary)
    return OfferDraft(...)
```

**Règle « le plus restrictif gagne »** sur intersection critères : pour chaque clé commune, si valeurs numériques alors `max(fund_val, intermediary_val)` pour critères « min_X » et `min(fund_val, intermediary_val)` pour critères « max_X » ; pour valeurs liste alors `set(fund_list) ∩ set(intermediary_list)` ; pour valeurs string : si égales alors la valeur, sinon avertissement dans `notes`.

**Règle déduplication documents** : clé `(title.lower().strip(), source_id)`. Sur doublons résiduels : si l'un est `mandatory=true`, le résultat est `mandatory=true`.

**Pays anglophones** (heuristique langue) : `["UK", "US", "CA", "KE", "GH", "NG", "ZA", "DE", "JP", "AU", "NZ", "IE"]`. Tout autre pays → `["FR"]`.

**Alternative considérée** : fuzzy matching documents via `difflib.SequenceMatcher`. Rejetée car risque de faux positifs cachant un vrai document obligatoire.

### 3. Stratégie feature flag `USE_OFFER_VIEW` : env var

**Décision** : env var `USE_OFFER_VIEW=false` (default) lue côté Nuxt via `runtimeConfig.public.useOfferView`. Le composant `pages/financing/index.vue` lit cette config et choisit dynamiquement l'affichage Cards Fonds (legacy) ou Cards Offres (nouveau).

**Alternative considérée** : table BDD `feature_flags`. Rejetée pour MVP F07 (over-engineering). Sera introduite si besoin runtime de toggling sans redéploiement.

**Documentation** : `docs/feature-flags.md` (à créer dans tasks.md) listera tous les feature flags actifs.

### 4. Pattern API REST `/api/offers/comparator` vs filtres sur `/api/offers`

**Décision** : endpoint dédié `GET /api/offers/comparator?fund_id=X` retournant un tableau structuré comparable côte-à-côte (colonnes alignées : `effective_fees_total_min`, `effective_fees_total_max`, `effective_processing_time_days_min/max`, `success_rate`, `accepted_languages`). C'est plus efficace côté frontend (pas de transformation post-fetch) et plus clair côté contrat OpenAPI.

**Alternative considérée** : utiliser `GET /api/offers?fund_id=X&compact=true` avec un mode compact. Rejetée car le contrat est moins explicite et le frontend doit re-trier les résultats.

### 5. Pattern singleton `Intermediary code='DIRECT'`

**Décision** : créer un intermédiaire singleton avec `code='DIRECT'`, `name='Direct (sans intermédiaire)'`, `country='ALL'` (placeholder), `intermediary_type='accredited_entity'`, `organization_type='un_agency'` (arbitraire neutre), `source_id=<source système Mefali>` (créer une source `system` dédiée).

Tous les fonds `access_type='direct'` ont une `Offer` couplée à ce singleton. Le frontend détecte ce cas et affiche un parcours « Soumission directe au fonds » (pas de section intermédiaire séparée).

**Alternative considérée** : `Offer.intermediary_id` nullable. Rejetée car cela complexifie les requêtes (`WHERE intermediary_id IS NULL OR intermediary_id = X`), les FK, et casse la promesse « toute candidature pointe vers une offre ».

**Identification du singleton en runtime** : par `code='DIRECT'` (recherche unique). Cache au démarrage de l'app (variable module) si performance devient critique.

### 6. Stratégie de tests intersection JSONB (PostgreSQL + SQLite)

**Décision** : les tests unitaires du calculator (`test_offer_calculator.py`) utilisent SQLite in-memory avec le fallback `JSON()` (cf. `JSONType = JSONB().with_variant(JSON(), "sqlite")` du modèle Source). Les tests d'intégration backfill (`test_alembic_028.py`) utilisent PostgreSQL via Docker pytest (cohérent avec convention existante du projet, fixture `pg_session`).

**Pourquoi** : intersection critères en Python pur (pas de query JSONB native) → SQLite suffit pour calculator. Backfill nécessite vraies migrations PG (enum natifs, JSONB ops).

### 7. Nommage tools LangChain

**Décision** : préfixe `list_offers`, `get_offer`, `compare_offers_for_fund` (pas de préfixe `financing_`). Les 3 tools sont ajoutés dans `app/graph/tools/financing_tools.py` (extension du fichier existant) et exposés dans les nœuds `chat` et `financing` du graphe.

**Description LangChain** (en français, conforme conventions existantes) :
- `list_offers` : « Liste les offres de financement vert disponibles avec filtres optionnels par fonds, intermédiaire, thème, instrument, pays, langue. »
- `get_offer` : « Récupère le détail complet d'une offre de financement (fonds, intermédiaire, critères effectifs, documents requis, frais, délais). »
- `compare_offers_for_fund` : « Compare côte-à-côte toutes les offres disponibles pour un même fonds (frais, délais, taux de succès, langue). »

### 8. Réutilisation de composants UI

**Audit `frontend/app/components/ui/`** : à effectuer en début de phase B. Composants génériques candidats à extraire si patterns apparaissent > 2 fois :
- `<MoneyDisplay :amount :currency />` : afficher une paire Money avec formatage local (XOF avec espaces milliers, EUR avec virgule décimale).
- `<DurationRange :min :max :unit />` : afficher un range de durées (ex : « 90-180 jours »).
- `<SourceBadge :source-id />` : badge cliquable affichant l'icône + tooltip + lien vers la source verifiée F01.

Ces composants peuvent être créés dans `components/ui/` puis utilisés depuis `components/financing/`.

### 9. Performance et indexes

**Décision** : indexes prévus pour `offers` :
- `CREATE INDEX idx_offers_fund_intermediary ON offers (fund_id, intermediary_id, valid_to)` — pour `GET /api/offers?fund_id=X` et lookup backfill.
- `CREATE INDEX idx_offers_publication_active ON offers (publication_status, is_active) WHERE publication_status = 'published' AND is_active = true` — index partiel pour API publique (filtre strict).
- `CREATE INDEX idx_offers_theme_gin ON offers USING gin (theme jsonb_path_ops)` — pour filtre `theme @>`.
- `CREATE INDEX idx_offers_submission_mode ON offers (submission_mode)` — pour filtre `submission_mode='call_for_proposals'`.
- `CREATE INDEX idx_offers_name_fts ON offers USING gin (to_tsvector('french', name))` — full-text search FR sur `name`.
- `UNIQUE INDEX uq_offers_fund_intermediary_version ON offers (fund_id, intermediary_id, version)` — invariant + dédup backfill.

Indexes complémentaires sur enrichissements :
- `CREATE INDEX idx_funds_theme_gin ON funds USING gin (theme jsonb_path_ops)`
- `CREATE INDEX idx_funds_instruments_gin ON funds USING gin (instruments jsonb_path_ops)`
- `CREATE INDEX idx_intermediaries_country ON intermediaries (country)` — pour filtre pays
- `CREATE INDEX idx_fund_intermediaries_accredited_to ON fund_intermediaries (accredited_to) WHERE accredited_to IS NOT NULL` — pour cron expiration

### 10. Rollback de la migration

**Décision** : `downgrade()` doit :
1. Supprimer la colonne `fund_applications.offer_id` (DROP COLUMN).
2. Supprimer la table `offers` (DROP TABLE).
3. Renommer l'enum `fund_type_v2_enum` → `fund_type_enum` legacy avec migration des valeurs inverse (`multilateral` → `international`, etc.).
4. Supprimer toutes les colonnes ajoutées sur `funds`, `intermediaries`, `fund_intermediaries`.
5. **Ne pas supprimer** l'intermédiaire singleton DIRECT (résiduel sans impact).
6. Ne pas restaurer les colonnes legacy `min_amount_xof`/`typical_fees` (elles n'ont jamais été supprimées, donc pas d'action).

**Test** : `alembic downgrade -1` puis `SELECT * FROM funds LIMIT 1` doit retourner les fonds avec leurs colonnes pre-028 intactes.
