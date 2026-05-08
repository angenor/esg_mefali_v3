# Matching Projet ↔ Offre (F14)

## Vue d'ensemble

F14 calcule la **compatibilité d'un projet vert d'une PME avec une offre
de financement** = `Fonds × Intermédiaire` (entité F07). Le score est
**décomposé en deux** :

- `fund_score` — alignement avec les critères du fonds bailleur
- `intermediary_score` — alignement avec les critères de l'intermédiaire
- `global_score` — moyenne pondérée des deux

Cela permet à la PME de comprendre **quel maillon limite son éligibilité**
(« bottleneck »), puis de comparer les intermédiaires d'un même fonds
côte-à-côte.

## Modèle conceptuel

```
Projet (F06) ──┐
               ├──> OfferMatch (F14) ──> Offre = Fonds × Intermédiaire (F07)
ESGAssessment ─┘                                         │
(F05)                                                    │
                                          Référentiel F13 ←── score décomposé
```

Une `OfferMatch` est l'évaluation persistée d'un couple `(projet, offre)`
à un instant donné. Elle est UPSERT in-place (UNIQUE
`(project_id, offer_id)`) et invalidée par event listeners SQLAlchemy
quand le projet ou l'offre est modifié.

## Pondération MVP

```python
MATCHING_WEIGHTS = {
    "sector":     0.25,  # binaire 100/0 (sectoral fit)
    "esg":        0.30,  # délégué à F13 compute_referential_score_for_offer
    "size":       0.15,  # graduel ±50% via Money typed F04
    "location":   0.10,  # binaire (pays UEMOA target)
    "documents":  0.10,  # ratio documents fournis / requis
    "instrument": 0.10,  # binaire (subvention/prêt/equity)
}
```

Pondérations stockées en constante module pour MVP. Post-MVP : table
`matching_weights` (configurable par admin).

## Règle bottleneck

Une fois `fund_score` et `intermediary_score` calculés :

- `fund_score - intermediary_score < -10` ⇒ `bottleneck = "fund"`
- `fund_score - intermediary_score > 10` ⇒ `bottleneck = "intermediary"`
- sinon ⇒ `bottleneck = "balanced"`

Le badge `<BottleneckBadge>` (rouge / amber / vert) communique cette
information à la PME avec un tooltip ARIA détaillé.

## Cycle de vie d'un match

1. **Création** : POST `/api/projects/{id}/recompute-matches` ou
   event listener `after_update` sur Project/Offer.
2. **Affichage** : GET `/api/projects/{id}/matches` (liste paginée,
   filtres `min_score`, `bottleneck`, `fund_id`).
3. **Drill-down** : GET `/api/projects/{id}/match-details/{offer_id}`.
4. **Comparaison** : GET `/api/projects/{id}/compare?fund_id=X` →
   `<ComparisonTableBlock>` F11 avec highlight gagnant.
5. **Invalidation** : `expires_at` < now() OU event listener déclenché.
   Recompute via cron F19 `recompute_stale_matches.py` (batch 100).
6. **Alertes** : `MatchAlertSubscription` par projet ; cron
   `notify_new_offer_matches.py` crée des Reminders F19 quand un nouveau
   match dépasse `min_global_score`. Idempotence via `last_notified_at`.

## Endpoints REST

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/projects/{id}/matches` | Liste paginée filtrée |
| POST | `/api/projects/{id}/recompute-matches` | Trigger BackgroundTasks (202) |
| GET | `/api/projects/{id}/compare?fund_id=X` | Comparaison F11 typed |
| GET | `/api/projects/{id}/match-details/{offer_id}` | Détail enrichi |
| GET/PATCH | `/api/projects/{id}/match-alerts` | Subscription |

Tous protégés par `Depends(get_current_user)` avec RLS PG via
`set_rls_context` (multi-tenant F02).

## Frontend

### Composants

- `<BottleneckBadge>` — pastille colorée + tooltip ARIA
- `<MatchScoreBreakdown>` — radar 6 axes SVG natif (sector, esg, size,
  location, documents, instrument)
- `<MissingCriteriaList>` — liste critères avec `<SourceLink>` F01
- `<MatchAlertToggle>` — switch ARIA `role=switch` + slider seuil
- `<OffersCompatibleSection>` — section pour `/profile/projects/[id]`

### Pages

- `/profile/projects/[id]/matches` — liste paginée + filtres
  URL-synchronisés
- `/profile/projects/[id]/alerts` — gestion abonnement alertes
- `/financing/compare/[fund_id]?project_id=X` — comparateur multi-
  intermédiaires (réutilise `<ComparisonTableBlock>` F11)

### Store & composable

- `useMatching()` — 6 méthodes async (listMatches, recomputeMatches,
  compareOffersForFund, getMatchDetails, getSubscription,
  updateSubscription)
- `useMatchesStore` — state `matchesByProject`, `comparisonsByFund`,
  `subscriptionsByProject` + getters `getActiveMatches`, `getTopMatch`,
  `bottleneckCount`

## Troubleshooting

### Aucun match affiché après création projet

1. Vérifier `ESGAssessment` finalisé (sinon `assessment_missing=true`
   dans `score_breakdown`)
2. Lancer un recompute manuel via le bouton « Recalculer » de la
   section
3. Vérifier RLS : `SELECT current_setting('app.current_account_id')`
4. Vérifier que des offres `is_active=true` et `publication_status=published`
   existent

### Alertes non envoyées

1. Vérifier `match_alerts_subscriptions.is_active = true`
2. Vérifier `global_score >= min_global_score`
3. Vérifier `last_notified_at IS NULL` (si non NULL = déjà notifié)
4. Vérifier le cron `notify_new_offer_matches.py` (logs F03 audit
   `source_of_change=import`)

### Ajouter un nouveau sub-score

1. Ajouter la clé à `MATCHING_WEIGHTS` (somme = 1.0)
2. Ajouter `_compute_<key>_match(project, fund) -> int` dans
   `matching_service.py`
3. Étendre `MatchSubBreakdown` Pydantic + TypeScript
4. Ajouter axe au radar `<MatchScoreBreakdown>`
5. Tests unitaires de la nouvelle règle

## Performance

- P95 `compute_offer_match` < 500 ms (5 sub-scores + délégation F13 +
  UPSERT)
- P95 page comparateur < 2s pour 5 offres
- Cron batch 100 matches/run < 30s

## Sécurité

- RLS PostgreSQL ENABLE+FORCE sur les 2 tables
- Cap dur 50 offres / `recompute-matches` (anti-DoS)
- Pas d'appel LLM dans le calcul (déterministe)
- Pas d'appel HTTP externe
- Audit log F03 sur INSERT/UPDATE de `OfferMatch` et
  `MatchAlertSubscription`
