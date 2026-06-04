# Implementation Plan: Fourniture des documents de la checklist d'un dossier de candidature (V1)

**Branch**: `049-checklist-documents` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/049-checklist-documents/spec.md`

## Summary

Rendre éditable la checklist documentaire d'un dossier de candidature (`FundApplication.checklist`) depuis l'onglet Checklist : téléverser un fichier ou rattacher un document existant à un item, prévisualiser, détacher, remplacer, et afficher la progression (M / N) sur le dossier et la liste des dossiers.

Approche technique retenue : **réutilisation maximale, zéro nouvelle table**. On exploite le champ JSON `checklist` déjà présent (chaque item porte `document_id` et `status`), le pattern read-modify-write éprouvé de `update_section`, le flux d'upload `/api/documents/upload` existant et les composants `DocumentUpload` / `DocumentList` / `DocumentPreview`. Deux nouveaux endpoints REST (rattacher / détacher) sur le routeur `applications`, un seul nouveau composant frontend (`DocumentPicker` = `DocumentList` dans une modale). Le statut d'item est persisté (`provided` / `missing`) et maintenu cohérent par un **nettoyage des références à la suppression d'un document**. Correction de parité du tool chatbot `get_application_checklist` (actuellement cassé) pour respecter FR-019.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy async, Pydantic v2 (backend) ; Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS (frontend)
**Storage**: PostgreSQL 16 — réutilisation du champ `fund_applications.checklist` (JSON) et de la table `documents`. **Aucune migration Alembic** (pas de changement de schéma).
**Testing**: pytest (backend, async), Vitest + Playwright (frontend) — TDD, couverture ≥ 80 % (Constitution IV).
**Target Platform**: Application web (serveur Linux + navigateur).
**Project Type**: web (frontend Nuxt + backend FastAPI, monolithe modulaire).
**Performance Goals**: opération rattacher/détacher perçue instantanée (< 1 s, SC-001) ; sérialisation checklist sans N+1 (chargement groupé des documents référencés).
**Constraints**: multi-tenant strict (`account_id`, RLS) ; UI 100 % française avec accents + dark mode obligatoire ; réutiliser les composants UI existants ; principe atomique par item (clarification 2026-06-03) **garanti par un verrou de ligne `with_for_update()`** sur le dossier pendant le read-modify-write (sérialise les écritures concurrentes chat/UI — voir research D11).
**Scale/Scope**: quelques dossiers par compte, 5–8 items par checklist ; documents ≤ 10 MB, types PDF/PNG/JPG/DOCX/XLSX (validation existante).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| I. Francophone-First | ✅ PASS | UI/messages d'erreur en français avec accents ; code en anglais ; libellés d'items déjà en français dans `templates.py`. |
| II. Architecture Modulaire | ✅ PASS | Changements cantonnés aux modules `applications` (endpoints/service) et `documents` (un appel de nettoyage). Dépendance unidirectionnelle `documents → applications` via un helper dédié (pas de cycle). |
| III. Conversation-Driven UX | ✅ PASS | Complète le chat sans le remplacer ; corrige et aligne le tool chatbot `get_application_checklist` (parité FR-019). |
| IV. Test-First (NON-NÉGOCIABLE) | ✅ PASS | Tâches structurées tests-d'abord, couverture ≥ 80 % (unit + intégration backend, composants + composable frontend, E2E du flux P1). |
| V. Sécurité & Données | ✅ PASS | Validation `account_id` au rattachement (refus inter-comptes → 403) ; auth requise ; requêtes ORM paramétrées ; pas de secret ; entrées validées Pydantic. |
| VI. Inclusivité & Accessibilité | ✅ PASS | Dark mode sur tous les nouveaux écrans ; messages d'erreur français clairs ; composants légers/lazy (modale, aperçu). |
| VII. Simplicité & YAGNI | ✅ PASS | Aucune nouvelle table ni migration ; réutilisation du JSON `checklist` + composants existants ; 1 seul nouveau composant frontend ; traitement synchrone. |

**Verdict** : aucun écart. Section Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/049-checklist-documents/
├── plan.md              # Ce fichier
├── spec.md              # Spécification (+ clarifications)
├── research.md          # Phase 0 — décisions techniques
├── data-model.md        # Phase 1 — entités & transitions d'état
├── quickstart.md        # Phase 1 — validation manuelle de bout en bout
├── contracts/           # Phase 1 — contrats API
│   ├── attach-document.md
│   ├── detach-document.md
│   └── checklist-serialization.md
└── checklists/
    └── requirements.md  # Checklist qualité de la spec (déjà créée)
```

### Source Code (repository root)

```text
backend/app/
├── modules/applications/
│   ├── router.py          # + PUT/DELETE .../checklist/{item_key}/document ; + checklist_progress
│   ├── service.py         # + attach_checklist_document / detach_checklist_document / compute_checklist_progress / clear_document_references
│   ├── schemas.py         # + AttachDocumentRequest, ChecklistItem enrichi (document, effective status), ChecklistProgress
│   └── templates.py       # (inchangé — statut initial "missing")
├── modules/documents/
│   └── service.py         # delete_document → appelle clear_document_references (nettoyage FR-014)
├── graph/tools/
│   └── application_tools.py # Fix parité get_application_checklist (status=="provided", name, required_by)
└── models/
    ├── application.py     # (inchangé)
    └── document.py        # (inchangé)

backend/tests/test_applications/
├── test_checklist_documents.py   # NOUVEAU — attach/detach/replace/cross-account/progress/audit
├── test_templates.py             # (inchangé)
└── ... 
backend/tests/test_documents/
└── test_delete_cleanup.py        # NOUVEAU — suppression → références nettoyées
backend/tests/test_tools/
└── test_application_tools.py     # MAJ mock checklist → forme réelle

frontend/app/
├── pages/applications/
│   ├── [id].vue           # Onglet Checklist éditable + progression M/N
│   └── index.vue          # Badge progression M/N sur la carte de dossier
├── components/documents/
│   └── DocumentPicker.vue # NOUVEAU — sélecteur (FullscreenModal + DocumentList)
├── components/applications/
│   └── ChecklistItemRow.vue # NOUVEAU — ligne d'item (statut, actions upload/choisir/aperçu/détacher/remplacer)
├── composables/
│   └── useApplications.ts # + attachDocument / detachDocument
├── stores/applications.ts # + ChecklistItem.document?, attachChecklistDocument/detach mutators, checklist_progress
└── types/                 # ChecklistItem enrichi (document optionnel)

frontend/test/ (Vitest)
├── components/DocumentPicker.spec.ts        # NOUVEAU
├── components/ChecklistItemRow.spec.ts      # NOUVEAU
└── composables/useApplications.checklist.spec.ts # NOUVEAU
frontend/e2e/ (Playwright)
└── checklist-documents.spec.ts              # NOUVEAU — flux P1 (upload → Fourni)
```

**Structure Decision** : structure web existante (monolithe modulaire). Backend dans `backend/app/modules/applications` + `modules/documents` ; frontend dans `frontend/app`. On étend les fichiers existants et on ajoute un minimum de fichiers neufs (2 composants frontend, fonctions service/composable, fichiers de tests). Pas de nouvelle frontière de module.

## Complexity Tracking

> Aucune violation de la Constitution. Section vide.
