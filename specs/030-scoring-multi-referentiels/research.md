# Phase 0 — Research : F13 Scoring ESG Multi-Référentiels

**Date** : 2026-05-07
**Spec** : [spec.md](./spec.md)
**Plan** : [plan.md](./plan.md)

## Décision 1 — Pattern d'historisation des scores : `superseded_by` self-référent vs table d'historique séparée

### Décision retenue

**Pattern F04 `superseded_by` (UUID nullable FK self-référente)** sur la table `referential_scores`, avec un index unique partiel `(assessment_id, referential_id) WHERE superseded_by IS NULL` qui garantit qu'un seul score « courant » existe par couple `(assessment_id, referential_id)`.

### Rationale

1. **Cohérence avec F04** : le pattern `superseded_by` est déjà utilisé sur `funds`, `intermediaries`, `fund_intermediaries` (post-F07), `offers`. Réutiliser le même pattern évite d'introduire un nouveau modèle parallèle.
2. **Simplicité de schéma** : pas de table satellite `referential_score_versions` à maintenir avec sa propre RLS, ses index, ses cascades.
3. **Index unique partiel PostgreSQL** (`CREATE UNIQUE INDEX ... ON referential_scores (assessment_id, referential_id) WHERE superseded_by IS NULL`) garantit l'invariant « un seul score courant par couple » au niveau DB sans relâcher la contrainte unique de manière permissive.
4. **Requêtes API simples** :
   - Score courant : `WHERE superseded_by IS NULL`
   - Historique : `WHERE superseded_by IS NOT NULL ORDER BY computed_at DESC`
5. **Cascade ON DELETE SET NULL** sur la FK self-référente évite les boucles de suppression.

### Alternatives considérées

- **Table `referential_score_versions` séparée** : table principale = score courant, satellite = historique. **Rejetée** car double maintenance (RLS, indexes, cascade), divergence avec le pattern F04 établi, et pas d'avantage perf (l'index partiel PostgreSQL est aussi performant).
- **Champ `is_current bool` + relâchement de l'unique** : ambiguïté potentielle (deux lignes `is_current=true` simultanément). **Rejetée** : moins robuste qu'un index unique partiel.
- **Soft delete `deleted_at`** : pas adapté car les versions historiques ne sont pas supprimées, elles sont remplacées.

## Décision 2 — Stratégie de calcul `compute_score_for_referential`

### Décision retenue

**Pondération qui ignore les indicateurs non renseignés** (pas zéro par défaut) avec calcul `coverage_rate` séparé.

Formule :
```
score = sum(indicator_value * indicator_weight for indicator in renseignés_du_référentiel) / sum(indicator_weight for indicator in renseignés_du_référentiel) * 100
coverage_rate = count(indicators_renseignés_pour_ce_référentiel) / count(indicators_total_du_référentiel)
```

Si `coverage_rate == 0` : `overall_score = NULL`, `notes = "Aucun indicateur lié à ce référentiel"`.

### Rationale

1. **Pédagogique** : un PME qui a renseigné 3 indicateurs sur 25 d'IFC PS voit un score sur ces 3 (« vous êtes à 70 sur ce que vous avez renseigné, vous couvrez 12 % du référentiel »). C'est plus actionnable que `score=8` (3/25*70).
2. **Pas de pénalité injuste** : si un indicateur n'a pas encore été demandé à la PME, ne pas le compter comme zéro.
3. **`coverage_rate` séparé** : la transparence sur la couverture permet à l'UI d'afficher le badge orange si < 50 %.
4. **Cohérent avec la philosophie du brainstorming Module 0.7** (« 1 saisie = N scores ») : pas de saisie forcée d'indicateurs « non applicables ».

### Alternatives considérées

- **Pondération avec zéro pour non-renseignés** : pénalise la PME injustement, donne un score artificiellement bas. **Rejetée**.
- **Refuser le calcul si `coverage_rate < 0.5`** : casse le parcours pédagogique et le pattern « explorer 5 référentiels en un clic ». **Rejetée**.
- **Score normalisé sur 0-100 scaling** : ajoute de la complexité sans bénéfice clair. **Rejetée**.

## Décision 3 — Recalcul async via `BackgroundTasks` FastAPI in-memory vs Redis+Celery

### Décision retenue

**`BackgroundTasks` FastAPI in-memory en MVP** ; migration vers Redis+Celery planifiée post-MVP (F19).

Architecture :
```python
from fastapi import BackgroundTasks
from uuid import uuid4

@router.patch("/api/esg/assessments/{id}/indicator-values")
async def update_indicator_value(id: UUID, payload: ..., background_tasks: BackgroundTasks):
    await persist_indicator_value(...)  # synchronous
    request_id = uuid4()
    background_tasks.add_task(recompute_referential_scores_async, id, request_id)
    return {"status": "accepted", "recompute_request_id": request_id}
```

### Rationale

1. **YAGNI** (Constitution VII) : le projet est en MVP, pas en production scale. Redis+Celery introduit 2 services supplémentaires (broker + worker) pour un gain marginal sur des workloads de < 10 jobs/min.
2. **Simplicité de déploiement** : pas de service externe à orchestrer.
3. **Tests E2E plus simples** : pas besoin de wait sur un broker externe ni de mocker Celery.
4. **Limitation acceptée et documentée** : un redéploiement perd les jobs en cours ; l'UI affiche un toast « Recalcul perdu, réessayer ». En MVP avec ~10-50 PMEs actives, c'est tolérable.
5. **Migration future facile** : l'interface du tool `recompute_score` est stable (`{recompute_request_id}`), seule l'implémentation de `recompute_referential_scores_async` change ; l'UI polling reste identique.

### Alternatives considérées

- **Synchrone (bloquer la réponse HTTP)** : 5-15 s par modification d'indicateur, UX dégradée. **Rejetée**.
- **Redis+Celery dès le MVP** : sur-ingénierie, viole YAGNI. **Rejetée**.
- **WebSocket pour push notifications complétion** : ajoute de la complexité (auth WS, état session) ; le polling 2s suffit en MVP. **Rejetée pour MVP**, à réévaluer post-MVP si UX dégrade.

## Décision 4 — Seed des 5 référentiels MVP : dans la migration F13 vs dépendance F01 vs F09 admin runtime

### Décision retenue

**Seed direct dans la migration `030_create_referential_scores`** pour Mefali (idempotent) ; les 4 autres référentiels (GCF, IFC PS, BOAD ESS, GRI 2021) sont seedés conditionnellement avec `INSERT ... ON CONFLICT (code) DO NOTHING` pour ne pas dupliquer si F01 les a déjà créés.

Stratégie :
1. La migration F13 INSERT-on-conflict-do-nothing pour les 5 référentiels MVP avec leurs versions (`v1.0.0` initial), seuils, `min_coverage_for_pdf=0.5`.
2. Si F01 a déjà seedé certains référentiels, ils restent inchangés (la migration F13 ne les écrase pas).
3. Les indicateurs liés (`referential_indicators`) sont seedés par F01 (pas par F13).
4. Si un référentiel attendu n'a aucun indicateur lié, le service `compute_score_for_referential` retourne `coverage_rate=0`, `overall_score=NULL`, et l'UI cache la card.

### Rationale

1. **Robustesse** : F13 ne dépend pas de l'ordre d'exécution des migrations F01/F13 (idempotence garantie).
2. **Découplage** : F13 peut être livré même si F01 n'a livré qu'un sous-ensemble des référentiels.
3. **Simplicité** : pas besoin d'un script seed séparé exécuté manuellement après la migration.
4. **Mefali doit être seedé** : c'est le référentiel par défaut pour le backfill de toutes les `EsgAssessment` existantes ; sa présence en BDD est un invariant F13.

### Alternatives considérées

- **Dépendance bloquante sur F01** : si F01 livre seulement Mefali + GCF, F13 ne pourrait pas seeder IFC PS / BOAD ESS / GRI. **Rejetée** : fragile.
- **Seed manuel via F09 admin runtime** : nécessite F09 livré avant F13, ce qui n'est pas le cas. **Rejetée**.
- **Seed via script Python distinct (`python scripts/seed_referentials.py`)** : ajoute une étape de déploiement. **Rejetée pour MVP**.

## Décision 5 — Fallback `fund.referential_id IS NULL` → ESG Mefali : helper service vs default DB column

### Décision retenue

**Helper service** `compute_referential_score_for_offer` qui retourne un `ReferentialScore` avec un flag `is_fallback=true` dans la réponse Pydantic (pas dans la table BDD). La colonne `referential_scores.referential_id` reste FK NOT NULL vers `referentials.id` (pointant vers Mefali en cas de fallback).

```python
async def compute_referential_score_for_offer(
    assessment_id: UUID, offer_id: UUID
) -> tuple[ReferentialScoreWithFallback, ReferentialScoreWithFallback | None]:
    offer = await get_offer(offer_id)
    fund_referential_id = offer.fund.referential_id or MEFALI_REFERENTIAL_UUID
    fund_score = await compute_score_for_referential(fund_referential_id, ...)
    fund_score_response = ReferentialScoreWithFallback(
        **fund_score.dict(),
        is_fallback=offer.fund.referential_id is None,
    )
    # idem intermediaire
    ...
```

### Rationale

1. **Pas de duplication de données** : un score Mefali calculé reste un score Mefali en base, pas une « version fallback » ; le flag est une vue d'API.
2. **Cohérence** : l'UI peut différencier visuellement (badge « Référentiel Mefali — fallback ») sans conditionner les requêtes DB.
3. **Auditabilité** : un événement `audit_log` `action='dual_view_fallback_used'` est créé chaque fois qu'un fallback est utilisé (traçabilité pour les admins qui sauront quand enrichir le catalogue F01).
4. **Pas de migration BDD** : pas besoin de colonne `is_fallback` ni de double FK sur `referential_scores`.

### Alternatives considérées

- **Colonne `is_fallback bool` sur `referential_scores`** : pollue la table avec un état dérivé. **Rejetée** : DRY, le flag se calcule à partir de l'état de l'offre.
- **Bloquer l'affichage si `referential_id IS NULL`** : casse le parcours PME (cf. spec.md Q5). **Rejetée**.
- **Créer un référentiel virtuel `fallback_mefali`** : confusion conceptuelle (Mefali est le référentiel de base, pas un fallback). **Rejetée**.

## Décision 6 — Structure du JSONB `pillar_scores` / `covered_criteria` / `missing_criteria`

### Décision retenue

**JSONB stricts validés par Pydantic v2** :

```python
# pillar_scores
{
    "environment": {"score": 78.5, "weight": 0.33, "criteria_count": 12, "criteria_renseignés": 10},
    "social": {"score": 65.0, "weight": 0.33, "criteria_count": 10, "criteria_renseignés": 8},
    "governance": {"score": 80.0, "weight": 0.34, "criteria_count": 8, "criteria_renseignés": 7},
}

# covered_criteria
[
    {
        "indicator_id": "uuid",
        "indicator_code": "pct_dechets_recycles",
        "score": 75.0,
        "weight": 0.05,
        "source_id": "uuid",
    },
    ...
]

# missing_criteria
[
    {
        "indicator_id": "uuid",
        "indicator_code": "biodiversite_policy",
        "reason": "non_renseigne",  # enum: non_renseigne | invalide | hors_scope
        "source_id": "uuid",
        "suggestion": "Renseignez votre politique biodiversité dans la section ESG.",
    },
    ...
]
```

### Rationale

1. **Pydantic v2 strict** sur le serveur garantit la conformité du JSONB en lecture/écriture.
2. **Pas de table séparée** : `covered_criteria` est un artefact de calcul, pas une entité métier persistante (Cohérence YAGNI).
3. **Indexable via PostgreSQL `@>` containment operator** si besoin futur (ex : « PMEs qui couvrent ce critère X »).
4. **Source traçabilité (F01)** : chaque entrée a `source_id` cliquable côté UI.

### Alternatives considérées

- **Tables séparées `referential_score_pillars`, `referential_score_covered_criteria`, `referential_score_missing_criteria`** : 3 tables supplémentaires pour des données peu requêtées (consultées avec le score parent). **Rejetée** : YAGNI.
- **JSON non typé** : laisser libre cours ; Pydantic v1 lax. **Rejetée** : risque d'incohérence sans validation.

## Décision 7 — Stratégie de tests JSONB en environnement CI (PostgreSQL prod, SQLite test)

### Décision retenue

**Tests d'intégration sur PostgreSQL** (Docker Compose `postgres` service en CI), **tests unitaires sur SQLite in-memory** avec mocking du containment `@>`.

Architecture :
- `tests/unit/test_*.py` : utilisent SQLite in-memory (`sqlite+aiosqlite://`), pas de RLS, JSONB simulé via `Text` colonnes Pydantic-converted.
- `tests/integration/test_*.py` : utilisent PostgreSQL via fixture `pytest-asyncio` + `docker-compose`, RLS activée, JSONB natif.
- `tests/migrations/test_alembic_030.py` : nécessite PostgreSQL (RLS, index partiel, JSONB).
- `tests/security/test_referential_scores_rls.py` : nécessite PostgreSQL (RLS).

### Rationale

1. **Vitesse des tests unitaires** : SQLite in-memory tourne en ~50ms par test, ~5x plus rapide que PostgreSQL.
2. **Fidélité des tests d'intégration** : PostgreSQL pour les invariants critiques (RLS, index partiel, JSONB).
3. **Cohérence avec F02/F07** : le pattern est déjà établi.

### Alternatives considérées

- **Tout en PostgreSQL** : tests trop lents en CI (~10 min pour 1000 tests). **Rejetée**.
- **Tout en SQLite** : RLS et JSONB containment non testables ; manque de fidélité. **Rejetée**.

## Décision 8 — Endpoint API REST `/recompute-score` vs commande LangChain dédiée

### Décision retenue

**Les deux** : l'endpoint `POST /api/esg/assessments/{id}/recompute-score?referentiel_id=X` sert l'UI directe (bouton « Recalculer maintenant » dans `<MissingCriteriaList>` ou `BottleneckBanner`) ; le tool LangChain `recompute_score(entity_id, referentiel_id)` sert le chat (« Recalcule mon score IFC »). Les deux délèguent au même service backend `recompute_score_async(entity_id, referentiel_id)`.

### Rationale

1. **Séparation des préoccupations** : l'UI directe ne passe pas par le LLM (pas de surcoût, pas de latence chat).
2. **Réutilisation du service** : pas de duplication de logique métier.
3. **Tool LangChain disponible pour le chat** : conversion conversationnelle naturelle.
4. **Audit cohérent** : les deux entry points journalisent dans `audit_log` avec la même action.

### Alternatives considérées

- **Endpoint API uniquement** : le chat ne peut pas déclencher un recalcul de manière conversationnelle. **Rejetée** : conversation-driven UX (Constitution III).
- **Tool LangChain uniquement** : l'UI doit passer par le LLM pour un simple recalcul. **Rejetée** : surcoût et latence inutiles.

## Décision 9 — Conservation des colonnes legacy `esg_assessments.overall_score|...` 2 sprints

### Décision retenue

**Conservation 2 sprints** ; le service `compute_all_referential_scores` met à jour **les deux endroits** (referential_scores + colonnes legacy) pendant la transition pour garantir cohérence avec F11 dashboard (qui lit les colonnes legacy) et F06 reports (qui lit les colonnes legacy en mono-référentiel mode).

Stratégie :
1. F13 ajoute le code de double-écriture (toujours UPSERT dans `referential_scores` + UPDATE colonnes legacy avec score Mefali).
2. F11 et F06 continuent à lire les colonnes legacy (compatibilité).
3. À la fin des 2 sprints (post-F13), une migration ultérieure (cf. F14 ou F15) supprime les colonnes legacy + adapte F11/F06 pour lire `referential_scores`.

### Rationale

1. **Pas de breaking change** F11/F06 lors du déploiement F13.
2. **Test d'égalité** : un test d'intégration `test_legacy_columns_equality.py` vérifie que `referential_scores[Mefali].overall_score == esg_assessments.overall_score` après chaque calcul.
3. **Migration future progressive** : F11/F06 peuvent migrer progressivement vers `referential_scores` sans pression temporelle.

### Alternatives considérées

- **Suppression immédiate dans F13** : casse F11/F06 le jour du déploiement. **Rejetée**.
- **Conservation indéfinie** : double maintenance permanente ; antagoniste à YAGNI. **Rejetée**.
- **View PostgreSQL** : créer une view `esg_assessments_with_overall_score` qui projette depuis `referential_scores`. **Rejetée pour MVP** : ajoute complexité de migration (view dépendant de jointures).

## Décision 10 — Gestion des recalculs partiels en cas d'échec d'un référentiel sur les N

### Décision retenue

**Atomicité par référentiel** : chaque calcul d'un référentiel est dans sa propre transaction PostgreSQL (savepoint) ; si l'un échoue, les autres sont persistés. L'UI affiche `len(referential_scores) < len(active_referentials)` et propose un bouton « Recompléter le calcul ».

```python
async def compute_all_referential_scores(assessment_id):
    referentials = await get_active_referentials()
    results = await asyncio.gather(
        *[compute_and_persist_one(ref, assessment_id) for ref in referentials],
        return_exceptions=True,
    )
    successful = [r for r in results if not isinstance(r, Exception)]
    failed = [(ref, r) for ref, r in zip(referentials, results) if isinstance(r, Exception)]
    if failed:
        await audit_log_partial_failure(assessment_id, failed)
    return successful
```

### Rationale

1. **Robustesse** : un crash sur IFC PS ne fait pas perdre les calculs Mefali, GCF, etc.
2. **Diagnostique** : `audit_log` détaille les références échouées avec stack trace.
3. **Recovery** : l'UI propose explicitement la recomplétion.

### Alternatives considérées

- **Atomicité globale (tout ou rien)** : un échec fait perdre N-1 calculs réussis. **Rejetée** : UX dégradée.
- **Retry automatique infini** : risque de boucle infinie si bug systémique. **Rejetée** : retry manuel via UI plus contrôlable.
