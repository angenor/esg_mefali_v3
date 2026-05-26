# Phase 1 — Data Model

**Feature**: 048-fix-chatbot-application-flow
**Date**: 2026-05-25

> **Aucune nouvelle table, aucune migration Alembic.** Cette feature corrige des chemins d'accès/exposition et la propagation de contexte. Les entités ci-dessous **existent déjà** ; seules les colonnes/champs **lus** ou **propagés** changent, plus 2 extensions de schémas Pydantic (non persistées en nouvelle table).

## Entités existantes réutilisées

### Dossier de candidature — `fund_applications`
- **Rôle** : candidature d'une PME à une offre/fonds.
- **Champs pertinents** : `id`, `user_id`, `account_id` (RLS F02), `fund_id`, `intermediary_id`, `offer_id` (F07, NOT NULL post-backfill), `project_id` (F06, NOT NULL post-backfill), `status` (draft initial), `sections` (JSON), `checklist`, `snapshot_data`.
- **Changement** : le **chemin de création** (service) doit désormais accepter `offer_id`/`project_id` (déjà supportés par le modèle, posés aujourd'hui uniquement par le tool chat). Voir [contracts/application-creation.md](./contracts/application-creation.md).
- **Invariant ajouté (FR-006)** : pas de second dossier `draft` pour le même `(user_id, project_id, offer_id)` → réutiliser l'existant.

### Évaluation ESG-projet — `project_esg_assessments` (F047)
- **Rôle** : évaluation d'un projet selon un référentiel.
- **Champs pertinents (lecture)** : `id`, `account_id`, `project_id`, `referential_id`, `referential_version`, `state` (`draft`/`finalized`), `score`, `pillar_scores`, `covered_criteria[]`, `missing_criteria[]`, `coverage_rate`, `finalized_at`.
- **Changement** : **aucune** mutation de schéma. Ces champs alimentent le **résumé proactif** injecté dans le contexte (D2).
- **Invariant existant conservé** : un seul `draft` par `(project_id, referential_id)` (409 sinon).

### Réponse à un critère ESG — `project_esg_criterion_responses` (F047)
- **Rôle** : réponse persistée par critère au sein d'une évaluation.
- **Champs pertinents** : `assessment_id`, `criterion_id`, `response_type`, `response_value` (JSONB), `normalized_score`, `source_id`, `unsourced`.
- **Changement** : **aucun**. UPSERT déjà en place. Détermine couvert/manquant.

### Critère / Référentiel — `criteria`, `referentials` (F13)
- **Champs pertinents (lecture)** : `Criterion.is_required`, `Criterion.applies_to_project`, `Criterion.weight`, `Criterion.code`, `Referential.code`, `publication_status`.
- **Usage** : déterminer les critères **requis** pour le gating D4.

### Offre — `offers` (F07)
- **Champs pertinents (lecture)** : `id`, `fund_id`, `intermediary_id`. Critères effectifs via `compute_effective_offer`.
- **Usage** : résoudre `fund_id`/`intermediary_id` à la création (parité chat/UI).

### Projet — `projects` (F06)
- **Usage** : cible du dossier et de l'évaluation ; déjà chargé par `get_active_projects_for_user`.

### Document — `documents`
- **Usage** : le document de candidature généré (D3) y est enregistré pour apparaître dans `/documents`.
- **Champs (existants, modèle `models/document.py`)** : `user_id`, `account_id`, `conversation_id?`, `filename`, `original_filename`, `mime_type`, `file_size`, `storage_path`, `status` (`DocumentStatus`), `document_type` (`DocumentType`).
- **Changement** : aucune colonne ajoutée. Ajout d'une fonction service `register_generated_document(...)` (`documents/service.py`) qui insère une ligne `Document` pour un fichier **déjà écrit sur disque** (le service actuel ne couvre que l'upload entrant via `upload_document`).

## Objets de contexte / transport (non persistés)

### `ConversationState.user_project_esg_assessments` — **nouveau champ d'état**
Liste de résumés légers injectée au démarrage de session (D2, FR-008a). Forme par item :

| Champ | Type | Source |
|-------|------|--------|
| `project_id` | str (UUID) | `project_esg_assessments.project_id` |
| `project_name` | str | `projects.name` |
| `referential_code` | str | `referentials.code` |
| `assessment_id` | str (UUID) | `project_esg_assessments.id` |
| `state` | str | `project_esg_assessments.state` |
| `score` | int \| null | `project_esg_assessments.score` |
| `coverage_rate` | float \| null | `project_esg_assessments.coverage_rate` |
| `covered_count` | int | `len(covered_criteria)` |
| `missing_count` | int | `len(missing_criteria)` |

Analogue à `user_projects` (déjà propagé `chat.py:1239`).

### `ApplicationCreate` (Pydantic) — **extension de schéma**
Ajout de `offer_id: UUID | None` et `project_id: UUID | None` (voir contrat). Pas de nouvelle table.

## Transitions d'état

- **Dossier** : `(absent)` → `draft` (création/dédup) → … (soumission ultérieure hors périmètre).
- **Évaluation ESG** : inchangée — `draft` → `finalized`. Le gating D4 **lit** l'état/couverture, ne le modifie pas.
- **Génération document** : autorisée **uniquement** si critères requis couverts (D4) ; sinon transition bloquée + guidage.

## Règles de validation (issues des requirements)

- FR-006 : unicité fonctionnelle `(user, project, offer)` pour les dossiers `draft`.
- FR-003b/D4 : génération document conditionnée à la couverture des critères `is_required` du référentiel de l'offre.
- FR-016 : chat et UI passent par le **même** service de création (équivalence garantie).
- F02 (RLS) : tout accès scoping `account_id` ; F01 sourçage des chiffres ; F03 audit sur création dossier et mutations ESG conservés.
