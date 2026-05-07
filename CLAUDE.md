# ESG Mefali - Conseiller ESG IA

Plateforme conversationnelle IA qui democratise l'acces a la finance durable pour les PME africaines francophones. Combine analyse de conformite ESG, conseil en financement vert et scoring de credit alternatif.

## Stack Technologique

### Frontend (Nuxt 4)
- **Framework** : Nuxt 4 + Vue Composition API
- **State** : Pinia
- **UI** : TailwindCSS + GSAP (animations)
- **Editeur** : toast-ui/editor
- **Graphiques** : Chart.js
- **IA Client** : LangGraph + LangChain (couche utilitaire)

### Backend (FastAPI)
- **Framework** : FastAPI (Python)
- **LLM** : Claude API (Anthropic) via OpenRouter
- **BDD** : PostgreSQL + pgvector (embeddings)
- **Stockage** : Local (MinIO/S3 plus tard)
- **Queue** : Synchrone (Redis + Celery plus tard)

## Architecture Modulaire

Le projet est organise en 8 modules :

1. **Agent Conversationnel** — Chat multimodal FR, profilage entreprise, memoire contextuelle
2. **Analyseur Conformite ESG** — Upload/OCR documents, grille E-S-G contextualisee Afrique, scoring dynamique /100, rapport PDF
3. **Conseiller Financement Vert** — BDD fonds (GCF, FEM, BOAD, BAD...), matching projet-financement, generateur de dossiers
4. **Calculateur Empreinte Carbone** — Questionnaire adapte contexte africain, calcul tCO2e, plan de reduction
5. **Scoring Credit Vert Alternatif** — Donnees non-conventionnelles (Mobile Money, photos IA), score hybride solvabilite+impact
6. **Plan d'Action** — Feuille de route 6-12-24 mois, rappels cron, bibliotheque ressources
7. **Tableau de Bord** — Dashboard scores, rapports exports, multi-utilisateurs (admin/collaborateur/lecteur)
8. **Extension Chrome** — Detection fonds, pre-remplissage formulaires, panneau guidage, suivi candidatures

## Conventions de Developpement

### Langue
- Code : anglais (variables, fonctions, classes)
- Commentaires : francais
- UI/UX : francais (interface utilisateur)
- Documentation : francais

### Frontend (Nuxt 4)
- Composition API avec `<script setup lang="ts">`
- Composables dans `composables/`
- Pages dans `pages/` avec routing automatique Nuxt
- Composants dans `components/` avec nommage PascalCase (sans prefixe de dossier, `pathPrefix: false`)
- Stores Pinia dans `stores/`
- Structure Nuxt 4 : tous les fichiers source dans `app/` (pages, components, composables, layouts, stores, etc.)

### Dark Mode (OBLIGATOIRE)
Chaque nouveau composant, page ou layout DOIT etre compatible dark mode :
- Utiliser les variantes `dark:` de Tailwind sur tous les elements visuels
- Fonds : `bg-white dark:bg-dark-card`, `bg-surface-bg dark:bg-surface-dark-bg`
- Textes : `text-surface-text dark:text-surface-dark-text`, `text-gray-600 dark:text-gray-400`
- Bordures : `border-gray-200 dark:border-dark-border`
- Inputs : `dark:bg-dark-input dark:text-surface-dark-text`
- Hover : `hover:bg-gray-50 dark:hover:bg-dark-hover`
- Le theme est gere par `stores/ui.ts` (classe `dark` sur `<html>`, persiste dans localStorage)
- Les variables de couleurs dark sont definies dans `app/assets/css/main.css` via `@theme`
- Ne jamais hardcoder des couleurs claires sans leur equivalente dark

### Reutilisabilite des Composants (OBLIGATOIRE)
- Avant de creer un nouveau composant, verifier si un composant existant peut etre reutilise ou etendu via des props
- Extraire les patterns visuels repetes (cartes, formulaires, boutons, inputs) en composants generiques dans `components/ui/`
- Les composants UI de base (boutons, inputs, badges, modals) doivent etre parametrables via props et slots, pas dupliques
- Privilegier la composition (slots, props, emit) plutot que la duplication de code
- Si un meme pattern apparait plus de 2 fois, l'extraire en composant reutilisable

### Backend (FastAPI)
- Routers dans `routers/`
- Services/logique metier dans `services/`
- Modeles SQLAlchemy dans `models/`
- Schemas Pydantic dans `schemas/`
- snake_case pour les fonctions et variables Python

### Base de Donnees
- Migrations avec Alembic
- Nommage tables : snake_case, pluriel (ex: `companies`, `esg_scores`)
- pgvector pour les embeddings de documents

## Contexte Metier

### Public Cible
- PME africaines francophones (zone UEMOA/CEDEAO)
- Secteurs : agriculture, energie, recyclage, transport, etc.
- Secteur informel pris en compte

### Referentiels ESG
- Taxonomies vertes UEMOA, BCEAO
- Reglementations CEDEAO
- Standards internationaux : Gold Standard, Verra, REDD+

### ODD Cibles
- ODD 8 (Travail decent), ODD 9 (Innovation), ODD 10 (Inclusion financiere)
- ODD 12 (Production responsable), ODD 13 (Climat), ODD 17 (Partenariats)

## Environnement Python

Le backend utilise un environnement virtuel Python (`venv`). Toujours l'activer avant d'executer des commandes Python ou d'installer des packages.

```bash
# Creation (une seule fois)
cd backend && python3 -m venv venv

# Activation (a chaque session)
source backend/venv/bin/activate

# Installation des dependances
pip install -r backend/requirements.txt
```

**Important** : Ne jamais installer de packages Python globalement. Toujours verifier que le venv est actif (`which python` doit pointer vers `backend/venv/bin/python`).

## Commandes Utiles

```bash
# Frontend
cd frontend && npm run dev

# Backend (toujours activer le venv d'abord)
source venv/bin/activate
uvicorn app.main:app --reload

# Base de donnees
alembic upgrade head
```

## Conventions

- **Français avec accents** (é, è, ê, à, ç, ù) obligatoires dans le les contenus

## Active Technologies
- Python 3.12, TypeScript 5.x (strict mode) (001-technical-foundation)
- PostgreSQL 16 + pgvector (001-technical-foundation)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) (002-chat-rich-visuals)
- PostgreSQL 16 + pgvector (async via asyncpg) (002-chat-rich-visuals)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph, LangChain, SQLAlchemy (async), Nuxt 4, Vue Composition API, Pinia, TailwindCSS (003-company-profiling-memory)
- PostgreSQL 16 + pgvector (async via asyncpg), Alembic pour migrations (003-company-profiling-memory)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph, LangChain, SQLAlchemy (async), PyMuPDF, pytesseract, pdf2image, docx2txt, openpyxl, Nuxt 4, Vue Composition API, Pinia, TailwindCSS (004-document-upload-analysis)
- PostgreSQL 16 + pgvector (embeddings), stockage fichiers local (/uploads/) (004-document-upload-analysis)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph, LangChain, SQLAlchemy async, PyMuPDF, Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Chart.js, vue-chartjs (005-esg-scoring-assessment)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, WeasyPrint, matplotlib, Jinja2, LangChain (resume IA), SQLAlchemy async, Nuxt 4, Vue Composition API, Pinia, TailwindCSS (006-esg-pdf-reports)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, LangGraph, LangChain, Claude API via OpenRouter (backend) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Chart.js, vue-chartjs (frontend) (007-carbon-footprint-calculator)
- PostgreSQL 16 + pgvector, Alembic pour migrations (007-carbon-footprint-calculator)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, LangGraph, LangChain, WeasyPrint, Jinja2 (backend) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Chart.js, vue-chartjs (frontend) (008-green-financing-matching)
- PostgreSQL 16 + pgvector (embeddings), Alembic pour migrations (008-green-financing-matching)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, LangGraph, LangChain, WeasyPrint, Jinja2, python-docx (backend) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, toast-ui/editor, Chart.js (frontend) (009-fund-application-generator)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, LangGraph, LangChain, WeasyPrint (backend) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Chart.js, vue-chartjs (frontend) (011-dashboard-action-plan)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangChain (>=0.3.0), LangGraph (>=0.2.0), langchain-openai (>=0.3.0), SQLAlchemy async (012-langgraph-tool-calling)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph (>=0.2.0), LangChain (>=0.3.0), langchain-openai (>=0.3.0), SQLAlchemy async, Nuxt 4, Vue Composition API (013-fix-multiturn-routing-timeline)
- PostgreSQL 16 + pgvector, MemorySaver (LangGraph checkpointer) (013-fix-multiturn-routing-timeline)
- Python 3.12 + FastAPI, LangGraph, LangChain, langchain-openai (014-concise-chat-style)
- N/A (pas de changement BDD) (014-concise-chat-style)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph (>=0.2.0), LangChain (>=0.3.0), langchain-openai, SQLAlchemy async (015-fix-toolcall-esg-timeout)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph (>=0.2.0), LangChain (>=0.3.0), langchain-openai, SQLAlchemy async, Nuxt 4, Vue Composition API (016-fix-tool-persistence-bugs)
- Python 3.12 + FastAPI, pytest, pytest-asyncio, LangChain, LangGraph (017-fix-failing-tests)
- PostgreSQL + pgvector (SQLite in-memory pour tests) (017-fix-failing-tests)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, LangGraph, LangChain, SQLAlchemy async, Pydantic v2 ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS (018-interactive-chat-widgets)
- PostgreSQL 16 (JSONB), Alembic, table satellite `interactive_questions` (aucune modification des tables existantes) (018-interactive-chat-widgets)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, Alembic ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Playwright (019-multitenant-roles-rls)
- PostgreSQL 16 + pgvector, Alembic migration 019, Row-Level Security (ENABLE+FORCE) sur 14 tables metier, tables `accounts`/`refresh_tokens`/`account_invitations`, colonnes `account_id` UUID NOT NULL FK + 2 policies (`pme_access_own_account`, `admin_full_access`) (019-multitenant-roles-rls)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, LangGraph, LangChain, langchain-openai (embeddings) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS (020-fondations-sourcage-catalogue / F01)
- PostgreSQL 16 + pgvector, Alembic migration 020 (11 nouvelles tables : `sources`, `indicators`, `criteria`, `formulas`, `thresholds`, `referentials`, `referential_indicators`, `emission_factors`, `required_documents`, `simulation_factors`, `unsourced_flags`), workflow 4-yeux (CHECK contraint captured_by != verified_by), RLS PostgreSQL en lecture publique sur entites verified/published (020-fondations-sourcage-catalogue / F01)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async (event listeners before_flush), Alembic, Pydantic v2 ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS (021-audit-log / F03)
- PostgreSQL 16 + pgvector, table `audit_log` strictement append-only (triggers PL/pgSQL BEFORE UPDATE/DELETE qui RAISE EXCEPTION + REVOKE UPDATE,DELETE best-effort), 4 indexes ciblés, 2 ENUMs (`audit_action`, `audit_source`), RLS héritée F02 avec 4 policies (pme_access_own_account, pme_insert_own_account, admin_full_access, admin_insert_anywhere) (021-audit-log / F03)
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async, Alembic, Pydantic v2 strict (Money type) ; httpx (exchangerate-api.com) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS (022-versioning-money-devises / F04)
- PostgreSQL 16 + pgvector, table `exchange_rates` (référentiel public global, sans account_id, avec UNIQUE (base, quote, as_of) + CHECK enum currencies), 4 colonnes versioning (`version`, `valid_from`, `valid_to`, `superseded_by`) ajoutées sur 12 tables catalogue + `catalog_version` sur sources (qui possède déjà un champ version métier), trigger PL/pgSQL `prevent_supersede_cycle` avec 13 triggers BEFORE INSERT/UPDATE (skip SQLite), snapshot immuable (`snapshot_at`, `snapshot_data` JSONB) sur fund_applications, paires Money typées (`<field>_amount` Numeric(20,2) + `<field>_currency` Char(3)) sur funds (min/max), company_profiles (annual_revenue), action_items (estimated_cost), backfill XOF idempotent (anciennes colonnes `*_xof` conservées en phase 1), 8 entrées seed `exchange_rates` (USD↔{XOF,EUR,GBP,JPY} + inverses), constante `FCFA_EUR_PEG = Decimal("655.957")` (Banque de France/BCEAO) (022-versioning-money-devises / F04)
- Python 3.12 (backend) ; TypeScript 5.x strict (frontend) (memoire-contextuelle-pgvector / F12 — phase A specs only)
- PostgreSQL 16 + extension pgvector. Nouvelle table `message_chunks` ; tables `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` créées par `AsyncPostgresSaver.setup()` (cf. README LangGraph). RLS PostgreSQL active (helper F02 `set_rls_context`). (memoire-contextuelle-pgvector / F12 — phase A specs only)

## Recent Changes
- 022-versioning-money-devises (F04): Money typed strict (Pydantic v2 frozen, Currency Literal XOF/EUR/USD/GBP/JPY, amount Decimal(20,2) ge=0, factory `Money.from_columns`) + peg fixe FCFA-EUR `Decimal("655.957")` (`FCFA_EUR_PEG`) + service currency conversion (peg sans HTTP/BDD, table `exchange_rates` avec fallback ascendant, pivot USD systématique pour devises non-peggées avec exception `ConversionPathUnavailableError` explicite). Versioning catalogue : champs `version` (regex `^\d+\.\d+$`), `valid_from`, `valid_to`, `superseded_by` (FK self) sur 12 tables catalogue + `catalog_version` dédié sur sources, mixin SQLAlchemy `VersioningMixin` / `SourceVersioningMixin`, service `bump_version(current, force_major=False)` (1.0 → 1.1 ou 1.0 → 2.0), `supersede(session, model_cls, old_id, new_id)` avec vérification anti-cycle applicative, trigger PL/pgSQL `prevent_supersede_cycle()` PostgreSQL en défense en profondeur (skip SQLite). Snapshot immuable JSONB `snapshot_data` autoportant créé automatiquement à la transition `submitted_to_intermediary` ou `submitted_to_fund` dans `update_application_status` (capture referential/fund/intermediary/scores/source_ids), service `build_snapshot_data` + garde anti-mutation `validate_immutable`, log structuré INFO avec taille bytes pour observabilité, warning si > 100 KB (gzip post-MVP). Endpoint `POST /api/applications/{id}/recompute-against-snapshot` (auth user, vérifie account_id) → recompute depuis snapshot, retourne `{score, comparison_with_origin: {match, delta}, referential_version_used}`, 409 si non soumis. Module `app/modules/currency/` complet (service, exceptions `NoRateAvailableError`/`ConversionPathUnavailableError`/`FetchFailedError`, schemas Pydantic, router public `/api/currency/rates/latest` + `/api/currency/convert`, admin_router `/api/admin/currency/fetch-status`). Script CLI `app/scripts/fetch_exchange_rates.py` exécutable via `python -m app.scripts.fetch_exchange_rates [--force]` avec cap dur 1/jour (vérification `MAX(fetched_at) < 24h`), mode dégradé si `EXCHANGERATE_API_KEY` vide, log structuré ERROR `EXCHANGERATE_FETCH_FAILED` (jamais swallowed), insère USD→{XOF,EUR,GBP,JPY} + dérivation paires inverses 1/rate. Tool LangChain `simulate_financing` corrigé : `_simulate_financing` utilise désormais `fund.min_amount_money` / `fund.max_amount_money` properties (fallback sur `*_xof` legacy si Money typé None) → plus d'AttributeError sur `fund.max_amount`. Frontend : type TypeScript `Money` (amount string + currency Literal), `Currency`, `ExchangeRate`, `ConvertResponse`, composable `useCurrency` (`format`, `convert` via API backend, `getRate`, `getPmeCurrency`=XOF), composants Vue `<MoneyDisplay>` (props money, showPmeCurrency, modeOverride ; lit `displayCurrencyMode` du store ui ; rend natif + équivalent FCFA en mode `both` ; omet équivalent si devise = devise PME ; tooltip `title` ; classes `dark:`) et `<ReferentialBadge>` (libellé « Évalué selon Référentiel <name> v<version> du <date FR> » cliquable → emit `open-source-modal`, dark mode, ARIA aria-label). Store Pinia `ui` étendu : `displayCurrencyMode: 'native' | 'pme' | 'both'` (défaut `both`), persistance `localStorage` clé `mefali.ui.displayCurrencyMode`, validation enum stricte sur le setter. Migration Alembic `022_money_and_versioning` (down_revision='021_audit_log') : CREATE TABLE exchange_rates + 8 lignes seed (USD↔{XOF,EUR,GBP,JPY} + 4 inverses calculées), 12 ALTER TABLE pour colonnes versioning + 1 pour sources (catalog_version), CREATE FUNCTION `prevent_supersede_cycle()` + 13 triggers (PostgreSQL only via `if op.get_bind().dialect.name == 'postgresql'`), 4 ALTER TABLE pour paires Money (funds×2, company_profiles, action_items) avec CHECK currency enum + CHECK pair, ALTER TABLE fund_applications ajoute snapshot_at + snapshot_data JSONB, backfill SQL idempotent `<field>_amount = <field>_xof, <field>_currency = 'XOF'`. `ExchangeRate` ajouté à `EXEMPT_MODELS` (catalogue F03 audit log, lecture publique sans account_id). Cohabitation phase 1 : anciennes colonnes `*_xof` / `*_fcfa` conservées (drop reporté à migration séparée hors-scope F04). 71 nouveaux tests backend (test_core/test_money 10 cas, test_core/test_constants 3 cas, test_models/test_exchange_rate 4 cas, test_versioning/test_supersede 13 cas + test_supersede_integration 2 cas, test_currency/test_service 11 cas + test_router 6 cas + test_admin_router 2 cas + test_fetch_script 4 cas, test_applications/test_snapshot_creation 5 cas + test_snapshot_immutable 4 cas + test_recompute_against_snapshot 4 cas, test_tools/test_simulate_financing_money 3 cas) + 23 tests frontend Vitest (MoneyDisplay 6 cas, ReferentialBadge 5 cas, useCurrency 6 cas, ui.f04 6 cas) + 4 scénarios Playwright `frontend/tests/e2e/F04-versioning-money-devises.spec.ts`. Couverture 92 % sur les nouveaux modules F04 (app.core.money, app.modules.currency, app.modules.versioning, app.modules.applications.snapshot, app.modules.applications.recompute, app.models.exchange_rate). 1523 tests backend verts (1452 baseline + 71 F04), 0 régression. 438 tests frontend verts (3 préexistants en échec hors F04). Round-trip Alembic `up/down/up` validé sur PostgreSQL.
- 021-audit-log (F03): Module audit log append-only complet. Table `audit_log` avec triggers PostgreSQL BEFORE UPDATE/DELETE qui RAISE EXCEPTION (`raise_audit_log_no_update` / `raise_audit_log_no_delete`) + REVOKE UPDATE,DELETE best-effort sur le rôle applicatif (no-op si superuser, NOTICE émis). Mixin SQLAlchemy `Auditable` couplé à un listener global `event.listens_for(Session, 'before_flush')` qui parcourt session.new/dirty/deleted, calcule un diff field-level via `inspect(obj).attrs[field].history`, borne chaque valeur à 10 KB (marqueur `_truncated: true`), et insère N lignes audit_log dans la même transaction (atomicité ACID). Anti-récursion : insertions de AuditLog ignorées. Constantes `AUDITABLE_MODELS` (CompanyProfile, FundApplication, ESGAssessment, CarbonAssessment, CreditScore, ActionPlan, ActionItem) + `EXEMPT_MODELS` documenté (catalogue F01, infra, AuditLog, CarbonEmissionEntry/CreditDataPoint pas d'account_id propre, ESGCriterionScore vit dans assessment_data JSON). ContextVar Python `current_source_of_change` (default 'manual') + helper `source_of_change_scope(value)` (context manager Token-safe). 9 nœuds LangGraph décorés `@_with_llm_source` (chat, esg_scoring, carbon, financing, application, credit, action_plan, document, profiling) → toute mutation via tool LangChain est tracée `source_of_change=llm`. Middleware `AdminAuditContextMiddleware` monté sur `/api/admin/*` → `source_of_change=admin` automatique. Service `AuditService.record_admin_view(admin, target_account_id, request)` idempotent par requête (cache `request.state.audit_view_recorded`), insère ligne `view_admin` côté PME pour transparence. 4 endpoints API : `GET /api/audit/me` (PME, filtres entity_type/entity_id/action/source_of_change/since/until/page/limit/order), `GET /api/audit/me/export` (CSV UTF-8 BOM ou JSON streaming via StreamingResponse), `GET /api/admin/audit/{account_id}` (admin, déclenche view_admin), `GET /api/admin/audit` (admin global). Frontend : page `/historique` (PME, layout default, timeline + filtres + pagination + export), pages `/admin/audit` et `/admin/audit/[accountId]` (layout admin F02, accent rouge), 4 composants Vue (`AuditLogEntry`, `AuditTimeline`, `AuditFilters`, `AuditExportButton`) avec dark mode complet et libellés français (Création/Modification/Suppression/Consultation Admin), composable `useAuditLog.ts` (fetchMe/fetchByAccount/fetchGlobal/exportCsv/exportJson), store Pinia `audit.ts`, types TypeScript `AuditEvent`/`AuditAction`/`AuditSourceOfChange`/`AuditFilters`. Migration Alembic `021_create_audit_log` (down_revision='020_sources') avec ENUMs PG, table, 4 indexes, 2 fonctions PL/pgSQL, 2 triggers, REVOKE best-effort, RLS ENABLE+FORCE + 4 policies. Tests : 76 tests backend (unit context/truncate/csv_writer/mixin/models, intégration endpoints/source_of_change/admin_view/whitelist, postgres triggers/RLS/migration) + 16 tests frontend Vitest (AuditLogEntry/AuditFilters/useAuditLog) + 4 scénarios Playwright `frontend/tests/e2e/F03-audit-log.spec.ts`. Couverture >= 85 % sur le périmètre F03. Documentation `docs/audit-log.md` (modèle de menaces, schéma, requêtes SQL communes, format export, limites MVP RGPD/Merkle/PDF signé/partitionnement/rôle PG séparé, procédure pour rendre auditable un nouveau modèle). Zéro régression sur les 1376 tests baseline.
- 020-fondations-sourcage-catalogue (F01): Catalogue de sources verifiees + sourcage obligatoire de chaque chiffre. 11 nouvelles tables (sources, indicators, criteria, formulas, thresholds, referentials, referential_indicators, emission_factors, required_documents, simulation_factors, unsourced_flags) avec workflow 4-yeux strict (captured_by != verified_by, CHECK constraint applicatif + base) et statuts (draft/pending/verified/outdated). Migration Alembic `020_create_sources_catalog` avec RLS PostgreSQL active (lecture publique des entites verified/published, ecriture admin only via current_setting('app.current_role')). 30+ sources verified seedees automatiquement (ADEME Base Carbone v23, IPCC AR6 WG3, IEA Africa Energy Outlook 2024, Taxonomie verte UEMOA, Circulaire BCEAO 002-2024, GCF Investment Framework, IFC Performance Standards, BOAD Politique Sectorielle ESS, Gold Standard, Verra VCS, ODD ONU 8/9/10/12/13/17, GRI 2021, ISO 14064-1, etc.). Migration des donnees codees en dur (EMISSION_FACTORS, ESGCriterion, SECTOR_WEIGHTS, simulation_factors) vers les tables BDD avec FK source_id obligatoire. 3 tools LangChain `cite_source` / `search_source` / `flag_unsourced` injectes en GLOBAL_WHITELIST des 7 noeuds metiers (chat, esg_scoring, carbon, financing, application, credit, action_plan), borne MAX_TOOLS_PER_TURN portee de 10 a 13. Validator `source_required.py` post-tour LLM detecte les grappes chiffre+unite via regex compilee, ignore les motifs ISO 14001/AR6/COP/ODD/etc., demande retry max 1 puis substitue par fallback texte « [je ne dispose pas d'une source verifiee pour ce chiffre] ». Service `SourceService` avec 7 routes REST `/api/sources` (list/get/create/request-verification/verify/mark-outdated/patch) protegees par `get_current_admin` (sauf list/get qui filtrent verified pour PME). Frontend : 4 composants Vue `SourceLink`, `SourceModal` (Teleport+focus piege), `SourceBadge` (4 statuts colores draft/pending/verified/outdated), `SourcesList` (etat vide/chargement) avec dark mode complet et ARIA roles ; composable `useSources` (cache 5 min) + store Pinia `sources` ; page publique `/sources` filtrable par publisher avec pagination 20/page. Annexe « Sources et references » auto-generee dans le rapport ESG PDF (collecte des cite_source via tool_call_logs, numerotation [n], URL cliquable, libelle « Aucune source mobilisee » si vide). Integrations `<SourceLink>` dans ScoreCard, FinancingCard, esg/Recommendations, esg/StrengthsBadges, esg/CriteriaProgress, credit/Recommendations, pages /carbon/results, /financing/[id], /applications/[id]. Tests : 70 tests backend (modeles, schemas, service, router, tools, validator, seed, migration_helpers) + 24 tests frontend (Vitest sur composants/store) + golden_set_50.json (50 cas annotes pour le validator) + spec E2E Playwright. 1373 tests backend verts (zero regression sur baseline F02). Couverture sources >= 83 %.
- 019-multitenant-roles-rls: Multi-tenant + roles + Row-Level Security PostgreSQL. 3 nouveaux modeles (`Account`, `RefreshToken`, `AccountInvitation`) + extension `User` (role PME/ADMIN, account_id) + colonne `account_id` ajoutee a 14 tables metier (companies, conversations, messages, documents, esg_assessments, carbon_assessments, fund_matches, fund_applications, credit_scores, action_plans, action_items, reminders, interactive_questions, tool_call_logs, reports). Migration Alembic `019_multitenant_and_roles` complete (CREATE TYPE user_role/invitation_status, 3 CREATE TABLE, ALTER TABLE users + 14 tables metier avec backfill via users, ENABLE+FORCE RLS + 2 policies par table). Helper `set_rls_context(session, account_id, role, user_id)` cable dans `get_current_user` (deps.py) — toute route protegee beneficie automatiquement de l'isolation. Refresh token rotatif (rotation systematique + fenetre de grace 5s + revocation `replaced_by_jti`), endpoint `POST /auth/logout` revoque tous les refresh tokens, JWT 24h. Module account complet (`POST /account/invite`, `GET /account/users`, `DELETE /account/users/:id`) avec `LoggingEmailDelivery` (Protocol injection-ready pour SMTP/SendGrid post-MVP). Whitelist email `admin@esg-mefali.com` supprimee de `financing/router.py` au profit de `Depends(get_current_admin)`. Module admin squelette (`GET /admin/health`) protege via dependance commune. Frontend : composant `RoleBadge.vue` (variante ADMIN rouge / PME emerald, dark mode complet), middleware `admin.ts` (route-scope, redirige PME vers /dashboard), layout `admin.vue` (accent rouge, sidebar Catalogue/Sources/Comptes/Metriques pre-cablees pour F09), pages `/admin/health` et `/account/team` (dark mode + modale confirmation retrait), composable `useAccountTeam.ts` (listTeam/inviteMember/removeMember/revokeInvitation), extension store `auth.ts` (champs `account` + `role`, getter `isAdmin`), pages `login.vue`/`register.vue` adaptees pour `?invite=<token>` (banniere d'invitation + relai du token au backend). Tests E2E Playwright `F02-multitenant-roles-rls.spec.ts` (4 scenarios US1-US4) + helpers `F02-helpers.ts` (mock backend complet). Documentation `docs/auth-and-multitenant.md` (modele de menaces, architecture RLS, rotation refresh, ajout table metier, seed Admin, troubleshooting). Script CLI `app.scripts.seed_admin` pour creation Admin off-server. Couverture tests verte : 1294 backend + tests frontend dedies (RoleBadge, middleware admin, useAccountTeam, store auth).
- 018-interactive-chat-widgets: Widgets interactifs pour les questions de l'assistant IA. Nouveau tool LangChain `ask_interactive_question` (4 variantes qcu/qcm/qcu_justification/qcm_justification) injecte dans les 7 noeuds LangGraph (chat, esg_scoring, carbon, financing, application, credit, action_plan). Table satellite `interactive_questions` + migration Alembic `018_create_interactive_questions.py` (aucune modification des tables existantes). Transport via marker `<!--SSE:{"__sse_interactive_question__":true,...}-->` detecte par `stream_graph_events`. 2 nouveaux events SSE (`interactive_question`, `interactive_question_resolved`) + extension `POST /api/chat/messages` (3 champs `interactive_question_*`) + 2 nouveaux endpoints REST (`POST /api/chat/interactive-questions/{id}/abandon`, `GET /api/chat/conversations/{id}/interactive-questions`). Helper `WIDGET_INSTRUCTION` partage injecte dans les 6 prompts modules (esg_scoring, carbon, financing, application, credit, action_plan) + chat_node. Frontend : 5 composants Vue (`InteractiveQuestionHost`, `SingleChoiceWidget`, `MultipleChoiceWidget`, `JustificationField`, `AnswerElsewhereButton`) avec dark mode complet et ARIA roles (`radiogroup`, `checkbox`, `aria-checked`, `aria-describedby`), types TypeScript `InteractiveQuestion*`, extension `useChat.ts` (`currentInteractiveQuestion`, `interactiveQuestionsByMessage`, `submitInteractiveAnswer`, `onInteractiveQuestionAbandoned`), integration dans `ChatMessage.vue` et `pages/chat.vue` avec verrouillage de l'input texte quand une question `pending` existe. Invariant 1 question pending max par conversation (les anciennes sont marquees `expired` avant insertion). Fallback « Repondre autrement » + expiration automatique sur message texte libre (clarification Q4). Justification bornee a 400 caracteres (clarification Q5, defense en profondeur cote serveur). 34 nouveaux tests unitaires + integration, 935 tests backend verts, zero regression.
- 015-fix-toolcall-esg-timeout: Correction 3 anomalies bloquant les tests d'integration (tool calling application/credit + timeout ESG). Nouveau tool create_fund_application dans application_tools.py pour creer des dossiers via le chat. Nouveau tool batch_save_esg_criteria dans esg_tools.py pour sauvegarder N criteres ESG en une seule transaction (evite timeout 30 appels sequentiels). Prompts application.py, credit.py et esg_scoring.py renforces avec ROLE actif, section OUTILS DISPONIBLES et REGLE ABSOLUE forcant le tool calling au lieu de reponses textuelles. Timeout LLM explicite request_timeout=60 dans get_llm(). 14 nouveaux tests unitaires prompts/tools, zero regression sur les 856 tests existants.
- 014-concise-chat-style: Style de communication concis pour l'assistant IA. STYLE_INSTRUCTION injectee dans les 6 modules specialises + conditionnelle dans le chat general (post-onboarding seulement).
- 013-fix-multiturn-routing-timeline: Correction routing multi-tour LangGraph (BUG-1) et format timeline (BUG-2). Mecanisme active_module dans ConversationState (2 champs: active_module str|None, active_module_data dict|None) pour maintenir le contexte entre les tours de conversation. Classification binaire LLM continuation/changement dans router_node avec defaut securitaire (rester dans le module en cas d'erreur). Tous les 9 noeuds specialistes gerent le cycle de vie active_module (activation au demarrage, mise a jour progressive, desactivation a la finalisation). Reprise de module apres interruption via detection in_progress en base. Transition directe entre modules sans perte de donnees. Frontend: normalisation TimelineBlock.vue tolerante aux variantes (phases/items/steps → events, aliases period→date, name→title, state→status, details→description, defaut status=todo). Prompts backend standardises sur format canonique events (action_plan.py, carbon.py, financing.py). 34 tests backend + 21 tests frontend, zero regression.
- 012-langgraph-tool-calling: Integration tool calling LangGraph dans les 9 noeuds du graphe (chat, esg_scoring, carbon, financing, application, credit, action_plan, document, profiling). 32 tools LangChain repartis dans graph/tools/ par module metier (profiling_tools, esg_tools, carbon_tools, financing_tools, application_tools, credit_tools, document_tools, action_plan_tools, chat_tools). Pattern ToolNode conditionnel avec boucle max 5 iterations, retry automatique 1x par tool. SSE refactore avec astream_events() pour streaming natif tokens + tool_call_start/end/error. Journalisation complete des tool calls dans table tool_call_logs. Frontend: composable useChat.ts parse les events tool, composant ToolCallIndicator.vue avec indicateur visuel contextuel en francais. Migration evenements profil (profile_update/profile_completion) depuis l'ancien extract_and_update_profile vers le tool update_company_profile avec metadonnees SSE structurees. Dark mode complet, 100+ tests.
- 011-dashboard-action-plan: Dashboard principal agregeant ESG/carbone/credit/financement en 4 cartes synthetiques + carte financements enrichie avec parcours intermediaires, plan d'action personnalise genere par Claude (10-15 actions multi-categories environment/social/governance/financing/carbon/intermediary_contact avec coordonnees intermediaires snapshot), page plan d'action avec timeline verticale chronologique + filtres par categorie + barre progression globale/par-categorie, systeme de rappels types (action_due/assessment_renewal/fund_deadline/intermediary_followup/custom) avec polling 60s et toasts in-app variante intermediaire bleu, gamification 5 badges automatiques (first_carbon/esg_above_50/first_application/first_intermediary_contact/full_journey), action_plan_node LangGraph avec blocs visuels timeline/table/mermaid/gauge/chart, API REST /api/dashboard + /api/action-plan 8 endpoints, pages /dashboard et /action-plan, dark mode complet, 105 tests
- 008-green-financing-matching: Module conseiller financement vert (BDD 12 fonds reels GCF/FEM/BOAD/BAD/SUNREF/FNDE/etc + 14 intermediaires avec coordonnees + ~50 liaisons fund-intermediary, matching projet-financement par scoring multi-criteres secteur/ESG/taille/localisation/documents, parcours d'acces direct vs intermediaire avec etapes LLM, catalogue fonds filtrable type/secteur/montant/acces/statut, annuaire intermediaires filtrable type/pays, workflow interet→choix intermediaire→fiche preparation PDF WeasyPrint, financing_node LangGraph avec RAG pgvector + blocs visuels mermaid/table/progress/timeline, API REST /api/financing 10+ endpoints, pages /financing liste 3 onglets + /financing/[id] detail fonds, embeddings text-embedding-3-small, dark mode complet, gestion etats vides/erreurs)
- 007-carbon-footprint-calculator: Module calculateur empreinte carbone conversationnel (questionnaire guide par categorie energie/transport/dechets/industriel/agriculture, facteurs emission Afrique Ouest, equivalences parlantes FCFA, carbon_node LangGraph avec visualisations inline chart/gauge/table/timeline, API REST /api/carbon 6 endpoints, page /carbon liste bilans + /carbon/results dashboard donut/barres/equivalences/plan reduction/benchmark sectoriel/evolution temporelle, benchmarks 9 secteurs avec fallback, contrainte unicite bilan/annee, reprise bilans interrompus, dark mode, 57 tests)
- 006-esg-pdf-reports: Module generation rapports ESG PDF (WeasyPrint HTML->PDF, graphiques matplotlib SVG, resume executif IA Claude, template 9 sections, conformite UEMOA/BCEAO/ODD, API REST /api/reports, page /reports liste+preview+download, notification chat SSE, dark mode, edge cases generation simultanee)
- 005-esg-scoring-assessment: Module evaluation et scoring ESG complet (30 criteres E-S-G, ponderation sectorielle, scoring dynamique, esg_scoring_node LangGraph, API REST /api/esg, page resultats /esg, RAG documentaire par critere, benchmark sectoriel avec fallback, historique evaluations Chart.js, reprise evaluations interrompues, 71 tests, 80% couverture)
- 004-document-upload-analysis: Module complet upload/analyse documents (PyMuPDF, pytesseract, OCR, embeddings pgvector, chat integration, dark mode, 81% couverture tests)
- 001-technical-foundation: Added Python 3.12, TypeScript 5.x (strict mode)


## Parallel Sub-agents Strategy

Use multiple sub-agents in parallel for efficiency(10 max):
- Search frontend + backend simultaneously
- Explore multiple files/folders at the same time
