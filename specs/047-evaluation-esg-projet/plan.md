# Implementation Plan: Évaluation ESG-projet (extension F05 au mode projet)

**Branch**: `047-evaluation-esg-projet` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/047-evaluation-esg-projet/spec.md`

## Summary

Introduire un pipeline d'**évaluation ESG au niveau projet** dans Mefali, distinct de l'évaluation entreprise F05 (qui reste intacte). Le pipeline produit un **score 0..100 calculé** contre les référentiels projet déjà seedés F13 (IFC PS, GCF ESS, BOAD ESS), un **rapport ESIA-light PDF** consommable par les bailleurs (GCF/FEM/BOAD/AFD), et **alimente le sub-score `project_esg`** du matching projet-centric F045 (poids 0,10 inchangé). Le matching pilote automatiquement le référentiel selon le fonds ciblé (GCF→GCF ESS, BOAD→BOAD ESS, fonds sans ESS→IFC PS universel + flag `is_fallback=true`). La saisie est hybride : LLM via widgets F18 (US4 chat-first) **ou** wizard UI dédié `<ProjectEsgWizard>` (US1 form-first). Migration douce du champ `projects.project_esg_score` legacy F045 vers un cache lecture seule alimenté par listener SQLAlchemy ; rejet HTTP 409 si modification API tentée alors qu'une évaluation finalisée existe.

Migration Alembic 047 introduit **2 nouvelles tables** (`project_esg_assessments`, `project_esg_criterion_responses`) avec RLS F02 strict, audit log F03 via mixin `Auditable`, sourçage F01 obligatoire sur chaque critère. F05 entreprise reste strictement inchangée — aucun discriminant ajouté à `ESGAssessment`. La pondération du score réutilise `criterion.weight` du catalogue F13.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy async, Pydantic v2, Alembic, LangGraph (>=0.2), LangChain (>=0.3), WeasyPrint, Jinja2, matplotlib (backend) ; Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS, Chart.js (frontend)
**Storage**: PostgreSQL 16 + pgvector. **2 nouvelles tables** (`project_esg_assessments`, `project_esg_criterion_responses`) + 1 migration Alembic 047. Réutilisation des tables existantes `projects` (F045), `referentials` + `criteria` (F13), `sources` (F01), `audit_log` (F03).
**Testing**: pytest + httpx AsyncClient + pytest-asyncio (backend), Vitest (unit/composables), Playwright (E2E frontend)
**Target Platform**: Web (desktop + mobile responsive ≥ 360 px) ; dark mode obligatoire ; accessibilité WCAG AA visée (ARIA FR, navigation clavier, focus visible)
**Project Type**: Web application monolithe modulaire (backend FastAPI + frontend Nuxt 4 existants, principe constitutionnel VII Simplicité)
**Performance Goals**: Finalisation évaluation ≤ 3 s p95 (calcul score + UPSERT + listener async) ; rapport ESIA-light PDF ≤ 30 s p95 pour 20 critères + 3 graphiques ; matching avec consommation score projet ≤ 1 s additionnel ; LLM ≤ 12 widgets F18 et ≤ 3 tours utilisateur pour boucler une évaluation
**Constraints**: RLS F02 strict (ENABLE+FORCE, 2 policies minimum) ; F01 sourçage obligatoire avec validator post-LLM retry 1× ; F03 audit append-only via mixin `Auditable` ; F12 mémoire contextuelle pgvector pour reprise multi-session ; F18 1 question pending max/conversation ; F23 skill draft initial, publication conditionnée à eval ≥ 90 % ; F045 rétrocompat 2 sprints du champ `project_esg_score` ; 0 régression sur la suite baseline 3 136 tests passants
**Scale/Scope**: 3 référentiels MVP × ~15-20 critères = ~50-60 critères catalogués F13 ; jusqu'à ~10 évaluations finalisées par projet (5 référentiels × 2 versions), ~100 projets actifs par tenant en cible 2 ans ; rapport ESIA-light ≤ 30 pages PDF

## Constitution Check

*Évaluation contre `.specify/memory/constitution.md` (v1.0.0, ratifié 2026-03-30)*

| Principe | Statut | Justification |
|---|---|---|
| I. Francophone-First & Contextualisation Africaine | **PASS** | UI/UX 100 % FR avec accents ; code EN. Référentiels MVP incluent BOAD ESS (UEMOA) en parallèle d'IFC PS et GCF ESS. Public cible PME informelle UEMOA explicitement adressé via US1 (cf. cas coopérative agricole Togo). |
| II. Architecture Modulaire | **PASS** | Nouveau sous-module `backend/app/modules/esg/project_*` clairement séparé de `app/modules/esg/` entreprise (F05). Frontières définies par tables dédiées et API publique propre. Aucune dépendance circulaire avec F05. |
| III. Conversation-Driven UX | **PASS** | US4 LLM-first via skill F23 `skill_project_esg_assessment` + widgets F18 (qcu/qcm/justification) ; profilage progressif via mémoire contextuelle F12. Le wizard UI dédié US1 reste cohérent avec l'identité conversationnelle car il se synchronise avec la même `ProjectEsgAssessment` que le chat. |
| IV. Test-First (NON-NEGOTIABLE) | **PASS** | TDD strict : tests pytest backend AVANT implémentation des services et tools ; tests Vitest AVANT composants Vue et composable ; Playwright E2E pour US1/US2/US4. Cible couverture ≥ 80 % (SC-004). Suite baseline 3 136 tests reste verte (SC-005). |
| V. Sécurité & Protection des Données | **PASS** | RLS F02 `ENABLE+FORCE` + 2 policies (`pme_access_own_account`, `admin_full_access`) sur les 2 nouvelles tables ; aucun secret hard-codé ; entrées validées via Pydantic v2 strict ; rate limiting via middleware existant ; sourçage F01 obligatoire avec workflow 4-yeux pour les sources nouvelles. Test `test_*_rls.py` obligatoire pour chaque endpoint (R4 mitigation). |
| VI. Inclusivité & Accessibilité | **PASS** | Dark mode obligatoire (FR-040) ; ARIA labels FR complets, navigation clavier, focus visible (FR-041) ; reprise multi-session pour connexions instables (US4/F12) ; messages d'erreur FR clairs et actionnables (refus finalisation, refus rapport `draft`, conflit 409 sur saisie F045 legacy). Mode guidé natif via skill F23 conversationnel. |
| VII. Simplicité & YAGNI | **PASS** | Réutilise le pattern `ReferentialScore` F13 et le moteur `compute_referential_score_for_offer` côté entreprise (extension pour le projet, pas nouveau moteur). Réutilise le pipeline rapport F06 (WeasyPrint + Jinja2 + matplotlib) avec un template additionnel `_esia_report.html`. Réutilise les composants `<DualScoreDisplay>`, `<MissingProjectCriteriaList>`, `<SourceLink>` F045. Aucun microservice, aucun job asynchrone, aucun stockage externe ajouté pour le MVP. |

**Gate Result** : **PASS** — aucun écart constitutionnel non justifié. Section « Complexity Tracking » laissée vide.

## Project Structure

### Documentation (this feature)

```text
specs/047-evaluation-esg-projet/
├── plan.md              # Ce fichier
├── spec.md              # Spécification fonctionnelle (avec Clarifications Session 2026-05-21)
├── research.md          # Phase 0 — décisions techniques D1..D10
├── data-model.md        # Phase 1 — schémas tables + DTO Pydantic
├── quickstart.md        # Phase 1 — validation manuelle US1..US5
├── contracts/           # Phase 1 — OpenAPI YAML par endpoint nouveau
│   ├── project-esg-assessment.openapi.yaml
│   └── project-esg-report.openapi.yaml
├── checklists/
│   └── requirements.md  # Validation spec quality (créée par /speckit.specify)
├── PROMPTS.md           # Prompt utilisateur source
└── tasks.md             # Généré par /speckit.tasks (hors-scope ici)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 047_project_esg_assessments.py        # NEW — migration round-trippable
├── app/
│   ├── modules/
│   │   └── esg/
│   │       ├── project_models.py                  # NEW — ProjectEsgAssessment, ProjectEsgCriterionResponse
│   │       ├── project_schemas.py                 # NEW — DTO Pydantic v2 strict
│   │       ├── project_service.py                 # NEW — create/save_criterion/finalize/get/list (RLS-safe)
│   │       ├── project_scoring.py                 # NEW — calcul score 0..100 (extension F13 weight)
│   │       ├── project_listener.py                # NEW — after_insert/after_update → snapshot projects.project_esg_score
│   │       ├── project_router.py                  # NEW — /api/projects/{id}/esg-assessment/*
│   │       └── project_report.py                  # NEW — pipeline ESIA-light (WeasyPrint + Jinja2 + matplotlib)
│   ├── graph/
│   │   ├── nodes.py                                # MODIFIED — esg_scoring_node : router target_kind (no F05 mutation)
│   │   └── tools/
│   │       └── project_esg_tools.py                # NEW — 5 tools LangChain (create/save_criterion/finalize/get/list)
│   ├── modules/financing/
│   │   └── matching_service.py                    # MODIFIED — _compute_project_score consomme ProjectEsgAssessment + fallback F045 + IFC PS si pas d'ESS
│   ├── modules/projects/
│   │   ├── router.py                              # MODIFIED — endpoint PATCH /projects/{id} rejette project_esg_score si évaluation finalisée (409)
│   │   └── service.py                             # MODIFIED — listener wiring + project_esg_score read-only enforcement
│   ├── modules/skills/
│   │   └── seeds/
│   │       └── skill_project_esg_assessment.json  # NEW — skill F23 draft (4 golden examples US1-US4)
│   ├── scripts/
│   │   └── seed_sources_047.py                    # NEW — 3 sources F01 (IFC PS, GCF ESS 2022, BOAD ESS) + criteria seed idempotent
│   └── templates/
│       └── reports/
│           └── _esia_report.html                  # NEW — Jinja2 ESIA-light 5-7 sections + annexe F01
└── tests/
    └── modules/esg/project/
        ├── test_project_service_create.py         # NEW
        ├── test_project_service_save_criterion.py # NEW
        ├── test_project_service_finalize.py       # NEW
        ├── test_project_scoring_weighted.py       # NEW — pondération criterion.weight F13
        ├── test_project_listener_snapshot.py      # NEW — debounce 30s + snapshot
        ├── test_project_router_rls.py             # NEW — RLS tenant tiers retourne 404
        ├── test_project_router_409_legacy.py      # NEW — PATCH project_esg_score quand évaluation existe
        ├── test_project_esg_tools.py              # NEW — 5 tools LangChain
        ├── test_project_report_pdf.py             # NEW — 7 sections + annexe F01 + ≥ 1 graphique
        ├── test_matching_consumes_project_esg.py  # NEW — priorité calculé > F045 > 0
        ├── test_matching_fallback_ifc_ps.py       # NEW — flag is_fallback=true
        └── test_skill_project_esg_eval.py         # NEW — eval gating ≥ 90 %

frontend/
├── app/
│   ├── pages/
│   │   └── profile/projects/[id]/
│   │       └── esg.vue                            # NEW — page wizard ESG-projet (URL provisoire, Q5 différée)
│   ├── components/esg/project/
│   │   ├── ProjectEsgWizard.vue                   # NEW — orchestrateur multi-étapes
│   │   ├── EsgReferentialPicker.vue               # NEW — choix IFC PS / GCF ESS / BOAD ESS
│   │   ├── EsgCriterionWidget.vue                 # NEW — un critère avec qcu/qcm/justification + SourceLink
│   │   ├── EsgScoreDisplay.vue                    # NEW — score 0..100 + breakdown par standard
│   │   ├── EsgReportPreview.vue                   # NEW — preview avant export PDF
│   │   ├── EsgTargetBadge.vue                     # NEW — badge « ESG Projet » vs « ESG Entreprise » (R1)
│   │   └── ProjectEsgMatchImpact.vue              # NEW — bloc « Impact sur matching » (US4 étape 7)
│   ├── composables/
│   │   └── useProjectEsg.ts                       # NEW — fetch + état évaluation + finalize + report
│   ├── stores/
│   │   └── projectEsg.ts                          # NEW — Pinia : évaluation courante, brouillon, critères, score
│   └── types/
│       └── projectEsg.ts                          # NEW — miroir TypeScript DTO Pydantic
└── tests/
    ├── unit/esg/project/
    │   ├── ProjectEsgWizard.spec.ts               # NEW
    │   ├── EsgCriterionWidget.spec.ts             # NEW
    │   ├── useProjectEsg.spec.ts                  # NEW
    │   └── projectEsg.store.spec.ts               # NEW
    └── e2e/
        └── project-esg-assessment.spec.ts         # NEW — US1 + US2 + US4 parcours bout-en-bout

docs/
└── esg-projet-vs-entreprise.md                    # NEW — note clarification UX/support (R1 mitigation)
```

**Structure Decision** : application web existante monolithique (backend FastAPI + frontend Nuxt 4). La feature crée un **nouveau sous-module isolé** `app/modules/esg/project_*` parallèle au sous-module entreprise existant ; côté frontend, un nouveau dossier de composants `components/esg/project/` et une page Vue dédiée. Aucune création de top-level. Réutilisation maximale des composants visuels F045 (`<DualScoreDisplay>`, `<MissingProjectCriteriaList>`, `<SourceLink>`) et du pipeline rapport F06.

## Complexity Tracking

> Aucun écart constitutionnel à justifier — section vide.
