# Data Model — Feature 045 (Matching projet-centric)

**Date** : 2026-05-21
**Branche** : `045-matching-projet-centric`

Ce document décrit les entités persistées (tables, contraintes, relations) et les structures JSON manipulées par la feature. Toutes les conventions héritent de F02 (multi-tenant + RLS), F03 (audit log), F04 (Money typed + versioning), F01 (sourçage).

---

## 1. Table `projects` (enrichie — F06 → F045)

### 1.1 Colonnes ajoutées par migration 045

| Colonne | Type SQL | Nullable | Default | Contrainte | Description |
|---|---|---|---|---|---|
| `taxonomie_verte_uemoa_aligned` | `BOOLEAN` | YES | NULL | — | NULL = non évalué ; TRUE = aligné taxonomie BCEAO ; FALSE = explicitement non aligné. Si TRUE, source F01 obligatoire (validator `source_required.py`). |
| `gcf_priority_themes` | `JSONB` | NO | `'[]'::jsonb` | CHECK applicatif (whitelist) | Array de thèmes GCF. Valeurs autorisées : `atténuation`, `adaptation`, `cross_cutting`, `REDD+`, `forêts`, `eau`, `agriculture`, `énergie`. Max 8 éléments (toute la whitelist). |
| `gender_inclusion` | `BOOLEAN` | YES | NULL | — | NULL = non évalué ; TRUE = politique genre GCF 2019 intégrée ; FALSE = pas de volet genre. Si TRUE, source F01 obligatoire. |
| `vulnerable_populations` | `JSONB` | NO | `'[]'::jsonb` | CHECK applicatif (whitelist) | Array de populations cibles. Valeurs autorisées : `femmes`, `jeunes`, `handicapés`, `réfugiés`, `déplacés_internes`. Max 5 éléments. |
| `project_esg_score` | `INTEGER` | YES | NULL | `CHECK (project_esg_score IS NULL OR (project_esg_score >= 0 AND project_esg_score <= 100))` | Score ESG propre au projet (saisi manuel MVP), distinct du score entreprise F13. |

### 1.2 Indexes ajoutés

- `idx_projects_taxonomie_uemoa` : `BTREE (taxonomie_verte_uemoa_aligned)` — accélère le filtre des projets éligibles taxonomie pour le matching.
- `idx_projects_gcf_themes_gin` : `GIN (gcf_priority_themes)` (PostgreSQL only — skip si SQLite) — accélère les requêtes `WHERE gcf_priority_themes @> '["adaptation"]'`.

### 1.3 Whitelists applicatives Python (constantes)

Dans `backend/app/core/matching_constants.py` (NOUVEAU — source de vérité partagée backend/frontend selon R9) :

```python
PROJECT_GCF_PRIORITY_THEMES_VALUES: frozenset[str] = frozenset({
    "atténuation",
    "adaptation",
    "cross_cutting",
    "REDD+",
    "forêts",
    "eau",
    "agriculture",
    "énergie",
})

PROJECT_VULNERABLE_POPULATIONS_VALUES: frozenset[str] = frozenset({
    "femmes",
    "jeunes",
    "handicapés",
    "réfugiés",
    "déplacés_internes",
})
```

### 1.4 Validation Pydantic v2 strict

`ProjectBase` (schema dans `backend/app/modules/projects/schemas.py`) reçoit 5 nouveaux champs :

```python
class ProjectBase(BaseModel):
    # ... champs F06 existants ...
    taxonomie_verte_uemoa_aligned: bool | None = None
    gcf_priority_themes: list[Literal[
        "atténuation", "adaptation", "cross_cutting", "REDD+",
        "forêts", "eau", "agriculture", "énergie",
    ]] = Field(default_factory=list, max_length=8)
    gender_inclusion: bool | None = None
    vulnerable_populations: list[Literal[
        "femmes", "jeunes", "handicapés", "réfugiés", "déplacés_internes",
    ]] = Field(default_factory=list, max_length=5)
    project_esg_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("gcf_priority_themes", "vulnerable_populations")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))  # dedup en préservant l'ordre
```

### 1.5 Audit F03

Tous les nouveaux champs sont automatiquement audités par le listener `before_flush` (mixin `Auditable` déjà actif sur Project depuis F06). Pas de modification de `AUDITABLE_MODELS` nécessaire.

### 1.6 RLS F02

Inchangé — les RLS policies existantes de `projects` (pme_access_own_account + admin_full_access) s'appliquent automatiquement aux nouvelles colonnes.

---

## 2. Table `offer_matches` (enrichie — F14 → F045)

### 2.1 Colonnes ajoutées par migration 045

| Colonne | Type SQL | Nullable | Default | Contrainte | Description |
|---|---|---|---|---|---|
| `project_score` | `INTEGER` | NO | `0` | `CHECK (project_score >= 0 AND project_score <= 100)` | Score d'éligibilité projet 0..100, calculé par `_compute_project_score` (R5). |
| `company_score` | `INTEGER` | NO | `0` | `CHECK (company_score >= 0 AND company_score <= 100)` | Score d'éligibilité entreprise 0..100, hérité de la logique F14 (`sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10, instrument=0.10`). |
| `project_score_breakdown` | `JSONB` | NO | `'{}'::jsonb` | — | Détail du calcul projet : sub-scores par critère, sources F01 mobilisées, critères manquants. Schéma JSON décrit en §3 ci-dessous. |
| `divergence_explanation` | `TEXT` | YES | NULL | — | Paragraphe FR gabarit (pas freetext LLM) expliquant la divergence project/company. NULL si `abs(project_score - company_score) ≤ 15` (cas convergent). Généré par `divergence_templates.build_divergence_explanation(...)` (R6). |

### 2.2 Colonnes existantes — comportement post-045

| Colonne | Statut | Description |
|---|---|---|
| `global_score` | DÉPRÉCIÉ (lecture seule 2 sprints) | Conservé NOT NULL pour rétrocompatibilité F14. Plus utilisé pour le tri. Backfill = `project_score` initial. |
| `fund_score` | DÉPRÉCIÉ (lecture seule 2 sprints) | Hérité F14. Plus utilisé pour le tri. |
| `intermediary_score` | DÉPRÉCIÉ (lecture seule 2 sprints) | Hérité F14. Plus utilisé pour le tri. |
| `score_breakdown` | CONSERVÉ | Contient désormais 2 sous-arbres : `{ project: { ... }, company: { ... } }` (au lieu de `{ fund: { ... }, intermediary: { ... } }` F14). Backfill = mapping `fund → company`, `intermediary → company`, ajout d'un sous-arbre `project = {}` vide pour les anciennes lignes. |
| `bottleneck` | CONSERVÉ | Valeur F14 `fund/intermediary/balanced`. Plus utilisé pour le tri, conservé pour rétrocompatibilité endpoint F14. |
| `recommended_actions` | CONSERVÉ | Format JSONB F14, étendu pour citer aussi les critères projet manquants. |
| `status`, `computed_at`, `expires_at`, `last_notified_at` | INCHANGÉ | TTL 30 jours. |

### 2.3 Contraintes mises à jour

- UNIQUE existante `(project_id, offer_id)` : inchangée.
- Nouveaux CHECK : `project_score IN [0..100]`, `company_score IN [0..100]`.
- RLS F02 : inchangé (les policies couvrent toute la table).

### 2.4 Tri par défaut

Le service `list_matches_for_project` (F14) bascule en 045 vers :
```sql
ORDER BY project_score DESC, company_score DESC, computed_at DESC
```
(au lieu de `ORDER BY global_score DESC` actuellement).

### 2.5 Backfill migration 045

```sql
-- Pseudo-SQL (Alembic op.execute)
UPDATE offer_matches
SET
  project_score = global_score,
  company_score = global_score,
  project_score_breakdown = COALESCE(score_breakdown, '{}'::jsonb),
  divergence_explanation = NULL
WHERE project_score = 0; -- rows nouvelles ont DEFAULT 0, donc tous les existants
```

Round-trip up/down/up : la down migration DROP les 4 nouvelles colonnes sans toucher aux données F14 originales.

---

## 3. Schéma JSONB `project_score_breakdown` (NOUVEAU)

Stocké dans `offer_matches.project_score_breakdown`. Structure stable, validée par schema Pydantic `ProjectScoreBreakdown` côté backend.

```jsonc
{
  "weights_version": "1.0",                          // Constante PROJECT_SCORE_WEIGHTS version
  "sub_scores": {                                    // Score 0..100 par sous-critère
    "sector": 100,                                   // Secteur ∈ target_sectors fonds
    "taxonomy": 100,                                 // taxonomie_verte_uemoa_aligned matche besoin fonds
    "gcf_themes": 75,                                // Recouvrement themes projet ↔ themes fonds (Jaccard × 100)
    "co2_impact": 60,                                // expected_impact_tco2e ≥ seuil fonds (graduel)
    "beneficiaries": 80,                             // expected_beneficiaries ≥ target fonds
    "gender": 100,                                   // gender_inclusion=true ET fonds requiert gender
    "vulnerable": 50,                                // Recouvrement vulnerable_populations
    "project_esg": 70                                // project_esg_score / 100 si renseigné, 50 sinon (neutre)
  },
  "sources_used": [                                  // F01 sources mobilisées (1..N par sub-score)
    {
      "sub_score": "taxonomy",
      "source_id": "uuid-bceao-2024",
      "source_name": "Taxonomie verte UEMOA — BCEAO 2024",
      "url": "https://..."
    },
    {
      "sub_score": "gcf_themes",
      "source_id": "uuid-gcf-strat-plan",
      "source_name": "GCF Strategic Plan 2024-2027",
      "url": "https://..."
    }
    // ... 1 par sub-score, OU flag unsourced si pas de source verified
  ],
  "missing_criteria": [                              // Critères projet manquants (max top 5)
    {
      "key": "co2_impact_below_threshold",
      "label_fr": "Impact CO2 estimé en dessous du seuil GCF (1 000 tCO2e/an minimum)",
      "source_id": "uuid-gcf-strat-plan",
      "kind": "below_threshold",                     // below_threshold | missing | wrong_value
      "current_value": 450,
      "target_value": 1000
    }
  ],
  "boost_applied": {                                 // R13 — boost post-tri pour 3 fonds prioritaires
    "rule_triggered": false,
    "rule_name": "rouge_entreprise_vert_projet"
  },
  "computed_at": "2026-05-21T14:32:00Z",
  "factor_status": "ok"                              // ok | sources_pending | unsourced_fallback
}
```

### 3.1 Champs critiques

- **`weights_version`** : permet de re-scorer un ancien match si la pondération évolue post-MVP.
- **`sub_scores`** : 8 clés strictes (cohérent R5). Validator Pydantic refuse les clés inconnues.
- **`sources_used`** : array, 1 source minimum par `sub_score` qui contribue au score > 0. Si manquant, le validator `source_required.py` (F01) re-déclenche le calcul avec retry 1× puis fallback texte.
- **`missing_criteria`** : top 5 (tri par impact négatif sur le score). Utilisé par UI `<MissingProjectCriteriaList>`.
- **`factor_status`** :
  - `ok` : 100 % des sub_scores ont une source verified.
  - `sources_pending` : ≥ 1 source en statut `pending`, le match est calculé mais affiché avec badge orange.
  - `unsourced_fallback` : fallback texte appliqué après retry — score affiché avec mention « calcul approximatif ».

### 3.2 Validation Pydantic

`backend/app/modules/financing/matching_schemas.py` :

```python
class ProjectSubScoresSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sector: int = Field(ge=0, le=100)
    taxonomy: int = Field(ge=0, le=100)
    gcf_themes: int = Field(ge=0, le=100)
    co2_impact: int = Field(ge=0, le=100)
    beneficiaries: int = Field(ge=0, le=100)
    gender: int = Field(ge=0, le=100)
    vulnerable: int = Field(ge=0, le=100)
    project_esg: int = Field(ge=0, le=100)

class SourceUsedSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sub_score: Literal["sector","taxonomy","gcf_themes","co2_impact",
                       "beneficiaries","gender","vulnerable","project_esg"]
    source_id: UUID
    source_name: str
    url: HttpUrl | None = None

class MissingCriterionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label_fr: str
    source_id: UUID | None = None
    kind: Literal["below_threshold","missing","wrong_value"]
    current_value: float | int | str | None = None
    target_value: float | int | str | None = None

class BoostAppliedSchema(BaseModel):
    rule_triggered: bool
    rule_name: str | None = None

class ProjectScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    weights_version: str = "1.0"
    sub_scores: ProjectSubScoresSchema
    sources_used: list[SourceUsedSchema] = Field(default_factory=list)
    missing_criteria: list[MissingCriterionSchema] = Field(max_length=5, default_factory=list)
    boost_applied: BoostAppliedSchema
    computed_at: datetime
    factor_status: Literal["ok","sources_pending","unsourced_fallback"]
```

---

## 4. Sources F01 nouvelles à seeder

Inscrites en BDD par `backend/app/scripts/seed_sources_045.py` (idempotent SELECT-before-INSERT) :

| Slug | Type | Status | Date | Référence métier |
|---|---|---|---|---|
| `bceao-taxonomie-verte-2024` | `regulatory_taxonomy` | `verified` | 2024-01-01 | R1 — Taxonomie verte UEMOA |
| `gcf-strategic-plan-2024-2027` | `priority_themes` | `verified` | 2024-01-01 | R2 — Thèmes GCF |
| `gcf-gender-policy-2019` | `gender_policy` | `verified` | 2019-07-01 | R3 — Politique genre |
| `un-sdg-10-indicators` | `social_indicators` | `verified` | 2023-09-01 | R4 — ODD 10 (à vérifier si déjà seedé) |

Chaque source : `captured_by ≠ verified_by` (CHECK F01 four-eyes), `valid_from`, `url`, `version`, `catalog_version` valides.

---

## 5. Skill F23 `skill_match_project_funds` (NOUVEAU)

Table `skills` (F23 mig. 033) — un seul enregistrement :

| Champ | Valeur |
|---|---|
| `name` | `skill_match_project_funds` |
| `domain` | `MATCHING_FINANCING` (à ajouter à l'enum `SkillDomain` si absent ; fallback `FINANCING`) |
| `version` | `1.0` |
| `valid_from` | date de déploiement |
| `status` | `draft` initial puis `published` après eval ≥ 90 % |
| `prompt_expert` | (cf. R8) |
| `tool_whitelist` | JSONB : 21 tools (cf. R8) |
| `activation_rules` | JSONB : `{"keywords": [...], "min_keyword_matches": 1, "requires_active_project": false, "priority": 80}` |
| `golden_examples` | JSONB : 4 conversations FR (cf. R8) |
| `sources` | JSONB : références F01 mobilisées (`bceao-taxonomie-verte-2024`, `gcf-strategic-plan-2024-2027`) |
| `created_by` / `verified_by` | UUID admin distincts (CHECK F23 four-eyes) |

### 5.1 Seed via `seed_skills.py`

Le fichier `backend/app/scripts/seed_skills.py` est étendu pour inclure le nouveau skill — pattern identique aux 3 skills existants (`skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad`).

---

## 6. Relations entre entités (vue d'ensemble)

```text
┌──────────────────┐         ┌──────────────────┐
│   accounts (F02) │         │   sources (F01)  │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │ 1..N                       │ 1..N (verified)
         ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│   projects (F06) │         │ skill_match_     │
│  +5 colonnes 045 │◄────────┤ project_funds    │
└────────┬─────────┘         │   (F23 seed)     │
         │                   └──────────────────┘
         │ 1..N
         ▼
┌──────────────────┐         ┌──────────────────┐
│  offer_matches   │────────►│  offers (F07)    │
│  (F14 + 4 col.   │ N..1    │  ─────► funds    │
│   045)           │         │  ─────► intermed │
└──────────────────┘         └──────────────────┘
```

- 1 `project` (F06) ↔ N `offer_matches` (un par offer)
- 1 `offer_match` cite N sources F01 via `project_score_breakdown.sources_used[].source_id`
- 1 `skill_match_project_funds` orchestre la création/update/match projet en chat
- Tous les liens FK respectent RLS F02 (`account_id NOT NULL` partout)

---

## 7. Transitions d'état

### 7.1 Project (F06) — inchangé

```text
draft → seeking_funding → funded → in_execution → closed
              │                                       ▲
              └────────────► cancelled ───────────────┘
```

**Modification 045** : le matching projet est disponible **dès `draft`** (assumption documentée). Pas de gate `status='seeking_funding'`.

### 7.2 OfferMatch — étendu

```text
suggested (initial)
   │
   ├──► viewed (PME a ouvert la fiche)
   ├──► dismissed (PME a fermé / pas intéressé)
   └──► converted (PME a démarré un fund_application)
```

**Modification 045** : les transitions restent identiques mais `expires_at` reste à `computed_at + 30 jours`. Le recompute (auto F08 ou on-demand) réinitialise `expires_at`.

---

## 8. Volumétrie attendue

| Table | Volumétrie estimée (post-MVP) |
|---|---|
| `projects` | ~5 000 projets total (250 PME × 20 projets max chacune) |
| `offer_matches` | ~50 offres × ~5 000 projets = ~250 000 lignes |
| Sources nouvelles 045 | 4 sources seedées |
| Skills nouveaux 045 | 1 skill |

Les indexes proposés (GIN sur `gcf_priority_themes`, BTREE sur `taxonomie_verte_uemoa_aligned`) restent acceptables à cette échelle.

---

## 9. Schémas Pydantic v2 récapitulatifs (à créer dans 045)

Dans `backend/app/modules/financing/matching_schemas.py` (extension) :

- `MatchFundsRequest` : payload du nouvel endpoint `POST /api/projects/{project_id}/match-funds`
- `MatchFundsResponse` : payload de retour (liste de matches)
- `ProjectSubScoresSchema` : sub-scores projet (§3.2)
- `SourceUsedSchema` : source F01 utilisée pour un sub-score
- `MissingCriterionSchema` : critère manquant
- `BoostAppliedSchema` : trace du boost R13
- `ProjectScoreBreakdown` : breakdown complet
- `DivergenceExplanationSchema` : payload divergence (texte + métadonnées)

Tous `extra="forbid"` strict, `frozen=True` pour les sous-modèles immuables.
