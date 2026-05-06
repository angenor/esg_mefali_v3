# F14 — Matching Projet ↔ Offre + Comparateur Multi-Intermédiaires

**Module(s) source(s)** : Module 3.2 (Matching Intelligent Projet ↔ Offre)
**Priorité** : P1 — différenciateur produit (matching réel projet vs naïf user/fund)
**Dépendances** : F01 (sources), F06 (Project), F07 (Offer), F13 (multi-référentiels)
**Estimation** : 2 sprints

## Contexte & motivation

Module 3.2 du brainstorming : « Le matching n'est jamais 'Projet ↔ Fonds' mais toujours 'Projet ↔ Offre'. L'intermédiaire est souvent le **vrai filtre**. »

**État actuel** :
- Matching `User ↔ Fund` (`backend/app/modules/financing/service.py:194-449`) :
  - Table `fund_matches` clé `(user_id, fund_id)` — pas `(project_id, offer_id)`
  - Score global unique `compatibility_score` calculé sur 5 critères pondérés (`sector/esg/size/location/documents`)
  - **Aucun calcul séparé fonds vs intermédiaire**
- Recommandation = liste intermédiaires triée par `is_primary` + ville (`service.py:563-606`) — pas une recommandation d'**Offre scorée**
- Comparateur même fonds via plusieurs intermédiaires : **inexistant** (différenciateur clé manquant)
- Pas d'alertes nouveaux appels à projets

## User stories

- **PME** : « Quand je crée un nouveau projet "Panneaux solaires 5M FCFA", je veux voir une liste d'**Offres** compatibles (pas de fonds nus), chaque offre avec son score décomposé fonds + intermédiaire. »
- **PME** : « Pour le fonds GCF, je veux comparer 3 voies d'accès (BOAD, UNDP, AFD) côte-à-côte sur frais, vitesse, taux de succès, avec score décomposé. »
- **PME** : « Je veux qu'un critère manquant soit cliquable vers la source officielle qui le définit (ex : "vous n'atteignez pas le seuil ESS BOAD" → modal avec extrait BOAD policy + URL). »
- **PME** : « Je veux recevoir des alertes quand un nouveau call_for_proposals s'ouvre pour un fonds compatible avec mes projets. »

## Périmètre fonctionnel

### Refactor du modèle `FundMatch`

Renommer/refactorer en `OfferMatch` (ou créer en parallèle puis deprecate) :
- `id: UUID PK`
- `account_id: UUID FK accounts.id NOT NULL` (F02)
- `project_id: UUID FK projects.id NOT NULL` (F06)
- `offer_id: UUID FK offers.id NOT NULL` (F07)
- `global_score: int` (0..100, min de fund_score et intermediary_score, ou pondération)
- `fund_score: int` (0..100)
- `intermediary_score: int` (0..100)
- `score_breakdown: jsonb` :
  ```json
  {
    "fund": {
      "sector_match": 80,
      "esg_match": 75,
      "size_match": 90,
      "location_match": 100,
      "documents_match": 60,
      "missing_criteria": [{"indicator_id": "...", "label": "...", "source_id": "..."}]
    },
    "intermediary": {...}
  }
  ```
- `bottleneck: enum('fund', 'intermediary', 'balanced')` (où est le goulot)
- `recommended_actions: jsonb` (liste d'actions pour combler les écarts)
- `computed_at: datetime`
- `expires_at: datetime` (re-calcul mensuel)

Index unique `(project_id, offer_id, computed_at)`.

### Service `compute_offer_match`

`backend/app/modules/financing/matching_service.py` :

```python
async def compute_offer_match(project_id: UUID, offer_id: UUID) -> OfferMatch:
    project = await get_project(project_id)
    offer = await get_offer(offer_id)
    
    # Score sur le fonds source
    fund_score, fund_missing = await score_against_referential(
        project, offer.fund.referential, offer.fund.eligibility_criteria
    )
    
    # Score sur l'intermédiaire (couche supplémentaire)
    intermediary_score, inter_missing = await score_against_referential(
        project, offer.intermediary.referential, offer.intermediary.eligibility_for_sme
    )
    
    global_score = min(fund_score, intermediary_score)  # min = éligibilité réelle
    bottleneck = "fund" if fund_score < intermediary_score - 10 else \
                 "intermediary" if intermediary_score < fund_score - 10 else "balanced"
    
    return OfferMatch(...)
```

Le scoring utilise la couche `Indicator/Referential` de F01 et F13.

### Endpoints API

- `GET /api/projects/{project_id}/matches` : matches actifs pour un projet (toutes offres compatibles, triées par `global_score`)
- `POST /api/projects/{project_id}/recompute-matches` : déclenche un recalcul
- `GET /api/projects/{project_id}/compare?fund_id=X` : **comparateur** — toutes les offres pour ce fonds (variantes via plusieurs intermédiaires) avec scoring décomposé, frais effectifs, délais effectifs, success_rate côte à côte
- `GET /api/projects/{project_id}/match-details/{offer_id}` : détail d'un match avec tous les critères couverts/manquants et sources

### Comparateur multi-intermédiaires (différenciateur clé)

Page `pages/financing/compare/[fund_id].vue` :
- Header : "Comparer les voies d'accès au GCF pour le projet [Project name]"
- Tableau (ou ComparisonTable F11) avec lignes :
  - Score global
  - Score fonds (commun)
  - Score intermédiaire (varie selon l'intermédiaire)
  - Frais cumulés
  - Délais cumulés
  - Documents requis (union)
  - Track record / success rate
- Highlight du gagnant par row
- Tool LangChain `compare_offers_for_fund(project_id, fund_id)` qui rend `<ComparisonTableBlock>` (F11)

### Alertes nouveaux appels à projets

Table `match_alerts_subscriptions` :
- `account_id`, `project_id`, `triggers: jsonb`, `notification_channels: list[str]`

Cron quotidien (cf. F19) :
- Pour chaque project actif, recalcul des matches
- Si nouveau match avec `global_score >= 60` ET pas déjà notifié : créer un Reminder F19 avec `type='new_offer_alert'`
- Notification SSE + email (post-MVP)

### Frontend

Page `pages/profile/projects/[id].vue` (créée par F06) : section "Offres compatibles" avec :
- Liste de `<MatchCard>` (F11) cliquables
- Score décomposé visible
- Bouton "Comparer 3 intermédiaires pour GCF" si plusieurs intermédiaires pour un même fonds

Page `pages/financing/offers/[offer_id].vue` :
- Section "Mon score pour ce projet" (sélecteur de projet si plusieurs)
- Affichage décomposé fonds + intermédiaire
- Critères manquants cliquables vers sources F01

## Hors-scope (post-MVP)

- ML scoring (apprentissage sur historique soumissions / acceptations)
- Recommandations narratives "Voici comment combler le score IFC : 1) ..., 2) ..."
- Score prédictif "probabilité d'acceptation"
- Email digest hebdo des nouvelles offres
- Filtres avancés (instruments, durée, devise) sur la liste de matches

## Exigences techniques

### Backend

- Migration Alembic `030_offer_matches.py` :
  - Table `offer_matches` (refactor de `fund_matches`)
  - Backfill : pour chaque fund_match existant, créer un offer_match avec un offer généré ou trouvé
  - Table `match_alerts_subscriptions`
- Modèle `app/models/offer_match.py`
- Service `app/modules/financing/matching_service.py` (refactor)
- Routes refactorées : `/api/projects/{id}/matches`, `/api/projects/{id}/compare`
- Tools LangChain :
  - `list_matches_for_project(project_id)`
  - `compare_offers_for_fund(project_id, fund_id)` → ComparisonTable (F11)
  - `recompute_score(project_id, referentiel_id)` (Module 1.1.3)
- Tests :
  - Test scoring décomposé : fund_score + intermediary_score, min = global
  - Test bottleneck : si fund_score = 80, inter_score = 50 → bottleneck=intermediary
  - Test comparateur : 3 offres pour même fonds → tableau cohérent
  - Test alertes : nouveau call_for_proposals → Reminder créé

### Frontend

- Page `pages/financing/compare/[fund_id].vue`
- Section "Offres compatibles" sur `pages/profile/projects/[id].vue`
- Composants `<MatchCard>` (F11) intégrés
- Composable `useMatching.ts`
- Dark mode

### Base de données

- Tables : `offer_matches`, `match_alerts_subscriptions`
- Index : `(project_id, computed_at DESC)`, `(account_id, expires_at)`

## Critères d'acceptation

- [ ] Modèle `OfferMatch` créé, lié à project + offer
- [ ] Score décomposé fund + intermediary calculé
- [ ] Bottleneck identifié
- [ ] Page `/financing/compare/[fund_id]?project_id=X` affiche comparateur
- [ ] Tool `compare_offers_for_fund` rend ComparisonTable
- [ ] Critères manquants cliquables vers sources F01
- [ ] Cron de recalcul matches quotidien (lien F19)
- [ ] Alertes nouvelles offres fonctionnelles
- [ ] Test E2E : créer projet → matches calculés → comparer 3 intermédiaires → tableau OK
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : recalcul N matches × M projets coûteux. **Garde-fou** : recalcul incrémental (seulement si projet ou offre modifié), cache 30 jours.
- **Risque** : score fonds vs intermédiaire diverge trop → confusion utilisateur. **Garde-fou** : tooltip explicatif systématique, documentation pédagogique.
- **Risque** : utilisateurs PME inondés d'offres faussement compatibles. **Garde-fou** : threshold `global_score >= 60` pour notification, possibilité de désabonnement par catégorie.
