# ESG Mefali - Conseiller ESG IA

Plateforme conversationnelle IA qui democratise l'acces a la finance durable pour les PME africaines francophones. Combine analyse de conformite ESG, conseil en financement vert et scoring de credit alternatif.

> Historique exhaustif des features (verbatim) : voir `CLAUDE.md.bak`.

## Stack Technologique

### Frontend (Nuxt 4)
- **Framework** : Nuxt 4 + Vue Composition API (`<script setup lang="ts">`)
- **State** : Pinia
- **UI** : TailwindCSS + GSAP (animations)
- **Editeur** : toast-ui/editor
- **Graphiques** : Chart.js, vue-chartjs ; Leaflet (cartes UEMOA, F11)
- **Tests** : Vitest, Playwright

### Backend (FastAPI)
- **Runtime** : Python 3.12, FastAPI, SQLAlchemy async, Alembic, Pydantic v2 strict
- **LLM** : Claude API via OpenRouter ; LangGraph (>=0.2) + LangChain (>=0.3) + langchain-openai (embeddings text-embedding-3-small)
- **Documents/Rapports** : PyMuPDF, pytesseract, pdf2image, docx2txt, openpyxl, python-docx, WeasyPrint, Jinja2, matplotlib
- **HTTP externe** : httpx (taux de change exchangerate-api.com)
- **Tokens** : tiktoken (cl100k_base) ; semver
- **BDD** : PostgreSQL 16 + pgvector (HNSW cosine), asyncpg ; SQLite in-memory pour tests
- **Checkpointer** : LangGraph `AsyncPostgresSaver` (lifespan FastAPI), MemorySaver fallback
- **Stockage** : Local `/uploads/` (MinIO/S3 plus tard)
- **Queue** : Synchrone (Redis + Celery plus tard)
- **Extension Chrome** : Vite + @crxjs/vite-plugin + Vue 3 + Pinia + Manifest V3

## Architecture Modulaire

8 modules :
1. **Agent Conversationnel** — Chat multimodal FR, profilage entreprise, memoire contextuelle
2. **Analyseur Conformite ESG** — Upload/OCR, grille E-S-G Afrique, scoring /100, rapport PDF
3. **Conseiller Financement Vert** — BDD fonds (GCF/FEM/BOAD/BAD…), matching projet-financement, generateur dossiers
4. **Calculateur Empreinte Carbone** — Questionnaire africain, tCO2e, plan de reduction
5. **Scoring Credit Vert Alternatif** — Mobile Money, photos IA, score hybride solvabilite+impact
6. **Plan d'Action** — Roadmap 6/12/24 mois, rappels, bibliotheque ressources
7. **Tableau de Bord** — Dashboard scores, exports, multi-utilisateurs (admin/collaborateur/lecteur)
8. **Extension Chrome** — Detection fonds, pre-remplissage, panneau guidage, suivi candidatures

## Conventions de Developpement

### Langue
- Code : anglais (variables, fonctions, classes)
- Commentaires, UI/UX, documentation : francais (avec accents é è ê à ç ù **obligatoires** dans les contenus)

### Frontend (Nuxt 4)
- Composition API `<script setup lang="ts">`
- `composables/`, `pages/` (routing auto), `components/` PascalCase (`pathPrefix: false`), `stores/` Pinia
- Structure Nuxt 4 : tout source dans `app/`

### Dark Mode (OBLIGATOIRE)
Tout composant/page/layout DOIT supporter dark mode :
- Fonds : `bg-white dark:bg-dark-card`, `bg-surface-bg dark:bg-surface-dark-bg`
- Textes : `text-surface-text dark:text-surface-dark-text`, `text-gray-600 dark:text-gray-400`
- Bordures : `border-gray-200 dark:border-dark-border`
- Inputs : `dark:bg-dark-input dark:text-surface-dark-text`
- Hover : `hover:bg-gray-50 dark:hover:bg-dark-hover`
- Theme gere par `stores/ui.ts` (classe `dark` sur `<html>`, persiste localStorage). Variables dans `app/assets/css/main.css` via `@theme`. Ne jamais hardcoder une couleur claire sans son equivalent dark.

### Reutilisabilite (OBLIGATOIRE)
- Avant de creer un composant, chercher s'il en existe un reutilisable/extensible via props
- Patterns visuels recurrents (cartes, formulaires, boutons, inputs) → `components/ui/` parametrables (props + slots)
- Si un pattern apparait > 2 fois, l'extraire en composant generique. Privilegier composition aux duplications.

### Backend (FastAPI)
- `routers/`, `services/`, `models/` SQLAlchemy, `schemas/` Pydantic. snake_case Python.

### Base de Donnees
- Migrations Alembic. Tables : snake_case pluriel. pgvector pour embeddings.

## Contexte Metier

- **Public** : PME africaines francophones (UEMOA/CEDEAO), secteur informel inclus. Secteurs : agriculture, energie, recyclage, transport, etc.
- **Referentiels ESG** : Mefali (interne), GCF, IFC PS, BOAD ESS, GRI 2021 ; taxonomie verte UEMOA/BCEAO ; reglementations CEDEAO ; standards Gold Standard, Verra, REDD+.
- **ODD cibles** : 8, 9, 10, 12, 13, 17.

## Environnement Python

```bash
# Une seule fois
cd backend && python3 -m venv venv
# A chaque session
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```
**Important** : jamais de pip global. `which python` → `backend/venv/bin/python`.

## Commandes Utiles

```bash
# Frontend
cd frontend && npm run dev

# Backend (venv actif)
uvicorn app.main:app --reload

# BDD
alembic upgrade head
```

## Parallel Sub-agents Strategy

Multiples sub-agents en parallele (10 max) pour rechercher frontend + backend + plusieurs dossiers simultanement.

---

## Fondations Transverses (a respecter dans toute nouvelle feature)

- **F01 — Sourcage obligatoire** (mig. 020) : table `sources` + 10 catalogues (`indicators`, `criteria`, `formulas`, `thresholds`, `referentials`, `referential_indicators`, `emission_factors`, `required_documents`, `simulation_factors`, `unsourced_flags`). Workflow 4-yeux (CHECK `captured_by != verified_by`), statuts draft/pending/verified/outdated. Tools globaux LangChain `cite_source` / `search_source` / `flag_unsourced`. Validator post-LLM `source_required.py` (retry 1x puis fallback texte). Composants Vue : `SourceLink`, `SourceModal`, `SourceBadge`, `SourcesList`. Annexe « Sources et references » auto-generee dans rapport ESG PDF. ~30 sources verified seedees (ADEME, IPCC AR6, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD, GRI, ISO 14064-1).
- **F02 — Multi-tenant + roles + RLS** (mig. 019) : modeles `Account`, `RefreshToken`, `AccountInvitation` ; `User.role` (PME/ADMIN) + `account_id`. Colonne `account_id UUID NOT NULL` ajoutee a 14 tables metier. `ENABLE+FORCE` RLS + 2 policies (`pme_access_own_account`, `admin_full_access`). Helper `set_rls_context(session, account_id, role, user_id)` cable dans `get_current_user`. Refresh token rotatif + fenetre grace 5s + revocation `replaced_by_jti`. Endpoint `POST /auth/logout` revoque tous tokens. JWT 24h. Module `account` (`POST /account/invite`, `GET /account/users`, `DELETE`). Module `admin` squelette. Layout `admin.vue` (accent rouge), middleware `admin.ts`, composant `RoleBadge.vue`. CLI `app.scripts.seed_admin`. Doc `docs/auth-and-multitenant.md`.
- **F03 — Audit log append-only** (mig. 021) : table `audit_log` strictement append-only (triggers PL/pgSQL BEFORE UPDATE/DELETE qui RAISE EXCEPTION + REVOKE UPDATE,DELETE best-effort), 4 indexes, 2 ENUMs (`audit_action`, `audit_source`), 4 RLS policies. Mixin `Auditable` + listener `before_flush` : diff field-level via `inspect().attrs.history`, valeurs bornees 10 KB (marqueur `_truncated:true`), N rows audit_log dans la meme transaction. Constantes `AUDITABLE_MODELS` (CompanyProfile, FundApplication, ESGAssessment, CarbonAssessment, CreditScore, ActionPlan, ActionItem) + `EXEMPT_MODELS` (catalogue F01, infra, AuditLog, Skill, ExchangeRate, etc.). ContextVar `current_source_of_change` + helper `source_of_change_scope(value)`. 9 noeuds LangGraph decorés `@_with_llm_source`. Middleware `AdminAuditContextMiddleware` sur `/api/admin/*`. `AuditService.record_admin_view` (ligne `view_admin` cote PME). 4 endpoints (`/api/audit/me`, `/api/audit/me/export` CSV/JSON streaming, `/api/admin/audit/{account_id}`, `/api/admin/audit`). Pages `/historique`, `/admin/audit`, `/admin/audit/[accountId]`. Doc `docs/audit-log.md`.
- **F04 — Money typed + versioning + devises** (mig. 022) : type `Money` (Pydantic v2 frozen, Currency Literal XOF/EUR/USD/GBP/JPY, `amount Decimal(20,2) ge=0`, factory `from_columns`). Constante `FCFA_EUR_PEG = Decimal("655.957")`. Service currency conversion (peg + table `exchange_rates` UNIQUE(base,quote,as_of), pivot USD avec `ConversionPathUnavailableError`). Versioning catalogue : `version` (regex `^\d+\.\d+$`), `valid_from`, `valid_to`, `superseded_by` (FK self) sur 12 tables + `catalog_version` sur sources. Mixins `VersioningMixin` / `SourceVersioningMixin`. Service `bump_version`, `supersede(...)`. Trigger PL/pgSQL `prevent_supersede_cycle` (13 triggers, skip SQLite). Snapshot immuable JSONB `snapshot_data` + `snapshot_at` sur `fund_applications` (cree a transition `submitted_to_*`). Endpoint `POST /api/applications/{id}/recompute-against-snapshot`. Module `app/modules/currency/` (router public `/api/currency/*`, admin `/api/admin/currency/fetch-status`). CLI `python -m app.scripts.fetch_exchange_rates [--force]` cap 1/jour. Tool `simulate_financing` lit `fund.min_amount_money`/`max_amount_money`. Frontend : type `Money`, composable `useCurrency`, composants `<MoneyDisplay>` (mode `native|pme|both`) + `<ReferentialBadge>`. Store `ui.displayCurrencyMode` persiste localStorage. Anciennes colonnes `*_xof`/`*_fcfa` conservees phase 1.
- **F12 — Memoire contextuelle pgvector** (mig. 023) : table `message_chunks` (UUID PK, account_id/conversation_id/message_id FK, embedding VECTOR(1536) NULL), 3 indexes (composite, partiel pending_embedding, HNSW vector_cosine_ops m=16 ef=64), RLS + 2 policies. Module `app/modules/memory/` : `mask_secrets` (tokens→email→IBAN→cartes Luhn, marqueurs `[TOKEN]/[EMAIL]/[BANK]/[CARD]`), `chunk_text` 6000c+overlap 200c, `embed_message` async best-effort, `search_history` SQL pgvector `<=>` cosine + threshold 0.6, `purge_account_chunks` cascade thread_id. Hook `after_insert` Message → `asyncio.create_task(embed_message)`. Tool global `recall_history(query, max_results, since, include_current_conversation)` (Pydantic 2..500c, max 1..10, hard cap 10, helper `_format_relative_time` FR). Ajoute a `GLOBAL_WHITELIST` (4 tools globaux) + `MAX_TOOLS_PER_TURN=14`. `_load_context_memory` : 15 derniers messages bruts conversation courante + 3 resumes. Refactor `app/graph/checkpointer.py` en `@asynccontextmanager` (ouvert au lifespan FastAPI). `stream_graph_events` accepte `account_id`. Composant `ToolCallIndicator.vue` libelle « Recherche dans l'historique… ».
- **F11 — Tools de visualisation typés** (sans migration, F02/F04/F06/F07/F01 lecture seule) : 4 tools Pydantic strict dans `app/graph/tools/visualization_tools.py` — `show_kpi_card`, `show_match_card`, `show_map`, `show_comparison_table`. Schemas centralisés `app/schemas/visualization.py` (8 modeles). Constante `app/core/visualization_centroids.py` (UEMOA 8 centroides). Validator `payload_invalid.py` (retry 1x + fallback texte). Transport SSE via marker `<!--SSE:{"__sse_visualization_block__":true,...}-->` → event `visualization_block`. Bind par page dans `tool_selector_config.py` + 7 noeuds. Frontend : `leaflet@^1.9.4`, asset `frontend/app/assets/geo/uemoa-borders.geo.json` (~8 KB Natural Earth), 4 composants `KPICardBlock`/`MatchCardBlock`/`MapBlock` (lazy `defineAsyncComponent` + DOMPurify popups)/`ComparisonTableBlock` (table desktop + cartes mobile <=768px). Composable `useMapTiles` (OSM light / CartoDB Dark Matter selon store ui). `useChat.ts` étendu : `visualizationBlocksByMessage` Record<msgId, VisualizationBlock[]>.

---

## Features Métier (ledger condensé — chronologique inverse)

> Format : `Fxx (mig. NNN ou n/a) — nom court — periscope ; ancrages techniques`. Code spec : voir `specs/<branch>/`.

### Module 1 — Conversationnel & UX

- **F23 — Skills (Playbooks Métier)** (mig. 033) : table `skills` 18 col. (versioning F04, JSONB tool_whitelist/sources/activation_rules/golden_examples, status draft/published, FK created_by/verified_by RESTRICT four-eyes, superseded_by self-FK), 3 CHECK + 3 indexes (BTREE composite, status, GIN PG-only sur activation_rules). 3 skills MVP seedees (skill_esg_diagnostic, skill_score_gcf, skill_dossier_gcf_via_boad). Module `app/modules/skills/` (schemas Pydantic, validator anti-injection 10 patterns OWASP, tokens cap tiktoken cl100k_base, eval_runner asyncio.gather max 5 + timeout 60s, DRY `app/lib/eval_matching.py`). Helpers `skill_loader.py` (multi-critères score, top 2), `prompt_fusion.py` (fuse_prompt + cap 12k tokens, select_tools_with_skills intersection), `skill_integration.py`. Refactor 7 noeuds + champ `active_skills` dans `ConversationState`. Helper `prompt_injection_detector.py`. Conformity test `test_no_skill_mutation_tool.py` (regex `^(create|update|delete|publish|unpublish)_skill`). Router admin 8 endpoints `/api/admin/skills/*` + gating eval >=90 % publication. Frontend admin : `useAdminSkills.ts`, types, 7 composants, 3 pages `/admin/skills/{index,new,[id]}`. Doc `docs/skills-playbooks.md`.
- **F10 — Widgets bottom-sheet** : table `interactive_questions` étendue (`payload jsonb`, `response_payload jsonb`).
- **F12** — voir Fondations.
- **F13** : voir « Module ESG ».
- **F18 — Widgets interactifs chat** (mig. 018) : tool `ask_interactive_question` (4 variantes qcu/qcm/qcu_justification/qcm_justification) injecté dans 7 noeuds. Table `interactive_questions` satellite (aucune modif autres). Marker SSE `<!--SSE:{"__sse_interactive_question__":true,...}-->`. 2 events SSE (`interactive_question`, `interactive_question_resolved`) + endpoints `POST /chat/interactive-questions/{id}/abandon`, `GET /chat/conversations/{id}/interactive-questions`. Helper `WIDGET_INSTRUCTION` injecte dans 6 prompts modules + chat_node. Composants Vue : `InteractiveQuestionHost`, `SingleChoiceWidget`, `MultipleChoiceWidget`, `JustificationField`, `AnswerElsewhereButton` (ARIA radiogroup/checkbox). 1 question pending max/conversation. Justification ≤ 400 c.
- **F11** — voir Fondations.
- **016-fix-tool-persistence-bugs** : correctifs persistance tool calling.
- **015-fix-toolcall-esg-timeout** : tools `create_fund_application`, `batch_save_esg_criteria` (évite timeout 30 appels). Prompts application/credit/esg_scoring renforcés (ROLE actif, OUTILS, REGLE ABSOLUE). Timeout LLM `request_timeout=60`.
- **014-concise-chat-style** : `STYLE_INSTRUCTION` injectée dans 6 modules + chat post-onboarding.
- **013-fix-multiturn-routing-timeline** : `active_module` + `active_module_data` dans `ConversationState`. Classification binaire LLM continuation/changement (defaut: rester). Reprise module via détection `in_progress`. Frontend `TimelineBlock.vue` normalisation tolérante (phases/items/steps→events, period→date, name→title, state→status, details→description, defaut status=todo).
- **012-langgraph-tool-calling** : 32 tools LangChain dans `app/graph/tools/` (profiling/esg/carbon/financing/application/credit/document/action_plan/chat). Pattern `ToolNode` conditionnel max 5 itérations + retry 1x. SSE `astream_events()` : tokens + tool_call_start/end/error. Table `tool_call_logs`. Frontend : `useChat.ts` parse events + `ToolCallIndicator.vue`.

### Module 2 — ESG

- **F13 — Scoring multi-référentiels** (mig. 030) : table `referential_scores` (16 col., FK account_id CASCADE, assessment_id CASCADE, referential_id RESTRICT, superseded_by self SET NULL, pillar_scores/covered_criteria/missing_criteria JSONB, coverage_rate Numeric(4,3) [0,1], computed_by ENUM manual/llm/auto), index unique partiel `WHERE superseded_by IS NULL` + 3 indexes + RLS. Seed 5 référentiels MVP (Mefali UUID stable `0e5f1310-1310-1310-1310-13101310f013`, GCF, IFC PS, BOAD ESS, GRI 2021). Backfill ESGAssessment → Mefali. ALTER TYPE `reminder_type_enum` ADD `referential_version_evolved`. Service `multi_referential_service.py` (`compute_score_for_referential`, `compute_all_referential_scores` parallèle UPSERT, `compute_referential_score_for_offer` fallback Mefali + bottleneck min(fund,intermediary), `recompute_score_async`). 3 tools (`finalize_esg_assessment_multi_ref`, `recompute_score`, `compare_referentials`). 3 endpoints REST + refactor `POST /api/reports/esg/{id}/generate` (body `{referentials, include_appendix_sources}`). Partial Jinja2 `_appendix_sources.html`. Cron `check_referential_versions_evolution.py`. Frontend : 6 composants (`ReferentialSelector`, `ReferentialScoreCard`, `MissingCriteriaList`, `BottleneckBanner`, `DualReferentialView`, `MultiReferentialReportModal`), composable `useEsgMultiReferential.ts`, store étendu, refactor `/esg/results.vue`.
- **F06 (Module 2 perimetre)** : aussi cite F06 cote financement/projet (voir Module 3).
- **006 — Rapports PDF ESG** : WeasyPrint HTML→PDF, graphiques matplotlib SVG, resume executif Claude, template 9 sections, conformite UEMOA/BCEAO/ODD. API `/api/reports`. Page `/reports`. Notification chat SSE.
- **005 — Evaluation & scoring ESG** : 30 critères E-S-G, ponderation sectorielle, scoring dynamique. `esg_scoring_node` LangGraph. API `/api/esg`. Page `/esg`. RAG documentaire par critere. Benchmark sectoriel + fallback. Historique Chart.js. Reprise évaluations interrompues.
- **004 — Upload/analyse documents** : PyMuPDF, pytesseract, OCR, embeddings pgvector, chat integration.

### Module 3 — Financement & Projets

- **F16 — Simulateur financement sourcé** (sans migration, lecture F01/F04/F06/F07/F17) : module `app/modules/applications/` (simulation_schemas Pydantic v2 strict avec validators cross-field cost+ROI ; `factor_service.py` snapshot frozen via `MappingProxyType`, `load_factors_snapshot` 2-SELECT cohérent ; `simulation_engine.py` 4 fonctions pures `compute_total_cost`/`compute_roi`/`compute_carbon_impact`/`build_timeline` + composition `simulate_offer`, dispatch `_ROI_DISPATCH` par instrument subvention/pret_concessionnel/equity/blending, exceptions `FactorMissingError`/`OfferDataMissingError`, mode dégradé explicite ; `multi_simulate_service.py` `simulate_multi(db, project_id, offer_ids, account_id)` avec fallback secteur 4-niveaux country/year, ranking cheapest/fastest tie-break UUID lex). Endpoint `POST /api/projects/{project_id}/simulate-multi` (1..5 offres dedup, 200/403/404/422). Tool LangChain `compare_simulations` (ComparisonTable F11 conforme). Inject MAPPING financing/application + nouveau slug `simulator` + pattern URL `^/financing/simulator(?:/|$)` AVANT `^/financing` dans `_PATH_TO_SLUG_PATTERNS`. Frontend : types `simulator.ts` + 8 interfaces miroir + type guards, composable `useSimulator.ts`, store Pinia `simulator.ts` (volatile, hard cap 5 offres, **aucune persistance** FR-012), 2 composants `SimulationDetailedCard.vue` (ring emerald cheapest / blue fastest, badges factor_status pending/outdated, ARIA region) + `SimulationComparator.vue`, page `/financing/simulator.vue`.
- **F07 — Entité Offre = Fonds × Intermédiaire** (mig. 028) : table `offers` (versioning F04 + 4 CHECK). Enrichissement `funds` (instruments JSONB, theme JSONB, submission_mode, submission_calendar, source_id, publication_status, enum `fund_type` → multilateral|bilateral|regional|national|private|carbon_marketplace), `intermediaries` (code unique sparse, required_documents JSONB, fees_structured JSONB, processing/disbursement_time_days_min/max, submission_portal_url, success_rate, total_funded_volume Money typed, source_id, publication_status), `fund_intermediaries` (accredited_from NOT NULL, accredited_to, max_amount_per_fund Money typed, accreditation_source_id), nouvelle col `fund_applications.offer_id NOT NULL` post-backfill. Seed singleton DIRECT (intermediary `code='DIRECT'` + Source `system://mefali/direct-singleton`). Calculator `compute_effective_offer` (intersection critères « le plus restrictif gagne », union docs dedup `(title, source_id)`, somme frais XOF, somme délais, hint langues anglophones). 6 endpoints `/api/offers/*` public + `/api/admin/offers/*`. 3 tools (`list_offers`, `get_offer`, `compare_offers_for_fund`) + extension `create_fund_application` (offer_id prioritaire). Cron `check_expired_accreditations.py` idempotent (`source_of_change='import'`). Feature flag `USE_OFFER_VIEW` (env `NUXT_PUBLIC_USE_OFFER_VIEW`, default false MVP). 8 composants Vue (`OfferCard`, `OfferDetail`, `EffectiveCriteriaList`, `EffectiveDocumentsList`, `EffectiveFees`, `SubmissionModeBadge`, `FundCard`, `IntermediaryCard`) + 4 pages.
- **F06 — Entité Projet Vert** (mig. 025) : tables `projects` 21 col. (multi-tenant F02, Auditable F03, Money typed F04 sur `target_amount`, JSONB array `objective_env` whitelist 8 valeurs, maturity 5 valeurs, status 6 valeurs, financing_structure 5 valeurs, expected_impact_*, location_country/region, flag `auto_generated`) + `project_documents` (UNIQUE project_id+document_id, doc_type 5 valeurs). Col `fund_applications.project_id` UUID FK NOT NULL après backfill. 5 indexes, 11 CHECK, RLS + 4 policies. Backfill SQL CTE PG idempotent + Python loop SQLite (mapping accepted→funded). Module `app/modules/projects/` (service async list/get/create/update/soft_delete/duplicate/link_document/list_applications/get_active_projects_for_user). Refus dur suppression si applications actives → 409 + hint, `force=true` soft-delete. Duplication force `status=draft` + suffix `' (copie)'`, project_documents NON copiés. 7 tools `project_tools.py`. Inject : `list_projects` chat global + lecture profile + 7 tools dans `profile_projects` slug + pattern URL `^/profile/projects(?:/|$)` AVANT `/profile`. PROJECT_TOOLS au ToolNode `chat`. `_load_full_context_for_state(db, user_id)` retourne `{profile, projects}` (actifs status≠cancelled/closed limit 20), injectée via `user_projects` dans state. Prompts application/financing : section « PROJET CIBLE — OBLIGATOIRE AVANT CANDIDATURE ». Frontend : 6 composants + 4 pages `/profile/projects/*`, composable `useProjects.ts`, store `projects.ts`, types exhaustifs, lien sidebar « Mes Projets ».
- **F24 — Extension Chrome MV3** (mig. 042) : `funds.url_patterns JSONB`, `intermediaries.url_patterns JSONB`, `refresh_tokens.scope VARCHAR(20)` + CHECK enum web/extension, valeur ENUM `'extension'` ajoutée à `audit_source`, seed UPSERT idempotent ~5 patterns prioritaires (BOAD/GCF/AFD/PNUD/Ecobank Sunref). Module `app/modules/extension/` (schemas Pydantic v2 strict `extra='forbid'`, service `match_url`/`list_active_applications`/`build_profile_snapshot`, dependency `get_current_extension_user`, `ExtensionAuditContextMiddleware` `source_of_change='extension'`). 4 endpoints `/api/extension/v1/*` (`POST /auth/exchange` public, `GET /me/profile-snapshot`, `POST /detect`, `GET /applications/active`). CORS `allow_origin_regex=^chrome-extension://.*$`. Matching priorité DIRECT puis tri created_at. Extension : dossier racine `extension/` (Vite + @crxjs/vite-plugin + Vue 3 + Pinia + TS strict, manifest MV3, _locales/fr, content scripts createElement+textContent anti-XSS, popup login + dashboard, service worker cache LRU TTL 1 h dual `chrome.storage.local`+memCache, stores Pinia auth+applications avec `chrome.storage.session` pour token bearer). Doc `docs/extension-chrome.md`. Hors-scope MVP : pré-remplissage formulaires, side panel, notifications, multi-langue, Chrome Web Store, UI admin F09 url_patterns.
- **011 — Dashboard + Plan d'Action** : 4 cartes synthétiques (ESG/carbone/credit/financement) + carte financements parcours intermédiaires. Plan d'action Claude (10-15 actions, catégories environment/social/governance/financing/carbon/intermediary_contact, snapshot coordonnees). Page plan d'action timeline verticale + filtres + barre progression. Rappels typés (`action_due/assessment_renewal/fund_deadline/intermediary_followup/custom`) polling 60s + toasts. Gamification 5 badges (first_carbon, esg_above_50, first_application, first_intermediary_contact, full_journey). `action_plan_node` LangGraph (timeline/table/mermaid/gauge/chart). API `/api/dashboard` + `/api/action-plan` 8 endpoints. Pages `/dashboard`, `/action-plan`.
- **008 — Conseiller financement vert** : BDD 12 fonds (GCF/FEM/BOAD/BAD/SUNREF/FNDE/…) + 14 intermédiaires + ~50 liaisons fund-intermediary. Matching scoring multi-critères (secteur/ESG/taille/localisation/documents). Parcours direct vs intermédiaire. Catalogue filtrable + annuaire. Workflow intérêt→choix intermédiaire→fiche préparation PDF. `financing_node` LangGraph + RAG pgvector + blocs visuels. API `/api/financing` 10+ endpoints. Pages `/financing` (3 onglets) + `/financing/[id]`. Embeddings text-embedding-3-small.
- **009 — Generateur dossiers candidatures** : python-docx, toast-ui/editor.

### Module 4 — Carbone

- **F17 — Carbone mix UEMOA sourcé** (mig. 024) : col `year` Integer NOT NULL sur `emission_factors` (backfill 2024), index composite `idx_emission_factors_lookup (category, country, year)`, UNIQUE `emission_factors_cat_country_year_uniq`. ~33 facteurs F17 seedés (8 pays UEMOA × 2 années + global ; 3 combustibles, 7 transport, 3 déchets, 6 achats matières premières) sources ADEME Base Carbone v23 / IEA Africa Energy Outlook 2024 / IPCC AR6 WG3. FK `source_id`+`factor_id` UUID NOT NULL sur `carbon_emission_entries` (backfill matching strict subcategory→code + fallback prefix + fallback global). Conservation legacy `source_description` (drop reporté ≥ 2 sprints). Service `factor_service.py` : dataclass `EmissionFactorResolution`, exception `EmissionFactorNotFoundError`, `get_emission_factor(db, category, country, year)` priorité (1) country+year exact, (2) country+year antérieure (diff ≤ 3 = approximate=False), (3) global+year exact, (4) global+year antérieure. Service `seed_factors.py` (`SEED_DATA` ~33 lignes, `seed_emission_factors(db, admin_user_id) -> SeedResult` idempotent SELECT-before-INSERT). Schema `reduction_plan_schema.py` : `ReductionPlanAction` (title/description/estimated_reduction_tco2e/cost_estimate_fcfa/timeline/source_id/unsourced) + validator cohérence source_id↔unsourced, `ReductionPlan` `actions[]`. Élargissement `VALID_CATEGORIES` (+ `purchases`) et `EMISSION_CATEGORIES`. Tool `save_emission_entry` : lit country profil + `get_emission_factor(...)` fallback subcategory→category, stocke `source_id`+`factor_id`, retourne JSON enrichi (`factor_used`, `source_id`, `is_approximate`, `fallback_reason`). `complete_assessment` valide `reduction_plan` via `ReductionPlan.model_validate` (legacy `quick_wins`/`long_term` accepté). Prompt `CARBON_PROMPT` : section Achats + règle sourçage cite_source + guide is_approximate (year_older/country_global) + table valeurs UEMOA 2024 + matières premières ADEME. Endpoint admin `POST /api/admin/carbon/seed-factors`. Frontend : composant `EmissionFactorBadge.vue` (label + valeur + `<SourceLink>` + picto warning amber tooltip year_older/country_global, ARIA region+img). Types `EmissionCategory` (+ purchases), `ReductionPlanActionV2`, `ReductionPlan` accepte `actions[]` OU legacy. Page `/carbon/results` : section plan rendue avec nouveau schema (titre/description/timeline/coût + SourceLink ou badge non sourcée), branche legacy 2 sprints, ajout `purchases` dans `categoryLabels`/`categoryColors`.
- **007 — Calculateur empreinte carbone** : questionnaire guidé par catégorie (énergie/transport/déchets/industriel/agriculture), facteurs Afrique Ouest, équivalences FCFA. `carbon_node` LangGraph + visualisations inline (chart/gauge/table/timeline). API `/api/carbon` 6 endpoints. Pages `/carbon` (liste) + `/carbon/results` (donut/barres/équivalences/plan/benchmark sectoriel/évolution). 9 secteurs benchmarkés + fallback. Contrainte unicité bilan/année. Reprise bilans interrompus.

### Module 5 — Crédit

- (référencé via tools `credit_*` + node `credit` + page produit ; pas de migration récente listée).

### Tests, base & infra

- **017-fix-failing-tests** : SQLite in-memory pour tests, pytest-asyncio.
- **001-technical-foundation** : Python 3.12 + TS 5.x strict, PostgreSQL 16 + pgvector.
- **002-chat-rich-visuals** : asyncpg async.
- **003-company-profiling-memory** : Alembic + base modules.

---

## Notes opérationnelles transverses (à connaître)

- **Pattern tool routing** : `_PATH_TO_SLUG_PATTERNS` est ordonné — placer les patterns spécifiques (ex. `^/profile/projects(?:/|$)`, `^/financing/simulator(?:/|$)`) AVANT les patterns génériques (`/profile`, `/financing`).
- **`MAX_TOOLS_PER_TURN=14`**. `GLOBAL_WHITELIST` = `ask_interactive_question`, `trigger_guided_tour`, F01 sourcing×3 (`cite_source`, `search_source`, `flag_unsourced`), `recall_history`.
- **Catalogue admin-only** ajouté à `EXEMPT_MODELS` (Skill, ExchangeRate, etc.) — audit log via middleware admin.
- **Round-trip Alembic** `up/down/up` validé sur PostgreSQL pour toutes les migrations 019-042.
- **SourceLink** doit décorer **chaque chiffre** (ESG/Carbone/Financement/Simulateur). Validator `source_required.py` retry 1x puis fallback texte.
- **MoneyDisplay** mode `both` par défaut (devise native + équivalent FCFA). Persiste dans `localStorage` (`mefali.ui.displayCurrencyMode`).
