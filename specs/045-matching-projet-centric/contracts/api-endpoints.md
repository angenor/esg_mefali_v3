# Contracts — API REST endpoints (Feature 045)

**Date** : 2026-05-21
**Branche** : `045-matching-projet-centric`

Ce document décrit les endpoints REST nouveaux ou modifiés par la feature 045. Les endpoints F14 existants restent fonctionnels (cohabitation 2 sprints).

---

## 1. `POST /api/projects/{project_id}/match-funds` (NOUVEAU)

**Objectif** : Déclencher le calcul (ou récupérer du cache) du matching projet → fonds avec scores projet et entreprise séparés.

### 1.1 Authentification & autorisation

- Bearer token JWT requis (header `Authorization: Bearer <token>`).
- Rôle : PME ou ADMIN.
- RLS PostgreSQL F02 : `current_setting('app.current_account_id')` filtre automatiquement le `project_id` au compte appelant.

### 1.2 Request

**Path parameters** :
| Nom | Type | Description |
|---|---|---|
| `project_id` | UUID | Identifiant du projet F06. Doit appartenir au `account_id` du token (sinon 404 silencieux RLS). |

**Query parameters** (optionnels) :
| Nom | Type | Default | Description |
|---|---|---|---|
| `min_score` | int 0..100 | 60 | Seuil minimum sur `project_score` pour inclusion dans la liste. |
| `limit` | int 1..50 | 10 | Nombre maximum de matches retournés (top N par `project_score DESC`). |
| `force_recompute` | bool | false | Si `true`, ignore le cache `expires_at` et force le recalcul de tous les matches. |

**Body** : aucun (POST sans body — déclenchement idempotent par défaut, force_recompute pour bypass cache).

### 1.3 Response 200 OK — `MatchFundsResponse`

```jsonc
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "Agroforesterie 200ha Togo",
  "matches_count": 5,                                  // Nombre total de matches retournés
  "top_matches": [
    {
      "offer_id": "...",
      "fund_id": "...",
      "fund_name": "Green Climate Fund",
      "intermediary_id": "...",
      "intermediary_name": "BOAD",
      "project_score": 78,
      "company_score": 12,
      "project_score_breakdown": {
        // cf. data-model.md §3
        "sub_scores": {
          "sector": 100, "taxonomy": 100, "gcf_themes": 75,
          "co2_impact": 60, "beneficiaries": 80,
          "gender": 100, "vulnerable": 50, "project_esg": 70
        },
        "sources_used": [...],
        "missing_criteria": [...],
        "boost_applied": { "rule_triggered": true, "rule_name": "rouge_entreprise_vert_projet" },
        "factor_status": "ok",
        "weights_version": "1.0",
        "computed_at": "2026-05-21T14:32:00Z"
      },
      "divergence_explanation": "Votre projet est éligible parce qu'il aligne 4 critères impact ...",
      "computed_at": "2026-05-21T14:32:00Z",
      "expires_at": "2026-06-20T14:32:00Z"
    }
    // ... 4 autres matches
  ],
  "no_match_reason": null,                             // String si matches_count == 0
  "recompute_request_id": "..."                        // UUID si force_recompute=true et recalcul background
}
```

**Champ `no_match_reason`** (présent uniquement si `matches_count == 0`) :
```json
"Aucun fonds n'aligne ses critères avec ce projet. Renforcez les thèmes suivants : taxonomie verte UEMOA, impact CO2 chiffré, alignement adaptation."
```

### 1.4 Response 202 Accepted (si force_recompute=true)

Le calcul tourne en background. Le frontend doit poll `GET /api/projects/{project_id}/matches` jusqu'à `expires_at` mis à jour.

```jsonc
{
  "recompute_request_id": "...",
  "total_offers_to_compute": 47,
  "matches_count": 5,                                  // Snapshot du cache pré-recompute
  "top_matches": [...]                                 // Optionnel : peut renvoyer le cache stale en attendant
}
```

### 1.5 Errors

| Status | Cas |
|---|---|
| 400 | `min_score` ou `limit` hors plage |
| 401 | Token manquant ou invalide |
| 403 | `account_id` manquant sur le user |
| 404 | `project_id` introuvable (peut être RLS — pas de fuite d'existence) |
| 422 | `project_id` mal formé (UUID invalide) |
| 503 | Migration 045 non encore appliquée (`offer_matches.project_score` absent) |

---

## 2. `GET /api/projects/{project_id}/matches` (EXISTANT F14 — MAJ format payload)

**Modification 045** : le payload de chaque item est étendu pour inclure `project_score`, `company_score`, `divergence_explanation`, `project_score_breakdown`. Les champs F14 (`global_score`, `fund_score`, `intermediary_score`, `bottleneck`) restent présents (rétrocompatibilité).

### 2.1 Tri par défaut modifié

Avant 045 : `ORDER BY global_score DESC`.
Après 045 : `ORDER BY project_score DESC, company_score DESC, computed_at DESC`.

### 2.2 Query parameters ajoutés

| Nom | Type | Default | Description |
|---|---|---|---|
| `min_project_score` | int 0..100 | 0 | Seuil minimum sur `project_score` (en complément de `min_score` F14 qui s'applique au `global_score`). |
| `min_company_score` | int 0..100 | 0 | Seuil minimum sur `company_score`. |

### 2.3 Compatibilité ascendante

Les clients F14 existants qui ne lisent que `global_score` continuent de fonctionner. Le champ est conservé en lecture seule, alimenté au backfill par `project_score` initial.

---

## 3. `POST /api/projects/{project_id}/recompute-matches` (EXISTANT F14 — INCHANGÉ)

Sémantique identique F14 : déclenche un recompute async via `BackgroundTasks`. Le calcul interne utilise désormais `_compute_project_score` et `_compute_company_score` (refactor de `compute_offer_match`).

---

## 4. `GET /api/projects/{project_id}/match-details/{offer_id}` (EXISTANT F14 — MAJ format payload)

**Modification 045** : payload étendu avec :
- `project_score`, `company_score` séparés
- `project_score_breakdown` complet (cf. data-model.md §3)
- `company_score_breakdown` (héritage F14, format `{ fund: { ... }, intermediary: { ... } }`)
- `divergence_explanation` (texte gabarit FR)

---

## 5. `GET /api/projects/{project_id}/compare?fund_id={fund_id}` (EXISTANT F14 — MAJ format payload)

**Modification 045** : chaque colonne du ComparisonTableBlock affiche désormais 2 lignes de scores (`Score projet` / `Score entreprise`) au lieu d'1 (`Score global`).

---

## 6. Endpoints alertes F14 — INCHANGÉS

- `PATCH /api/projects/{project_id}/match-alerts` (F14)
- `GET /api/projects/{project_id}/match-alerts` (F14)

Les souscriptions `match_alerts_subscriptions` utilisent désormais `project_score` au lieu de `global_score` pour le seuil `min_global_score` → renommer le champ en `min_project_score` post-MVP (hors-scope 045 stricte mais pré-tâche tasks.md).

---

## 7. OpenAPI export

Les nouveaux schemas Pydantic v2 (`MatchFundsRequest`, `MatchFundsResponse`, `ProjectScoreBreakdown`, `MissingCriterionSchema`, etc.) sont automatiquement exposés via `app.openapi()` FastAPI → `/api/docs` (Swagger UI) et `/api/openapi.json`. Un test conformity vérifie que ces schemas existent dans le bundle OpenAPI à la fin du sprint.
