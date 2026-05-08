# Implementation Plan: F15 — Génération de Dossiers de Candidature par Offre

**Branch** : `feat/F15-generation-dossiers-par-offre` | **Date** : 2026-05-08 | **Spec** : [spec.md](./spec.md)
**Input** : Feature specification from `/specs/041-f15-dossiers-offre/spec.md`

## Summary

F15 introduit l'entité `Template_dossier` rattachée à une offre F07 (couple Fonds × Intermédiaire), à une Skill F23 (`prompt_expert` métier) et à une source F01 vérifiée. Les candidatures `FundApplication` sont enrichies de `template_id`, `language` (`fr`/`en`), `attestation_id` (lien optionnel F08) et `snapshot_data` JSONB immuable au moment de la soumission (versioning F04). Le service de génération est refactoré pour : (1) charger le profil PME réel (correction du bug `company_context` codé en dur), (2) router le bon `prompt_expert` selon la langue, (3) calculer une checklist union docs fonds + intermédiaire dédupliquée. Trois bugs critiques sont corrigés : `company_context` hardcodé, `AttributeError fund.max_amount` dans `_simulate_financing`, doublon tool LangChain `create_fund_application`. Migration Alembic 041 ajoute la table `templates_dossier` et 4 colonnes sur `fund_applications` avec backfill template fallback par `target_type`. Frontend Nuxt enrichit les pages candidature avec sélecteur langue (widget F10), checklist union, attache attestation, tabs section. Conformité multi-tenant F02, audit F03, dark mode obligatoire.

## Technical Context

**Language/Version** : Python 3.12 (backend) ; TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, LangGraph, LangChain, langchain-openai, WeasyPrint, Jinja2, python-docx (legacy DOCX), httpx (tests)
- Frontend : Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Playwright (E2E)
**Storage** :
- PostgreSQL 16 + pgvector (existant). Nouvelle table `templates_dossier` + colonnes ajoutées sur `fund_applications`.
- Stockage fichiers : local sous `/uploads/applications/<account_id>/<application_id>/` (cohérent F06 PDF).
**Testing** : pytest (backend, asyncio + httpx + alembic round-trip) ; Vitest (frontend unit) ; Playwright (E2E) — couverture cible ≥ 80 %.
**Target Platform** : Linux server (FastAPI/Uvicorn) + navigateurs modernes (frontend SSR/CSR Nuxt 4).
**Project Type** : Web application monolithe modulaire (backend `/backend`, frontend `/frontend`).
**Performance Goals** :
- Génération première section ≤ 15 s p95 (SC-007).
- Endpoint REST CRUD template < 300 ms p95.
- Calcul checklist union < 50 ms (5 paires fonds/intermédiaire moyennes).
- Export PDF avec attestation ≤ 8 s p95 (réutilise pipeline F06).
**Constraints** :
- Multi-tenant F02 : RLS PostgreSQL ENABLE+FORCE sur `templates_dossier` (admin-only ou exempt selon décision research) ; `fund_applications` reste sous policies F02 existantes.
- Audit F03 : `Template_dossier` et `FundApplication` portent le mixin `Auditable` (mutation = ligne `audit_log`).
- Versioning F04 : `Template_dossier` hérite du mixin `VersioningMixin` (`version`, `valid_from`, `valid_to`, `superseded_by`). `snapshot_data` réutilise le pattern `build_snapshot_data` F04 existant.
- Sourçage F01 : `source_id` FK NOT NULL sur templates ; validator `source_required` post-tour LLM s'applique aux sections générées.
- Dark mode obligatoire sur tous les composants Nuxt (variantes `dark:`).
- FR avec accents (é, è, ê, à, ç, ù) obligatoires dans les contenus.
**Scale/Scope** :
- 50 templates publiés à terme (10 prioritaires en seed F15) × 2 langues = ≤ 100 lignes `templates_dossier` v1.
- ~5 000 candidatures projetées sur 12 mois (volumétrie pilote PME UEMOA).
- Snapshots JSONB ~50-100 KB chacun (warning > 100 KB cohérent avec F04).
- Couverture tests ≥ 80 % sur le périmètre F15 strict (model + service + router + tools + frontend composants/composables).

## Constitution Check

*Gate Phase 0 → 1 et re-check post-Phase 1.*

| Principe | Conformité F15 |
|----------|----------------|
| **I. Francophone-First & Contextualisation Africaine** | UI 100 % FR, code anglais, commentaires FR. Templates seed FR par défaut (4 instruments) + 2 templates EN pour offres GCF Direct Access. Référentiels UEMOA/BCEAO référencés via `source_id` F01. Multilingue FR/EN strict (autres langues hors scope MVP). |
| **II. Architecture Modulaire** | Module `app/modules/applications/` étendu (déjà existant) ; nouveau sous-module `templates/`. Frontières claires avec F07 (Offer), F23 (Skills), F08 (Attestation). API internes via Pydantic v2 strict. |
| **III. Conversation-Driven UX** | Sélection langue via widget F10 (`ask_interactive_question` QCU). Génération section par section guidée par le tool `generate_application_section` LangGraph. Pas de formulaire monolithique. |
| **IV. Test-First** | Plan TDD strict : tests d'abord (model, service, router, tools, frontend) avant chaque implémentation. Couverture cible ≥ 80 %. |
| **V. Sécurité & Données** | Pas de secrets dans le code. Pydantic v2 valide toutes les entrées. RLS F02 préservée. Audit F03 sur toutes mutations. Validator `source_required` F01. Snapshot immuable garde-fou anti-mutation. |
| **VI. Inclusivité & Accessibilité** | Composants Vue avec ARIA (rôles, labels), focus trap modales, navigation clavier. Contraste OK dark mode. Messages d'erreur français explicites. |
| **VII. Simplicité & YAGNI** | Réutilisation maximale : F06 WeasyPrint, F04 snapshot pattern, F07 `compute_effective_offer`, F23 `load_skills_for_context`, F09 admin workflow. Pas d'abstraction nouvelle prématurée. DOCX reporté post-MVP. |

**Result** : ✅ Pas de violation de principe. Aucune entrée Complexity Tracking nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/041-f15-dossiers-offre/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 (résolutions techniques)
├── data-model.md        # Phase 1 (entités + migrations)
├── quickstart.md        # Phase 1 (parcours dev/test)
├── contracts/           # Phase 1 (OpenAPI REST + tools LangChain)
│   ├── openapi-templates.yaml
│   ├── openapi-applications.yaml
│   └── tools-langchain.json
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Phase 2 (/speckit.tasks output)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── template_dossier.py            # NEW : modèle Template_dossier (Auditable + VersioningMixin)
│   │   └── fund_application.py            # PATCH : ajoute template_id, language, attestation_id, snapshot_data
│   ├── modules/
│   │   ├── applications/
│   │   │   ├── service.py                 # PATCH : fix bug company_context, refactor generate_section
│   │   │   ├── template_service.py        # NEW : CRUD templates + fallback + versioning
│   │   │   ├── checklist_service.py       # NEW : compute_union_checklist
│   │   │   ├── snapshot_service.py        # NEW : build_snapshot_data F15 (réutilise pattern F04)
│   │   │   ├── router.py                  # PATCH : nouveaux endpoints batch + recompute_against_snapshot
│   │   │   ├── schemas.py                 # PATCH : nouveaux schemas Pydantic v2
│   │   │   ├── export.py                  # PATCH : intégration attestation F08 dans bundle PDF
│   │   │   ├── seed_templates.py          # NEW : 10 templates seed (FR+EN) avec source_id + skill_id
│   │   │   └── prompt_builder.py          # NEW : build_prompt(profile, project, offer, template, skill, lang)
│   │   └── admin/
│   │       └── templates_router.py        # NEW : 8 endpoints /api/admin/templates/*
│   ├── graph/
│   │   ├── tools/
│   │   │   ├── application_tools.py       # PATCH : fix AttributeError fund.max_amount, fusion create_fund_application
│   │   │   ├── financing_tools.py         # PATCH : retrait du doublon create_fund_application
│   │   │   └── template_tools.py          # NEW : tools list_templates, generate_application_section, attach_attestation_to_application, export_application
│   │   ├── prompt_fusion.py               # PATCH : injecte template prompt expert + Skill F23
│   │   └── nodes.py                       # PATCH : node `application` charge profile + project + offer + template + skill
│   └── api/
│       └── chat.py                        # PATCH : transmet user_projects + active_template au state LangGraph
├── alembic/
│   └── versions/
│       └── 041_templates_and_application_refactor.py   # NEW migration
├── templates/
│   └── applications/                      # NEW : Jinja2 templates PDF (FR + EN)
│       ├── application_pdf.html
│       ├── _section.html
│       ├── _checklist.html
│       ├── _attestation_appendix.html
│       └── _appendix_sources.html         # réutilise F01 partial
└── tests/
    ├── models/test_template_dossier.py
    ├── modules/applications/test_template_service.py
    ├── modules/applications/test_checklist_service.py
    ├── modules/applications/test_snapshot_service_f15.py
    ├── modules/applications/test_service_company_context_fix.py     # BUG-001
    ├── modules/applications/test_export_with_attestation.py
    ├── modules/applications/test_router_idempotency.py             # FR-023
    ├── modules/applications/test_seed_templates.py
    ├── modules/admin/test_templates_router.py
    ├── graph/tools/test_application_tools_money_fix.py             # BUG-002
    ├── graph/tools/test_no_duplicate_create_fund_application.py    # BUG-003
    ├── graph/tools/test_template_tools.py
    ├── graph/test_prompt_fusion_template.py
    ├── alembic/test_migration_041.py                               # round-trip up/down/up
    └── e2e/                                                         # via Playwright côté frontend

frontend/
├── app/
│   ├── components/
│   │   ├── applications/
│   │   │   ├── TemplateSelector.vue        # NEW
│   │   │   ├── LanguageSelector.vue        # NEW (réutilise widget F10 si possible)
│   │   │   ├── ChecklistUnion.vue          # NEW
│   │   │   ├── ChecklistItem.vue           # NEW (badge fund/intermediary/both)
│   │   │   ├── AttachAttestationToggle.vue # NEW
│   │   │   ├── SectionEditor.vue           # NEW (tabs par section + bouton régénérer)
│   │   │   ├── BatchOfferSelector.vue      # NEW
│   │   │   └── ApplicationStatusBadge.vue  # PATCH (langue + template version)
│   │   └── admin/
│   │       └── templates/
│   │           ├── TemplateList.vue         # NEW
│   │           ├── TemplateForm.vue         # NEW (sections JSONB editor + skill picker)
│   │           ├── TemplateSectionsEditor.vue # NEW
│   │           └── TemplateRequiredDocsEditor.vue # NEW
│   ├── pages/
│   │   ├── applications/[id].vue           # PATCH : intègre TemplateSelector, LanguageSelector, ChecklistUnion, AttachAttestationToggle, SectionEditor
│   │   ├── profile/projects/[id]/applications.vue # NEW : liste candidatures par projet + batch
│   │   └── admin/templates/                # NEW
│   │       ├── index.vue
│   │       ├── new.vue
│   │       └── [id].vue
│   ├── composables/
│   │   ├── useApplications.ts              # PATCH : createApplicationsBatch, generateSection, attachAttestation, exportPdf
│   │   ├── useAdminTemplates.ts            # NEW : 8 méthodes CRUD
│   │   └── useChecklistUnion.ts            # NEW
│   ├── stores/
│   │   ├── applications.ts                 # PATCH
│   │   └── templates.ts                    # NEW
│   ├── types/
│   │   └── template.ts                     # NEW
│   └── tests/
│       └── e2e/
│           └── F15-generation-dossiers-par-offre.spec.ts # NEW (5 scénarios US1-US6)
```

**Structure Decision** : Web application monolithe modulaire (`backend/` + `frontend/`) — option 2 du template, cohérente avec les 21 features mergées. Aucune restructuration majeure requise.

## Phases

### Phase 0 : Outline & Research

→ Voir [research.md](./research.md). Synthèse :

- Décision migration : `down_revision = '040_carbon_report_dashboard'`. À reconfirmer en début d'implémentation par `alembic heads` ; ajuster si un head plus récent existe (F22, F23 utilisent `032`/`033` mais sont sur des branches latérales — F15 reprend la chaîne 03x principale). Round-trip up/down/up sur PostgreSQL et SQLite obligatoire (constitution IV).
- Décision RLS : `templates_dossier` est un catalogue admin-only (similaire à `skills` F23). Ajout à `EXEMPT_MODELS` côté F03 audit middleware (cohérent F23). RLS PostgreSQL : ENABLE+FORCE, lecture publique des `published`, écriture `current_setting('app.current_role')='ADMIN'`.
- Décision snapshot : réutilisation 1:1 du pattern `build_snapshot_data` F04 existant. Extension du payload avec `template_snapshot` (id, version, sections, language, source_id, skill_id+version).
- Décision Skills F23 : référencer une Skill existante par défaut (`skill_dossier_gcf_via_boad`, `skill_score_gcf` créées en F23 seed). Si la Skill n'existe pas pour un instrument donné, l'admin doit créer la Skill avant de publier le template (FK NOT NULL).
- Décision tool fusion BUG-003 : conserver `application_tools.create_fund_application` (plus complet, supporte `language` + `project_id`), retirer `financing_tools.create_fund_application` du `__all__` et de `MODULE_TOOL_MAPPING`. Test garde-fou `test_no_duplicate_create_fund_application` qui échoue si deux tools du même nom sont enregistrés.
- Décision DOCX : pas d'extension F15 ; legacy `application_tools.export_to_docx` conservé en lecture seule.
- Décision idempotence (FR-023) : DB UNIQUE INDEX `(project_id, offer_id) WHERE deleted_at IS NULL` + service catch `IntegrityError` → retourne ressource existante avec header `X-Mefali-Idempotent: replay`.

### Phase 1 : Design & Contracts

→ Voir [data-model.md](./data-model.md) et [contracts/](./contracts/).

Sortie attendue :
- `data-model.md` : entités, relations, indexes, contraintes, RLS policies, transitions d'état.
- `contracts/openapi-templates.yaml` : 8 endpoints `/api/admin/templates/*`.
- `contracts/openapi-applications.yaml` : endpoints PATCH (`/api/applications/{id}/section`, `/applications/{id}/attestation`, `/applications/batch`, `/applications/{id}/export`, `/applications/{id}/recompute-against-snapshot`).
- `contracts/tools-langchain.json` : signatures Pydantic des 4 nouveaux tools (`generate_application_section`, `attach_attestation_to_application`, `export_application`, `list_templates`) + tools modifiés (`create_fund_application` fusionné, `simulate_financing` corrigé).
- `quickstart.md` : parcours dev (créer template seed → candidater → générer → exporter → soumettre snapshot) et parcours admin (publier template avec 4-yeux).

## Re-check Constitution post-Phase 1

| Principe | État après design | Justification éventuelle |
|----------|-------------------|--------------------------|
| I — Francophone | ✅ | Templates seed couvrent FR + EN ; UI FR ; sources UEMOA priorisées |
| II — Modulaire | ✅ | Sous-modules `templates/`, `checklist/`, `snapshot/` clairement séparés |
| III — Conversation | ✅ | Widget F10 + tools LangGraph |
| IV — Test-First | ✅ | Plan tasks (Phase 2) impose tests avant implémentation à chaque étape |
| V — Sécurité | ✅ | RLS, audit, sourçage, snapshot immuable, validation Pydantic |
| VI — Inclusivité | ✅ | ARIA, dark mode, messages clairs FR |
| VII — Simplicité | ✅ | Réutilisation massive, DOCX hors scope, pas d'abstraction prématurée |

**Result** : ✅ Toujours conforme. Aucune justification Complexity Tracking requise.

## Complexity Tracking

> Aucune violation à justifier — tableau intentionnellement vide.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| —         | —          | —                                    |
