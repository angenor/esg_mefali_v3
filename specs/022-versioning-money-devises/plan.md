# Implementation Plan: F04 — Versioning + Money Type + Multi-devises

**Branch** : `feat/F04-versioning-money-devises` | **Date** : 2026-05-06 | **Spec** : [spec.md](./spec.md)
**Input** : Feature specification from `/specs/022-versioning-money-devises/spec.md`

## Summary

Cette feature introduit (1) un mécanisme de versioning linéaire (`version`, `valid_from`, `valid_to`, `superseded_by`) sur 13 tables catalogue, (2) un snapshot immuable JSONB sur les candidatures soumises pour reproduire le score d'origine indépendamment des évolutions du référentiel, (3) un type Pydantic v2 strict `Money = (amount: Decimal, currency: Currency)` avec enum strict `XOF/EUR/USD/GBP/JPY`, (4) la constante peg fixe `FCFA_EUR_PEG = Decimal("655.957")`, (5) un service `currency` adossé à une table `exchange_rates` alimentée par exchangerate-api.com (cap dur 1 fetch/jour/paire), (6) un endpoint `POST /api/applications/{id}/recompute-against-snapshot` pour audit, (7) un refactor en deux phases des champs financiers `*_xof` / `*_fcfa` en paires `(amount, currency)` (phase 1 = ajout colonnes + backfill ; phase 2 = drop legacy hors-scope F04), (8) deux composants Vue `<MoneyDisplay>` et `<ReferentialBadge>` avec dark mode, (9) un composable `useCurrency` et un store `ui` étendu pour la préférence d'affichage.

L'approche technique respecte la constitution (TDD, dark mode obligatoire, monolithe modulaire, sécurité Pydantic) et les invariants F01 (sourçage) et F02 (multi-tenant + RLS).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (`asyncpg`), Alembic, Pydantic v2, LangGraph, LangChain, `httpx` (pour exchangerate-api), `pytest`, `pytest-asyncio`, `pytest-cov`
- Frontend : Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Vitest + @vue/test-utils + happy-dom, Playwright
**Storage** : PostgreSQL 16 + pgvector (existant) ; nouvelle table `exchange_rates` ; modifications schéma sur 13 tables catalogue + `fund_applications` ; aucune nouvelle dépendance externe (exchangerate-api.com via HTTP)
**Testing** : pytest (backend), Vitest (frontend), Playwright (E2E)
**Target Platform** : Linux server (Docker Compose) ; navigateurs modernes (Chrome/Firefox/Safari) ; mode dark obligatoire
**Project Type** : web-service monolithe modulaire (`backend/` + `frontend/`)
**Performance Goals** :
- Conversion `Money` < 5 ms (sans appel BDD pour peg fixe FCFA↔EUR)
- Conversion via `exchange_rates` < 50 ms (lecture indexée + fallback ascendant)
- Composant `<MoneyDisplay>` rendu < 50 ms (Vitest assertion)
- Endpoint `recompute-against-snapshot` < 500 ms p95
**Constraints** :
- Cap dur 1 fetch HTTP exchangerate-api.com par paire et par jour (tier gratuit 1500 req/mois)
- Snapshot JSONB autoportant (no FK qui casse si entité supprimée)
- Versioning linéaire uniquement (pas de branches editorial pré-publication, post-MVP)
- Aucune mutation du snapshot après création (immuabilité applicative + tests)
- Aucun secret hardcodé (`EXCHANGERATE_API_KEY` via env var)
**Scale/Scope** :
- ~12-15 fichiers Python nouveaux/modifiés (modèle, service, router, tools, schemas, migration, scripts)
- ~5-7 fichiers Vue/TS nouveaux/modifiés (composants UI, composable, store, types)
- 1 migration Alembic 022 (down_revision conditionnelle : `021_create_audit_log` si F03 mergé, sinon `020_sources`)
- 30-40 tests unitaires backend nouveaux + 5-10 tests intégration + 1 fichier E2E Playwright (4 scénarios)
- Volume de données catalogue prévu : 30+ sources + ~30 indicators + ~12 funds + ~14 intermediaries = quelques centaines de lignes versionnées au max sur l'horizon MVP

## Constitution Check

### Principle I — Francophone-First & Contextualisation Africaine

- **Conforme** : devise par défaut XOF (UEMOA/CEDEAO), peg FCFA-EUR fixe (Banque de France/BCEAO), composant `<MoneyDisplay>` affiche FCFA en natif et tooltip français.
- **Conforme** : tous les libellés UI en français (« Évalué selon Référentiel », « Devise native (≈ équivalent PME) », messages d'erreur français).

### Principle II — Architecture Modulaire

- **Conforme** : nouveau module `app.modules.currency` autonome, ne dépend que de `app.core.money` et `app.models.exchange_rate`. Le service de snapshot est exposé via `app.modules.applications.snapshot` (sous-module dédié dans le module existant).
- **Conforme** : pas de couplage transversal entre versioning et currency — chacun est testable indépendamment.

### Principle III — Conversation-Driven UX

- **Conforme** : le tool LangChain `simulate_financing` retourne des `Money` typés ; aucun nouveau formulaire complexe ; les composants UI s'intègrent dans les pages existantes sans rupture conversationnelle.

### Principle IV — Test-First (NON-NEGOTIABLE)

- **Conforme** : tasks.md impose la création des tests AVANT l'implémentation pour chaque module (tests unitaires Money, currency_service, snapshot, recompute, versioning ; tests intégration migration up/down/up ; tests Vitest sur composants ; tests E2E Playwright). Couverture cible 80 % sur les nouveaux modules.

### Principle V — Sécurité & Protection des Données

- **Conforme** : `EXCHANGERATE_API_KEY` via env var. Validation Pydantic stricte sur `Money` (refus devise hors enum). Snapshot stocké avec contrôle d'accès via RLS héritée de `fund_applications`. Mutation catalogue (versioning) réservée aux admins via `get_current_admin` (F02).
- **Conforme** : SQL paramétré via SQLAlchemy ORM. Aucune concaténation manuelle.

### Principle VI — Inclusivité & Accessibilité

- **Conforme** : `<MoneyDisplay>` et `<ReferentialBadge>` portent des libellés textuels (pas que des icônes), tooltip ARIA `aria-describedby`, espace insécable comme séparateur (lecture confortable). Dark mode obligatoire.

### Principle VII — Simplicité & YAGNI

- **Conforme** : pas de microservices. Snapshot JSONB autoportant (pas de versionning relationnel complexe). Cron synchrone via CLI script (pas de Redis/Celery, intégration future avec F19). Versioning linéaire (pas de branches éditoriales). Phase 2 (drop legacy) reportée à une migration séparée.
- **Conforme** : compression gzip du snapshot reportée post-MVP (mesure d'abord, décide ensuite).

### Conclusion gate Phase 0 → Phase 1

- ✅ AUCUN écart constitutionnel détecté → autorisation de poursuivre Phase 0.
- Aucune complexité injustifiée à tracker.

## Project Structure

### Documentation (this feature)

```text
specs/022-versioning-money-devises/
├── plan.md              # This file
├── spec.md              # Functional spec (User Stories + FR + SC)
├── research.md          # Phase 0 — décisions techniques
├── data-model.md        # Phase 1 — schéma BDD détaillé
├── quickstart.md        # Phase 1 — guide démarrage rapide
├── contracts/
│   ├── currency_api.yaml          # OpenAPI snippet pour /api/currency
│   ├── application_recompute.yaml # OpenAPI snippet pour /api/applications/{id}/recompute-against-snapshot
│   └── currency_status.yaml       # OpenAPI snippet pour /api/admin/currency/fetch-status
├── checklists/
│   └── requirements.md  # Validation qualité spec (créé en Phase A)
└── tasks.md             # Phase B — créé par /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   ├── money.py                              [NEW] Type Pydantic Money + Currency Literal
│   │   └── constants.py                          [MODIFIED] FCFA_EUR_PEG = Decimal("655.957")
│   ├── models/
│   │   ├── exchange_rate.py                      [NEW] Modèle SQLAlchemy ExchangeRate
│   │   ├── source.py                             [MODIFIED] +version, valid_from, valid_to, superseded_by
│   │   ├── indicator.py                          [MODIFIED] idem
│   │   ├── referential.py                        [MODIFIED] idem (Referential, ReferentialIndicator, Criterion, Formula, Threshold)
│   │   ├── emission_factor.py                    [MODIFIED] idem
│   │   ├── required_document.py                  [MODIFIED] idem
│   │   ├── simulation_factor.py                  [MODIFIED] idem
│   │   ├── financing.py                          [MODIFIED] Fund + Intermediary + FundIntermediary +version,..., +min_amount/min_amount_currency, max_amount/...
│   │   ├── company.py                            [MODIFIED] CompanyProfile +annual_revenue_amount/_currency
│   │   ├── action_plan.py                        [MODIFIED] ActionItem +estimated_cost_amount/_currency
│   │   ├── carbon.py                             [MODIFIED] CarbonAssessment +savings_amount/_currency (si savings_fcfa présent ; check à confirmer en B)
│   │   └── application.py                        [MODIFIED] FundApplication +snapshot_at, snapshot_data
│   ├── modules/
│   │   ├── currency/                             [NEW] Module devises
│   │   │   ├── __init__.py
│   │   │   ├── service.py                        [NEW] convert(), get_rate(), fetch_one_shot()
│   │   │   ├── router.py                         [NEW] /api/currency/rates/latest, /convert
│   │   │   ├── admin_router.py                   [NEW] /api/admin/currency/fetch-status
│   │   │   ├── schemas.py                        [NEW] Pydantic ConvertRequest, ConvertResponse, RatesLatestResponse, FetchStatusResponse
│   │   │   └── exceptions.py                     [NEW] NoRateAvailableError, ConversionPathUnavailableError
│   │   ├── versioning/                           [NEW] Helpers versioning catalogue
│   │   │   ├── __init__.py
│   │   │   ├── service.py                        [NEW] supersede(), bump_version(), is_published()
│   │   │   └── exceptions.py                     [NEW] VersioningError, SupersedeCycleError
│   │   └── applications/
│   │       ├── service.py                        [MODIFIED] create_snapshot() à la transition submitted_*
│   │       ├── snapshot.py                       [NEW] build_snapshot_data(), validate_immutable()
│   │       ├── recompute.py                      [NEW] recompute_against_snapshot(application_id)
│   │       ├── router.py                         [MODIFIED] POST /{id}/recompute-against-snapshot
│   │       └── simulation.py                     [MODIFIED] retour Money typés, fix AttributeError
│   ├── graph/
│   │   └── tools/
│   │       └── application_tools.py              [MODIFIED] simulate_financing → Money typés
│   ├── scripts/
│   │   └── fetch_exchange_rates.py               [NEW] CLI : python -m app.scripts.fetch_exchange_rates
│   └── main.py                                   [MODIFIED] router currency + admin currency, lifespan check fetch
├── alembic/
│   └── versions/
│       └── 022_money_and_versioning.py           [NEW] Migration : exchange_rates + versioning columns + snapshot + paires Money
└── tests/
    ├── test_core/
    │   ├── test_money.py                         [NEW] Money type, validation, peg
    │   └── test_constants.py                     [NEW] FCFA_EUR_PEG = 655.957
    ├── test_currency/
    │   ├── test_service.py                       [NEW] convert(), get_rate(), fallback
    │   ├── test_router.py                        [NEW] endpoints HTTP
    │   ├── test_admin_router.py                  [NEW] fetch-status
    │   ├── test_pivot.py                         [NEW] EUR→JPY via USD
    │   └── test_fetch_script.py                  [NEW] cap 1/jour, mocking httpx
    ├── test_versioning/
    │   ├── test_supersede.py                     [NEW] bump version, valid_to, superseded_by
    │   └── test_cycle_trigger.py                 [NEW] trigger anti-cycle (PostgreSQL) + fallback applicatif (SQLite)
    ├── test_applications/
    │   ├── test_snapshot_creation.py             [NEW] snapshot à la soumission
    │   ├── test_snapshot_immutable.py            [NEW] tentative modif rejetée
    │   ├── test_recompute_against_snapshot.py    [NEW] score reproductible
    │   └── test_simulation.py                    [MODIFIED] Money typés
    ├── test_models/
    │   ├── test_exchange_rate.py                 [NEW] modèle + index
    │   └── test_versioning_columns.py            [NEW] colonnes version sur 13 tables
    └── test_migrations/
        └── test_022_money_and_versioning.py      [NEW] up/down/up + backfill XOF

frontend/
├── app/
│   ├── components/
│   │   └── ui/
│   │       ├── MoneyDisplay.vue                  [NEW] composant montant
│   │       └── ReferentialBadge.vue              [NEW] badge version référentiel
│   ├── composables/
│   │   └── useCurrency.ts                        [NEW] format(), convert(), getRate()
│   ├── stores/
│   │   └── ui.ts                                 [MODIFIED] +displayCurrencyMode
│   ├── types/
│   │   └── currency.ts                           [NEW] Money, Currency, ExchangeRate types TS
│   └── pages/
│       ├── financing/                            [MODIFIED] migrate to <MoneyDisplay>
│       ├── financing/[id].vue                    [MODIFIED] idem + <ReferentialBadge>
│       ├── dashboard/                            [MODIFIED] idem
│       ├── action-plan.vue                       [MODIFIED] idem
│       └── applications/[id].vue                 [MODIFIED] idem + bouton "Recalculer contre snapshot"
└── tests/
    ├── unit/
    │   ├── components/
    │   │   ├── MoneyDisplay.spec.ts              [NEW] rendu, modes, dark mode
    │   │   └── ReferentialBadge.spec.ts          [NEW] click → modale
    │   ├── composables/
    │   │   └── useCurrency.spec.ts               [NEW] format, convert
    │   └── stores/
    │       └── ui.spec.ts                        [MODIFIED] +displayCurrencyMode
    └── e2e/
        └── F04-versioning-money-devises.spec.ts  [NEW] scénarios E2E (4 scénarios)
```

**Structure Decision** : monolithe modulaire (`backend/` + `frontend/`), conforme principle VII et stack obligatoire. Nouveaux sous-modules backend `app.modules.currency` et `app.modules.versioning` ; sous-fichiers `snapshot.py` + `recompute.py` ajoutés au module `app.modules.applications` existant. Frontend réutilise les conventions (composants UI, composables, store Pinia, types TS).

## Phase 0 — Outline & Research

**Décisions techniques** consolidées dans `research.md` (créé en Phase 0) :

1. **Représentation BDD du type Money** : 2 colonnes par champ (`<field>_amount: NUMERIC(20,2)`, `<field>_currency: CHAR(3)`) — préférence à un type composé PostgreSQL pour conserver la portabilité SQLite (tests in-memory) et éviter la complexité d'un type personnalisé.
2. **JSONB pour snapshot** : type `JSONB` natif PostgreSQL avec variant `JSON` pour SQLite (cf. `JSONType` déjà utilisé par F01 dans `app/models/source.py`).
3. **Trigger anti-cycle PostgreSQL** : fonction PL/pgSQL `prevent_supersede_cycle()` + trigger BEFORE INSERT/UPDATE par table catalogue. Sur SQLite (tests), trigger non créé (fallback applicatif via service `versioning.supersede()` qui vérifie la chaîne).
4. **Cap fetch quotidien** : vérification applicative via `SELECT MAX(fetched_at) FROM exchange_rates WHERE base_currency=? AND quote_currency=?` ; si < 24h, skip silencieux.
5. **API exchangerate-api.com** : endpoint `https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD` retourne dict de paires USD→XYZ. Parsing : USD→{XOF, EUR, GBP, JPY}, puis dérivation des paires inverses (XOF→USD = 1/USD→XOF).
6. **Pivot USD pour conversion non-peggée** : algorithme déterministe `convert(EUR, JPY) = convert(USD, JPY) * convert(EUR, USD)`. Si l'un des deux est manquant → exception métier explicite.
7. **Validation Pydantic v2 strict pour Money** : utilisation de `field_validator` + `Decimal` strict (pas de coercion str/float). Sérialisation JSON via `model_dump(mode='json')` qui produit `{"amount": "655.957", "currency": "XOF"}`.
8. **Stratégie migration en 2 phases** : phase 1 (F04) = ajout colonnes `<field>_amount` + `<field>_currency` + backfill ; ancien `*_xof` conservé. Phase 2 (hors-scope F04) = drop `*_xof` après refactor exhaustif. Cohabitation par accesseurs Python (property `Fund.min_amount_money` qui priorise `min_amount` puis fallback sur `min_amount_xof`).
9. **Bump version semver-like** : format `MAJOR.MINOR` (regex `^\d+\.\d+$`). Bump minor par défaut, bump major via flag explicite. Service `versioning.bump_version(current, force_major=False)` — split sur `.`, increment l'élément ciblé.
10. **Format snapshot_data** : structure standardisée
    ```json
    {
      "schema_version": "1.0",
      "captured_at": "2026-05-06T...",
      "referential": {"id": "...", "version": "1.2", "valid_from": "2026-01-01", "indicators": [...]},
      "fund": {...},
      "intermediary": {...} | null,
      "offer": {...} | null,
      "scores": {...},
      "documents_requis": [...],
      "source_ids_cited": [...]
    }
    ```
11. **Persistance Pydantic Money en BDD via SQLAlchemy** : pas de TypeDecorator personnalisé pour le MVP. Les modèles SQLAlchemy exposent les deux colonnes `_amount` + `_currency` ; les schemas Pydantic API exposent un objet `Money` reconstruit à la sérialisation. Helper `Money.from_columns(amount, currency)` côté schema.
12. **Compatibilité SQLite (tests)** : `Numeric(20,2)` supporté natif. CHAR(3) supporté. Trigger PL/pgSQL non créé sur SQLite (skip dans la migration, vérification cycle applicative dans tests).

**Output** : `research.md` (créé ci-dessous).

## Phase 1 — Design & Contracts

**Prérequis** : `research.md` complet (généré en Phase 0).

### 1. Data Model

Créer `data-model.md` avec :
- Détail complet de la table `exchange_rates` (DDL, contraintes, index)
- Liste exhaustive des 13 tables catalogue avec les 4 colonnes versioning ajoutées
- Détail de `fund_applications.snapshot_at` + `snapshot_data` (avec exemple JSON)
- Liste des paires `<field>_amount` + `<field>_currency` ajoutées aux 5 tables financières
- Schéma JSON du `snapshot_data`
- Diagramme de relations (versioning + snapshot)

### 2. Contracts (OpenAPI snippets)

Créer `contracts/currency_api.yaml` pour :
- `GET /api/currency/rates/latest` → `RatesLatestResponse[]`
- `POST /api/currency/convert` (body: ConvertRequest) → `ConvertResponse`

Créer `contracts/application_recompute.yaml` pour :
- `POST /api/applications/{id}/recompute-against-snapshot` (auth user) → `RecomputeResponse`

Créer `contracts/currency_status.yaml` pour :
- `GET /api/admin/currency/fetch-status` (auth admin) → `FetchStatusResponse`

### 3. Quickstart

Créer `quickstart.md` avec :
- Commandes activation venv + alembic upgrade head
- Seed minimal `exchange_rates` (4 paires de référence)
- Exemples d'appel API : convert FCFA→EUR (peg), USD→XOF (table)
- Exemple de création de candidature, soumission, recompute
- Lancement frontend + démo `<MoneyDisplay>`

### 4. Agent context update

Exécuter `.specify/scripts/bash/update-agent-context.sh claude` après écriture des artefacts pour ajouter les technologies pertinentes au CLAUDE.md (peg FCFA-EUR, table exchange_rates, type Money, snapshot JSONB).

### 5. Re-evaluation Constitution Check

À refaire après écriture des artefacts Phase 1 — aucun écart attendu.

## Implementation Strategy (synthèse pour Phase B)

### Ordre des tâches (TDD strict)

#### Bloc A — Fondations (sans dépendance externe)

1. Tests `app.core.money` → implémentation Money + Currency Literal
2. Tests `app.core.constants` (FCFA_EUR_PEG) → implémentation
3. Tests modèle `ExchangeRate` (SQLAlchemy) → implémentation
4. Tests service versioning (`bump_version`, `supersede`) → implémentation

#### Bloc B — Migration BDD

5. Test migration 022 (up/down/up) → écriture migration Alembic
6. Tests modèles modifiés (versioning columns sur 13 tables, paires Money sur 5 tables, snapshot sur fund_applications) → édition modèles SQLAlchemy

#### Bloc C — Currency module

7. Tests `currency_service.convert` (peg, table, fallback, pivot USD) → implémentation
8. Tests `currency_router` + `admin_router` → implémentation routers
9. Tests `fetch_exchange_rates.py` (cap 1/jour, mock httpx) → implémentation script

#### Bloc D — Snapshot + Recompute

10. Tests `snapshot.build_snapshot_data` → implémentation
11. Tests `applications.service.create_snapshot` (transition submitted_*) → modification service
12. Tests `recompute_against_snapshot` → implémentation
13. Tests endpoint `POST /api/applications/{id}/recompute-against-snapshot` → implémentation router

#### Bloc E — Tools LangChain

14. Tests `simulate_financing` (Money typés, plus d'AttributeError) → fix tool

#### Bloc F — Frontend

15. Tests Vitest `<MoneyDisplay>`, `<ReferentialBadge>`, `useCurrency`, store ui (`displayCurrencyMode`) → implémentation
16. Migration des composants existants (`ScoreCard`, `FinancingCard`, pages /financing, /dashboard, /action-plan, /applications/[id]) → édition

#### Bloc G — E2E Playwright

17. Tests E2E `F04-versioning-money-devises.spec.ts` (4 scénarios)

### Dépendances backend à ajouter

`backend/requirements.txt` : ajouter `httpx>=0.27.0` si pas déjà présent (utilisé pour exchangerate-api.com).

### Variables d'environnement

`backend/app/core/config.py` (ZONE INTERDITE — un seul écrivain) :
- `EXCHANGERATE_API_KEY: str = ""` (vide = mode dégradé / dev)
- `EXCHANGERATE_API_BASE_URL: str = "https://v6.exchangerate-api.com/v6"`
- `CURRENCY_FETCH_DAILY_QUOTA: int = 50`

### Migration Alembic 022

**Down revision** : `021_create_audit_log` SI F03 mergé avant F04, sinon `020_sources`. Ce paramètre sera fixé au moment de l'implémentation Phase B en lisant `alembic heads` sur `main`.

**Tables affectées** :
- CREATE TABLE `exchange_rates`
- ALTER TABLE pour les 13 tables catalogue (ajout 4 colonnes versioning)
- ALTER TABLE pour les 5 tables financières (ajout 2 colonnes Money par champ)
- ALTER TABLE `fund_applications` (ajout `snapshot_at`, `snapshot_data`)
- CREATE FUNCTION + CREATE TRIGGER `prevent_supersede_cycle` x 13 (PostgreSQL uniquement, skip sur SQLite)
- Backfill SQL `<field>_amount = <field>_xof / <field>_fcfa` et `<field>_currency = 'XOF'`
- Seed initial `exchange_rates` (4 paires de référence)

**Down** : drop des colonnes versioning, drop des paires Money (PAS drop des `*_xof`/`*_fcfa` qui restent), drop snapshot fields, drop table `exchange_rates`, drop functions/triggers anti-cycle.

### Frontend — store ui étendu

`frontend/app/stores/ui.ts` : ajouter
- `displayCurrencyMode: 'native' | 'pme' | 'both'` (défaut `'both'`)
- Persistance localStorage clé `mefali.ui.displayCurrencyMode`
- Setter avec validation enum

### Frontend — composable useCurrency

`frontend/app/composables/useCurrency.ts` :
- `format(money: Money): string` (ex `1 000 000 FCFA`)
- `convert(money: Money, target: Currency): Promise<Money>` → POST /api/currency/convert
- `getRate(base: Currency, quote: Currency): Promise<number>` → GET /api/currency/rates/latest
- `getPmeCurrency(): Currency` → constante `'XOF'` pour le MVP (cf. clarif Q2)

## Risques techniques & mitigations (Phase B)

| Risque | Mitigation |
|---|---|
| Migration Alembic plante sur backfill (NULL dans `*_xof`) | `COALESCE(<field>_xof, 0)` lors du backfill, log des lignes affectées. |
| Test SQLite ne supporte pas trigger PL/pgSQL | Skip création trigger sur SQLite (`if op.get_bind().dialect.name == 'postgresql'`), fallback applicatif vérifie cycle dans `versioning.supersede()`. |
| Conflit avec migration F03 (`021_create_audit_log`) | Fixer `down_revision` au moment de l'implémentation B en lisant `alembic heads`. |
| Snapshot trop volumineux (> 100 KB) | Log warning, métrique d'observabilité ; gzip post-MVP. |
| Tests Vitest happy-dom ne support pas `Intl.NumberFormat` | Vérifier en B ; utiliser polyfill ou format manuel si besoin. |
| Tool `simulate_financing` cassé (AttributeError actuelle) | Fix immédiat dans Bloc E ; ajout test de régression dans `test_applications/test_simulation.py`. |
| Cron exchangerate-api refusé en CI | Mock systématique en CI ; script appelable hors CI seulement. |

## Complexity Tracking

> Aucune violation constitutionnelle à justifier — la feature respecte les principes I à VII.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (aucune) | — | — |
