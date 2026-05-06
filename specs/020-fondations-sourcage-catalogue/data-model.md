# Phase 1 — Data Model : Fondations Sourçage et Catalogue Source

**Feature** : F01 — `feat/F01-fondations-sourcage-catalogue` / `020-fondations-sourcage-catalogue`
**Date** : 2026-05-06

> Ce document décrit les 11 nouvelles entités introduites par F01, leurs relations, transitions d'état et règles d'intégrité. La migration Alembic correspondante sera `020_create_sources_catalog.py`.

## Vue d'ensemble

```
                       ┌────────────┐
                       │   users    │
                       │ (existing) │
                       └─────┬──────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
      captured_by                    verified_by
              │                             │
              └────────┬────────────────────┘
                       ▼
               ┌───────────────┐
               │    sources    │  ← entité de premier rang
               │  (catalogue)  │
               └───────┬───────┘
                       │ source_id (FK NOT NULL)
       ┌───────────────┼────────────────────────────┬─────────┐
       ▼               ▼                            ▼         ▼
  ┌───────────┐  ┌──────────────┐   ┌─────────────────────┐   …
  │ indicators│  │ referentials │   │  emission_factors   │
  │           │  │              │   │                     │
  └─────┬─────┘  └──────┬───────┘   └─────────────────────┘
        │               │
        └───────┬───────┘
                ▼
   ┌──────────────────────────┐
   │  referential_indicators  │  (jointure N-N)
   │  (poids, seuil, source)  │
   └──────────────────────────┘
```

## Entité 1 : `sources`

**Rôle** : représente un document de référence officiel mobilisable pour étayer toute affirmation factuelle.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Identifiant unique |
| `url` | `TEXT` | NOT NULL | URL officielle accessible |
| `title` | `VARCHAR(500)` | NOT NULL | Titre du document |
| `publisher` | `VARCHAR(100)` | NOT NULL, indexed | Organisme émetteur (GCF, BOAD, IPCC, ADEME, IFC, UEMOA, BCEAO, etc.) |
| `version` | `VARCHAR(50)` | NOT NULL | Version au moment de la capture (« v23 », « 2024 », « AR6 ») |
| `date_publi` | `DATE` | NOT NULL | Date de publication du document |
| `page` | `INTEGER` | NULL | Numéro de page |
| `section` | `VARCHAR(200)` | NULL | Référence textuelle (« Annexe 3 », « § 4.2.1 ») |
| `captured_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Quand on a saisi la source |
| `captured_by` | `UUID` | NOT NULL, FK `users.id` ON DELETE RESTRICT | Admin qui a saisi |
| `verified_by` | `UUID` | NULL, FK `users.id` ON DELETE RESTRICT | Admin différent de `captured_by` qui a validé |
| `verification_status` | `VARCHAR(20)` | NOT NULL, ENUM, default `'draft'` | `draft` / `pending` / `verified` / `outdated` |
| `verified_at` | `TIMESTAMPTZ` | NULL | Date de validation |
| `outdated_reason` | `TEXT` | NULL | Raison d'obsolescence |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | Identifiant propriétaire (TODO(F02): account_id) |
| `embedding` | `vector(1536)` | NULL | Embedding `text-embedding-3-small` pour `search_source` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Trace création (pour observabilité) |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Mise à jour (trigger UPDATE) |

**Contraintes d'intégrité** :

- `sources_four_eyes_chk` : `CHECK (verified_by IS NULL OR verified_by != captured_by)` — invariant 4-yeux.
- `sources_verified_consistency_chk` : `CHECK ((verification_status IN ('verified','outdated') AND verified_by IS NOT NULL AND verified_at IS NOT NULL) OR verification_status IN ('draft','pending'))`.
- `sources_outdated_reason_chk` : `CHECK ((verification_status = 'outdated' AND outdated_reason IS NOT NULL) OR verification_status != 'outdated')`.

**Index** :

- `sources_verification_status_idx` sur `verification_status` (filtre fréquent côté API).
- `sources_publisher_idx` sur `publisher` (filtre côté UI catalogue).
- `sources_title_publisher_fts_idx` : index full-text PostgreSQL sur `(title || ' ' || publisher || ' ' || COALESCE(section,''))` via `to_tsvector('french', ...)`.
- `sources_embedding_hnsw_idx` HNSW sur `embedding` avec `vector_cosine_ops` (`m=16, ef_construction=64`).
- `sources_url_uniq_idx` UNIQUE sur `url` (évite doublons à URL identique ; les versions différentes auront des URL différentes ou un suffixe).

**Transitions d'état** :

```
   draft ──────► pending ──────► verified
                                   │
                                   ▼
                                outdated
                                   │
                                   ▼
                                  (terminal — pas de retour à verified)
```

Règles :
- `draft → pending` : par n'importe quel admin (typiquement `captured_by`).
- `pending → verified` : par admin **différent** de `captured_by`.
- `verified → outdated` : par n'importe quel admin avec `outdated_reason` non vide.
- Toute autre transition rejetée par le service (et par la CHECK constraint pour les invariants structurels).

## Entité 2 : `indicators`

**Rôle** : unité atomique de mesure ESG (par exemple « pourcentage de déchets recyclés »).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | Identifiant |
| `code` | `VARCHAR(20)` | NOT NULL, UNIQUE | Code court (« E1 », « S5 », « G3 ») |
| `pillar` | `VARCHAR(20)` | NOT NULL | `environment` / `social` / `governance` |
| `label` | `VARCHAR(200)` | NOT NULL | Libellé court |
| `description` | `TEXT` | NOT NULL | Description longue |
| `question` | `TEXT` | NOT NULL | Question-type adressée à l'utilisateur (chat) |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` ON DELETE RESTRICT | Source justifiant l'indicateur |
| `publication_status` | `VARCHAR(20)` | NOT NULL, ENUM, default `'draft'` | `draft` / `published` |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | TODO(F02): account_id |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

**Contraintes** :
- `indicators_publication_gated_chk` : trigger ou check applicatif vérifiant que la transition `draft → published` n'est possible que si `sources.id = source_id` est en `verification_status = 'verified'`.
- `indicators_pillar_chk` : `CHECK (pillar IN ('environment','social','governance'))`.

**Migration des 30 critères ESG** : la fonction `seed_esg_indicators()` (dans `migration_helpers.py`) lit `backend/app/modules/esg/criteria.py` (`ENVIRONMENT_CRITERIA`, `SOCIAL_CRITERIA`, `GOVERNANCE_CRITERIA`) et insère 30 indicators avec :
- `source_id` pointant vers la Taxonomie verte UEMOA pour les pillars `environment` (par défaut)
- `source_id` pointant vers IFC Performance Standards pour `social`
- `source_id` pointant vers les ODD ONU 8/10/17 pour `governance`
…sauf cas spécifiques (cf. `migration_helpers.py` mapping détaillé).

## Entité 3 : `referentials`

**Rôle** : collection cohérente d'indicateurs (par exemple : « Référentiel ESG UEMOA Standard »).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | Identifiant |
| `code` | `VARCHAR(50)` | NOT NULL, UNIQUE | Code (« UEMOA-2024-STD ») |
| `label` | `VARCHAR(200)` | NOT NULL | Libellé |
| `description` | `TEXT` | NOT NULL | |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | Source structurante (taxonomie de référence) |
| `publication_status` | `VARCHAR(20)` | NOT NULL, default `'draft'` | |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

**Migration** : un seed initial crée le référentiel `UEMOA-2024-STD` lié à la source « Taxonomie verte UEMOA ».

## Entité 4 : `referential_indicators` (jointure N-N)

**Rôle** : association entre un indicateur et un référentiel, porteur d'attributs propres (poids, seuil, source justifiant).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `referential_id` | `UUID` | NOT NULL, FK `referentials.id` ON DELETE CASCADE | |
| `indicator_id` | `UUID` | NOT NULL, FK `indicators.id` ON DELETE RESTRICT | |
| `weight` | `NUMERIC(4,2)` | NOT NULL, default `1.00` | Pondération |
| `threshold` | `NUMERIC(10,2)` | NULL | Seuil d'éligibilité |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | Source justifiant le poids/seuil retenu |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

**Contraintes** :
- UNIQUE `(referential_id, indicator_id)` : un même couple ne peut apparaître qu'une fois par référentiel.

**Migration des `SECTOR_WEIGHTS`** : la fonction `seed_sector_weights()` lit `backend/app/modules/esg/weights.py` (`SECTOR_WEIGHTS: dict[str, dict[str, float]]`) et crée :
- 1 referential par secteur (`AGRI-WEIGHTS`, `ENERGIE-WEIGHTS`, etc.)
- N referential_indicators par secteur (1 par couple `(critère, poids)` non unitaire).

`source_id` pointe vers les sources des publishers compétents (par exemple BOAD pour les pondérations sectorielles UEMOA, ou Taxonomie verte UEMOA selon le secteur). Si aucune source officielle ne couvre le poids, l'enregistrement est marqué « pending » via le trigger.

## Entité 5 : `criteria`

**Rôle** : condition logique sur un ou plusieurs indicateurs (par exemple : « éligible Green Bond UEMOA si E2 ≥ 7 ET E5 ≥ 6 »).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `code` | `VARCHAR(50)` | NOT NULL, UNIQUE | |
| `label` | `VARCHAR(200)` | NOT NULL | |
| `expression` | `JSONB` | NOT NULL | Arbre logique (`{op:"AND", clauses:[{indicator:"E2", cmp:">=", val:7}, ...]}`) |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | |
| `publication_status` | `VARCHAR(20)` | NOT NULL, default `'draft'` | |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

## Entité 6 : `formulas`

**Rôle** : formules de calcul mobilisant indicateurs et constantes (par exemple : « score combiné crédit = 0.4*solvency + 0.3*esg + 0.3*impact »).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `code` | `VARCHAR(50)` | NOT NULL, UNIQUE | |
| `label` | `VARCHAR(200)` | NOT NULL | |
| `expression` | `TEXT` | NOT NULL | Formule textuelle (parsable par numexpr ou interpréteur dédié) |
| `parameters` | `JSONB` | NOT NULL | `{"solvency": "indicator:G1", "esg": "indicator:E_avg", ...}` |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | |
| `publication_status` | `VARCHAR(20)` | NOT NULL, default `'draft'` | |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

## Entité 7 : `thresholds`

**Rôle** : seuils d'éligibilité ou de classification (par exemple : « PME UEMOA = chiffre d'affaires < 1,5 milliard FCFA »).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `code` | `VARCHAR(50)` | NOT NULL, UNIQUE | |
| `label` | `VARCHAR(200)` | NOT NULL | |
| `value` | `NUMERIC(20,2)` | NOT NULL | |
| `unit` | `VARCHAR(20)` | NOT NULL | (« FCFA », « employees », « tCO2e/an », etc.) |
| `scope` | `VARCHAR(100)` | NOT NULL | (« UEMOA », « CEDEAO », « Côte d'Ivoire », etc.) |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | |
| `publication_status` | `VARCHAR(20)` | NOT NULL, default `'draft'` | |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

## Entité 8 : `emission_factors`

**Rôle** : facteurs d'émission par catégorie et par pays (ADEME, IPCC, IEA).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `code` | `VARCHAR(100)` | NOT NULL, UNIQUE | (« electricity_ci », « diesel_generator », etc.) |
| `label` | `VARCHAR(200)` | NOT NULL | (« Électricité (réseau Côte d'Ivoire) ») |
| `category` | `VARCHAR(50)` | NOT NULL, indexed | (« energy », « transport », « waste », « agriculture », « industrial ») |
| `country` | `VARCHAR(50)` | NOT NULL | (« CI », « SN », « UEMOA », « WORLD ») |
| `value` | `NUMERIC(10,4)` | NOT NULL | |
| `unit` | `VARCHAR(50)` | NOT NULL | (« kgCO2e/kWh », « kgCO2e/L », « kgCO2e/kg ») |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | |
| `publication_status` | `VARCHAR(20)` | NOT NULL, default `'draft'` | |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

**Index** : `(category, country)` composite pour les lookups fréquents par le carbon module.

**Migration des `EMISSION_FACTORS`** : la fonction `seed_emission_factors()` lit `backend/app/modules/carbon/emission_factors.py` (`EMISSION_FACTORS: dict[str, dict]`) et crée 1 enregistrement par clé du dict. `source_id` pointe vers ADEME (pour les facteurs énergie/transport) ou IEA (pour électricité par pays).

## Entité 9 : `required_documents`

**Rôle** : documents obligatoires par fonds ou par intermédiaire (par exemple : « registre des actionnaires »).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `label` | `VARCHAR(200)` | NOT NULL | |
| `description` | `TEXT` | NOT NULL | |
| `fund_id` | `UUID` | NULL, FK `funds.id` ON DELETE CASCADE | XOR avec intermediary_id |
| `intermediary_id` | `UUID` | NULL, FK `intermediaries.id` ON DELETE CASCADE | |
| `source_id` | `UUID` | NOT NULL, FK `sources.id` | |
| `publication_status` | `VARCHAR(20)` | NOT NULL, default `'draft'` | |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

**Contraintes** :
- `required_documents_owner_chk` : `CHECK ((fund_id IS NOT NULL AND intermediary_id IS NULL) OR (fund_id IS NULL AND intermediary_id IS NOT NULL))`.

## Entité 10 : `simulation_factors`

**Rôle** : constantes numériques utilisées par les simulateurs (taux d'épargne, impact carbone par million de FCFA investi, etc.).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `code` | `VARCHAR(100)` | NOT NULL, UNIQUE | (« savings_rate », « carbon_impact_per_mxof ») |
| `label` | `VARCHAR(200)` | NOT NULL | |
| `value` | `NUMERIC(20,6)` | NOT NULL | |
| `unit` | `VARCHAR(50)` | NOT NULL | |
| `scope` | `VARCHAR(100)` | NOT NULL | |
| `source_id` | `UUID` | NULL, FK `sources.id` | NULL si `status = pending` |
| `status` | `VARCHAR(20)` | NOT NULL, ENUM, default `'pending'` | `verified` / `pending` |
| `created_by_user_id` | `UUID` | NOT NULL, FK `users.id` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

**Contraintes** :
- `simulation_factors_source_required_chk` : `CHECK ((status = 'verified' AND source_id IS NOT NULL) OR (status = 'pending' AND source_id IS NULL))`.

**Migration** : `seed_simulation_factors()` migre les constantes du module financier (`_SAVINGS_RATE = 0.15`, `_CARBON_IMPACT_PER_MXOF = 1.7`) en `status = 'pending'` car aucune source officielle ne les couvre aujourd'hui. Liste de suivi naturelle pour traitement éditorial.

## Entité 11 : `unsourced_flags`

**Rôle** : journal des invocations `flag_unsourced` par l'agent IA, pour revue administrateur et calcul des métriques (SC-012).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | |
| `claim` | `TEXT` | NOT NULL | Texte de l'affirmation non sourçable |
| `reason` | `TEXT` | NOT NULL | Motif fourni par l'agent |
| `conversation_id` | `UUID` | NULL, FK `conversations.id` ON DELETE SET NULL | Conversation contextuelle (NULL si tour orphelin) |
| `message_id` | `UUID` | NULL, FK `messages.id` ON DELETE SET NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Horodatage |

**Index** : `created_at DESC` pour le calcul des métriques 24h glissantes.

## Modifications des entités existantes

### `funds`, `intermediaries`, `templates_dossier`

Ajout d'une colonne `publication_status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (publication_status IN ('draft','published'))`.

> **Important** : la colonne est ajoutée seulement si la table existe au moment de la migration. Pour `templates_dossier` (qui n'existe peut-être pas encore au moment de F01), un `IF NOT EXISTS` ou un branchement Alembic garde la migration robuste.

### Pas de modification des autres tables

Les tables existantes (`carbon_assessments`, `esg_assessments`, etc.) **ne sont pas modifiées** en F01. Elles consommeront le catalogue dans des features ultérieures (F13 scoring multi-référentiels, F17 carbone mix UEMOA).

## Workflow de publication des entités sourcées

```
            ┌─────────────────────────────────────────┐
            │     Création par admin (status=draft)    │
            └──────────────────┬──────────────────────┘
                               │
                               ▼
           ┌────────────────────────────────────────────────────┐
           │  Admin demande passage en `published`               │
           │  Service vérifie : toutes les sources liées sont    │
           │  en verification_status='verified' ?                │
           └─────────────┬───────────────────┬──────────────────┘
                  oui    │                   │   non
                         ▼                   ▼
                 ┌──────────────┐     ┌────────────────────┐
                 │ status=published│     │ ERREUR 422        │
                 │ visible LLM/UI │     │ + liste sources    │
                 └──────────────┘     │ à valider d'abord  │
                                      └────────────────────┘
```

**Implémentation** : check applicatif dans le service (préféré pour message d'erreur lisible) + trigger PostgreSQL `enforce_published_requires_verified_sources()` (defense-in-depth).

```sql
CREATE TRIGGER enforce_published_requires_verified_sources
BEFORE UPDATE OF publication_status ON indicators
FOR EACH ROW
WHEN (NEW.publication_status = 'published' AND OLD.publication_status = 'draft')
EXECUTE FUNCTION assert_source_verified();
-- (et idem pour referentials, criteria, formulas, thresholds, emission_factors,
--  required_documents, simulation_factors)
```

## Volumes attendus

| Table | Volume initial (seed) | Volume cible année 1 |
|-------|----------------------|----------------------|
| `sources` | 30 | 200 |
| `indicators` | 30 | 100 |
| `referentials` | 8 (1 std + 7 secteurs) | 15 |
| `referential_indicators` | ~250 | ~600 |
| `criteria` | 10 | 50 |
| `formulas` | 5 | 20 |
| `thresholds` | 10 | 50 |
| `emission_factors` | 25 | 100 |
| `required_documents` | 50 | 200 |
| `simulation_factors` | 5 | 20 |
| `unsourced_flags` | 0 | ~1000 (journal) |

Volumes très modestes : aucun risque de saturation PostgreSQL en année 1.

---

**Sortie Phase 1 (data-model)** : 11 entités spécifiées, 12 contraintes structurelles documentées (CHECK, UNIQUE, FK), 5 transitions d'état formalisées. Prêt pour les contracts.
