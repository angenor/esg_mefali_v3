# Contract — `POST /api/projects/{project_id}/simulate-multi`

**Module** : `app.modules.applications.router`
**Auth** : `Depends(get_current_user)` (F02), RLS PG via `set_rls_context(account_id, role, user_id)`.
**Idempotence** : OUI (lecture seule, pas de mutation).
**Persistance** : NON (FR-012, SC-006).

## Path parameters

| Nom | Type | Description |
|-----|------|-------------|
| `project_id` | `UUID` | Identifiant projet (F06). Doit appartenir au tenant appelant. |

## Request body (`application/json`)

```json
{
  "offer_ids": ["<uuid>", "<uuid>", "<uuid>"]
}
```

**Schema** : `MultiSimulateRequest` (Pydantic v2)

| Champ | Type | Contraintes |
|-------|------|-------------|
| `offer_ids` | `list[UUID]` | `min_length=1`, `max_length=5`. Validateur applicatif dédupliquant les doublons avant calcul. |

## Response 200 (`application/json`)

```json
{
  "project_id": "<uuid>",
  "factor_snapshot_loaded_at": "2026-05-08T10:32:11.234Z",
  "per_offer": {
    "<offer_id_1>": {
      "offer_id": "<offer_id_1>",
      "project_id": "<uuid>",
      "principal": {"amount": "5000000.00", "currency": "XOF"},
      "principal_pme_equivalent": {"amount": "5000000.00", "currency": "XOF"},
      "cost_breakdown": {
        "principal": {"amount": "5000000.00", "currency": "XOF"},
        "doc_fee": {
          "amount": {"amount": "150000.00", "currency": "XOF"},
          "amount_pme_equivalent": {"amount": "150000.00", "currency": "XOF"},
          "source_id": "<src_uuid>",
          "factor_name": "default_doc_fee",
          "factor_status": "verified",
          "degraded_reason": null
        },
        "total_fees_over_duration": {"...": "..."},
        "guarantee_required": {"...": "..."},
        "fx_margin": {"...": "..."},
        "total_cost": {"amount": "5180000.00", "currency": "XOF"}
      },
      "roi": {
        "instrument": "pret_concessionnel",
        "formula_id": "roi.loan.gain_minus_cost_ratio",
        "gain_estimated": {"amount": "1200000.00", "currency": "XOF"},
        "payback_months": 42,
        "ratio": "0.231",
        "notes_fr": "Ratio gains estimés / coût total = 0.23",
        "sources": ["<src_uuid_a>", "<src_uuid_b>"]
      },
      "carbon_impact": {
        "tco2e_per_year": "12.4",
        "sector_factor": "1.00",
        "factor_source_id": "<src_uuid_c>",
        "project_estimate_used": "12.4",
        "is_approximate": false,
        "degraded_reason": null
      },
      "timeline": [
        {"step_id": "preparation", "label_fr": "Préparation dossier", "weeks_min": 2, "weeks_max": 4, "source_id": null, "degraded_reason": null},
        {"step_id": "instruction_intermediaire", "label_fr": "Instruction intermédiaire", "weeks_min": 6, "weeks_max": 10, "source_id": "<src_uuid_d>", "degraded_reason": null},
        {"step_id": "validation_fonds", "label_fr": "Validation fonds source", "weeks_min": 22, "weeks_max": 26, "source_id": "<src_uuid_e>", "degraded_reason": null},
        {"step_id": "decaissement", "label_fr": "Décaissement", "weeks_min": 4, "weeks_max": 8, "source_id": "<src_uuid_f>", "degraded_reason": null}
      ],
      "sources_used": ["<src_uuid>", "..."],
      "degraded": false,
      "computed_at": "2026-05-08T10:32:11.567Z"
    },
    "<offer_id_2>": {
      "offer_id": "<offer_id_2>",
      "degraded": true,
      "reason": "facteur_critique_introuvable",
      "computed_at": "2026-05-08T10:32:11.612Z"
    }
  },
  "comparison_metadata": {
    "cheapest_offer_id": "<offer_id_1>",
    "fastest_offer_id": "<offer_id_3>",
    "degraded_offers": ["<offer_id_2>"],
    "total_offers": 3
  }
}
```

## Errors

| Code | Cas | Body |
|------|-----|------|
| 401 | Non authentifié | `{"detail":"Not authenticated"}` |
| 403 | Une `offer_id` n'est pas visible par le tenant (RLS) | `{"detail":"Access denied"}` (cohérent FR-013, ne révèle pas si l'offre existe) |
| 404 | `project_id` introuvable ou pas dans le tenant | `{"detail":"Project not found"}` (FR-013, même message que vrai 404) |
| 422 | `offer_ids` vide après dedup, ou > 5, ou format UUID invalide | `{"detail":[{...Pydantic errors...}]}` (FR-014) |
| 503 | Catalogue corrompu (facteurs essentiels absents — situation impossible en prod, signal admin) | `{"detail":"Simulation catalog unavailable"}` |

## Sécurité

- RLS PG active sur `projects` et `offers` (F02 — déjà câblée par `get_current_user`).
- Aucune information révélatrice dans les messages d'erreur (FR-013).
- Aucune persistance en base (FR-012). Pas de log applicatif contenant le résultat de simulation (seulement les paramètres anonymisés et la durée d'exécution pour observabilité).

## Performance attendue

- p95 < 2 s pour 3 offres, < 5 s pour 5 offres (SC-005).
- Charge DB : 1 SELECT factors + 1 SELECT projects + 1 SELECT offers/funds/intermediaries (N=5) + 1 SELECT exchange_rates si conversion ; total < 10 requêtes.

## Tests à fournir

| Type | Fichier | Cas couverts |
|------|---------|--------------|
| Unit | `tests/unit/test_multi_simulate_service.py` | dedup ; 1 offre = pas de winner ; 2+ offres = cheapest/fastest calculés ; offre dégradée exclue du ranking. |
| Integration | `tests/integration/test_simulate_multi_router.py` | 200 happy path 3 offres ; 422 > 5 ; 422 vide ; 404 projet hors tenant ; 403 offre hors tenant ; 200 avec colonne dégradée ; vérifie `factor_snapshot_loaded_at` cohérent. |
| Integration | `tests/integration/test_simulate_multi_rls.py` | bascule de session avec deux comptes, vérifie isolation. |
| Conformité sources | `tests/integration/test_simulate_multi_sources.py` | Toute valeur Money dans `cost_breakdown` non-dégradée a `source_id IS NOT NULL`. |
