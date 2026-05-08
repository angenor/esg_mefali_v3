# Tasks : F15 — Génération de Dossiers de Candidature par Offre

**Feature** : F15 (spec 041)
**Branch** : `feat/F15-generation-dossiers-par-offre`
**Stack** : FastAPI + SQLAlchemy async + Alembic + Pydantic v2 + LangGraph + LangChain + WeasyPrint + Jinja2 (backend) ; Nuxt 4 + Vue Composition API + Pinia + TailwindCSS + Playwright (frontend).
**Migration** : `041_templates_and_application_refactor` (down_revision = head courant, à reconfirmer via `alembic heads`).
**TDD** : tests AVANT implémentation (constitution principe IV).
**Couverture cible** : ≥ 80 % sur le périmètre F15.

Inputs traités : `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/*.{yaml,json}`, `quickstart.md`.

## Conventions

- `[P]` = peut être exécuté en parallèle (fichier distinct, pas de dépendance non résolue).
- `[US1]…[US6]` = mappe à une user story de la spec (US1 P1 contexte PME, US2 P1 multilingue, US3 P1 checklist union, US4 P2 attestation, US5 P2 multi-offres, US6 P2 snapshot).
- `[BUG]` = correctif bug critique (BUG-001 company_context, BUG-002 fund.max_amount, BUG-003 doublon tool).
- Tests AVANT implémentation à l'intérieur de chaque user story.

---

## Phase 1 — Setup

- [ ] T001 Vérifier que les features prerequises (F01, F02, F03, F04, F06, F07, F08, F09, F10, F23) sont mergées sur `main` via `git log --oneline | grep -E 'F0[1-9]|F2[37]|F1[0-9]' | head -20`
- [ ] T002 Confirmer le head Alembic courant via `cd backend && source venv/bin/activate && alembic heads` ; documenter le `down_revision` réel pour la migration 041 dans le commentaire du fichier de migration
- [ ] T003 [P] Créer le squelette des fichiers de tests (vides avec docstrings) dans `backend/tests/models/test_template_dossier.py`, `backend/tests/modules/applications/test_template_service.py`, `backend/tests/modules/applications/test_checklist_service.py`, `backend/tests/modules/applications/test_snapshot_service_f15.py`, `backend/tests/modules/applications/test_service_company_context_fix.py`, `backend/tests/modules/applications/test_export_with_attestation.py`, `backend/tests/modules/applications/test_router_idempotency.py`, `backend/tests/modules/applications/test_seed_templates.py`, `backend/tests/modules/admin/test_templates_router.py`, `backend/tests/graph/tools/test_application_tools_money_fix.py`, `backend/tests/graph/tools/test_no_duplicate_create_fund_application.py`, `backend/tests/graph/tools/test_template_tools.py`, `backend/tests/graph/test_prompt_fusion_template.py`, `backend/tests/alembic/test_migration_041.py`
- [ ] T004 [P] Créer le squelette des composants Vue (vides) dans `frontend/app/components/applications/TemplateSelector.vue`, `LanguageSelector.vue`, `ChecklistUnion.vue`, `ChecklistItem.vue`, `AttachAttestationToggle.vue`, `SectionEditor.vue`, `BatchOfferSelector.vue` ; et `frontend/app/components/admin/templates/TemplateList.vue`, `TemplateForm.vue`, `TemplateSectionsEditor.vue`, `TemplateRequiredDocsEditor.vue`
- [ ] T005 [P] Créer le squelette des composables `frontend/app/composables/useApplications.ts` (PATCH), `useAdminTemplates.ts` (NEW), `useChecklistUnion.ts` (NEW) ; types `frontend/app/types/template.ts` (NEW)
- [ ] T006 Verrouiller le périmètre TDD : ajouter une cible Makefile / script `backend/scripts/run_f15_tests.sh` qui exécute uniquement les tests du périmètre F15 avec coverage cible ≥ 80 %

---

## Phase 2 — Foundational (blocage avant toute story)

### Tests AVANT implémentation (TDD)

- [ ] T007 [P] Écrire `backend/tests/alembic/test_migration_041.py` (round-trip up/down/up sur PostgreSQL ET SQLite, vérification structure des tables, contraintes 4-yeux, index unique partiel, RLS policies présentes, seed templates fallback, count == 9)
- [ ] T008 [P] Écrire `backend/tests/models/test_template_dossier.py` (validation enum instrument_type/language/status, contrainte 4-yeux, contrainte status published implique verified_by, mixin Auditable hérité, mixin VersioningMixin hérité, sérialisation JSONB sections/required_documents/vocabulary_hints/anti_patterns)

### Implémentation foundational

- [ ] T009 [BUG-002] Patcher `backend/app/graph/tools/application_tools.py::_simulate_financing` : utiliser `fund.max_amount_money or Money.from_columns(fund.max_amount_xof, "XOF")` (et idem pour `min_amount_money`) ; tester via `backend/tests/graph/tools/test_application_tools_money_fix.py` PARAMÉTRÉ sur les 12 fonds seed F07 ; SC-002 = 0 régression
- [ ] T010 [BUG-003] Retirer `create_fund_application` de `backend/app/graph/tools/financing_tools.py::__all__` et de `MODULE_TOOL_MAPPING` ; conserver uniquement la version dans `application_tools.py` ; écrire le test garde-fou `backend/tests/graph/tools/test_no_duplicate_create_fund_application.py` (assertion `names.count('create_fund_application') == 1`)
- [ ] T011 Créer le modèle SQLAlchemy `backend/app/models/template_dossier.py` (UUID PK, mixins Auditable + VersioningMixin + UUIDMixin + TimestampMixin, colonnes selon data-model.md, relations `skill`, `source`, `offer`, `captured_by_user`, `verified_by_user`, validators applicatifs portables `@validates` pour les enum)
- [ ] T012 Ajouter `TemplateDossier` à `EXEMPT_MODELS` dans `backend/app/core/audit.py` (catalogue admin-only — cohérent F23 `Skill`)
- [ ] T013 Patcher `backend/app/models/fund_application.py` : ajouter `template_id` FK NOT NULL post-backfill, `language` enum CHECK NOT NULL DEFAULT 'fr', `attestation_id` FK nullable, `export_path` str(500) nullable ; relations `template`, `attestation`
- [ ] T014 Créer la migration `backend/alembic/versions/041_templates_and_application_refactor.py` : (1) source seed `system://mefali/catalogue-templates` `verified` si absente, (2) CREATE TABLE `templates_dossier` avec contraintes + indexes + RLS PostgreSQL (skip SQLite), (3) seed des 9 templates fallback (instrument × langue) liés à `skill_esg_diagnostic` + source seed F15, (4) ALTER TABLE `fund_applications` ajout `template_id` (NULLABLE), `language`, `attestation_id`, `export_path`, (5) backfill : pour chaque application existante, déterminer `instrument_type` via mapping legacy `target_type`, lier au template fallback `(instrument_type, language)`, (6) ALTER COLUMN `template_id` SET NOT NULL, (7) UNIQUE INDEX partiel `idx_fund_applications_project_offer_unique`. Round-trip up/down/up garanti par T007.
- [ ] T015 Exécuter `alembic upgrade head` localement et vérifier que T007 passe (round-trip)

---

## Phase 3 — User Story 1 (P1) : Génération sourcée avec contexte PME complet + bugs critiques

**Goal** : la PME génère un dossier qui s'appuie sur son profil réel, son projet F06, l'offre F07 et la Skill F23 (corrige BUG-001 + branche templates par offre + Skills).

**Independent test** : créer un compte PME avec profil rempli, rattacher un projet F06, choisir une offre F07 disposant d'un template publié, déclencher la génération d'une section, vérifier que le rendu cite secteur/pays/CA et au moins une source F01.

### Tests US1 (avant implémentation)

- [ ] T016 [P] [US1] Écrire `backend/tests/modules/applications/test_service_company_context_fix.py` (BUG-001 — vérifie que `generate_section` reçoit `company_context = profile_full_text(profile)` non vide et que `"Aucun profil d'entreprise disponible"` n'apparaît plus jamais dans le prompt construit ; cas profil incomplet → exception explicite)
- [ ] T017 [P] [US1] Écrire `backend/tests/modules/applications/test_template_service.py` (CRUD + fallback par instrument + récupération template effectif pour offre + version bump + workflow draft/published)
- [ ] T018 [P] [US1] Écrire `backend/tests/modules/applications/test_seed_templates.py` (idempotence par `name`, count ≥ 10 templates publiés, chaque template a `source_id` + `skill_id` non null, 4 instruments couverts, 2 templates EN)
- [ ] T019 [P] [US1] Écrire `backend/tests/graph/tools/test_template_tools.py` (`list_templates`, `generate_application_section` Pydantic strict, `compute_application_checklist`)
- [ ] T020 [P] [US1] Écrire `backend/tests/graph/test_prompt_fusion_template.py` (fusion `system_prompt + skill.prompt_expert + template.tone + section.instructions + profile + project + offer.effective_criteria` ; respect cap 5000 tokens prompt expert F23 ; sélection langue routée correctement)
- [ ] T021 [P] [US1] Écrire `frontend/tests/unit/composables/useApplications.test.ts` (PATCH : `generateSection`, `getApplication`, gestion 422 profil incomplet)
- [ ] T022 [P] [US1] Écrire `frontend/tests/unit/components/applications/SectionEditor.test.ts` (props, événement `regenerate`, dark mode, ARIA)

### Implémentation US1

- [ ] T023 [US1] Créer `backend/app/modules/applications/template_service.py` : `list_templates`, `get_template`, `get_effective_template_for_offer(offer_id, language) -> Template | None` (résolution template publié pour offre puis fallback instrument), `create_template_draft`, `update_template`, `publish_template` (4-yeux), `unpublish_template`, `bump_version` (réutilise `app.modules.versioning.bump_version` F04)
- [ ] T024 [US1] Créer `backend/app/modules/applications/prompt_builder.py::build_section_prompt(profile, project, offer_effective, template, section_def, skill, language) -> str` : sections en français ou anglais selon `language`, injection profil PME complet (secteur, pays, taille, CA, employés), résumé projet F06, critères effectifs offre F07, `prompt_expert` Skill F23, `tone` + `vocabulary_hints` + `anti_patterns` du template
- [ ] T025 [US1] [BUG-001] Refactorer `backend/app/modules/applications/service.py::generate_section` (ligne ~262) : remplacer le hardcoded par `profile = await get_or_create_profile(application.account_id)` ; charger en parallèle via `asyncio.gather` profile/project/offer/template/skill ; appeler `build_section_prompt` ; appeler le LLM avec timeout 60s ; tracer dans `audit_log` `source_of_change='llm'` ; persister la section dans `application.sections[section_key]`
- [ ] T026 [US1] Créer `backend/app/modules/applications/seed_templates.py::seed_templates(db, admin_user_id, verifier_user_id) -> SeedResult` : insert idempotent par `name` des 10 templates publiés (4 instruments FR + 2 EN GCF Direct Access + 4 spécifiques GCF/BOAD Mitigation, GCF/BOAD Adaptation, SUNREF/AFD, FEM/UNDP Blending) ; mapping vers Skills F23 selon `research.md::R-004`
- [ ] T027 [US1] Brancher le seed dans la migration 041 (suite de T014) ou via script standalone exécuté en post-migration ; idempotent
- [ ] T028 [US1] Créer `backend/app/graph/tools/template_tools.py::list_templates` (Pydantic args + `args_schema`)
- [ ] T029 [US1] Créer `generate_application_section` dans `template_tools.py` (Pydantic strict, déclenche `service.generate_section`, retourne `{generation_id, status, section_key}`)
- [ ] T030 [US1] Patcher `backend/app/graph/prompt_fusion.py` pour intégrer le bloc « TEMPLATE ACTIF » dans le prompt (similaire pattern F23 SKILL ACTIVE) avec section `instructions`, `tone`, `vocabulary_hints`
- [ ] T031 [US1] Patcher `backend/app/graph/nodes.py::application_node` pour charger profile + project + offer effective + template + skill via `asyncio.gather` et passer dans `state["active_template"]` + `state["active_skills"]`
- [ ] T032 [US1] Ajouter `template_tools.TEMPLATE_TOOLS` à `MODULE_TOOL_MAPPING['application']` et `PAGE_TOOL_MAPPING['applications']` dans `backend/app/graph/tool_selector_config.py`
- [ ] T033 [US1] Patcher `backend/app/api/chat.py::_load_full_context_for_state` pour inclure `active_template` (sélection automatique selon offer_id si présente)
- [ ] T034 [US1] Créer le composant `frontend/app/components/applications/SectionEditor.vue` (tabs par section, bouton « Régénérer », statut génération en cours via SSE, dark mode complet, ARIA `role="tablist"`)
- [ ] T035 [US1] Patcher `frontend/app/composables/useApplications.ts::generateSection(applicationId, sectionKey, userInputs?)` pour appeler `POST /api/applications/{id}/section/generate` et écouter le SSE
- [ ] T036 [US1] Patcher `frontend/app/pages/applications/[id].vue` pour inclure `<SectionEditor>` et brancher `generateSection`
- [ ] T037 [US1] Vérifier que T016-T022 passent ; couverture US1 ≥ 80 % via `pytest --cov=app.modules.applications.template_service --cov=app.modules.applications.prompt_builder --cov=app.modules.applications.seed_templates`

**Checkpoint US1** : MVP livrable indépendamment. Bug BUG-001 corrigé, génération sourcée fonctionnelle. SC-001 + SC-003 + SC-007 vérifiables.

---

## Phase 4 — User Story 2 (P1) : Choix de la langue selon `accepted_languages` de l'offre

**Goal** : multilingue FR/EN avec widget bloquant sur offres bilingues.

**Independent test** : créer une offre acceptant `["fr","en"]`, démarrer un dossier, choisir `en`, vérifier 3 sections générées en anglais et libellés EN.

### Tests US2 (avant implémentation)

- [ ] T038 [P] [US2] Écrire `backend/tests/modules/applications/test_language_selection.py` (création application avec `language` issu de `offer.accepted_languages` ; offre mono-langue → langue forcée ; offre multilingue → 422 si `language` non fourni)
- [ ] T039 [P] [US2] Écrire `backend/tests/modules/applications/test_template_service.py::test_get_effective_template_returns_en` (résolution template EN pour offre EN-only)
- [ ] T040 [P] [US2] Écrire un test E2E heuristique de langue dans `backend/tests/modules/applications/test_template_service.py::test_generate_section_en_outputs_english` (regex heuristique selon `research.md::R-012` : ratio mots EN ≥ 60 %)
- [ ] T041 [P] [US2] Écrire `frontend/tests/unit/components/applications/LanguageSelector.test.ts` (rendu QCU FR/EN, événement `change`, accessibilité)

### Implémentation US2

- [ ] T042 [US2] Patcher `backend/app/modules/applications/service.py::create_application` pour valider `language` selon `offer.accepted_languages` ; 422 explicite si offre multilingue et `language` absent ; force la langue mono-langue
- [ ] T043 [US2] Patcher `prompt_builder.py` pour router le bon `prompt_expert` Skill (FR ou EN — selon convention F23) et libeller les sections en `language`
- [ ] T044 [US2] Patcher `seed_templates.py` pour enrichir les 2 templates EN GCF Direct Access (langue, sections en anglais, tone EN)
- [ ] T045 [US2] Créer le composant `frontend/app/components/applications/LanguageSelector.vue` (QCU bloquant, dark mode, ARIA `role="radiogroup"`, pré-sélection visuelle = langue UI courante)
- [ ] T046 [US2] Brancher `<LanguageSelector>` dans `frontend/app/pages/applications/[id].vue` et dans le flux de création (modal `BatchOfferSelector` quand offre multilingue)
- [ ] T047 [US2] Patcher `frontend/app/composables/useApplications.ts::createApplication` pour passer `language` ; gestion erreur 422 → afficher widget langue
- [ ] T048 [US2] Vérifier que T038-T041 passent

**Checkpoint US2** : multilingue FR/EN opérationnel. SC-006 vérifiable.

---

## Phase 5 — User Story 3 (P1) : Checklist union docs fonds + intermédiaire dédupliquée

**Goal** : checklist consolidée union, déduplication par titre normalisé, badge origine.

**Independent test** : offre dont fund exige `["business_plan","etude_impact"]` et intermediary exige `["business_plan","kbis"]` → checklist 3 pièces (`business_plan` = `both`).

### Tests US3 (avant implémentation)

- [ ] T049 [P] [US3] Écrire `backend/tests/modules/applications/test_checklist_service.py` : déduplication NFKD, mandatory most-restrictive (FR-016), union sources (FR-017), badge origine fund/intermediary/both (FR-018), 10 paires seed F07 testées (SC-005)
- [ ] T050 [P] [US3] Écrire `frontend/tests/unit/components/applications/ChecklistUnion.test.ts` + `ChecklistItem.test.ts` (rendu badges, ARIA, dark mode)
- [ ] T051 [P] [US3] Écrire `frontend/tests/unit/composables/useChecklistUnion.test.ts`

### Implémentation US3

- [ ] T052 [US3] Créer `backend/app/modules/applications/checklist_service.py::compute_union_checklist(offer_id) -> list[ChecklistItem]` selon algorithme `research.md::R-008` (chargement `compute_effective_offer` F07, normalisation NFKD, groupement par titre normalisé, mandatory most-restrictive, union source_ids, origine `fund|intermediary|both`)
- [ ] T053 [US3] Créer le tool `compute_application_checklist` dans `backend/app/graph/tools/template_tools.py` (Pydantic args strict)
- [ ] T054 [US3] Ajouter endpoint `GET /api/applications/{id}/checklist` dans `backend/app/modules/applications/router.py` (auth user + RLS F02 implicite via `account_id`)
- [ ] T055 [US3] Créer `frontend/app/components/applications/ChecklistUnion.vue` (liste groupée par mandatory, progress bar de complétion, dark mode, ARIA `role="list"`)
- [ ] T056 [US3] Créer `frontend/app/components/applications/ChecklistItem.vue` (badge `fund|intermediary|both`, lien sur `<SourceLink>` F01, checkbox uploaded, attache document)
- [ ] T057 [US3] Créer `frontend/app/composables/useChecklistUnion.ts` (`fetch`, `attachDocumentToItem`)
- [ ] T058 [US3] Brancher dans `frontend/app/pages/applications/[id].vue`
- [ ] T059 [US3] Vérifier que T049-T051 passent

**Checkpoint US3** : checklist union fonctionnelle. SC-005 vérifiable.

---

## Phase 6 — User Story 4 (P2) : Intégration attestation F08 dans l'export PDF

**Goal** : la PME peut joindre une attestation F08 active à son dossier, le PDF exporté inclut l'attestation avec QR scannable.

**Independent test** : générer attestation F08 active → cocher « Joindre » → export PDF → QR scannable redirige vers endpoint vérification publique.

### Tests US4 (avant implémentation)

- [ ] T060 [P] [US4] Écrire `backend/tests/modules/applications/test_export_with_attestation.py` (4 cas : attestation active jointe → présente dans PDF + QR ; attestation expirée → exclue + warning log ; attestation révoquée → option désactivée ; sans attestation → PDF normal sans annexe)
- [ ] T061 [P] [US4] Écrire `frontend/tests/unit/components/applications/AttachAttestationToggle.test.ts`

### Implémentation US4

- [ ] T062 [US4] Créer le partial Jinja2 `backend/templates/applications/_attestation_appendix.html` (QR code data URI base64, ID public, signature lisible, libellés FR ou EN)
- [ ] T063 [US4] Patcher `backend/app/modules/applications/export.py::export_to_pdf(application_id, with_attestation=True)` : charger l'attestation si liée et active, inliner via le partial, exclure + log WARNING si expirée/révoquée, stocker `export_path` sur `fund_applications`
- [ ] T064 [US4] Créer endpoint `PUT /api/applications/{id}/attestation` (attacher) et `DELETE /api/applications/{id}/attestation` (détacher) dans `router.py` ; valider l'attestation appartient bien au compte (RLS F02)
- [ ] T065 [US4] Créer endpoint `POST /api/applications/{id}/export` (body `{with_attestation, include_appendix_sources}`) qui retourne le binaire PDF (`StreamingResponse`)
- [ ] T066 [US4] Créer le tool `attach_attestation_to_application` dans `template_tools.py`
- [ ] T067 [US4] Créer le tool `export_application` dans `template_tools.py`
- [ ] T068 [US4] Créer `frontend/app/components/applications/AttachAttestationToggle.vue` (checkbox + statut attestation + lien preview + désactivé si expirée/révoquée, dark mode complet)
- [ ] T069 [US4] Patcher `frontend/app/composables/useApplications.ts` : `attachAttestation`, `detachAttestation`, `exportPdf` (download blob)
- [ ] T070 [US4] Brancher `<AttachAttestationToggle>` + bouton « Exporter PDF » dans `frontend/app/pages/applications/[id].vue`
- [ ] T071 [US4] Vérifier que T060-T061 passent

**Checkpoint US4** : attestation joignable. SC-009 vérifiable.

---

## Phase 7 — User Story 5 (P2) : Génération multi-offres en lot pour un même projet

**Goal** : créer plusieurs candidatures distinctes pour un même projet (idempotence sur `(project_id, offer_id)`).

**Independent test** : 1 projet F06 + 3 offres → 3 candidatures distinctes ; tentative de doublon → ressource existante renvoyée avec header `X-Mefali-Idempotent: replay`.

### Tests US5 (avant implémentation)

- [ ] T072 [P] [US5] Écrire `backend/tests/modules/applications/test_router_idempotency.py` (création batch 3 offres → 201 + 3 IDs ; replay → 200 + même ID + header `X-Mefali-Idempotent: replay` ; mix création/replay)
- [ ] T073 [P] [US5] Écrire `frontend/tests/unit/components/applications/BatchOfferSelector.test.ts`

### Implémentation US5

- [ ] T074 [US5] Patcher `backend/app/modules/applications/service.py::create_application` selon `research.md::R-007` (try/except IntegrityError, retourne `(resource, replayed)`)
- [ ] T075 [US5] Créer endpoint `POST /api/applications/batch` (body `{project_id, offer_ids: list[UUID], language?}`) qui itère via `create_application` et regroupe `created` / `replayed` dans la réponse
- [ ] T076 [US5] Patcher le tool `create_fund_application` (déjà fusionné en T010) pour exposer `replayed: bool` dans le retour
- [ ] T077 [US5] Créer `frontend/app/pages/profile/projects/[id]/applications.vue` : liste candidatures rattachées au projet (statut, template, langue, offre) ; bouton « Candidater à d'autres offres » ouvre modal
- [ ] T078 [US5] Créer `frontend/app/components/applications/BatchOfferSelector.vue` (multi-select offres compatibles, validation min 1 / max 10, dark mode, ARIA)
- [ ] T079 [US5] Patcher `frontend/app/composables/useApplications.ts::createApplicationsBatch(projectId, offerIds, language?)` ; toast informant des replays
- [ ] T080 [US5] Vérifier que T072-T073 passent

**Checkpoint US5** : multi-offres opérationnel. SC-008 vérifiable.

---

## Phase 8 — User Story 6 (P2) : Snapshot immuable F04 à la soumission

**Goal** : à la transition `draft → submitted_*`, créer un snapshot autoportant immuable.

**Independent test** : créer candidature → soumettre → modifier template (nouvelle version F04) → snapshot pointe sur ancienne version.

### Tests US6 (avant implémentation)

- [ ] T081 [P] [US6] Écrire `backend/tests/modules/applications/test_snapshot_service_f15.py` : `build_snapshot_data` contient `template_snapshot` complet (id, version, sections, language, source_id, skill_id+version) ; mutation post-submission refusée ; cas attestation jointe → ID dans snapshot ; warning > 100 KB (cohérent F04)
- [ ] T082 [P] [US6] Écrire `backend/tests/modules/applications/test_recompute_against_snapshot_f15.py` (rejouer scoring → score identique au moment soumission, même si template a évolué)

### Implémentation US6

- [ ] T083 [US6] Créer `backend/app/modules/applications/snapshot_service.py::build_template_snapshot(template) -> dict` (extrait id/version/sections/required_documents/language/source_id/skill_id/skill_version selon `research.md::R-003`)
- [ ] T084 [US6] Patcher `backend/app/modules/applications/service.py::update_application_status` (déjà existant F04) : à la transition vers `submitted_to_*`, appeler `build_snapshot_data` étendu avec `template_snapshot` + `attestation_snapshot` si liée ; assigner `snapshot_at = now()` et `snapshot_data = ...`
- [ ] T085 [US6] Patcher `backend/app/modules/applications/service.py::recompute_against_snapshot` (déjà existant F04) pour utiliser le `template_snapshot` figé (sections, version) plutôt que le template courant
- [ ] T086 [US6] Endpoint `POST /api/applications/{id}/recompute-against-snapshot` (déjà F04 — vérifier compatibilité F15) ; retourner `template_version_used` dans la réponse
- [ ] T087 [US6] Vérifier que T081-T082 passent ; SC-004 vérifiable

**Checkpoint US6** : snapshot immuable opérationnel. SC-004 + SC-011 vérifiables.

---

## Phase 9 — Back-office admin Templates (F09 — soutien transverse)

**Goal** : CRUD admin Templates avec workflow draft/published + 4-yeux ; cohérent F09.

### Tests admin (avant implémentation)

- [ ] T088 [P] Écrire `backend/tests/modules/admin/test_templates_router.py` : 8 endpoints (`GET /`, `POST /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/publish` 4-yeux, `POST /{id}/unpublish`, `GET /{id}/preview`) ; sécurité `Depends(get_current_admin)` ; RLS isolation PME bloquée ; audit log `source_of_change='admin'`

### Implémentation admin

- [ ] T089 Créer `backend/app/modules/admin/templates_router.py` avec les 8 endpoints selon `contracts/openapi-templates.yaml`
- [ ] T090 Créer schémas Pydantic `backend/app/modules/applications/schemas.py::TemplateCreate/TemplateUpdate/TemplateRead/SectionDef/RequiredDocument` (validators stricts selon `data-model.md`)
- [ ] T091 Créer composable `frontend/app/composables/useAdminTemplates.ts` (8 méthodes)
- [ ] T092 Créer types TypeScript `frontend/app/types/template.ts` (miroir Pydantic)
- [ ] T093 Créer `frontend/app/components/admin/templates/TemplateList.vue` (liste paginée + filtres offer/instrument/language/status, ARIA, dark mode)
- [ ] T094 Créer `frontend/app/components/admin/templates/TemplateForm.vue` (mode create/edit, picker Skill, picker Source, éditeur sections JSONB, éditeur required_documents, dark mode)
- [ ] T095 Créer `frontend/app/components/admin/templates/TemplateSectionsEditor.vue` (CRUD inline sections, drag-and-drop ordre, validation key unique)
- [ ] T096 Créer `frontend/app/components/admin/templates/TemplateRequiredDocsEditor.vue` (CRUD inline, picker source_id F01, badge origine)
- [ ] T097 Créer `frontend/app/pages/admin/templates/index.vue`, `new.vue`, `[id].vue` (layout admin F02, sidebar templates)
- [ ] T098 Brancher `Templates` dans la sidebar admin `frontend/app/layouts/admin.vue`
- [ ] T099 Vérifier que T088 passe

---

## Phase 10 — E2E Playwright

- [ ] T100 Écrire `frontend/tests/e2e/F15-generation-dossiers-par-offre.spec.ts` avec 6 scénarios (US1 à US6) :
  - `US1` : login PME → ouvrir candidature avec template publié → générer section → vérifier profil cité + SourceLink F01 visible
  - `US2` : créer candidature pour offre EN-only → vérifier sections en anglais
  - `US3` : ouvrir candidature → vérifier checklist union avec badges fund/intermediary/both
  - `US4` : attacher attestation → exporter PDF → vérifier annexe attestation présente
  - `US5` : depuis page projet, candidater à 3 offres en lot → 3 candidatures créées
  - `US6` : soumettre candidature → snapshot créé → rejouer scoring → vérifier `template_version_used` retourné
- [ ] T101 Créer helpers Playwright dans `frontend/tests/e2e/F15-helpers.ts` (mock backend complet : seed templates, seed offers, seed projets, seed attestations)

---

## Phase 11 — Polish & cross-cutting concerns

- [ ] T102 [P] Vérifier la couverture globale F15 ≥ 80 % via `pytest --cov=app.modules.applications --cov=app.models.template_dossier --cov=app.graph.tools.template_tools --cov=app.modules.admin.templates_router --cov-report=term-missing` ; ajouter tests manquants si < 80 %
- [ ] T103 [P] Vérifier les libellés FR avec accents (é, è, ê, à, ç, ù) dans tous les nouveaux composants Vue + templates Jinja2 (constitution principe I)
- [ ] T104 [P] Vérifier dark mode complet sur tous les composants `applications/*` et `admin/templates/*` (CLAUDE.md OBLIGATOIRE) — chaque élément visuel a sa variante `dark:`
- [ ] T105 [P] Vérifier ARIA + navigation clavier sur les 4 modales (LanguageSelector, BatchOfferSelector, AttachAttestationToggle, TemplateForm) — focus trap + role + aria-label
- [ ] T106 [P] Documentation : mettre à jour `docs/applications-templates.md` (cycle de vie template, anti-injection guidelines, snapshot, troubleshooting) et CLAUDE.md section `## Recent Changes` avec entrée F15
- [ ] T107 [P] Validator `source_required` F01 : vérifier que les sections générées sont bien validées (réutilisation du validator existant) ; ajouter test golden de 5 cas dossier
- [ ] T108 Test garde-fou conformity : `tests/graph/tools/test_no_template_mutation_tool.py` (aucun tool LLM ne mute Template — pattern interdit `^(create|update|delete|publish|unpublish)_template$`)
- [ ] T109 Lancer la suite complète backend `pytest backend/tests/ -v --cov` ; vérifier 0 régression sur la baseline (~2693 tests verts hérités F23)
- [ ] T110 Lancer la suite complète frontend `npm run test:unit && npm run test:e2e` ; vérifier 0 régression
- [ ] T111 Vérifier que les 12 SC (SC-001 à SC-012) sont tous démontrables par un test ou un parcours documenté dans `quickstart.md`

---

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational : T007-T015)  [BUG-002 + BUG-003 + Migration + Modèles]
    ↓
    ├── Phase 3 (US1 : T016-T037)  ← inclut BUG-001 ; MVP livrable
    │       ↓
    │   ┌── Phase 4 (US2 : T038-T048)  ← multilingue, dépend du template
    │   ├── Phase 5 (US3 : T049-T059)  ← checklist, dépend de offer F07
    │   ├── Phase 6 (US4 : T060-T071)  ← attestation, indépendant
    │   ├── Phase 7 (US5 : T072-T080)  ← multi-offres, indépendant
    │   └── Phase 8 (US6 : T081-T087)  ← snapshot, dépend des autres ayant créé des données
    ↓
Phase 9 (Admin templates : T088-T099)  ← peut démarrer après Phase 2
    ↓
Phase 10 (E2E : T100-T101)
    ↓
Phase 11 (Polish : T102-T111)
```

## Parallel execution opportunities

- **Phase 1 — T003, T004, T005** parallélisables (squelettes de fichiers distincts).
- **Phase 2 — T007 et T008** parallélisables.
- **Phase 3 — Tests T016-T022** parallélisables (fichiers distincts) AVANT implémentation T023-T036.
- **Phases 4 à 8** : les tests `[P]` au sein de chaque phase sont parallélisables. Les phases US2 / US3 / US4 / US5 sont indépendantes entre elles et peuvent être menées en parallèle si l'équipe est multiple, mais nécessitent toutes Phase 3 (US1) complétée.
- **Phase 9 (admin)** : peut démarrer en parallèle de Phase 3 dès que Phase 2 est verte.
- **Phase 11 (polish)** : T102-T108 parallélisables.

## MVP scope

**Strict MVP** : Phase 1 + Phase 2 + Phase 3 (US1) seuls livrent une valeur autonome :
- Génération sourcée avec contexte PME complet (BUG-001 corrigé)
- Templates par offre publiés
- Sources F01 + Skills F23 branchées
- BUG-002 et BUG-003 corrigés en collatéral

US2 (multilingue) et US3 (checklist union) sont fortement recommandées pour la cohérence produit (P1) mais peuvent être livrées en sprint suivant si nécessaire.

US4, US5, US6 sont des P2 — peuvent être différées d'un sprint sans casser la valeur.

## Independent test criteria per story

| Story | Test indépendant |
|-------|------------------|
| US1 | Login PME, générer section pour offre avec template publié, vérifier profil cité + source F01 |
| US2 | Créer application pour offre `accepted_languages=['en']`, générer section, vérifier sortie EN |
| US3 | Offre fund=`[BP, EI]` + intermediary=`[BP, KBIS]` → checklist 3 pièces avec `BP` badge `both` |
| US4 | Attestation F08 active → cocher join → export PDF → QR scannable redirige vers /api/attestations/{id}/verify |
| US5 | 1 projet + 3 offres → POST /applications/batch → 3 candidatures distinctes ; replay → header `X-Mefali-Idempotent: replay` |
| US6 | Soumettre application → modifier template (bump version) → recompute_against_snapshot → score identique |

## Validation finale

- [ ] T-final : tous les SC-001 à SC-012 vérifiés via test ou commande de quickstart.md
- [ ] T-final : couverture ≥ 80 % atteinte sur le périmètre F15
- [ ] T-final : round-trip Alembic up/down/up validé sur PostgreSQL ET SQLite
- [ ] T-final : 0 régression sur la baseline backend (~2693 tests) et frontend (~731 tests)

---

**Total tâches : 111** (T001 à T111).
**Tâches MVP (US1 strict)** : 37 (T001 à T037).
**Tâches P1 complètes (US1 + US2 + US3)** : 59.
**Tâches P2 ajoutées** : 28 (US4 + US5 + US6).
**Admin + E2E + Polish** : 24.
