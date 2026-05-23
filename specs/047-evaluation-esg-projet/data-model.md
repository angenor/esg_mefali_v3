# Phase 1 — Data Model

**Feature** : 047-evaluation-esg-projet
**Date** : 2026-05-21
**Migration Alembic** : `backend/alembic/versions/047_project_esg_assessments.py`

---

## Vue d'ensemble

Deux nouvelles tables introduites par 047 :

```text
project_esg_assessments  (1 ───► N)  project_esg_criterion_responses
        │
        │ (N ───► 1)
        ▼
    projects (F045 — existant)
    referentials (F13 — existant)
    criteria (F13 — existant)
    sources (F01 — existant)
    accounts (F02 — existant)
```

Aucune mutation de table existante (`esg_assessments` F05, `projects` F045, `referentials` F13, etc.). La colonne `projects.project_esg_score` (héritage F045) reste inchangée structurellement ; son comportement devient un cache lecture-seule alimenté par listener (cf. D8).

---

## Table 1 — `project_esg_assessments`

### Schéma SQL (PostgreSQL 16)

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Identifiant unique de l'évaluation |
| `account_id` | `UUID` | `NOT NULL`, FK → `accounts.id` ON DELETE CASCADE | Tenant propriétaire (RLS F02) |
| `project_id` | `UUID` | `NOT NULL`, FK → `projects.id` ON DELETE CASCADE | Projet évalué |
| `referential_id` | `UUID` | `NOT NULL`, FK → `referentials.id` ON DELETE RESTRICT | Référentiel cible (IFC PS, GCF ESS, BOAD ESS, etc.) |
| `referential_version` | `VARCHAR(16)` | `NOT NULL` | Snapshot F04 du `referentials.version` au moment de création (rétrospective stable même si le référentiel est versionné ultérieurement) |
| `state` | `VARCHAR(16)` | `NOT NULL`, CHECK IN (`'draft'`, `'finalized'`) | Cycle de vie : draft → finalized (immuable une fois finalized) |
| `score` | `INT` | NULL, CHECK 0..100 | Score 0..100 calculé à la finalisation (NULL tant que `state='draft'`) |
| `pillar_scores` | `JSONB` | `NOT NULL DEFAULT '{}'` | Détail par standard du référentiel (ex : `{"PS1": 75, "PS2": 60, ...}`) |
| `covered_criteria` | `JSONB` | `NOT NULL DEFAULT '[]'` | Liste des `criterion_id` répondus (UUID array) |
| `missing_criteria` | `JSONB` | `NOT NULL DEFAULT '[]'` | Liste des `criterion_id` obligatoires non répondus (vide à la finalisation, sinon refus) |
| `coverage_rate` | `NUMERIC(4,3)` | NULL, CHECK 0..1 | Ratio critères répondus / total critères du référentiel |
| `snapshot_data` | `JSONB` | NULL | Snapshot F04 des paramètres ayant servi au calcul (`{criterion_weights: {...}, scoring_formula: "weighted_avg"}`) ; figé à la finalisation |
| `finalized_at` | `TIMESTAMPTZ` | NULL | Horodatage de finalisation (NULL tant que `state='draft'`) |
| `created_by` | `UUID` | `NOT NULL`, FK → `users.id` ON DELETE RESTRICT | Utilisateur ayant créé l'évaluation |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | Mis à jour à chaque modification |

### Contraintes additionnelles

- **CHECK** `chk_finalized_score_present` : `(state = 'finalized' AND score IS NOT NULL AND finalized_at IS NOT NULL) OR state = 'draft'`
- **CHECK** `chk_finalized_no_missing_required` : `(state = 'finalized' AND missing_criteria::jsonb = '[]'::jsonb) OR state = 'draft'`
- **UNIQUE partielle** `uq_finalized_active_per_ref` : `UNIQUE (account_id, project_id, referential_id) WHERE state = 'finalized' AND superseded_at IS NULL` — garantit une seule évaluation finalisée active par (projet, référentiel). Une nouvelle évaluation contre le même référentiel marquera la précédente `superseded_at = now()` côté service (pas trigger SQL pour éviter cycles).

### Indexes

| Index | Colonnes | Type | Justification |
|---|---|---|---|
| `idx_pea_lookup` | `(account_id, project_id, referential_id)` | BTREE | Lookup principal côté matching et UI fiche projet |
| `idx_pea_finalized_active` | `(project_id, referential_id) WHERE state = 'finalized'` | BTREE partial | Lookup matching consomme uniquement finalized |
| `idx_pea_state_account` | `(account_id, state)` | BTREE | Liste « mes évaluations en cours » |

### RLS F02

```sql
ALTER TABLE project_esg_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_esg_assessments FORCE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account ON project_esg_assessments
    USING (account_id = current_setting('app.account_id')::uuid)
    WITH CHECK (account_id = current_setting('app.account_id')::uuid);

CREATE POLICY admin_full_access ON project_esg_assessments
    TO admin
    USING (true)
    WITH CHECK (true);
```

### Audit log F03

Le modèle SQLAlchemy applique le mixin `Auditable` (déjà existant). Listener `before_flush` capture le diff field-level et insère une ligne `audit_log` par modification (transitions `state`, mises à jour de `score`, etc.). Append-only garanti par les triggers PL/pgSQL existants sur `audit_log`.

---

## Table 2 — `project_esg_criterion_responses`

### Schéma SQL

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Identifiant unique de la réponse |
| `account_id` | `UUID` | `NOT NULL`, FK → `accounts.id` ON DELETE CASCADE | Tenant (RLS F02) |
| `assessment_id` | `UUID` | `NOT NULL`, FK → `project_esg_assessments.id` ON DELETE CASCADE | Évaluation parente |
| `criterion_id` | `UUID` | `NOT NULL`, FK → `criteria.id` ON DELETE RESTRICT | Critère du catalogue F13 |
| `response_type` | `VARCHAR(32)` | `NOT NULL`, CHECK IN (`'qcu'`, `'qcm'`, `'qcu_justification'`, `'qcm_justification'`, `'numeric'`, `'money'`, `'free_text'`) | Type de widget F18 ayant collecté la réponse |
| `response_value` | `JSONB` | `NOT NULL` | Valeur typée selon `response_type` : `{"choice": "yes"}`, `{"choices": ["a", "c"]}`, `{"choice": "no", "justification": "..."}`, `{"value": 12.5}`, `{"amount": "1000.00", "currency": "XOF"}`, `{"text": "..."}` |
| `normalized_score` | `NUMERIC(4,3)` | `NOT NULL`, CHECK 0..1 | Valeur normalisée en [0,1] pour le calcul agrégé (cf. `project_scoring.normalize_response`) |
| `source_id` | `UUID` | NULL, FK → `sources.id` ON DELETE RESTRICT | Source F01 citée par la PME pour cette réponse (NULL si le critère est `unsourced=true` accepté) |
| `unsourced` | `BOOLEAN` | `NOT NULL DEFAULT false` | True si la PME a choisi explicitement « non sourcé » (validator F01 retry 1× puis fallback texte) |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | Mis à jour à chaque correction (révision draft autorisée par FR-003a) |

### Contraintes additionnelles

- **UNIQUE** `uq_one_response_per_criterion_per_assessment` : `UNIQUE (assessment_id, criterion_id)` — une seule réponse active par (évaluation, critère). La révision (FR-003a) fait un UPDATE plutôt qu'un INSERT.
- **CHECK** `chk_source_or_unsourced` : `(source_id IS NOT NULL AND unsourced = false) OR (source_id IS NULL AND unsourced = true)` — XOR strict pour respecter F01.

### Indexes

| Index | Colonnes | Type | Justification |
|---|---|---|---|
| `idx_pecr_assessment` | `(assessment_id)` | BTREE | Liste des réponses d'une évaluation |
| `idx_pecr_lookup` | `(account_id, assessment_id, criterion_id)` | BTREE | Lookup direct (mise à jour révision draft) |
| `idx_pecr_unsourced` | `(assessment_id) WHERE unsourced = true` | BTREE partial | Audit qualité sourçage F01 (SC-009) |

### RLS F02

Identique pattern table 1 (`pme_access_own_account` + `admin_full_access`).

### Audit log F03

Mixin `Auditable` appliqué. Chaque correction de réponse (révision draft) génère une ligne d'audit avec diff `response_value` avant/après.

---

## Modification table existante `projects` (F045 — comportement, pas schéma)

**Aucune migration sur la table `projects`.** La colonne `project_esg_score INT NULL` (introduite par F045 mig. 046) reste inchangée structurellement. Son comportement évolue **applicatif** :

- Le service `projects.update_project()` ajoute une règle : si une `ProjectEsgAssessment` finalisée existe pour ce projet, toute mise à jour du champ `project_esg_score` via API DOIT retourner HTTP 409 (Conflict) avec message FR clair (FR-033, clarification Q6).
- Le listener SQLAlchemy `project_listener.py` (D8) écoute `after_insert`/`after_update` sur `ProjectEsgAssessment` et UPDATE `projects.project_esg_score = ProjectEsgAssessment.score` quand `state='finalized'` (debounce 30 s in-process).

---

## DTO Pydantic v2 (schemas dans `backend/app/modules/esg/project_schemas.py`)

### Création d'évaluation

```python
class ProjectEsgAssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    referential_id: UUID

class ProjectEsgAssessmentRead(BaseModel):
    id: UUID
    project_id: UUID
    referential_id: UUID
    referential_version: str
    state: Literal["draft", "finalized"]
    score: int | None  # 0..100
    pillar_scores: dict[str, int]
    covered_criteria: list[UUID]
    missing_criteria: list[UUID]
    coverage_rate: Decimal | None  # 0..1
    snapshot_data: dict[str, Any] | None
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### Sauvegarde réponse critère

```python
class ProjectEsgCriterionResponseSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion_id: UUID
    response_type: Literal["qcu", "qcm", "qcu_justification", "qcm_justification", "numeric", "money", "free_text"]
    response_value: dict[str, Any]  # Validé selon response_type via validator
    source_id: UUID | None = None
    unsourced: bool = False

    @model_validator(mode="after")
    def check_source_xor_unsourced(self) -> "ProjectEsgCriterionResponseSave":
        if (self.source_id is None) != self.unsourced:
            raise ValueError("source_id et unsourced doivent être mutuellement exclusifs (XOR strict)")
        return self
```

### Finalisation

```python
class ProjectEsgAssessmentFinalize(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Aucun champ d'entrée — finalisation déterministe à partir des réponses persistées

class ProjectEsgAssessmentFinalizeResult(BaseModel):
    assessment: ProjectEsgAssessmentRead
    score: int
    pillar_scores: dict[str, int]
    missing_criteria: list[CriterionRef]  # Ne devrait être vide si finalisation autorisée
    coverage_rate: Decimal
```

### Rapport ESIA-light

```python
class ProjectEsgReportGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_appendix_sources: bool = True  # Annexe F01 obligatoire mais paramétrable pour preview

class ProjectEsgReportResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    file_path: str  # Chemin local /uploads/reports/esia/...
    generated_at: datetime
    template_version: str  # "esia_v1"
    section_count: int
    chart_count: int
    sources_cited: int
```

### Matching breakdown (extension F045)

```python
# Existing F045 ProjectScoreBreakdown enrichi
class ProjectEsgSubScore(BaseModel):
    score: int  # 0..100
    weight: float  # 0.10 (inchangé F045)
    is_fallback: bool  # True si IFC PS utilisé par défaut (clarification Q4)
    referential_used: ReferentialRef  # ID + nom + version
    assessment_id: UUID | None  # NULL si fallback F045 manuel ou unsourced
    source_kind: Literal["calculated", "manual_f045", "unsourced"]
    unsourced: bool  # True si source_kind='unsourced'
```

---

## State machine `ProjectEsgAssessment`

```text
┌───────┐  create_project_esg_assessment(project_id, referential_id)
│ START │ ──────────────────────────────────────────────────────────────►  ┌───────┐
└───────┘                                                                  │ DRAFT │
                                                                           └───┬───┘
                                                                               │
                                            save_project_esg_criterion(×N)    │ FR-003, FR-003a
                                          ┌─────────────────────────────────►│
                                          │                                   │
                                          │   finalize_project_esg_assessment │ FR-005, FR-006
                                          │   (refusé si critères obligatoires manquants)
                                          │                                   ▼
                                          │                              ┌───────────┐
                                          │                              │ FINALIZED │  (immuable, FR-005)
                                          │                              └─────┬─────┘
                                          │                                    │
                                          │                                    │  re-évaluation crée nouvelle ligne (FR-008)
                                          │                                    │  l'ancienne est marquée superseded_at (service)
                                          ▼                                    ▼
                                       (RESTE EN DRAFT)                  (NOUVEAU DRAFT créé pour la nouvelle évaluation)
```

**Transitions explicitement interdites** :
- `finalized → draft` : refus dur (immuabilité FR-005).
- `finalized → finalized` (mutation du score) : refus dur (snapshot frozen).
- Suppression `draft` : autorisée via service `delete_project_esg_assessment_draft`.
- Suppression `finalized` : autorisée via service `delete_project_esg_assessment_finalized` mais déclenche listener D8 qui reset le snapshot `projects.project_esg_score` (cohérent avec FR-029/FR-031).

---

## Relations cross-module

| Source | Cible | Type | Comportement ON DELETE |
|---|---|---|---|
| `project_esg_assessments.account_id` | `accounts.id` | N:1 | CASCADE (suppression d'un compte purge ses évaluations) |
| `project_esg_assessments.project_id` | `projects.id` | N:1 | CASCADE (suppression d'un projet purge ses évaluations) |
| `project_esg_assessments.referential_id` | `referentials.id` | N:1 | RESTRICT (un référentiel utilisé ne peut être supprimé) |
| `project_esg_assessments.created_by` | `users.id` | N:1 | RESTRICT (préserver la traçabilité F03 audit) |
| `project_esg_criterion_responses.assessment_id` | `project_esg_assessments.id` | N:1 | CASCADE |
| `project_esg_criterion_responses.criterion_id` | `criteria.id` | N:1 | RESTRICT |
| `project_esg_criterion_responses.source_id` | `sources.id` | N:1 | RESTRICT (une source citée ne peut être supprimée) |

---

## Cas particuliers / Edge cases (mapping spec ↔ data model)

| Edge case spec | Comportement data model |
|---|---|
| Évaluation orpheline (projet supprimé) | CASCADE supprime toutes les évaluations + réponses du projet ; listener D8 ne se déclenche pas (le projet n'existe plus) |
| Changement de référentiel en cours | Nouvelle `ProjectEsgAssessment` créée (1 par couple project × referential) ; l'ancienne reste en `draft` jusqu'à suppression manuelle |
| Évolution version référentiel F13 | `referential_version` snapshot dans la ligne d'évaluation ; pas de recalcul auto ; cron F13 envoie reminder PME |
| Tenant tiers accède à une évaluation | RLS F02 filtre la ligne → service retourne 404 (jamais 403) |
| Finalisation sans critères obligatoires | `missing_criteria != []` → CHECK `chk_finalized_no_missing_required` viole → transaction rollback → service retourne 422 avec liste explicite |
| Score F045 manuel et calculé différents | Matching consomme le calculé (priorité FR-029) ; listener D8 réécrit le snapshot |
| Conversion draft abandonné | Pas de purge auto ; PME peut supprimer ; F12 mémoire contextuelle conserve les traces des widgets passés |
| PDF échoue (timeout WeasyPrint) | Aucune ligne `ProjectEsgReport` créée ; HTTP 504 retourné ; pas de transaction partielle |
| LLM dépasse 12 widgets F18 | Service `project_service.next_pending_criterion()` retourne `None` après 12 widgets émis ; LLM bascule sur lien wizard UI (D5) |
| Référentiel F13 dépublié (`status='outdated'`) | Création de nouvelle évaluation refusée par le service (CHECK applicatif sur `referentials.status`) ; évaluations finalisées existantes restent lisibles |

---

## Performance & volume

- Volume estimé : ~100 projets actifs par tenant × ~5 évaluations en moyenne = ~500 lignes `project_esg_assessments` par tenant.
- Volume `project_esg_criterion_responses` : ~500 × 16 critères = ~8 000 lignes par tenant.
- Indexes BTREE suffisants pour les requêtes principales (lookup matching, list évaluations).
- Pas de besoin de pgvector ni de table partitionnée pour 047 MVP.

---

## Outputs Phase 1

- ✅ `data-model.md` (ce fichier)
- ⏭️ `contracts/*.openapi.yaml` (à suivre)
- ⏭️ `quickstart.md` (à suivre)
- ⏭️ Update agent context (CLAUDE.md via script)
