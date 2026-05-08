# Implementation Plan: F18 — Mobile Money + Photos IA + Données Publiques (avec Consentements)

**Branch**: `feat/F18-mobile-money-photos-ia-public-data` (numéro spec `037`)
**Spec**: [spec.md](spec.md)
**Date**: 2026-05-08

---

## 1. Architecture overview

F18 ajoute un **module crédit alternatif** au scoring crédit vert (Module 5.2), composé de 3 pipelines indépendants gardés par des consentements granulaires F05 :

```
PME → Consent F05 → Endpoint REST F18 → Service métier → Persistance (RLS F02 + Audit F03 + Sources F01)
                                          ↓
                              Calcul scoring (Money typed F04 ; pondérations dynamiques)
                                          ↓
                              UI Score Crédit (sections Mobile Money, Photos IA, Données publiques)
                                          ↓
                              Méthodologie publique (sans auth)
```

Le module s'insère dans `backend/app/modules/credit/` (existant) et `frontend/app/pages/credit-score/` (existant). Les invariants projet sont strictement respectés : sourçage F01, multi-tenant F02 + RLS, audit F03, Money typed F04, consentements F05, dark mode, FR avec accents.

---

## 2. Tech stack & invariants

| Couche | Stack | Invariant |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic, Pydantic v2 | snake_case, `Auditable` mixin (F03), RLS F02, Money typed F04 |
| LLM | OpenRouter (Claude Vision multimodal), LangChain, LangGraph | tools sourcés F01, `source_of_change=llm` côté nœud |
| BDD | PostgreSQL 16 + pgvector | timestamptz UTC, UUID v4 PK, FK `account_id` NOT NULL |
| Frontend | Nuxt 4, Vue Composition API, Pinia, TailwindCSS | dark mode, `<SourceLink>`, ARIA, FR avec accents |
| Tests | pytest + pytest-asyncio (backend), Vitest (frontend), Playwright (E2E) | Couverture ≥ 80 % sur F18 ; mock LLM |

---

## 3. Migration Alembic — `037_alternative_credit_data`

**Fichier** : `backend/alembic/versions/037_alternative_credit_data.py`
**down_revision** : `035_admin_publication_status_workflow` (dernière migration en `main`)

### 3.1 Extension de l'enum `CreditCategory`

Ajout de 3 valeurs : `mobile_money_flux`, `photos_ia`, `public_data`.

PostgreSQL : `ALTER TYPE credit_category ADD VALUE IF NOT EXISTS 'mobile_money_flux'` (× 3, dans des transactions séparées si nécessaire). SQLite : recréation table en test.

### 3.2 Nouvelles tables

#### `mobile_money_transactions`
```
id UUID PK
account_id UUID NOT NULL FK accounts(id) ON DELETE RESTRICT
import_id UUID NOT NULL FK mobile_money_imports(id) ON DELETE CASCADE
provider VARCHAR(20) NOT NULL CHECK IN ('wave','orange_money','mtn_momo','moov_money')
transaction_date TIMESTAMPTZ NOT NULL
direction VARCHAR(10) NOT NULL CHECK IN ('incoming','outgoing')
amount NUMERIC(20,2) NOT NULL CHECK (amount >= 0)
currency CHAR(3) NOT NULL CHECK IN ('XOF','EUR','USD','GBP','JPY')
counterparty_hash CHAR(64) NOT NULL  -- SHA-256 hex
balance_amount NUMERIC(20,2) NULL
balance_currency CHAR(3) NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
unused BOOLEAN NOT NULL DEFAULT FALSE  -- post-révocation
purge_after TIMESTAMPTZ NULL  -- 30 j après révocation
UNIQUE (account_id, transaction_date, amount, counterparty_hash, direction)  -- déduplication
INDEX (account_id, transaction_date DESC)
```

#### `mobile_money_imports`
```
id UUID PK
account_id UUID NOT NULL FK accounts(id) ON DELETE RESTRICT
provider VARCHAR(20) NOT NULL
file_path VARCHAR(500) NOT NULL  -- /uploads/{account_id}/credit/mobile_money/{uuid}.csv
imported_rows INT NOT NULL DEFAULT 0
rejected_rows INT NOT NULL DEFAULT 0
status VARCHAR(20) NOT NULL DEFAULT 'pending'  -- pending|completed|failed
error_summary JSONB NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
INDEX (account_id, created_at DESC)
```

#### `mobile_money_analyses`
```
id UUID PK
account_id UUID NOT NULL FK accounts(id) ON DELETE RESTRICT
methodology_version VARCHAR(20) NOT NULL  -- ex 1.2
kpis JSONB NOT NULL  -- {monthly_volume_avg, monthly_volume_stddev, regularity_30d, avg_balance_estimate, growth_12m, top_counterparties}
consent_active BOOLEAN NOT NULL
computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
INDEX (account_id, computed_at DESC)
UNIQUE (account_id, methodology_version)  -- 1 ligne courante par version
```

#### `credit_photos`
```
id UUID PK
account_id UUID NOT NULL FK accounts(id) ON DELETE RESTRICT
file_path VARCHAR(500) NOT NULL
content_hash CHAR(64) NOT NULL  -- SHA-256 contenu (déduplication + idempotence analyse)
captured_at TIMESTAMPTZ NULL
analyzed_at TIMESTAMPTZ NULL
analysis_result JSONB NULL  -- {scores: {material, organization, hygiene, env_practices, activity}, observations, red_flags, green_signals}
quality_status VARCHAR(20) NOT NULL DEFAULT 'pending'  -- pending|ok|low_quality|failed
methodology_version VARCHAR(20) NULL
unused BOOLEAN NOT NULL DEFAULT FALSE
purge_after TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
UNIQUE (account_id, content_hash)  -- déduplication intra-PME
INDEX (account_id, created_at DESC)
```

#### `public_data_sources`
```
id UUID PK
account_id UUID NOT NULL FK accounts(id) ON DELETE RESTRICT
source_type VARCHAR(30) NOT NULL CHECK IN ('google_my_business','facebook_page','google_reviews','trustpilot','green_program','other')
url VARCHAR(2000) NOT NULL
declared_rating NUMERIC(3,1) NULL CHECK (declared_rating IS NULL OR (declared_rating >= 0 AND declared_rating <= 5))
declared_reviews_count INT NULL CHECK (declared_reviews_count IS NULL OR declared_reviews_count >= 0)
program_label VARCHAR(100) NULL  -- PNUE, ADEME, GRI Sustainability...
evidence_path VARCHAR(500) NULL
status VARCHAR(20) NOT NULL DEFAULT 'declared'  -- declared|evidence_attached|pending_review
sentiment_score NUMERIC(3,2) NULL  -- analyse LLM ultérieure
green_signals JSONB NULL
unused BOOLEAN NOT NULL DEFAULT FALSE
purge_after TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
INDEX (account_id, source_type)
```

#### `credit_methodology_factors` (catalogue, exempté account_id, lecture publique)
```
id UUID PK
version VARCHAR(20) NOT NULL  -- 1.2
name VARCHAR(200) NOT NULL
category VARCHAR(50) NOT NULL  -- credit_category
weight NUMERIC(4,3) NOT NULL CHECK (weight >= 0 AND weight <= 1)
description TEXT NOT NULL
source_id UUID NOT NULL FK sources(id) ON DELETE RESTRICT
publication_status VARCHAR(20) NOT NULL DEFAULT 'draft'  -- draft|published
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
UNIQUE (version, name)
```

### 3.3 RLS PostgreSQL

`ENABLE ROW LEVEL SECURITY + FORCE` sur les 5 tables tenant (`mobile_money_*`, `credit_photos`, `public_data_sources`). 2 policies par table : `pme_access_own_account` (USING `account_id = current_setting('app.current_account_id')::uuid`) + `admin_full_access`.

`credit_methodology_factors` est exempt (catalogue admin-only) → ajouté à `EXEMPT_MODELS`.

### 3.4 Audit log F03

Modèles `MobileMoneyTransaction`, `MobileMoneyImport`, `MobileMoneyAnalysis`, `CreditPhoto`, `PublicDataSource` ajoutés à `AUDITABLE_MODELS`.

`MobileMoneyAnalysis` peut être exemptée (artefact recalculé) ; à valider en revue.

### 3.5 Backfill / migration legacy

Aucune donnée legacy à migrer (entités nouvelles). Conservation des colonnes/enums existants 2 sprints.

---

## 4. Backend — services & endpoints

### 4.1 Modules

```
backend/app/modules/credit/
  alternative/
    __init__.py
    mobile_money_parser.py        # Parsers CSV/Excel par fournisseur
    mobile_money_analyzer.py      # Calcul KPIs
    photo_analyzer.py             # Appel Claude Vision (OpenRouter)
    public_data_collector.py      # Persistance déclarative + signaux
    methodology_service.py        # Lecture méthodologie + sources F01
    consent_guard.py              # require_consent helper réutilisable
  service.py                      # compute_combined_score (refactor)
```

### 4.2 Schemas Pydantic v2 (strict)

`schemas/mobile_money.py`, `schemas/credit_photo.py`, `schemas/public_data.py`, `schemas/methodology.py`. Tous avec `extra='forbid'`, validators stricts (URL, taille fichiers, énumérations).

### 4.3 Endpoints REST

| Méthode | Route | Auth | Description |
|---|---|---|---|
| POST | `/api/credit/mobile-money/upload` | user + consent `mobile_money_analysis` | Upload CSV/Excel, parsing, persistance |
| GET | `/api/credit/mobile-money/analysis` | user + consent | KPIs courants |
| GET | `/api/credit/mobile-money/imports` | user + consent | Historique des imports |
| POST | `/api/credit/photos/upload` | user + consent `photo_analysis` | Upload 1..N photos (multipart) |
| GET | `/api/credit/photos` | user + consent | Liste des photos PME |
| POST | `/api/credit/photos/{id}/analyze` | user + consent | Déclenche analyse IA (idempotente) |
| GET | `/api/credit/photos/{id}` | user + consent | Détail + analyse |
| POST | `/api/credit/public-data/declare` | user + consent `public_data_lookup` | Déclaration source publique |
| GET | `/api/credit/public-data` | user + consent | Liste des sources déclarées |
| DELETE | `/api/credit/public-data/{id}` | user + consent | Soft-delete (unused=true) |
| GET | `/api/credit/methodology` | **public (no auth)** | Méthodologie courante |

Garde-fou consent : décorateur `Depends(require_consent("mobile_money_analysis"))` qui retourne 403 `{"error": "consent_required", "consent_type": "..."}` en cas d'absence.

### 4.4 Refactor `compute_combined_score`

```
combined = sum(score_i * weight_i for i in available_categories) * confidence_factor
```

Pondérations dynamiques : si une catégorie est indisponible (pas de consentement OU pas de données), son poids est redistribué proportionnellement aux autres. Plafond `public_data` = 10 % strict.

`methodology_version` est persistée sur chaque ligne `credit_scores` (audit trail).

### 4.5 Hook révocation consentement

Souscription à un événement F05 `consent_revoked(account_id, type)` :
- `mobile_money_analysis` → `unused=true` + `purge_after = now() + 30 days` sur transactions/imports/analysis ; suppression de la catégorie du score courant.
- `photo_analysis` → idem `credit_photos`.
- `public_data_lookup` → idem `public_data_sources`.

Cron `scripts/purge_revoked_credit_data.py` (idempotent) supprime physiquement les lignes `purge_after < now()` et les fichiers associés.

### 4.6 Sécurité fichiers

- Validation MIME (magic bytes, pas que extension) via `python-magic`.
- Tailles bornées : 5 Mo / photo, 5 Mo / CSV, 50 000 lignes max.
- Strip EXIF (Pillow) avant persistance.
- `content_hash` SHA-256 pour idempotence + déduplication.
- Stockage `/uploads/{account_id}/credit/{type}/{uuid}.{ext}` avec permissions 600.

---

## 5. LangGraph / Tools (optionnel, P3)

Tools LangChain (lecture seule) injectés dans le nœud `credit` :
- `get_mobile_money_kpis(account_id)` : retourne KPIs + version méthodologie.
- `get_photo_analyses(account_id, limit)` : liste résumée.
- `get_public_data_sources(account_id)` : liste résumée.

Pas de tool de mutation (uploads passent par REST exclusivement, gating consent runtime).

---

## 6. Frontend Nuxt 4

### 6.1 Pages

- `pages/credit-score/index.vue` (refactor) : 3 nouvelles sections `MobileMoneySection`, `PhotosIASection`, `PublicDataSection`.
- `pages/legal/methodology-credit.vue` (nouvelle, **no-auth**) : version, facteurs avec poids, `<SourceLink>` cliquables.

### 6.2 Composants

- `components/credit/MobileMoneyUpload.vue` : dropzone CSV/Excel, progress, KPIs après import.
- `components/credit/MobileMoneyKpiCard.vue` : KPI individuel + `<SourceLink>` méthodologie.
- `components/credit/PhotoUpload.vue` : multi-upload (max 10), aperçus, statuts qualité.
- `components/credit/PhotoAnalysisCard.vue` : 5 scores radar/bars + observations + red/green signals.
- `components/credit/PublicDataForm.vue` : formulaire de déclaration + capture optionnelle.
- `components/credit/PublicDataSourceCard.vue` : carte source + badge « déclaratif non vérifié ».
- `components/credit/ConsentRequestModal.vue` : modale réutilisable (texte explicite + CTA accepter/refuser, lien F05).
- `components/credit/ConsentRevokeButton.vue` : confirme + appelle F05.

Tous : dark mode (`dark:bg-dark-card`, `dark:text-surface-dark-text`...), ARIA (`role="dialog"`, `aria-live="polite"` pour progress, `aria-describedby`), libellés FR avec accents.

### 6.3 Composables

- `composables/useCreditAlternativeData.ts` :
  - `uploadMobileMoney(file)`, `getMobileMoneyAnalysis()`, `listImports()`
  - `uploadPhotos(files)`, `listPhotos()`, `analyzePhoto(id)`
  - `declarePublicData(payload)`, `listPublicData()`, `deletePublicData(id)`
  - `getMethodology()` (public, pas de Bearer)
- `composables/useConsent.ts` (extension F05 si déjà existant) : `hasConsent(type)`, `requestConsent(type)`, `revokeConsent(type)`.

### 6.4 Store Pinia

`stores/creditAlternative.ts` : `mobileMoneyAnalysis`, `photos[]`, `publicDataSources[]`, `methodology`, `loading`, `error`. Getters `hasMmKpis`, `analyzedPhotos`, `effectiveCategoriesForScoring`.

### 6.5 Types TypeScript

`types/creditAlternative.ts` : `MobileMoneyKpis`, `PhotoAnalysis`, `PublicDataSource`, `MethodologyFactor`, `ConsentType`, `Provider`, `PhotoQualityStatus`.

---

## 7. Tests

### 7.1 Backend (pytest + pytest-asyncio)

- **Unit** : 4 parsers MM (Wave/OM/MTN/Moov) avec fixtures CSV représentatives (≥ 95 % lignes valides) ; analyzer KPIs ; photo analyzer (mock OpenRouter Vision) ; public data validator ; methodology service ; consent_guard (403 sans consentement, OK avec).
- **Intégration** : 11 endpoints + RLS multi-tenant + audit log F03 + sourçage F01 obligatoire.
- **Migration** : round-trip Alembic up/down/up sur PostgreSQL (test container).
- **Sécurité** : MIME validation, EXIF strip, taille max, dedup hash, idempotence analyse photo.
- **Hook révocation** : transactions/photos/sources passent à `unused=true` + `purge_after` correct ; cron purge effective.
- **Scoring** : `compute_combined_score` avec / sans MM / Photos / Public ; poids public ≤ 10 % strict.

Cible : ≥ 80 % couverture sur les modules F18 ; LLM mocké.

### 7.2 Frontend (Vitest)

- Composants : MobileMoneyUpload (états vide/loading/erreur/succès), PhotoUpload (limite 10, MIME), ConsentRequestModal, PublicDataForm.
- Composables : useCreditAlternativeData (mocks API), useConsent.
- Store Pinia : mutations + getters.

Cible : ≥ 80 % couverture composants F18.

### 7.3 E2E (Playwright)

`frontend/tests/e2e/F18-mobile-money-photos-ia-public-data.spec.ts` :
1. Upload MM sans consentement → modale + bannière 403.
2. Donner consentement → upload CSV Wave fictif → KPIs visibles → catégorie présente dans le score.
3. Upload 3 photos → analyse → 5 scores affichés → catégorie « Photos IA » dans score.
4. Déclarer 1 source publique → catégorie « Données publiques » plafonnée à 10 %.
5. Page publique méthodologie sans login → ouvre modale Source F01.
6. Révocation consentement MM → catégorie disparaît immédiatement.

---

## 8. Observabilité

- Logs structurés JSON : `mobile_money_import_succeeded/failed`, `photo_analysis_succeeded/failed/cached`, `public_data_declared`, `consent_revoked_purge_scheduled`.
- Métriques (compteurs in-memory MVP) : `mm_imports_total`, `photo_analyses_total`, `public_sources_declared_total`, `consent_blocked_total{type}`.

---

## 9. Documentation

- `docs/credit-alternative-data.md` (nouveau) : pipelines, garde-fous consent, sécurité fichiers, méthodologie, troubleshooting, ajout d'un nouveau fournisseur MM.
- Ajout dans `CLAUDE.md` (section Active Technologies) après merge.

---

## 10. Risques & garde-fous (rappel spec, traduction technique)

| Risque | Garde-fou technique |
|---|---|
| RGPD photos (visages, géoloc) | Strip EXIF systématique, pas de reconnaissance faciale, prompt LLM explicite « ne décris pas les personnes », consent obligatoire |
| Coût Claude Vision | Idempotence par `content_hash` (1 analyse / photo), cap 10 photos / PME, cache résultat JSONB |
| Faux signaux données publiques | Plafond 10 % du score, badge « non vérifié » UI, statut `pending_review` exigé pour pondération > 5 % (post-MVP) |
| CSV malveillant | Validation MIME magic bytes, taille 5 Mo, 50 000 lignes, ligne par ligne avec rejection |
| Privacy Mobile Money | `counterparty_hash` SHA-256, jamais de noms en clair, droit d'effacement F05 |
| Méthodologie sans source | Filtre côté API (publication_status=published + source_id NOT NULL) + test automatisé SC-010 |

---

## 11. Phase plan (3 sprints)

| Sprint | Livrables | Critères d'acceptation |
|---|---|---|
| 1 | Migration 037, modèles, schemas, parsers MM, analyzer MM, endpoints MM, consent_guard, méthodologie service + endpoint public, page publique méthodologie. Tests unit MM + endpoints + RLS + audit. | US1, US4, US5 (volet MM + méthodologie). |
| 2 | Photo upload (avec EXIF strip + dedup), photo_analyzer (OpenRouter Vision mock-friendly), endpoints photos, components frontend Photos + ConsentRequestModal, scoring refactor avec MM + Photos. Tests photo + frontend Photos + scoring. | US2, US5 (volet Photos). |
| 3 | Public data collector + endpoints + composants, hook révocation consentement F05 + cron purge, plafond 10 % public, E2E Playwright complet, observabilité, documentation. | US3, US5 complet, SC-001..SC-010. |

---

## 12. Dépendances & déblocages

- **F05 consents** : helper `require_consent` opérationnel (vérifié `main`). Si signature diffère, créer adapter.
- **F01 sources** : seed des sources méthodologie (BCEAO Mobile Money Study, méthodologies scoring crédit) à ajouter dans la migration ou via script de seed.
- **F02 multi-tenant** : `set_rls_context` déjà câblé dans `get_current_user`.
- **F03 audit** : `Auditable` mixin et `AUDITABLE_MODELS` réutilisés.
- **F04 Money** : pour les montants MM, `<MoneyDisplay>` côté UI ; persistance amount/currency.
- **OpenRouter Vision** : confirmer modèle multimodal disponible (ex. Claude 3.5 Sonnet vision) ; sinon fallback texte temporaire en mock LLM en tests.
