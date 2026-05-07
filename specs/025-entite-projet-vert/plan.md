# Implementation Plan: F06 — Entité Projet Vert (Module 1.3)

**Branch**: `feat/F06-entite-projet-vert` (alias SpecKit `025-entite-projet-vert`)
**Date**: 2026-05-07
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/025-entite-projet-vert/spec.md`

## Summary

F06 introduit l'entité `Project` (avec table satellite `project_documents`) pour matérialiser le triangle conceptuel `Entreprise 1—N Projets 1—N Candidatures vers Offres = (Fonds × Intermédiaire)` et débloquer le matching projet-offre (F09). Les pré-requis F01 (sources), F02 (multi-tenant + RLS), F03 (audit log Auditable) et F04 (Money typed) sont mergés sur `main` ; F06 étend ces fondations par un module métier complet (modèle SQLAlchemy, migration Alembic réversible avec backfill, services, schémas Pydantic, router REST, 7 tools LangChain, refactor pages profil, 7 composants Vue, composable, store Pinia). La migration `025_create_projects` (down_revision=`024_carbone_mix_uemoa`) ajoute en 5 étapes la table `projects`, la table `project_documents`, la colonne `project_id` sur `fund_applications` (NULL transitoire), un backfill par génération automatique de projets minimaux pour les `FundApplication` orphelines, puis applique `NOT NULL`. Les tests TDD couvrent : modèle + RLS, service CRUD, duplication, garde-fou suppression avec applications actives, intégration tools LLM (source_of_change=llm dans audit log), backfill idempotent. Tests E2E Playwright avec 4 scénarios couvrant la spec (US1 création UI, US2 création LLM, US3 duplication, US4 garde-fou suppression).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, LangGraph (≥0.2.0), LangChain (≥0.3.0), langchain-openai
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4, DOMPurify
**Storage** : PostgreSQL 16 + pgvector (extension), Alembic pour migrations, RLS PostgreSQL héritée F02
**Testing** :
- Backend : pytest, pytest-asyncio, pytest-cov (couverture ≥ 80 %)
- Frontend : Vitest + @vue/test-utils + @vitest/coverage-v8 + happy-dom
- E2E : Playwright (`@playwright/test`) avec backend mocké
**Target Platform** : Linux server (Docker) + navigateurs modernes
**Project Type** : Web application (backend + frontend séparés)
**Performance Goals** :
- `GET /api/projects` (liste paginée 25/page) en < 80 ms p95 (index `(account_id, status)` + `(account_id, maturity)`)
- `POST /api/projects` (insertion + audit log + 1 INSERT) en < 100 ms p95
- `POST /api/projects/{id}/duplicate` en < 150 ms p95
- Migration Alembic `up/down/up` en < 30 s sur base de dev (~1000 fund_applications historiques à backfiller)
- Aucune régression sur le module financements/applications existant (temps `POST /api/applications` inchangé ± 20 %)
**Constraints** :
- Multi-tenant strict (F02) : `projects.account_id` NOT NULL, RLS PostgreSQL ENABLE+FORCE + 2 policies (`pme_access_own_account`, `admin_full_access`)
- Auditable (F03) : `Project` hérite du mixin `Auditable` ; toute mutation tracée automatiquement
- Money typed (F04) : `target_amount` est une paire `target_amount_amount` (Numeric(20,2) NULL) + `target_amount_currency` (Char(3) NULL parmi XOF/EUR/USD/GBP/JPY) ; CHECK contrainte `target_amount_pair_consistency_chk` (les 2 NULL OU les 2 non-NULL)
- Sourçage (F01) : si `target_amount` ou `expected_impact_tco2e` cités par le LLM, validator `source_required.py` post-tour vérifie `cite_source` ou `flag_unsourced`
- Migration backfill non destructive : conservation des `FundApplication` existantes, `auto_generated=true` pour les projets de migration
- Dark mode obligatoire sur les 7 composants Vue créés
- Français avec accents dans tous les contenus utilisateur
**Scale/Scope** :
- 1 nouvelle table métier (`projects`) + 1 table de jointure (`project_documents`) + 1 colonne ajoutée (`fund_applications.project_id`)
- 7 tools LangChain dans nouveau fichier `app/graph/tools/project_tools.py`
- 1 module métier complet `app/modules/projects/` (service, router, schemas)
- 4 nouvelles pages frontend (`pages/profile/{company,projects/index,projects/new,projects/[id],projects/[id]/duplicate}.vue`)
- 7 nouveaux composants Vue dans `components/projects/`
- 1 composable `composables/useProjects.ts`, 1 store Pinia `stores/projects.ts`
- 1 spec E2E Playwright avec 4 scénarios

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| **I. Francophone-First & Contextualisation Africaine** | PASS | Tous les libellés UI en français avec accents (« Mes Projets », « Projet hérité », « Ajouter un document », « Dupliquer ce projet », « Refuser la suppression — applications actives »). Devise par défaut XOF (UEMOA) sur formulaire `target_amount`. Validation `location_country` pays UEMOA prioritaires (pas exclusive). |
| **II. Architecture Modulaire** | PASS | Modifications cantonnées à un nouveau module isolé `app/modules/projects/` + un nouveau fichier tools `app/graph/tools/project_tools.py` + un nouveau modèle `app/models/project.py` + un nouveau modèle `app/models/project_document.py`. Modifications légères de `app/api/chat.py` (loader projets dans state) et 3 prompts (`application.py`, `financing.py`) — pas de touche à `system.py`, `graph.py`, `main.py`, `deps.py`, `config.py`, `tool_selector.py` (zones interdites). |
| **III. Conversation-Driven UX** | PASS | Le LLM reste pilote : 7 tools LangChain symétriques aux endpoints API REST. La proposition de création de projet pré-rempli passe par `ask_interactive_question` (F18 déjà déployé) avec QCU « Oui / Je veux ajuster / Non ». Aucun formulaire bloquant ne contourne le chat. |
| **IV. Test-First (NON-NEGOTIABLE)** | PASS | Plan TDD : tests pytest écrits AVANT le service `ProjectService`, le router, les tools, la migration. Tests Vitest pour les 7 composants Vue. Couverture ≥ 80 %. Test E2E Playwright `F06-entite-projet-vert.spec.ts` avec 4 scénarios. Migration testée via `test_alembic_f06.py` (round-trip up/down/up). |
| **V. Sécurité & Protection des Données** | PASS | Aucun secret hardcodé. Validation Pydantic stricte sur `ProjectCreate`, `ProjectUpdate` (whitelists enum, bornes numériques, validateur Money). Requêtes SQLAlchemy ORM (pas de concaténation SQL). RLS PostgreSQL F02 honorée (account_id implicite via `app.current_account_id`). Tools LangChain protégés par scope `source_of_change_scope('llm')` (F03). Validator `source_required.py` (F01) appliqué sur les chiffres cités par le LLM. |
| **VI. Inclusivité & Accessibilité** | PASS | 7 composants ARIA-conformes : `ProjectCard` avec `role="article"` + `aria-label`, `ProjectStatusSelector` avec `role="combobox"` + `aria-expanded`, `DuplicateProjectModal` avec `role="dialog"` + `aria-modal="true"` + focus trap (réutilise `useFocusTrap` existant), `ProjectImpactBadges` avec `role="list"`. Keyboard-navigable. Dark mode complet. |
| **VII. Simplicité** | PASS | Réutilise le pattern modulaire des modules `company`, `audit`, `financing`. Pas d'introduction de Redis/Celery. Pas d'extension PostGIS (différée F11 cf. clarification Q5). Pas de polymorphism complexe : `objective_env` JSONB simple, pas de table satellite. Backfill SQL pur (pas de Python loop ; CTE Postgres). |
| **Invariant projet n°1 (sourçage F01)** | PASS | Tool `create_project` instruit dans son docstring d'appeler `cite_source(source_id)` si `target_amount`/`expected_impact_tco2e` non null. Validator post-tour applique la discipline. Tests `test_create_project_source_required.py` couvrent les 3 cas (avec source / sans source → fallback / flagged unsourced). |
| **Invariant projet n°2 (multi-tenant F02)** | PASS | `projects.account_id` UUID FK accounts.id NOT NULL. RLS PostgreSQL ENABLE+FORCE + 2 policies. Test `test_project_rls_cross_tenant.py` couvre 5 opérations (list, get, update, delete, duplicate) cross-tenant. |
| **Invariant projet n°3 (audit log F03)** | PASS | `Project` hérite de `Auditable`. Listener `before_flush` global capture create/update/delete. Tests `test_project_audit_log.py` couvrent les 3 sources_of_change (manual, llm, admin). |
| **Invariant projet n°4 (Money typed F04)** | PASS | `target_amount_amount` Numeric(20,2) + `target_amount_currency` Char(3) ; CHECK contrainte `target_amount_pair_consistency_chk`. Schéma Pydantic utilise `Money` factory `Money.from_columns`. UI utilise `<MoneyDisplay>`. |
| **Invariant projet n°7 (admin only catalogue)** | PASS | Aucun tool LLM ne mute le catalogue. Les tools `create_project`/`update_project`/etc. mutent l'entité métier `Project` (donnée user), pas le catalogue. |
| **Invariant projet n°8 (dark mode)** | PASS | Les 7 composants implémentent toutes les variantes `dark:` (`dark:bg-dark-card`, `dark:text-surface-dark-text`, `dark:border-dark-border`, `dark:hover:bg-dark-hover`). |
| **Invariant projet n°9 (réutilisabilité composants)** | PASS | Audit pré-implémentation : aucun composant équivalent dans `frontend/app/components/`. Réutilise `<MoneyDisplay>` (F04), `<SourceLink>` (F01), `<RoleBadge>` (F02), `useFocusTrap` (F18 héritage). Crée des composants génériques réutilisables (`ProjectStatusSelector` paramétrable via prop `statuses`, `ProjectImpactBadges` paramétrable via prop `impacts`). |
| **Invariant projet n°10 (français accents)** | PASS | Tous les libellés UI, messages d'erreur, prompts et docstrings français contiennent les accents (é, è, ê, à, ç, ù) : « Créé », « Bénéficiaires », « Hérité », « Référence », « Hectares restaurés ». |
| **Invariant projet n°11 (tests E2E exécutables)** | PASS | Spec Playwright `frontend/tests/e2e/F06-entite-projet-vert.spec.ts` avec 4 scénarios (US1, US2, US3, US4) ; helpers `F06-helpers.ts` pour mock backend. |
| **Invariant projet n°12 (couverture ≥ 80 %)** | PASS | Couverture cible ≥ 80 % sur les nouveaux modules `app/modules/projects/`, `app/graph/tools/project_tools.py`, `app/models/project.py`, `app/models/project_document.py`. |

**Décision constitutionnelle** : ✅ TOUS LES GATES PASSENT. Aucune violation à justifier dans Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/025-entite-projet-vert/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (interfaces backend)
│   ├── project-api.md
│   └── project-tools-langchain.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spec.md              # Feature specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 025_create_projects.py             # Migration F06 (down_revision=024_carbone_mix_uemoa)
├── app/
│   ├── core/
│   │   └── auditable.py                    # +Project dans AUDITABLE_MODELS, +ProjectDocument dans EXEMPT_MODELS
│   ├── models/
│   │   ├── project.py                      # NEW — Modèle SQLAlchemy Project (Auditable, UUIDMixin, TimestampMixin)
│   │   └── project_document.py             # NEW — Modèle SQLAlchemy ProjectDocument (table de jointure)
│   ├── modules/
│   │   └── projects/                       # NEW — Module métier complet
│   │       ├── __init__.py
│   │       ├── service.py                  # CRUD + duplicate + delete avec garde-fou + backfill helper
│   │       ├── router.py                   # 7 endpoints API REST (GET list, GET id, POST, PATCH, DELETE, POST duplicate, GET id/applications)
│   │       └── schemas.py                  # Pydantic v2 strict : ProjectCreate, ProjectRead, ProjectSummary, ProjectUpdate, ProjectDetail, DeleteResult, ProjectDocumentRead, ProjectFilters
│   ├── graph/tools/
│   │   └── project_tools.py                # NEW — 7 tools LangChain (list_projects, get_project, create_project, update_project, delete_project, duplicate_project, link_document_to_project)
│   ├── graph/
│   │   ├── tool_selector_config.py         # +profile_projects, +tools dans chat module + page mappings (respect MAX_TOOLS_PER_TURN=14)
│   │   └── nodes.py                        # +injection PROJECT_TOOLS dans chat ToolNode (conservé identique à F12 pour memory_tools)
│   ├── api/
│   │   └── chat.py                         # Refactor _load_profile_for_state → _load_full_context_for_state (+ projects actifs dans state)
│   ├── prompts/
│   │   ├── application.py                  # +mention « identifier le projet avant la candidature »
│   │   └── financing.py                    # +mention « identifier le projet avant la candidature »
│   ├── main.py                             # +include_router(projects.router.router, prefix='/api/projects', tags=['projects'])
│   └── api/deps.py                         # Inchangé (auth + RLS héritées F02)
└── tests/
    ├── unit/
    │   ├── test_project_model.py           # Tests modèle SQLAlchemy + contraintes Pydantic
    │   ├── test_project_schemas.py         # Tests Pydantic strict
    │   └── test_project_tools_unit.py      # Tests tools LangChain (mock service)
    ├── integration/
    │   ├── test_project_crud.py            # Tests CRUD via API REST
    │   ├── test_project_duplicate.py       # Tests duplication champ par champ
    │   ├── test_project_delete_guard.py    # Tests garde-fou suppression avec applications actives
    │   ├── test_project_rls_cross_tenant.py # Tests RLS isolation 2 comptes
    │   ├── test_project_audit_log.py       # Tests audit log F03 (manual/llm/admin)
    │   └── test_project_tools_integration.py # Tests tools LangChain via graph
    └── migrations/
        └── test_alembic_f06.py             # Tests up/down/up + backfill idempotent

frontend/
├── app/
│   ├── pages/
│   │   ├── profile.vue                     # Refactor → page index avec navigation onglets vers /profile/company et /profile/projects
│   │   └── profile/
│   │       ├── company.vue                 # NEW — Contenu actuel de pages/profile.vue déplacé ici
│   │       └── projects/
│   │           ├── index.vue               # NEW — Liste cards + filtres + pagination
│   │           ├── new.vue                 # NEW — Création
│   │           ├── [id].vue                # NEW — Édition
│   │           └── [id]/
│   │               └── duplicate.vue       # NEW — Duplication
│   ├── components/
│   │   └── projects/
│   │       ├── ProjectCard.vue             # NEW
│   │       ├── ProjectForm.vue             # NEW (mode='create' | 'edit' | 'duplicate')
│   │       ├── ProjectList.vue             # NEW
│   │       ├── ProjectImpactBadges.vue     # NEW
│   │       ├── ProjectStatusSelector.vue   # NEW
│   │       ├── DuplicateProjectModal.vue   # NEW
│   │       └── ProjectFilters.vue          # NEW
│   ├── composables/
│   │   └── useProjects.ts                  # NEW
│   ├── stores/
│   │   └── projects.ts                     # NEW (Pinia)
│   ├── types/
│   │   └── project.ts                      # NEW — Types TS Project, ProjectSummary, ProjectDetail, ProjectFilters, ObjectiveEnv
│   └── layouts/
│       └── default.vue                     # +lien sidebar « Mes Projets » avec badge count
└── tests/
    ├── unit/
    │   ├── ProjectCard.spec.ts             # Vitest
    │   ├── ProjectForm.spec.ts             # Vitest (validation, modes)
    │   ├── ProjectImpactBadges.spec.ts     # Vitest
    │   ├── ProjectStatusSelector.spec.ts   # Vitest (ARIA + interactions)
    │   ├── ProjectFilters.spec.ts          # Vitest
    │   ├── DuplicateProjectModal.spec.ts   # Vitest (focus trap)
    │   ├── useProjects.spec.ts             # Vitest (composable)
    │   └── projects.store.spec.ts          # Vitest (Pinia)
    └── e2e/
        ├── F06-entite-projet-vert.spec.ts  # Playwright 4 scénarios
        └── F06-helpers.ts                  # Helpers mock backend
```

**Structure Decision** : Architecture modulaire stricte respectant le pattern existant `app/modules/<feature>/` (cf. modules `audit`, `financing`, `applications`). Aucune modification des zones interdites (`graph.py`, `system.py`, `main.py` réduit à un `include_router`). Le composant `ProjectMap.vue` mentionné dans la fiche F06 source est explicitement DIFFÉRÉ POST-MVP via la feature F11 (`show_map`) — la clarification Q5 documente cette décision et FR-024 le précise.

## Phase 0 : Outline & Research

Voir `research.md` pour les décisions de design technique :

1. **Choix `objective_env` JSONB vs table satellite** : décision JSONB (clarification Q1).
2. **Stratégie backfill** : décision génération automatique avec `auto_generated=true` (clarification Q2).
3. **Garde-fou suppression** : décision soft-delete via `force=true` + `status='cancelled'` (clarification Q3).
4. **Statut sur duplication** : décision force `status='draft'` (clarification Q4).
5. **PostGIS différé** : décision report F11 (clarification Q5).
6. **Pattern enum maturity/status/financing_structure** : VARCHAR + CHECK applicatif Pydantic (cohérence avec stratégie F17 sur enums portables PG/SQLite).
7. **Réutilisation composants F04 + F01** : `<MoneyDisplay>`, `<SourceLink>`, `useFocusTrap`, store `ui` displayCurrencyMode.

## Phase 1 : Design & Contracts

Voir :
- `data-model.md` : schéma SQL complet (tables `projects`, `project_documents`, modifications `fund_applications`), modèles SQLAlchemy, contraintes CHECK, indexes, RLS policies.
- `contracts/project-api.md` : 7 endpoints REST avec request/response schemas Pydantic, codes HTTP, exemples curl.
- `contracts/project-tools-langchain.md` : 7 tools LangChain avec schemas Pydantic (`ProjectCreateArgs`, `ProjectUpdateArgs`, `DeleteProjectArgs`, etc.), exemples d'invocation et exemples de réponses.
- `quickstart.md` : guide de démarrage local (migrer, créer un projet via API, créer via tool LLM, dupliquer, supprimer avec garde-fou).

## Phase 2 : Tasks

Voir `tasks.md` (généré par `/speckit.tasks`).

## Complexity Tracking

| Sujet | Choix retenu | Alternative écartée | Rationale |
|-------|-------------|---------------------|-----------|
| Multi-valeurs `objective_env` | JSONB array | Table satellite `project_objectives` | Simplicité requête, pas de jointure pour affichage card, indexable GIN si besoin futur. Volumétrie attendue ≤ 8 valeurs/projet. |
| Backfill stratégie | Auto-génération avec `auto_generated=true` | Demande utilisateur post-migration | Migration non-bloquante : aucun utilisateur ne perd l'accès à ses applications. Le flag `auto_generated` permet à la PME de revoir/affiner. |
| Suppression garde-fou | Soft-delete via `force=true` + `status='cancelled'` | Hard delete + ON DELETE CASCADE | Préserve la traçabilité audit log F03. Permet la récupération si erreur PME. Hard delete possible post-MVP via job admin. |
| Coordonnées géographiques | Différé via F11 (PostGIS) | PostGIS dès F06 | Évite l'introduction d'une extension PostgreSQL non triviale en F06. F11 ajoutera la colonne `location_coordinates` quand `show_map` sera implémenté. |
| Status sur duplication | Force `draft` | Copie statut source | Évite la confusion d'avoir 2 projets simultanément en `funded`/`seeking_funding`. La duplication est un acte de préparation, pas de promotion. |
| Pattern enum portable | VARCHAR + CHECK applicatif Pydantic | ENUM PG natif | Cohérence avec stratégie F17 (`carbon.py` VALID_CATEGORIES) : compatibilité tests SQLite. Les enums PG natifs sont réservés aux entités infrastructure (audit_action, audit_source). |
| Module ESG/Carbone bilingues | Hors scope F06 | — | F06 reste cantonné au modèle Project. Les liens projet ↔ ESG/Carbone seront ajoutés par les features qui en ont besoin (F09 matching, F11 dashboard projet). |
