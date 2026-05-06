# Implementation Plan: Fondations Sourçage et Catalogue Source

**Branch**: `feat/F01-fondations-sourcage-catalogue` (orchestrator) / `020-fondations-sourcage-catalogue` (SpecKit)
**Date**: 2026-05-06
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-fondations-sourcage-catalogue/spec.md`

## Summary

Faire passer la plateforme du statut « rebadge cosmétique » au statut « outil traçable » en introduisant un catalogue Source de premier rang, en sortant les valeurs factuelles codées en dur (facteurs d'émission, 30 critères ESG, pondérations sectorielles, constantes de simulation) vers des tables sourcées, en exposant à l'agent IA trois actions outillées (`cite_source`, `search_source`, `flag_unsourced`), en branchant un validator post-tour qui rejette toute affirmation factuelle sans citation, et en livrant l'UI (picto SourceLink + modal SourceModal + badge SourceBadge + page `/sources`) ainsi que l'annexe automatique des sources dans les rapports PDF.

**Approche technique** :

- 1 migration Alembic additive (`020_create_sources_catalog`) créant 11 tables (`sources`, `indicators`, `referentials`, `referential_indicators`, `criteria`, `formulas`, `thresholds`, `emission_factors`, `required_documents`, `simulation_factors`, `unsourced_flags`) + colonne `publication_status` sur les 5 entités existantes concernées (`funds`, `intermediaries`, `referentials`, `indicators`, `templates_dossier` — colonne `publication_status` ajoutée seulement quand la table existe déjà ; sinon embarquée dans le `CREATE TABLE`).
- Modèles SQLAlchemy split par fichier dans `backend/app/models/source.py` + extensions `indicator.py`, `referential.py`, `criterion.py`, `formula.py`, `threshold.py`, `emission_factor.py`, `required_document.py`, `simulation_factor.py`, `unsourced_flag.py`.
- Schémas Pydantic v2 dans `backend/app/schemas/source.py` (`Source`, `SourceCreate`, `SourceUpdate`, `SourceVerify`, `SourceList`, `SourceCitation`).
- Service applicatif `backend/app/modules/sources/service.py` (CRUD + verify + search full-text/embedding).
- Router FastAPI `backend/app/modules/sources/router.py` exposant `GET/POST/PATCH /api/sources` + endpoints administrateur.
- Tools LangChain dans `backend/app/graph/tools/sourcing_tools.py` (`cite_source`, `search_source`, `flag_unsourced`) injectés dans tous les nœuds producteurs de chiffres (chat, esg_scoring, carbon, financing, application, credit, action_plan).
- Validator middleware `backend/app/graph/validators/source_required.py` invoqué après chaque tour LLM (regex de détection + lookup tool_calls + retry max 1 + fallback texte).
- Composants Vue 3 dans `frontend/app/components/sources/` (`SourceLink`, `SourceModal`, `SourceBadge`, `SourcesList`) + composable `useSources.ts` + store Pinia `sources.ts` + page `pages/sources/index.vue`.
- Intégration `<SourceLink :sourceId="…" />` sur les composants prioritaires d'affichage (ScoreCard, Recommendations, StrengthsBadges, CriteriaProgress, FactorsRadar, FinancingCard, carbon/results, financing/[id], applications/[id]).
- Annexe « Sources et références » auto-générée dans `backend/app/modules/reports/templates/esg_report.html` via collecte des `cite_source` mobilisés pendant la génération.
- Seed initial 30+ sources `verified` (ADEME, IPCC, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD ONU) + migration des `EMISSION_FACTORS` Python → table `emission_factors`, des 30 `ESGCriterion` → table `indicators`, des `SECTOR_WEIGHTS` → table `referential_indicators`, et des constantes simulateur → table `simulation_factors` (statut `pending` quand aucune source officielle ne couvre).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)

**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, LangGraph ≥ 0.2.0, LangChain ≥ 0.3.0, langchain-openai ≥ 0.3.0, WeasyPrint (rapports PDF, déjà installé), pgvector (extension PostgreSQL, déjà activée).
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4 (dark mode obligatoire), `@heroicons/vue` (déjà installé via `nuxt-icon`), DOMPurify (déjà installé), Vitest + `@vue/test-utils` + `happy-dom` (unitaires), `@playwright/test` (E2E).

**Storage** : PostgreSQL 16 + pgvector via asyncpg ; Alembic pour les migrations. Aucun stockage tiers introduit en F01.

**Testing** :
- Backend : pytest + pytest-asyncio + pytest-cov ≥ 80 %.
- Frontend : Vitest + `@vitest/coverage-v8` (unitaires composants ≥ 80 %), Playwright (E2E parcours critiques, exécutables via `npx playwright test`).

**Target Platform** : application Web (desktop + mobile responsive). Backend déployé en monolithe FastAPI (uvicorn). Frontend Nuxt 4 mode SPA + SSR partiel.

**Project Type** : application Web (backend FastAPI + frontend Nuxt 4 + base PostgreSQL 16). Pas de mobile natif.

**Performance Goals** :
- Affichage `SourceModal` après clic sur `SourceLink` ≤ 1 s p95 (SC-009).
- Liste `/sources` filtrée par publisher ≤ 2 s p95 sur catalogue de 100 sources (SC-011).
- `cite_source` (lookup unique par identifiant) ≤ 100 ms côté backend.
- `search_source` (full-text + embedding pgvector HNSW, top 5) ≤ 500 ms côté backend.
- Validator `source_required` ≤ 50 ms par tour (regex + analyse tool_calls in-memory).

**Constraints** :
- Mode sombre obligatoire sur tous les composants frontend introduits.
- UI 100 % en français (avec accents corrects).
- Aucun secret hardcodé (URL OpenRouter, clés API → `backend/app/core/config.py`).
- Aucun tool LLM ne mute le catalogue (invariant ESG Mefali #7).
- F01 reste neutre vis-à-vis du multi-tenant : `created_by_user_id` (FK `users.id`) + marqueur `# TODO(F02): account_id` sur tous les nouveaux modèles.
- Pas d'audit log centralisé (introduit par F03) : conserver `db.commit()` directs dans le service avec `# TODO(F03): Auditable`.
- TDD strict : tests d'abord (RED), implémentation ensuite (GREEN), couverture ≥ 80 %.

**Scale/Scope** :
- Catalogue cible année 1 : 30 → 200 sources `verified` (puis croissance ouverte).
- 11 nouvelles tables (10 entités catalogue + 1 table journal `unsourced_flags`).
- ~9 nœuds LangGraph touchés (injection des 3 tools).
- 4 composants Vue + 1 composable + 1 store + 1 page.
- ~10 emplacements UI à équiper d'un `<SourceLink>` (ScoreCard, Recommendations, StrengthsBadges, CriteriaProgress, FactorsRadar, FinancingCard, carbon/results, financing/[id], applications/[id], dashboard widgets).
- ~120 nouveaux tests (50 unitaires backend + 20 intégration backend + 30 unitaires frontend + ≥ 8 E2E Playwright + 12 cas eval LLM golden set).

## Constitution Check

*Gate : doit passer avant Phase 0, re-vérifié après Phase 1.*

### I. Francophone-First & Contextualisation Africaine

- [x] UI 100 % française (libellés, modals, messages d'erreur, badges) avec accents corrects.
- [x] Code anglais (noms de tables, fonctions, classes, types).
- [x] Commentaires et documentation en français.
- [x] Référentiels couverts en priorité : Taxonomie verte UEMOA, Circulaire BCEAO 002-2024, BOAD Politique Sectorielle ESS, puis IPCC/IFC/GCF/ODD ONU/ADEME/IEA/Gold Standard/Verra.
- [x] Secteur informel pris en compte : les `simulation_factors` migrent les constantes utilisées dans le scoring crédit alternatif (Mobile Money, photos IA), avec marqueur `pending` honnête.

### II. Architecture Modulaire

- [x] Module `sources` autonome (`backend/app/modules/sources/`) avec frontières claires (router, service, schemas).
- [x] Tools `sourcing_tools.py` consommables par les 7 nœuds spécialistes via injection (pas de dépendance inverse).
- [x] Frontend : composants colocalisés dans `components/sources/`, composable et store dédiés (pas de pollution cross-module).
- [x] Aucun module existant n'est cassé : les tables actuelles (`carbon_assessments`, `esg_assessments`, etc.) n'évoluent pas en F01 ; elles consommeront le catalogue dans des features ultérieures (F13 scoring multi-référentiels, F17 carbone mix UEMOA).

### III. Conversation-Driven UX

- [x] Le sourçage reste invisible quand tout va bien (l'agent IA cite, l'utilisateur voit le picto sans friction).
- [x] L'experience reste conversationnelle : le validator backend agit en post-traitement, pas en formulaire imposé.
- [x] L'utilisateur PME peut consulter le catalogue depuis une page dédiée `/sources` (lecture libre, pas de formulaire de saisie).
- [x] Les flag_unsourced (« je ne dispose pas d'une source vérifiée ») préservent la promesse conversationnelle : l'agent répond honnêtement plutôt que de bloquer.

### IV. Test-First (NON-NEGOTIABLE)

- [x] Tests unitaires backend écrits AVANT le service `sources` et les tools `sourcing_tools.py`.
- [x] Tests d'intégration API écrits AVANT les routes `GET/POST/PATCH /api/sources`.
- [x] Tests unitaires composants Vue écrits AVANT les composants (Vitest).
- [x] Tests E2E Playwright écrits AVANT l'intégration des composants dans les pages.
- [x] Couverture cible ≥ 80 % maintenue.
- [x] Eval LLM (golden set 10 questions) écrit AVANT le branchement final des tools dans les nœuds.

### V. Sécurité & Protection des Données

- [x] Aucun secret introduit (`captured_by`, `verified_by` = simples FK `users.id`).
- [x] Toutes les entrées validées via Pydantic v2 (`SourceCreate`, `SourceUpdate`, `SourceVerify`, `SourceCitation`).
- [x] Requêtes SQL paramétrées (SQLAlchemy ORM) : aucune concaténation.
- [x] Authentification réutilisée (`api/deps.py::get_current_user`, `require_admin`).
- [x] Rate limiting et auth déjà actifs sur `/api` (inchangés).
- [x] L'agent IA ne peut pas muter le catalogue (tools `cite_source/search_source/flag_unsourced` sont read-only ou journalisation seulement).

### VI. Inclusivité & Accessibilité

- [x] Composants Vue : labels descriptifs (`aria-label`), `aria-describedby` sur picto, focus piégé dans `SourceModal`, navigation clavier (Tab, Esc), focus visible.
- [x] Page `/sources` : recherche en texte libre tolérante aux accents, pagination, fonctionne sur connexions lentes (lazy loading résultats).
- [x] Messages d'erreur en français clair (« Source non vérifiée », « Aucune source disponible pour ce chiffre »).

### VII. Simplicité & YAGNI

- [x] Pas de microservice : module `sources` colocalisé dans le monolithe FastAPI.
- [x] Stockage pgvector déjà activé (pas d'introduction de Redis/Celery).
- [x] Hors-scope MVP explicitement listé : pas de Wayback, pas de hash de contenu, pas de revalidation cron, pas de scrapers, pas de marketplace.
- [x] Validator regex en code (constante `IGNORED_NUMERIC_PATTERNS`), pas de table de configuration en F01.
- [x] Cache Pinia côté frontend (in-memory) plutôt que Redis post-MVP.

**Verdict Constitution Check** : tous les principes sont satisfaits sans dérogation. Aucune entrée à porter dans **Complexity Tracking**.

## Project Structure

### Documentation (this feature)

```text
specs/020-fondations-sourcage-catalogue/
├── plan.md              # Ce fichier (/speckit.plan)
├── spec.md              # /speckit.specify + /speckit.clarify
├── research.md          # Phase 0 (/speckit.plan)
├── data-model.md        # Phase 1 (/speckit.plan)
├── quickstart.md        # Phase 1 (/speckit.plan)
├── contracts/           # Phase 1 (/speckit.plan)
│   ├── api-sources.md
│   ├── tools-sourcing.md
│   └── validator-source-required.md
├── checklists/
│   └── requirements.md  # checklist /speckit.specify
└── tasks.md             # Phase 2 (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 020_create_sources_catalog.py        # migration unique additive
├── app/
│   ├── models/
│   │   ├── source.py                            # Source + enums verification_status, publisher
│   │   ├── indicator.py                         # Indicator + Criterion + Formula + Threshold
│   │   ├── referential.py                       # Referential + ReferentialIndicator (N-N)
│   │   ├── emission_factor.py                   # EmissionFactor (catégorie, pays, FK source)
│   │   ├── required_document.py                 # RequiredDocument (FK fund/intermediary, FK source)
│   │   ├── simulation_factor.py                 # SimulationFactor (libellé, valeur, unité, FK source)
│   │   └── unsourced_flag.py                    # UnsourcedFlag (journal flag_unsourced)
│   ├── schemas/
│   │   └── source.py                            # Source/Create/Update/Verify/List/Citation
│   ├── modules/
│   │   └── sources/
│   │       ├── __init__.py
│   │       ├── router.py                        # GET/POST/PATCH /api/sources
│   │       ├── service.py                       # CRUD + verify + search full-text/embedding
│   │       ├── seed.py                          # 30+ sources verified (ADEME, IPCC, …)
│   │       └── migration_helpers.py             # helpers pour migrer EMISSION_FACTORS, ESGCriterion, SECTOR_WEIGHTS
│   ├── graph/
│   │   ├── tools/
│   │   │   └── sourcing_tools.py                # cite_source, search_source, flag_unsourced
│   │   └── validators/
│   │       ├── __init__.py
│   │       └── source_required.py               # Middleware post-tour LLM
│   └── prompts/
│       └── sourcing.py                          # SOURCING_INSTRUCTION partagée par les 7 prompts modules
└── tests/
    ├── unit/
    │   ├── test_source_schemas.py
    │   ├── test_source_service.py
    │   ├── test_sourcing_tools.py
    │   └── test_source_required_validator.py
    ├── integration/
    │   ├── test_sources_api.py
    │   └── test_sourcing_tools_in_graph.py
    └── llm_eval/
        └── test_cite_source_golden_set.py       # 10 cas eval LLM

frontend/
├── app/
│   ├── components/
│   │   └── sources/
│   │       ├── SourceLink.vue                   # picto cliquable inline + tooltip
│   │       ├── SourceModal.vue                  # modal détail (focus trap, aria, dark)
│   │       ├── SourceBadge.vue                  # badge verified/pending/outdated
│   │       └── SourcesList.vue                  # liste sources d'un objet
│   ├── composables/
│   │   └── useSources.ts                        # fetchSource, searchSources, cacheSource
│   ├── stores/
│   │   └── sources.ts                           # cache Pinia
│   └── pages/
│       └── sources/
│           └── index.vue                        # page PME read-only catalogue verified
└── tests/
    ├── unit/
    │   ├── SourceLink.test.ts
    │   ├── SourceModal.test.ts
    │   ├── SourceBadge.test.ts
    │   └── SourcesList.test.ts
    └── e2e/
        └── F01-fondations-sourcage-catalogue.spec.ts   # E2E Playwright
```

**Structure Decision** : application Web (Option 2 du template), monorepo `backend/` + `frontend/` déjà en place. Le module `sources` est colocalisé dans le monolithe FastAPI (`backend/app/modules/sources/`) suivant la même convention que `carbon`, `esg`, `financing`, `applications`. Côté frontend, les composants sont colocalisés dans `frontend/app/components/sources/` suivant la même convention que `chat/`, `dashboard/`, `esg/`, `credit/`. La nouvelle migration Alembic 020 reprend la numérotation séquentielle après 018 (interactive widgets) et 019 (multitenant en cours, F02), garantissant zéro collision Alembic.

## Phase 0 — Research

> Voir [research.md](./research.md) pour la consolidation des décisions techniques.

Sujets de recherche couverts :

1. **Workflow 4-yeux SQL** : meilleure stratégie pour empêcher `verified_by = captured_by` (CHECK constraint vs validation applicative). → Décision : CHECK constraint PostgreSQL (`captured_by != verified_by` quand `verified_by IS NOT NULL`) + validation applicative en doublon (defense-in-depth).

2. **Détection de chiffres dans une réponse LLM** : regex robuste vs parser AST de la réponse markdown. → Décision : regex compilée unique + liste blanche `IGNORED_NUMERIC_PATTERNS` pour les standards ISO et identifiants techniques. Validation cible : ≤ 5 % d'erreur sur golden set de 50 réponses.

3. **Indexation pgvector pour `search_source`** : HNSW vs IVFFlat sur catalogue 30-200 sources. → Décision : HNSW (m=16, ef_construction=64) qui scale gracieusement jusqu'à 10k sources sans tuning.

4. **Embeddings : modèle utilisé** : `text-embedding-3-small` OpenAI (déjà adopté par feature 008 financing). → Décision : réutilisation pour cohérence, dimension 1536.

5. **Annexe PDF — collecte des sources mobilisées** : capture en `contextvars.ContextVar` durant la génération du rapport vs reconstruction post-hoc depuis les tool_calls de la session. → Décision : reconstruction post-hoc depuis les tool_calls journalisés (`tool_call_logs` table existante) — plus simple, pas de fuite de contextvars en cas d'exception, déterministe.

6. **Validator middleware — point d'injection LangGraph** : nœud post-LLM dédié vs hook sur `astream_events`. → Décision : hook sur la fonction `stream_graph_events` (déjà refactorée en feature 012) qui collecte le texte final + tool_calls et invoque `source_required.validate()` avant émission de l'event final. Conserve le streaming utilisateur (token-by-token) tout en ré-écrivant la dernière chunk si rejet.

7. **Stratégie de seed des 30+ sources `verified`** : insertion via le service (validation Pydantic + workflow 4-yeux) ou bulk SQL en migration ? → Décision : seed via fonction `seed_sources()` appelée depuis la migration `020_create_sources_catalog.py` dans `data_upgrade()`. Marquage spécial `captured_by = 'system'` (un user système provisionné dans le seed) pour bypasser le workflow 4-yeux (cas Edge mentionné dans spec.md).

8. **Migration des constantes simulateur** : où stocker les libellés (`_SAVINGS_RATE`, `_CARBON_IMPACT_PER_MXOF`) ? → Décision : table `simulation_factors(code, label, value, unit, scope, source_id, status)` ; status = `pending` quand aucune source officielle ne couvre, libellé honnête signalant que la valeur reste à sourcer correctement.

**Sortie Phase 0** : `research.md` avec décision + rationale + alternatives évaluées pour chaque sujet.

## Phase 1 — Design & Contracts

> Voir [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md).

### Data model (data-model.md)

11 entités catalogue + 1 entité de journalisation, toutes liées à `Source` (FK NOT NULL après seed). Les transitions d'état sont documentées dans data-model.md :

- `Source` : `draft → pending → verified` (par admin différent du captured_by) ou `verified → outdated` (avec raison).
- Entités factuelles : `draft → published` (gated par `verification_status = verified` de toutes les sources liées, vérifié par trigger PostgreSQL ou check applicatif).

### Contracts

3 contrats publiés dans `contracts/` :

1. **`api-sources.md`** : 5 routes REST `/api/sources/*` (liste, détail, création admin, validation 4-yeux, marquage obsolète) + schémas Pydantic + codes d'erreur.

2. **`tools-sourcing.md`** : 3 tools LangChain :
   - `cite_source(source_id: UUID) → SourceCitation` (rejette si source non `verified`).
   - `search_source(query: str, publisher: str | None = None, limit: int = 5) → list[SourceSummary]` (full-text PostgreSQL + cosine pgvector, top-k).
   - `flag_unsourced(claim: str, reason: str) → FlagResult` (insertion table `unsourced_flags`).

3. **`validator-source-required.md`** : spécification du middleware post-tour LLM :
   - Entrée : `final_text: str`, `tool_calls: list[ToolCall]`.
   - Sortie : `ValidationResult` (passed: bool, missing_citations: list[str], substituted_text: str | None).
   - Algorithme : regex de détection → groupage en grappes → matching avec `cite_source` calls → ré-écriture si manque + retry max 1 → fallback texte si échec.

### Quickstart (quickstart.md)

Procédure pas-à-pas reproductible localement :

1. `git pull && git checkout feat/F01-fondations-sourcage-catalogue`
2. `cd backend && source venv/bin/activate && alembic upgrade head` (applique la migration 020)
3. `cd backend && python -m app.modules.sources.seed` (seed 30+ sources)
4. `cd backend && uvicorn app.main:app --reload --port 8000`
5. `cd frontend && npm install && npm run dev`
6. Ouvrir `http://localhost:3000/sources` (page catalogue PME)
7. Naviguer vers `http://localhost:3000/esg` après une évaluation : pictos `<SourceLink>` cliquables sur les scores
8. Tester le validator : envoyer dans le chat une question type « quel est le facteur d'émission de l'électricité réseau ? », vérifier que l'agent invoque `cite_source` et que la réponse contient un lien source dans la modal.

### Agent context update

> Mise à jour du `CLAUDE.md` racine pour ajouter F01 dans la section "Recent Changes" et "Active Technologies" (la commande `update-agent-context.sh` est appelée à la fin de Phase 1 par /speckit.plan ; cf. workflow).

## Phase 2 — Tasks (déclaration uniquement)

> Cette phase est exécutée par `/speckit.tasks` (et non par `/speckit.plan`). La sortie sera `tasks.md`.

Aperçu des phases de tâches prévues :

1. **Setup** (squelette de fichiers vides + dépendance Alembic).
2. **Foundational** (modèle Source + Enum + migration Alembic + tests modèle).
3. **US3 — Workflow administrateur 4-yeux** (P1, indépendant) : tests service `create_source`, `verify_source` (rejet si même user), `mark_outdated` ; routes `POST /api/sources`, `POST /api/sources/{id}/verify`, `POST /api/sources/{id}/mark-outdated`.
4. **US7 — Migration des données existantes** (P1, indépendant) : seed 30+ sources, migration `EMISSION_FACTORS`, `ESGCriterion`, `SECTOR_WEIGHTS`, constantes simulateur ; tests migration up/down/up.
5. **US1 — UI : pictos source cliquables et modal détail** (P1, dépend de Foundational) : tests `SourceLink.test.ts`, `SourceModal.test.ts`, `SourceBadge.test.ts` ; composants ; intégration sur ScoreCard, Recommendations, StrengthsBadges, CriteriaProgress, FactorsRadar, FinancingCard, carbon/results, financing/[id], applications/[id].
6. **US2 — Tools LangChain + validator backend** (P1, dépend de Foundational) : tests `test_sourcing_tools.py`, `test_source_required_validator.py` ; tools ; validator ; injection dans 7 nœuds LangGraph ; eval LLM golden set.
7. **US4 — Annexe PDF** (P2) : tests collecte `tool_call_logs` ; modification `esg_report.html` template ; tests rapport généré.
8. **US5 — Page /sources catalogue public** (P2) : tests E2E navigation page ; composant `SourcesList.vue`, page `pages/sources/index.vue`, store `sources.ts`, composable `useSources.ts`.
9. **US6 — Recherche full-text + pgvector** (P2) : tests `search_source` ; index HNSW pgvector ; route `GET /api/sources?search=...`.
10. **Polish & E2E final** : test E2E Playwright `F01-fondations-sourcage-catalogue.spec.ts` couvrant les 3 parcours critiques (clic SourceLink → modal, recherche page /sources, fund officer ouvre lien officiel) ; couverture ≥ 80 % vérifiée.

## Risques & garde-fous

- **Risque** : la regex de détection des chiffres est trop laxiste/stricte → faux positifs ou faux négatifs sur le validator. **Garde-fou** : itération sur le golden set de 50 réponses LLM annotées, ajustement de `IGNORED_NUMERIC_PATTERNS`, tolérance ≤ 5 % d'erreur (FR-018).
- **Risque** : le LLM se met à invoquer `flag_unsourced` systématiquement pour éviter le rejet → contournement du sourçage. **Garde-fou** : surveillance du taux de signalements ; alerte (journalisée) si > 20 % sur 24 h glissantes (SC-012).
- **Risque** : seed initial 30 sources insuffisant pour couvrir les chiffres affichés → application inutilisable. **Garde-fou** : phase pilote avec validation humaine quotidienne pendant 2 semaines, ajout itératif (en dehors du périmètre F01 mais documenté dans le runbook).
- **Risque** : performance `search_source` avec embeddings sur catalogue 1000+ sources. **Garde-fou** : index HNSW pgvector + limit hard à 5 résultats + cache Pinia côté frontend.
- **Risque** : conflit Alembic avec F02 (multitenant) qui crée aussi une migration en parallèle. **Garde-fou** : numérotation séquentielle 020 (F01) vs 021 (F02 attribué automatiquement par la spec_kit du sous-agent F02), validation `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` en Phase B.

## Complexity Tracking

> *Aucune dérogation à la constitution. Section vide.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (aucune) | — | — |
