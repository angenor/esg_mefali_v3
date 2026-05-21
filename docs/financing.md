# Financement vert — référence consolidée (F08 + F14 + F045)

Index de référence pour le module `financing` côté backend et `/financing`
côté frontend. Combine les trois itérations majeures de la feature.

## Évolution chronologique

| Feature | Sprint | Périmètre |
|---|---|---|
| **F08** (008-conseiller-financement-vert) | Sprint initial | Catalogue fonds + intermédiaires, matching scoring multi-critères PME ↔ fonds, parcours direct vs intermédiaire, dossier candidature |
| **F14** (matching-offers, mig. 026) | Post-F07 | Entité `OfferMatch` (projet, offre) avec décomposition `fund_score` / `intermediary_score` / `global_score`, comparateur intermédiaires d'un même fonds, scoring multi-référentiels F13 |
| **F045** (045-matching-projet-centric, mig. 046) | Sprint en cours | Recentrage sur le projet : `project_score` séparé de `company_score`, 5 nouveaux champs projet (taxonomie UEMOA, thèmes GCF, genre, vulnérables, ESG projet), tool `match_funds_for_project`, skill F23 dédié, 4 gabarits FR divergence |

## Modèle conceptuel consolidé

```
Account (F02 multi-tenant)
   └─> CompanyProfile (PME)
        ├─> ESGAssessment (F05) ─── pilier ESG entreprise (F14)
        └─> Project (F06 + 5 col F045) ─┐
              taxonomie_verte_uemoa     │
              gcf_priority_themes       │
              gender_inclusion          ├─> OfferMatch (F14 + 4 col F045)
              vulnerable_populations    │     fund_score, intermediary_score
              project_esg_score         │     global_score (F14, déprécié 2 sprints)
                                        │     project_score (F045)
                                        │     company_score (F045)
                                        │     project_score_breakdown JSONB
                                        │     divergence_explanation TEXT
                                        │
Offer (F07) = Fund × Intermediary ──────┘
   ├─> Sources F01 (cite_source obligatoire)
   ├─> Money typed F04
   └─> Référentiel F13 (Mefali/GCF/IFC PS/BOAD ESS/GRI)
```

## Catalogues de référence

- **F08** : 12 fonds (GCF, FEM, BOAD, BAD, SUNREF, FNDE, …) + 14 intermédiaires.
- **F07** : ~50 liaisons `fund_intermediaries` accreditées.
- **F25** (044-admin-catalog-financing) : interface admin `/admin/catalog`
  avec 4 onglets (fonds, intermédiaires, offres, fund_intermediaries) + export CSV.

## Pondérations

### F14 — score entreprise (réutilisé comme `company_score` dans F045)

```python
MATCHING_WEIGHTS = {
    "sector":     0.25,
    "esg":        0.30,   # ESGAssessment entreprise
    "size":       0.15,
    "location":   0.10,
    "documents":  0.10,
    "instrument": 0.10,
}
```

### F045 — score projet (8 sub-scores, voir [matching-projet-centric.md](./matching-projet-centric.md))

```python
PROJECT_SCORE_WEIGHTS = {
    "sector":        0.15,
    "taxonomy":      0.20,
    "gcf_themes":    0.20,
    "co2_impact":    0.15,
    "beneficiaries": 0.10,
    "gender":        0.05,
    "vulnerable":    0.05,
    "project_esg":   0.10,
}
```

## Endpoints

### F08 (legacy)

- `GET /api/financing/funds` — catalogue fonds avec filtres
- `GET /api/financing/intermediaries` — annuaire intermédiaires
- `POST /api/financing/match` — matching simple PME ↔ fonds (déprécié au profit de F14/F045)
- `POST /api/financing/dossiers` — génération dossier candidature

### F14

- `GET /api/projects/{id}/matches` — liste matches d'un projet
- `POST /api/projects/{id}/recompute-matches` — recalcule l'ensemble
- `GET /api/projects/{id}/matches/{offer_id}` — détail match
- `GET /api/funds/{fund_id}/compare?project_id={id}` — comparaison intermédiaires d'un fonds

### F045 (nouveau)

- `POST /api/projects/{id}/match-funds` — matching projet-centric, retourne `project_score`/`company_score` séparés
- `GET /api/projects/{id}/match-details/{offer_id}` — détail complet 2 scores + breakdowns + divergence_explanation

## Tools LangChain (état consolidé)

| Tool | Origine | Description |
|---|---|---|
| `list_funds`, `get_fund` | F08 | Lecture catalogue |
| `list_intermediaries`, `get_intermediary` | F08 | Annuaire |
| `list_offers`, `get_offer`, `compare_offers_for_fund` | F07 | Offre = Fonds × Intermédiaire |
| `list_matches_for_project`, `recompute_matches_for_project`, `get_match_details` | F14 | Matching offer-centric |
| **`match_funds_for_project`** | **F045** | **Matching projet-centric** |
| `simulate_offer`, `compare_simulations` | F16 | Simulateur financier sourcé |
| `create_fund_application`, `submit_application` | F08 + F09 | Workflow candidature |

## Skills F23

- `skill_match_project_funds` (F045, en draft → published après eval ≥ 90 %)
- `skill_score_gcf` (F23 initial)
- `skill_dossier_gcf_via_boad` (F23 initial)

## Composants frontend

### Pages

- `/financing` — catalogue 3 onglets (F08)
- `/financing/[id]` — fiche fonds (F08)
- `/financing/offers/[id]` — fiche offre = fonds × intermédiaire (F07)
- `/financing/compare/[fund_id]?project_id=X` — comparateur intermédiaires (F14)
- `/financing/simulator` — simulateur multi-offres (F16)
- `/profile/projects/[id]` — fiche projet avec section « Fonds compatibles » (F045 US5)

### Composants clés

- `<MatchCard>` (F14), `<MatchCardBlock>` (F11 chat), **`<ProjectMatchCardBlock>` (F045)**
- `<EffectiveCriteriaList>`, `<EffectiveDocumentsList>`, `<EffectiveFees>` (F07)
- `<SubmissionModeBadge>`, `<FundCard>`, `<IntermediaryCard>` (F07)
- **`<DualScoreDisplay>`, `<DivergenceBadge>`, `<MissingProjectCriteriaList>`, `<ProjectFundsSection>` (F045)**
- `<SimulationDetailedCard>`, `<SimulationComparator>` (F16)

## Sources F01 mobilisées

- Catalogue F08 : sources fonds (GCF, FEM, BOAD officiel docs)
- F14 référentiels : Mefali, IFC PS, BOAD ESS, GCF, GRI 2021
- **F045** : Taxonomie verte UEMOA (BCEAO 2024), GCF Strategic Plan 2024-2027,
  GCF Updated Gender Policy 2019, ODD 10 — Reduce Inequality

## Tri par défaut des matches

- **F14** : `global_score DESC` (cohabitation 2 sprints)
- **F045** : `project_score DESC, company_score DESC` (nouveau défaut)

Bascule pilotée par `NUXT_PUBLIC_USE_PROJECT_CENTRIC_MATCHING` côté frontend
et `ENABLE_PROJECT_CENTRIC_MATCHING_ENDPOINT` côté backend (rollback ciblé).

## Documents de référence

- [matching-offers.md](./matching-offers.md) — F14 détaillé (comparateur)
- [matching-projet-centric.md](./matching-projet-centric.md) — F045 détaillé
- [catalog-glossary.md](./catalog-glossary.md) — F25 admin catalogue
- `specs/008-conseiller-financement-vert/` — spec F08 originelle
- `specs/045-matching-projet-centric/` — spec F045 complète
