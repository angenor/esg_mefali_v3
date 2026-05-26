# ESG Mefali — Conseiller ESG IA

Plateforme conversationnelle IA pour démocratiser la finance durable auprès des PME africaines francophones (UEMOA/CEDEAO). Analyse ESG + financement vert + scoring crédit alternatif.

> Historique détaillé : `CLAUDE.md.bak` et `CLAUDE.md.bak2`. Spécifications par feature : `specs/<branch>/`.

## Stack

**Frontend** : Nuxt 4, Vue 3 Composition API (`<script setup lang="ts">`), Pinia, TailwindCSS, GSAP, toast-ui/editor, Chart.js, Leaflet. Tests Vitest + Playwright.

**Backend** : Python 3.12, FastAPI, SQLAlchemy async, Alembic, Pydantic v2 strict. LLM Claude via OpenRouter + LangGraph (>=0.2) + LangChain (>=0.3). Embeddings Voyage (mig. 043, voir `docs/embeddings-voyage.md`). Documents : PyMuPDF, pytesseract, WeasyPrint, Jinja2, python-docx, matplotlib. httpx, tiktoken (cl100k_base), semver.

**BDD** : PostgreSQL 16 + pgvector (HNSW cosine), asyncpg ; SQLite in-memory pour tests. LangGraph `AsyncPostgresSaver` (lifespan FastAPI), fallback MemorySaver. Stockage local `/uploads/`. Queue synchrone.

**Extension Chrome** : Vite + @crxjs/vite-plugin + Vue 3 + Pinia + MV3.

## Architecture (8 modules)
1. Agent conversationnel (chat FR, profilage, mémoire)
2. Analyseur ESG (upload/OCR, scoring /100, rapport PDF)
3. Conseiller financement vert (GCF/FEM/BOAD/BAD…)
4. Calculateur carbone (tCO2e, plan réduction)
5. Scoring crédit vert alternatif
6. Plan d'action (roadmap, rappels)
7. Tableau de bord (multi-utilisateurs)
8. Extension Chrome (détection fonds, pré-remplissage)

## Conventions

- **Langue** : code en anglais ; commentaires + UI + docs en français (accents é è ê à ç ù **obligatoires**).
- **Frontend** : `composables/`, `pages/` (routing auto), `components/` PascalCase (`pathPrefix: false`), `stores/` Pinia. Tout dans `app/`.
- **Backend** : `routers/`, `services/`, `models/` SQLAlchemy, `schemas/` Pydantic. snake_case.
- **BDD** : Alembic. Tables snake_case pluriel.

### Dark Mode (OBLIGATOIRE)
Tout composant/page DOIT supporter le dark mode :
- Fonds : `bg-white dark:bg-dark-card`, `bg-surface-bg dark:bg-surface-dark-bg`
- Textes : `text-surface-text dark:text-surface-dark-text`, `text-gray-600 dark:text-gray-400`
- Bordures : `border-gray-200 dark:border-dark-border`
- Inputs : `dark:bg-dark-input dark:text-surface-dark-text`
- Hover : `hover:bg-gray-50 dark:hover:bg-dark-hover`

Thème géré par `stores/ui.ts` (classe `dark` sur `<html>`, localStorage). Variables `@theme` dans `app/assets/css/main.css`. **Jamais** de couleur claire sans équivalent dark.

### Réutilisabilité (OBLIGATOIRE)
Chercher avant de créer. Patterns récurrents (cartes, formulaires, boutons, inputs) → `components/ui/` paramétrables (props + slots). Si un pattern apparaît > 2 fois : extraire en composant générique.

## Contexte métier

- **Public** : PME africaines francophones (UEMOA/CEDEAO), secteur informel inclus (agriculture, énergie, recyclage, transport, etc.).
- **Référentiels ESG** : Mefali (interne), GCF, IFC PS, BOAD ESS, GRI 2021 ; taxonomie verte UEMOA/BCEAO ; Gold Standard, Verra, REDD+.
- **ODD cibles** : 8, 9, 10, 12, 13, 17.

## Environnement Python

```bash
# Une fois
cd backend && python3 -m venv venv
# À chaque session
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

**Jamais de pip global.** `which python` → `backend/venv/bin/python`.

## Commandes utiles

```bash
cd frontend && npm run dev                  # Frontend
uvicorn app.main:app --reload               # Backend (venv actif)
alembic upgrade head                        # BDD
```

## Parallel Sub-agents
Jusqu'à 10 sub-agents en parallèle pour rechercher frontend + backend + dossiers simultanément.

---

## Fondations transverses (à respecter dans toute nouvelle feature)

- **F01 — Sourçage obligatoire** (mig. 020) : table `sources` + 10 catalogues. Workflow 4-yeux (`captured_by != verified_by`), statuts draft/pending/verified/outdated. Tools globaux `cite_source`/`search_source`/`flag_unsourced`. Validator post-LLM `source_required.py` (retry 1x + fallback). Composants `SourceLink`, `SourceModal`, `SourceBadge`, `SourcesList`. Annexe « Sources » auto dans rapport ESG PDF. ~30 sources verified (ADEME, IPCC AR6, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD, GRI, ISO 14064-1).
- **F02 — Multi-tenant + rôles + RLS** (mig. 019) : `Account`, `RefreshToken`, `AccountInvitation` ; `User.role` (PME/ADMIN) + `account_id`. 14 tables avec `account_id UUID NOT NULL`. RLS `ENABLE+FORCE` + policies. Helper `set_rls_context`. Refresh token rotatif + grâce 5s + révocation. JWT 24h. Module `account` + `admin`. Layout `admin.vue`, middleware `admin.ts`, `RoleBadge.vue`. CLI `app.scripts.seed_admin`. Doc `docs/auth-and-multitenant.md`.
- **F03 — Audit log append-only** (mig. 021) : table `audit_log` (triggers PL/pgSQL BEFORE UPDATE/DELETE + REVOKE). Mixin `Auditable` + listener `before_flush` (diff field-level, valeurs bornées 10 KB). `AUDITABLE_MODELS` vs `EXEMPT_MODELS` (Skill, ExchangeRate, catalogue F01…). ContextVar `current_source_of_change` + `source_of_change_scope(value)`. Middleware `AdminAuditContextMiddleware`. 4 endpoints `/api/audit/*`. Pages `/historique`, `/admin/audit`. Doc `docs/audit-log.md`.
- **F04 — Money typed + versioning + devises** (mig. 022) : type `Money` (Pydantic v2 frozen, Literal XOF/EUR/USD/GBP/JPY, Decimal(20,2) ge=0). `FCFA_EUR_PEG = 655.957`. Table `exchange_rates`. Versioning catalogue (`version`, `valid_from`, `valid_to`, `superseded_by`) sur 12 tables. Mixins `VersioningMixin`/`SourceVersioningMixin`. Trigger `prevent_supersede_cycle`. Snapshot JSONB `snapshot_data` sur `fund_applications`. Endpoint `POST /api/applications/{id}/recompute-against-snapshot`. Module `currency/` + CLI `fetch_exchange_rates`. Frontend : composable `useCurrency`, composants `<MoneyDisplay>` (mode `native|pme|both`, défaut `both`, localStorage `mefali.ui.displayCurrencyMode`) + `<ReferentialBadge>`.
- **F12 — Mémoire contextuelle pgvector** (mig. 023) : table `message_chunks` (VECTOR Voyage, voir mig. 043), HNSW cosine. Module `memory/` : `mask_secrets` (tokens/email/IBAN/Luhn → marqueurs), `chunk_text` 6000c+overlap 200c, `embed_message` async, `search_history` threshold 0.6, `purge_account_chunks`. Hook `after_insert` Message → embed async. Tool global `recall_history`. `_load_context_memory` : 15 derniers messages + 3 résumés. Checkpointer `@asynccontextmanager` (lifespan). `stream_graph_events(account_id)`.
- **F11 — Tools de visualisation typés** (sans migration) : 4 tools Pydantic strict — `show_kpi_card`, `show_match_card`, `show_map`, `show_comparison_table`. Schemas `app/schemas/visualization.py`. Constante `visualization_centroids.py` (UEMOA 8 centroïdes). Validator `payload_invalid.py` (retry 1x + fallback). Transport SSE via marker `<!--SSE:...-->` → event `visualization_block`. Frontend : Leaflet, 4 composants `*Block` (lazy + DOMPurify), composable `useMapTiles` (OSM light / Carto Dark Matter).

---

## Notes opérationnelles (à connaître)

- **Tool routing** : `_PATH_TO_SLUG_PATTERNS` ordonné — placer les patterns spécifiques (`^/profile/projects(?:/|$)`, `^/financing/simulator(?:/|$)`) **AVANT** les génériques (`/profile`, `/financing`).
- **Sélection tools (F048)** : base = **union** `GLOBAL_WHITELIST ∪ MODULE_TOOL_MAPPING[node] ∪ PAGE_TOOL_MAPPING[slug]`. Troncature priorisée : whitelist > tools du nœud (intention) > tools de page.
- **`MAX_TOOLS_PER_TURN = 14`**. `GLOBAL_WHITELIST` = `ask_interactive_question`, `trigger_guided_tour`, `cite_source`, `search_source`, `flag_unsourced`, `recall_history`.
- **SourceLink obligatoire** sur chaque chiffre (ESG/Carbone/Financement/Simulateur).
- **Round-trip Alembic** `up/down/up` validé sur PG pour migrations 019-044.
- **Catalogue admin-only** en `EXEMPT_MODELS` — audit via middleware admin.

## Features livrées (résumé)

Pour le détail technique exhaustif (tables, colonnes, FK, endpoints, composants), consulter `CLAUDE.md.bak2` et `specs/<branch>/`.

### Module 1 — Conversationnel
- **F23** (mig. 033) — Skills/Playbooks métier (gating eval ≥ 90 %).
- **F18** (mig. 018) — Widgets interactifs chat (qcu/qcm/justification). Fix `account_id` NULL (2026-05-08).
- **F10** — Widgets bottom-sheet.
- **012/013/014/015/016** — Tool calling LangGraph (32 tools), routing multi-tour, style concis, fix timeouts/persistance.

### Module 2 — ESG
- **F13** (mig. 030) — Scoring multi-référentiels (5 référentiels MVP).
- **047** — Évaluation ESG par projet (mig. 047 ; 2 tables).
- **006** — Rapports PDF ESG (WeasyPrint + matplotlib).
- **005** — Scoring ESG (30 critères E-S-G).
- **004** — Upload/analyse documents (OCR + pgvector).

### Module 3 — Financement & Projets
- **F048** — Fiabilisation création dossier + mémoire ESG (sélecteur union, gating ESG, export DOCX/PDF réel, dédup draft, parité chat/UI).
- **F25** (feature 044) — Catalogue admin financement vert (lecture seule, `/api/admin/catalog/*`).
- **F16** — Simulateur financement sourcé (`POST /api/projects/{id}/simulate-multi`, ranking cheapest/fastest).
- **F07** (mig. 028) — Entité Offre = Fonds × Intermédiaire (calculator `compute_effective_offer`). Feature flag `USE_OFFER_VIEW`.
- **F06** (mig. 025) — Entité Projet Vert (multi-tenant, Auditable, Money typed). Tools projet + injection contexte.
- **F24** (mig. 042) — Extension Chrome MV3 (`/api/extension/v1/*`, CORS `chrome-extension://`).
- **011** — Dashboard + Plan d'action (Claude, 5 badges, rappels polling 60s).
- **008** — Conseiller financement (12 fonds + 14 intermédiaires + ~50 liaisons).
- **009** — Générateur dossiers (python-docx, toast-ui).

### Module 4 — Carbone
- **F17** (mig. 024) — Carbone mix UEMOA sourcé (~33 facteurs ADEME/IEA/IPCC, fallback country/year, schema `ReductionPlan`).
- **007** — Calculateur carbone (9 secteurs benchmarkés).

### Module 5 — Crédit
- Tools `credit_*`, node `credit`.

### Infra/tests
- **043** — Migration embeddings Voyage (`docs/embeddings-voyage.md`).
- **017** — SQLite in-memory + pytest-asyncio.
- **001-003** — Fondation technique, async, Alembic.

## Active Technologies
- Python 3.12, TypeScript 5.x strict + FastAPI, SQLAlchemy async, Pydantic v2, Alembic, LangGraph (>=0.2), LangChain (>=0.3), WeasyPrint, python-docx.
- Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS, Chart.js, Leaflet.
- PostgreSQL 16 + pgvector (embeddings Voyage depuis mig. 043).
