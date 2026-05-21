# Implementation Plan: Matching financement vert centré projet (045)

**Branch**: `045-matching-projet-centric` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/045-matching-projet-centric/spec.md`

## Summary

Recentrer le scoring des matches projet/offre sur les attributs du **projet** (impact CO2, taxonomie verte UEMOA, thèmes prioritaires GCF, bénéficiaires, inclusion sociale, ESG projet) plutôt que sur la **santé entreprise**. Deux scores indépendants (`project_score`, `company_score`) sont calculés et persistés séparément dans la table `offer_matches` (enrichie par migration 045), sans formule d'agrégation cachée. L'agent conversationnel pilote le cycle de vie complet du projet en chat (création → matching → modification → re-matching) via un nouveau tool `match_funds_for_project` et un skill F23 dédié `skill_match_project_funds`. La feature cohabite avec F14 (commit `c9204c8`) pendant 2 sprints minimum : le champ `global_score` est conservé en lecture seule, le tri par défaut bascule vers `project_score DESC`.

**Approche technique** : extension du module `app/modules/financing/` (refactor de `matching_service.compute_offer_match` pour produire deux scores au lieu d'un), ajout de 5 colonnes à `projects` (taxonomie UEMOA, thèmes GCF, gender, vulnerable populations, projet ESG) + 4 colonnes à `offer_matches` (project/company scores, breakdown, divergence), nouveau tool LangChain dans `project_tools.py`, nouveau skill F23 seedé via `seed_skills.py`, composants Vue dédiés (`<DualScoreDisplay>`, `<ProjectMatchCard>`), section UI sur `/profile/projects/[id]`. Seed obligatoire des sources F01 verified (taxonomie UEMOA, GCF themes, GCF gender policy).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async, Alembic, Pydantic v2 strict, LangChain ≥ 0.3, LangGraph ≥ 0.2, asyncpg, langchain-openai (embeddings text-embedding-3-small via OpenRouter)
- Frontend : Nuxt 4, Vue 3 Composition API (`<script setup lang="ts">`), Pinia, TailwindCSS, Chart.js, Playwright
**Storage** : PostgreSQL 16 + pgvector (HNSW cosine), asyncpg ; SQLite in-memory pour tests
**Testing** : pytest backend (avec pytest-asyncio, pytest-cov), Vitest + @vitest/coverage-v8 frontend, Playwright pour E2E
**Target Platform** : Linux server (backend uvicorn), Web (frontend Nuxt SSR/SPA)
**Project Type** : Web application (backend + frontend monorepo)
**Performance Goals** :
- Tool `match_funds_for_project` : retour < 2 s pour projet avec ≤ 50 offres publiées
- Recalcul incrémental après update projet : < 5 s pour 50 offres (en background)
- E2E Playwright parcours critique : < 90 s (3 tours de conversation max)
**Constraints** :
- Multi-tenant RLS F02 obligatoire (account_id NOT NULL, policies PME/ADMIN)
- Audit log F03 sur toute mutation critique (mixin `Auditable` déjà actif sur Project)
- Money typed F04 sur target_amount (conversion via `currency_service` pour size_match)
- Sources F01 verified obligatoires (validator `source_required.py` retry 1× + fallback texte)
- Dark mode obligatoire sur tout nouveau composant (Tailwind `dark:` variants)
- Francophone-first : accents é è ê à ç dans tous les labels FR (UI + tools args Literal)
- Aucune régression sur les 2900+ tests backend baseline (post-F25)
- Round-trip Alembic up/down/up validé sur PostgreSQL
**Scale/Scope** :
- ~50 offres publiées max par PME (cap dur recalcul)
- 5 user stories (P1 ×2, P2 ×2, P3 ×1)
- 1 migration Alembic (045)
- +1 tool LangChain (`match_funds_for_project`) ; tools projet existants (8) inchangés
- +1 skill F23 (`skill_match_project_funds`)
- +1 endpoint REST (`POST /api/projects/{project_id}/match-funds`) en complément de F14
- ~6 composants Vue nouveaux ou modifiés (`<DualScoreDisplay>`, `<ProjectMatchCard>`, `<MissingProjectCriteriaList>`, `<ProjectFundsSection>`, extension `<MatchCard>` F11, extension `OffersCompatibleSection` F14)
- ~3-5 sources F01 nouvelles à seeder (taxonomie verte UEMOA, GCF priority themes, GCF gender policy 2019)
- `MAX_TOOLS_PER_TURN` actuel = 29 → +1 tool reste largement sous la cap

## Constitution Check

*GATE : doit passer avant Phase 0 research. Re-check après Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| **I. Francophone-First & Contextualisation Africaine** | ✅ PASS | FR-017 impose les libellés FR avec accents sur enums (`gcf_priority_themes`, `vulnerable_populations`). Taxonomie verte UEMOA priorisée avant standards internationaux (cohérent avec F01). Secteur informel adressé directement (US1). |
| **II. Architecture Modulaire** | ✅ PASS | Extension du module `financing` existant et du module `projects` (F06) — pas de nouveau module. Communication via schemas Pydantic v2 strict. Pas de couplage entre modules nouveau. |
| **III. Conversation-Driven UX** | ✅ PASS | User Story 2 (P1) entièrement chat-driven. Tool `match_funds_for_project` exposé au LLM. Skill F23 `skill_match_project_funds` pilote la séquence conversationnelle. Aucun handover UI obligatoire pour le parcours principal. |
| **IV. Test-First (NON-NEGOTIABLE)** | ✅ PASS | FR-018 ≥ 80 % coverage backend + frontend. FR-019 E2E Playwright. TDD imposé par le workflow `/speckit.tasks` (générera les tests avant le code). |
| **V. Sécurité & Protection des Données** | ✅ PASS | RLS F02 (FR-011), audit F03 (FR-012), sources F01 verified obligatoires (FR-005). Aucun secret hardcodé. Validation Pydantic v2 strict sur tous les schemas. |
| **VI. Inclusivité & Accessibilité** | ✅ PASS | `gender_inclusion` et `vulnerable_populations` (5 catégories) intégrés au scoring — la feature elle-même renforce l'inclusion sociale. Dark mode obligatoire (FR-016). Empty states FR clairs et actionnables (US5). |
| **VII. Simplicité & YAGNI** | ✅ PASS | Pas de microservice. Pas de Redis/Celery (synchrone + BackgroundTasks). Pas de feature flag obligatoire (rollback Nuxt possible mais facultatif). Enrichit `offer_matches` plutôt que créer une nouvelle table. Pas de slider admin (Q1=C, simplicité gagnée). |

**Verdict** : ✅ Aucune violation. La feature passe les 7 gates de la constitution. Pas de Complexity Tracking nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/045-matching-projet-centric/
├── plan.md              # Ce fichier (/speckit.plan output)
├── spec.md              # /speckit.specify output
├── research.md          # Phase 0 output (/speckit.plan)
├── data-model.md        # Phase 1 output (/speckit.plan)
├── quickstart.md        # Phase 1 output (/speckit.plan)
├── contracts/           # Phase 1 output (/speckit.plan)
│   ├── api-endpoints.md
│   ├── tool-match-funds-for-project.md
│   └── skill-match-project-funds.md
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — pas créé par /speckit.plan)
```

### Source Code (repository root)

Structure monorepo web (backend + frontend) — extension des modules existants.

```text
backend/
├── alembic/
│   └── versions/
│       └── 045_xxxx_matching_projet_centric.py   # Nouvelle migration
├── app/
│   ├── models/
│   │   ├── project.py                            # MAJ : +5 colonnes
│   │   └── offer_match.py                        # MAJ : +4 colonnes, global_score déprécié
│   ├── modules/
│   │   ├── financing/
│   │   │   ├── matching_service.py               # MAJ : refactor compute_offer_match → split project/company
│   │   │   ├── matching_router.py                # MAJ : nouvel endpoint POST /match-funds
│   │   │   ├── matching_schemas.py               # MAJ : MatchFundsRequest, ProjectScoreBreakdown, DivergenceExplanation
│   │   │   └── divergence_templates.py           # NOUVEAU : gabarits FR de divergence_explanation
│   │   └── projects/
│   │       ├── schemas.py                        # MAJ : ProjectBase/Create/Update +5 champs
│   │       └── service.py                        # MAJ : event listener after_update (debounce 30s)
│   ├── graph/
│   │   └── tools/
│   │       └── project_tools.py                  # MAJ : +match_funds_for_project tool
│   ├── scripts/
│   │   ├── seed_sources_045.py                   # NOUVEAU : seed sources F01 verified (taxonomie UEMOA, GCF themes, GCF gender)
│   │   └── seed_skills.py                        # MAJ : +skill_match_project_funds
│   └── core/
│       └── matching_constants.py                 # NOUVEAU : labels FR enums (gcf themes, vulnerable populations)
└── tests/
    ├── unit/
    │   ├── test_matching_service_project_score.py    # NOUVEAU
    │   ├── test_matching_service_company_score.py    # NOUVEAU
    │   ├── test_divergence_templates.py              # NOUVEAU
    │   └── test_project_after_update_listener.py     # NOUVEAU
    ├── integration/
    │   ├── test_match_funds_endpoint.py              # NOUVEAU
    │   ├── test_match_funds_tool.py                  # NOUVEAU
    │   ├── test_migration_045_roundtrip.py           # NOUVEAU
    │   └── test_skill_match_project_funds.py         # NOUVEAU
    └── e2e/
        └── (couvert côté frontend Playwright)

frontend/
├── app/
│   ├── components/
│   │   ├── financing/
│   │   │   ├── DualScoreDisplay.vue              # NOUVEAU : 2 scores côte à côte + badge divergence
│   │   │   ├── ProjectMatchCard.vue              # NOUVEAU : MatchCard étendu avec project/company
│   │   │   ├── MissingProjectCriteriaList.vue    # NOUVEAU : critères manquants avec SourceLink
│   │   │   ├── ProjectFundsSection.vue           # NOUVEAU : section "Fonds compatibles" sur fiche projet
│   │   │   └── DivergenceBadge.vue               # NOUVEAU : badge coloré écart project/company
│   │   └── projects/
│   │       └── ProjectMatchAlertToggle.vue       # MAJ ou réutilise F14 MatchAlertToggle
│   ├── composables/
│   │   ├── useProjectMatching.ts                 # NOUVEAU : 4 méthodes (matchFunds, getMatches, recompute, getDetails)
│   │   └── useDivergenceTooltip.ts               # NOUVEAU : gabarits FR de tooltip
│   ├── stores/
│   │   └── projectMatching.ts                    # NOUVEAU : state matches par project_id
│   ├── pages/
│   │   ├── profile/
│   │   │   └── projects/
│   │   │       └── [id].vue                      # MAJ : intègre <ProjectFundsSection>
│   │   └── financing/
│   │       └── offers/
│   │           └── [offerId].vue                 # MAJ : section "Mon score pour ce projet" avec <DualScoreDisplay>
│   └── types/
│       └── projectMatching.ts                    # NOUVEAU : types ProjectScoreBreakdown, DivergenceExplanation, MatchFundsResponse
└── tests/
    ├── unit/
    │   ├── DualScoreDisplay.spec.ts
    │   ├── ProjectMatchCard.spec.ts
    │   ├── MissingProjectCriteriaList.spec.ts
    │   └── ProjectFundsSection.spec.ts
    ├── integration/
    │   └── useProjectMatching.spec.ts
    └── e2e/
        └── matching-project-centric.spec.ts      # NOUVEAU : parcours critique chat → matching → fiche fonds
```

**Structure Decision** : monorepo web app (backend FastAPI + frontend Nuxt 4). La feature étend les modules existants `financing` et `projects` sans créer de nouveau module — conforme au principe II de la constitution (architecture modulaire avec frontières claires). Les composants Vue sont placés dans `components/financing/` (proches du parcours utilisateur) tandis que la logique métier reste côté backend. Un seul nouveau dossier de constantes (`backend/app/core/matching_constants.py`) pour centraliser les libellés FR des enums et permettre le partage entre validators Pydantic et tooltips frontend (via génération de types ou duplication contrôlée — à trancher en Phase 0).

## Complexity Tracking

> *Fill ONLY if Constitution Check has violations that must be justified*

Aucune violation. Table vide.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| _(none)_ | _(none)_ | _(none)_ |
