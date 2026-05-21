# Matching projet-centric (F045)

## Vue d'ensemble métier

F045 recentre le matching financement vert sur le **projet** plutôt que sur
l'**entreprise**. Avant F045, le scoring F08 + F14 prenait l'`ESGAssessment`
de la PME comme principal pilote d'éligibilité (poids `esg=0.30`). Conséquence :

- Une PME informelle sans bilan ESG était écartée de fonds qui financent
  pourtant l'impact projet (GCF, FEM, Fonds d'Adaptation).
- Une entreprise « verte » bien notée pouvait porter un projet sans
  pertinence climatique et apparaître en tête des matches.

F045 sépare le score en **deux dimensions indépendantes** :

- `project_score` (0..100) — éligibilité du projet aux critères impact
  (taxonomie UEMOA, thèmes GCF, CO2, bénéficiaires, genre, vulnérables, ESG
  projet, secteur).
- `company_score` (0..100) — robustesse de la PME porteuse (héritage du
  scoring F14 entreprise).

**Aucune agrégation** : la liste de matches est triée par
`project_score DESC, company_score DESC`. La PME voit les deux scores
côte à côte avec une explication métier de la divergence.

## Différences avec F14

| Aspect | F14 (matching offer-centric) | F045 (matching project-centric) |
|---|---|---|
| Unité de matching | PME × Offre | **Projet × Offre** |
| Score retourné | `global_score` agrégé | **`project_score` + `company_score` séparés** |
| Pilier ESG | `ESGAssessment` entreprise | `project_esg_score` (champ projet) |
| Tri par défaut | `global_score DESC` | `project_score DESC, company_score DESC` |
| Tool LangChain | `recompute_matches_for_project` | **`match_funds_for_project`** (nouveau) |
| Skill F23 | — | **`skill_match_project_funds`** (4 golden examples) |
| Explication divergence | — | 4 gabarits FR (`divergence_templates.py`) |
| Boost post-tri | — | 3 fonds prioritaires impact (GCF/FEM/Fonds d'Adaptation) pour PME rouge + projet vert |

**Cohabitation** : `OfferMatch.global_score` reste `NOT NULL` (rétrocompatibilité
F14) pendant 2 sprints. Les endpoints F14 (`list_matches_for_project`,
`compare_offers_for_fund`) continuent de fonctionner. Migration 046 ajoute
4 colonnes (`project_score`, `company_score`, `project_score_breakdown`,
`divergence_explanation`) + 5 colonnes projet sans dropper l'existant.

## Modèle conceptuel

```
Projet (F06 + 5 colonnes F045) ──┐
   taxonomie_verte_uemoa_aligned │
   gcf_priority_themes JSONB     │
   gender_inclusion              ├──> OfferMatch (F14 + 4 colonnes F045)
   vulnerable_populations JSONB  │      project_score
   project_esg_score             │      company_score
                                 │      project_score_breakdown JSONB
                                 │      divergence_explanation TEXT
                                 │
ESGAssessment entreprise ────────┘──> Offre F07 = Fonds × Intermédiaire
```

## Schéma des 8 sub-scores projet

`project_score` se calcule comme moyenne pondérée de 8 sub-scores (constante
`PROJECT_SCORE_WEIGHTS` dans `app/modules/financing/matching_service.py`) :

| Sub-score | Poids | Critère métier | Source F01 |
|---|---|---|---|
| `sector` | 0.15 | Secteur ∈ `target_sectors` du fonds | Profil F06 + fonds F07 |
| `taxonomy` | 0.20 | `taxonomie_verte_uemoa_aligned=true` | BCEAO taxonomie verte 2024 |
| `gcf_themes` | 0.20 | Recouvrement projet ↔ fonds | GCF Strategic Plan 2024-2027 |
| `co2_impact` | 0.15 | `expected_impact_tco2e ≥ seuil fonds` | F17 facteurs d'émission |
| `beneficiaries` | 0.10 | `expected_beneficiaries` vs target fonds | F06 |
| `gender` | 0.05 | `gender_inclusion=true` + politique fonds | GCF Updated Gender Policy 2019 |
| `vulnerable` | 0.05 | Recouvrement `vulnerable_populations` | ODD 10 — Reduce Inequality |
| `project_esg` | 0.10 | `project_esg_score / 100` | Saisie PME (MVP) |

Total = 1.00. Si un sub-score n'a pas de source F01 verified, il est mis
à 0 avec un flag `unsourced=true` dans le `project_score_breakdown` JSONB
(validator F01 `source_required.py`).

## 4 gabarits FR de divergence

Module `app/modules/financing/divergence_templates.py`. Aucun appel LLM,
génération O(1). Détermination par `categorize_divergence(project_score,
company_score)` :

| Catégorie | Critère | Exemple de texte généré |
|---|---|---|
| **convergent** | `abs(project - company) <= 15` | « Votre projet et votre entreprise sont alignés sur les critères de ce fonds. Aucune divergence majeure détectée. » |
| **projet_fort** | `project - company > 30` | « Votre projet est éligible parce qu'il aligne {N} critères impact ({themes_gcf}). Votre entreprise reste à renforcer sur {M} critères financiers et ESG ({top_company_blockers}). » |
| **entreprise_forte** | `company - project > 30` | « Votre entreprise présente un profil solide ({top_company_strengths}) mais votre projet manque {M} attributs verts ({top_project_missing}). Renforcez ces points pour optimiser votre éligibilité. » |
| **moyen** | autres cas (15 < écart ≤ 30) | « Votre projet et votre entreprise présentent un profil contrasté. Consultez le détail des critères pour identifier les axes d'amélioration. » |

Les variables sont remplies à partir du `project_score_breakdown` et du
`company_score_breakdown` JSONB.

## Parcours US1 — PME profil incomplet, projet vert ambitieux

> Coopérative agricole informelle au Togo, sans `ESGAssessment` finalisée,
> projet d'agroforesterie 200 ha (`expected_impact_tco2e=2400`).

```
1. PME se connecte → /financing
2. Sans projet ? L'agent guide via skill_match_project_funds (chat)
3. Création projet via create_project (5 champs critiques F045 collectés
   par widgets F18)
4. Appel match_funds_for_project(project_id)
5. Backend calcule project_score (≥60 grâce à taxonomy + gcf_themes +
   co2_impact >= 1000), company_score reste bas
6. Boost post-tri R13 : GCF + FEM + Fonds d'Adaptation injectés en top
   si présents catalogue F25
7. SSE émet 5 <MatchCardProjectBlock> F11 avec project_score, company_score,
   divergence_explanation gabarit "projet_fort"
8. PME ouvre la fiche → DualScoreDisplay + MissingProjectCriteriaList
   avec SourceLink F01 pour chaque critère
```

**Garantie SC-002** : ≥ 3 fonds incluant GCF, FEM, Fonds d'Adaptation,
chaque match avec `project_score ≥ 60`, indépendamment du score entreprise.

## Parcours US2 — Pilotage cycle de vie projet en chat

```
Tour 1 (PME) : « Je veux installer 50 panneaux solaires dans mon village »
   ↓
Agent : widgets F18 (qcu objectif énergétique, qcu impact, qcm thèmes GCF)
   ↓
Tour 2 : create_project(...) + confirmation
   ↓
PME : « Lance le matching »
   ↓
Agent : match_funds_for_project(project_id)
   ↓
   SSE : 5 <MatchCardProjectBlock> F11 émis
   ↓
PME : « Augmente mon impact CO2 à 5000 tCO2e/an »
   ↓
Agent : update_project(project_id, expected_impact_tco2e=5000)
   ↓
Event listener after_update détecte champ critique → schedule recompute
   asyncio.create_task (debounce 30 s in-process)
   ↓
   SSE : nouvelle liste de MatchCardProjectBlock
```

**Cible perf** : 3 tours conversation max, parcours complet < 90 s
(SC-005, mesuré par E2E Playwright `matching-project-centric.spec.ts`).

## API endpoints

| Endpoint | Description |
|---|---|
| `POST /api/projects/{project_id}/match-funds` | Calcule (ou recalcule) les matches projet-centric, retourne top-N avec `project_score`/`company_score`/`divergence_explanation`. |
| `GET /api/projects/{project_id}/match-details/{offer_id}` | Détail complet d'un match (project_score_breakdown 8 sub-scores + company_score_breakdown 6 piliers F14 + divergence_explanation). |

Voir `specs/045-matching-projet-centric/contracts/api-endpoints.md` pour les
schemas Pydantic v2 complets.

## Tool LangChain `match_funds_for_project`

Whitelisté dans `MODULE_TOOL_MAPPING['financing']`, `['application']` et
`PAGE_TOOL_MAPPING['profile_projects']`, `['chat']`. Émet jusqu'à 5
`<MatchCardProjectBlock>` F11 via marker SSE `__sse_visualization_block__`.

Format JSON de retour LLM (compact) :

```json
{
  "project_id": "uuid",
  "project_name": "Agroforesterie 200ha Togo",
  "matches_count": 5,
  "top_matches": [
    {
      "offer_id": "uuid",
      "fund_name": "Green Climate Fund",
      "intermediary_name": "BOAD",
      "project_score": 78,
      "company_score": 12,
      "divergence_explanation": "...",
      "top_3_blockers_project": ["co2_impact_below_threshold", ...]
    }
  ],
  "no_match_reason": null
}
```

Si `matches_count == 0`, `no_match_reason` contient un message FR
explicitant les thèmes manquants (FR-009).

## Skill F23 `skill_match_project_funds`

- **Domain** : `MATCHING_FINANCING` (ou `FINANCING` en fallback)
- **Status** : `draft` initial — gating eval ≥ 90 % avant `published`
- **Tools whitelisted (21)** :
  - 8 tools projet F06 (`create_project`, `update_project`, `delete_project`,
    `list_projects`, `get_project`, `duplicate_project`,
    `link_document_to_project`, `match_funds_for_project`)
  - 4 tools F14 (`list_matches_for_project`, `recompute_matches_for_project`,
    `get_match_details`, `compare_offers_for_fund`)
  - 3 tools sourçage F01 globaux (`cite_source`, `search_source`,
    `flag_unsourced`)
  - 4 tools F11 visualisation
  - 1 tool F18 widgets (`ask_interactive_question`)
  - 1 tool F12 (`recall_history`)
- **Activation rules** : keywords `["matching", "financement", "fonds",
  "bailleur", "GCF", "FEM", "BOAD", "subvention"]`, priorité 80
- **4 golden examples** couvrant US1, US2, US3, US4

## Event listener after_update + debounce 30 s

Pattern `event.listens_for(Project, 'after_update')` dans
`app/modules/projects/service.py`. Détecte modification d'un champ critique
parmi : `sector`, `target_amount_amount/currency`, `objective_env`,
`expected_impact_tco2e`, `expected_beneficiaries`, et les 5 nouveaux F045.

- Debounce 30 s in-process via `dict[project_id, last_request_ts]`.
- Recompute via `asyncio.create_task(_runner(...))`.
- Cap dur 50 offres par recompute (cohérent F14).
- Volatile au restart (acceptable — au pire un recompute supplémentaire).

Pas de Redis, pas de Celery — principe constitutionnel VII (YAGNI).

## Sources F01 seedées (4 nouvelles)

| Source | Slug | Référence |
|---|---|---|
| Taxonomie verte UEMOA — BCEAO 2024 | `bceao-taxonomie-verte-2024` | BCEAO 2024 |
| GCF Strategic Plan 2024-2027 — Priority Themes | `gcf-strategic-plan-2024-2027` | GCF |
| GCF Updated Gender Policy 2019 | `gcf-gender-policy-2019` | GCF |
| ODD 10 — Reduce Inequality — Indicators | `un-sdg-10-indicators` | UN Stats |

Seed idempotent dans `app/scripts/seed_sources_045.py` (SELECT-before-INSERT).

## Constantes FR partagées backend ↔ frontend

Source de vérité : `backend/app/core/matching_constants.py` (frozensets +
labels FR avec accents). Script `frontend/scripts/sync-matching-constants.ts`
génère `frontend/app/types/matching_enums.generated.ts`. Fichier généré
commité (pas de build CI supplémentaire).

## Composants frontend

| Composant | Page | Description |
|---|---|---|
| `<DualScoreDisplay>` | `/profile/projects/[id]`, `/financing/offers/[id]` | Deux scores côte à côte + badge divergence + tooltip |
| `<DivergenceBadge>` | DualScoreDisplay | 4 variants (convergent vert, projet_fort emerald, entreprise_forte blue, moyen amber) avec ARIA |
| `<MissingProjectCriteriaList>` | Fiche projet, fiche offre | Liste des critères manquants avec SourceLink F01 cliquable |
| `<ProjectFundsSection>` | `/profile/projects/[id]` | Section US5 « Fonds compatibles avec ce projet » avec top 5 matches |
| `<ProjectMatchCardBlock>` | Chat (F11) | Bloc visualisation MatchCard projet-centric avec project_score, company_score, divergence courte, lien fiche fonds |

Composable : `useProjectMatching.ts`. Store : `stores/projectMatching.ts`.

## Rollback strategy

### Frontend (immédiat)

```bash
# frontend/.env
NUXT_PUBLIC_USE_PROJECT_CENTRIC_MATCHING=false
```

→ `<ProjectFundsSection>` se cache, retour comportement F14.

### Backend (ciblé)

- Désactiver le skill via `POST /api/admin/skills/{id}/unpublish`.
- Endpoint `POST /match-funds` reste fonctionnel mais peut être désactivé
  via `ENABLE_PROJECT_CENTRIC_MATCHING_ENDPOINT=false`.

### Total (migration down)

```bash
alembic downgrade -1   # Revient à 044
```

Perte des 4 colonnes `offer_matches` et 5 colonnes `projects`. Les sources
F01 et le skill restent (script cleanup manuel disponible).

## Cibles performance

| Cible | Métrique | Outil |
|---|---|---|
| `POST /match-funds` (cache hit) | < 300 ms | locust/ab |
| `POST /match-funds` (cold, 50 offres) | < 2 s p95 (SC-003) | locust |
| Tool LangChain `match_funds_for_project` | < 2 s | pytest timer |
| Event listener debounce overhead | < 100 ms | pytest-benchmark |
| Parcours E2E Playwright | < 90 s (SC-005) | Playwright HAR |

## Références

- `specs/045-matching-projet-centric/spec.md` — spécification fonctionnelle
- `specs/045-matching-projet-centric/research.md` — décisions techniques R1-R13
- `specs/045-matching-projet-centric/data-model.md` — modèle de données complet
- `specs/045-matching-projet-centric/contracts/api-endpoints.md` — schemas Pydantic
- `docs/matching-offers.md` — référence F14 (comparateur intermédiaires)
- `CLAUDE.md` ledger F045
