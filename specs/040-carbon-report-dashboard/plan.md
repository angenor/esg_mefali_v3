# Implementation Plan: F21 — Dashboard par Offre + Carte Intermédiaires + Rapport Carbone PDF

**Branch**: `feat/F21-dashboard-par-offre-rapport-carbone` | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/040-carbon-report-dashboard/spec.md`

## Summary

Compléter le tableau de bord PME et livrer le rapport carbone PDF. Trois axes :

1. **Dashboard granularité par Offre** : refactor `_get_financing_summary` pour exposer `applications_by_offer: list[ApplicationCard]` (5 cards max) + `active_intermediaries[]` avec coordonnées (fallback capitale UEMOA) + scores cliquables F01.
2. **Carte UEMOA des intermédiaires actifs** sur le dashboard via `<MapBlock>` F11 + popup détaillé + état vide.
3. **Rapport carbone PDF** : nouveau module `app/modules/reports/carbon/` réutilisant l'architecture F06 (WeasyPrint + Jinja2 + matplotlib + BackgroundTasks), 9 sections sourcées F01, génération asynchrone, tool LangChain `generate_carbon_report`.

PAS DE MIGRATION (lecture seule des tables existantes + table `Report` réutilisée). Multi-tenant F02 / audit F03 hérités automatiquement. Sourçage F01 obligatoire (validator `source_required.py` + tool `cite_source`).

## Technical Context

**Language/Version** : Python 3.12 (backend) ; TypeScript 5.x strict (frontend)
**Primary Dependencies** : FastAPI, SQLAlchemy async, LangChain, LangGraph, WeasyPrint, Jinja2, matplotlib (backend) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Leaflet (via F11) (frontend)
**Storage** : PostgreSQL 16 + pgvector (lecture seule, aucune migration). Stockage PDF local sous `/uploads/reports/` (existe).
**Testing** : pytest + pytest-asyncio (backend) ; Vitest + Playwright (frontend)
**Target Platform** : Linux server (FastAPI) + Web SPA Nuxt 4
**Project Type** : Web application (backend + frontend séparés, monorepo)
**Performance Goals** :
- Dashboard p95 < 2 s pour ≤ 20 candidatures actives, ≤ 10 intermédiaires actifs (FR-028 / SC-001)
- Génération PDF carbone p95 < 10 s pour ≤ 30 entrées, ≤ 5 années (FR-029 / SC-003)
**Constraints** :
- AUCUNE migration Alembic (`alembic_or_migration = false`)
- Sourçage F01 obligatoire sur tous les chiffres carbone (scope 1/2/3, intensités, équivalences)
- Multi-tenant F02 (RLS PostgreSQL) — un account ne voit que ses données
- Audit F03 — toutes les écritures et générations tracées via hooks existants
- Format date FR `DD/MM/YYYY` partout dans le PDF
- Dark mode complet sur tous les composants frontend
- Couverture tests ≥ 80 % sur le périmètre F21
**Scale/Scope** :
- ~5 nouveaux composants Vue, ~3 pages refactorées
- 1 nouveau module backend (`reports/carbon/`), refactor service dashboard, 2 nouveaux endpoints REST, 1 tool LangChain
- ~120 tests prévus (backend + frontend + Playwright)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|---|---|---|
| I. Francophone-First & UEMOA | PASS | UI 100% FR, dates DD/MM/YYYY, fallback capitales UEMOA, accents respectés. |
| II. Architecture Modulaire | PASS | Module `reports/carbon/` isolé ; refactor dashboard limité à `_get_financing_summary` ; pas de couplage croisé. |
| III. Conversation-Driven UX | PASS | Tool LangChain `generate_carbon_report` permet déclenchement conversationnel ; complète l'expérience chat. |
| IV. Test-First (TDD) | PASS | Couverture cible ≥ 80 % ; tests unit + intégration + E2E Playwright ; tests rédigés avant impl. |
| V. Sécurité & Données | PASS | RLS F02 + audit F03 hérités ; validation Pydantic ; aucun secret embarqué ; téléchargement protégé par auth + ownership. |
| VI. Inclusivité | PASS | Composants ARIA, dark mode, états vides explicites, messages erreur FR clairs. |
| VII. Simplicité (YAGNI) | PASS | Aucune migration ; réutilise F06/F11/F01/F03/F13/F17 ; BackgroundTasks au lieu de Celery ; stockage local. |

**Stack obligatoire** : FastAPI + SQLAlchemy + Nuxt 4 + Pinia + TailwindCSS — respectée.
**Conventions de nommage** : routes API en kebab-case (`/api/reports/carbon/...`), tables BDD inchangées, fichiers Python snake_case, composants Vue PascalCase.
**Limites de taille** : prévu < 50 lignes/fonction, < 800 lignes/fichier (générateur PDF découpé en sections).
**ODD ciblés** : ODD 13 (Climat — rapport carbone valorisable), ODD 17 (Partenariats — visibilité offres × intermédiaires), ODD 12 (Production responsable — plan de réduction sourcé).

**Aucune violation à justifier.** Section Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/040-carbon-report-dashboard/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (REST endpoints + tool schemas)
│   ├── dashboard-summary.openapi.yml
│   ├── dashboard-active-intermediaries.openapi.yml
│   ├── reports-carbon-generate.openapi.yml
│   └── tool-generate-carbon-report.json
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── dashboard/
│   │   │   └── service.py                    # REFACTOR: _get_financing_summary → applications_by_offer + active_intermediaries
│   │   └── reports/
│   │       ├── carbon/                       # NEW
│   │       │   ├── __init__.py
│   │       │   ├── service.py                # generate_carbon_report(assessment_id, account_id)
│   │       │   ├── pdf_renderer.py           # WeasyPrint + Jinja2 orchestrator
│   │       │   ├── chart_builder.py          # matplotlib SVG (pie, bar)
│   │       │   ├── equivalences.py           # km voiture/vols/foyers/FCFA (sourcé F01)
│   │       │   ├── sources_collector.py      # collecte cite_source via tool_call_logs + F17 emission_factors
│   │       │   ├── schemas.py                # Pydantic v2: CarbonReportRequest/Response
│   │       │   └── exceptions.py             # AssessmentNotFinalizedError, ConcurrentGenerationError
│   │       ├── router.py                     # EXTEND: + POST /api/reports/carbon/{id}/generate
│   │       └── templates/                    # NEW templates (réutilise WeasyPrint config F06)
│   │           ├── carbon_report.html
│   │           └── _carbon_appendix_sources.html
│   ├── graph/
│   │   └── tools/
│   │       └── carbon_tools.py               # EXTEND: + generate_carbon_report tool
│   ├── core/
│   │   └── uemoa_capitals.py                 # NEW: 8 capitales (lat/lon) — fallback intermédiaires
│   └── api/
│       └── dashboard_router.py               # EXTEND: + GET /api/dashboard/active-intermediaries
└── tests/
    ├── unit/
    │   ├── modules/reports/carbon/
    │   │   ├── test_service.py
    │   │   ├── test_pdf_renderer.py
    │   │   ├── test_chart_builder.py
    │   │   ├── test_equivalences.py
    │   │   ├── test_sources_collector.py
    │   │   └── test_schemas.py
    │   ├── modules/dashboard/
    │   │   └── test_service_applications_by_offer.py
    │   ├── core/
    │   │   └── test_uemoa_capitals.py
    │   └── graph/tools/
    │       └── test_generate_carbon_report_tool.py
    └── integration/
        ├── test_carbon_report_endpoint.py     # POST generate + RLS multi-tenant
        ├── test_dashboard_summary.py          # applications_by_offer + active_intermediaries
        ├── test_dashboard_active_intermediaries.py
        └── test_audit_log_carbon_report.py    # F03 hooks tracés

frontend/
├── app/
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── ApplicationStatusCard.vue     # NEW
│   │   │   ├── ApplicationStatusCardList.vue # NEW (limite 5 + lien voir tout)
│   │   │   ├── IntermediariesMap.vue         # NEW (utilise <MapBlock> F11)
│   │   │   ├── ScoreCard.vue                 # EXTEND: + <SourceLink>
│   │   │   └── RecentActivityCard.vue        # NEW (lien /historique F03)
│   │   └── reports/
│   │       └── CarbonReportButton.vue        # NEW
│   ├── pages/
│   │   ├── dashboard.vue                     # REFACTOR
│   │   ├── reports/
│   │   │   └── index.vue                     # REFACTOR: tabs ESG | Carbone
│   │   └── carbon/
│   │       └── results.vue                   # EXTEND: bouton générer rapport
│   ├── composables/
│   │   ├── useDashboard.ts                   # EXTEND
│   │   └── useCarbonReports.ts               # NEW
│   ├── stores/
│   │   ├── dashboard.ts                      # EXTEND
│   │   └── reports.ts                        # EXTEND (tabs ESG/Carbon)
│   └── types/
│       ├── dashboard.ts                      # EXTEND: ApplicationCard, ActiveIntermediary
│       └── carbon-report.ts                  # NEW
└── tests/
    ├── components/
    │   ├── ApplicationStatusCard.test.ts
    │   ├── IntermediariesMap.test.ts
    │   ├── CarbonReportButton.test.ts
    │   └── ScoreCard.f21.test.ts
    ├── composables/
    │   └── useCarbonReports.test.ts
    └── e2e/
        └── F21-dashboard-carbon-report.spec.ts
```

**Structure Decision** : Monorepo Web (Option 2) avec backend FastAPI + frontend Nuxt 4, conforme architecture existante. Pas de nouveau projet ni service.

## Complexity Tracking

> Aucune violation de constitution — section vide.
