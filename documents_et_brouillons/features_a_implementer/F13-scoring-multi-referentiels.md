# F13 — Scoring ESG Multi-Référentiels (GCF, IFC, BOAD, SUNREF, GRI, ODD)

**Module(s) source(s)** : Module 2.3 (Scoring ESG Dynamique multi-référentiels), Module 2.4 (Rapport multi-référentiels)
**Priorité** : P1 — important pour Innovation 7 ("Scoring ESG multi-référentiels")
**Dépendances** : F01 (Source + Indicator + Référentiel), F04 (versioning + snapshot), F07 (Offer activation contextuelle)
**Estimation** : 3 sprints

## Contexte & motivation

Module 2.3 du brainstorming : "approche hybride : un score synthétique 'ESG Mefali' en vitrine pour la lisibilité, complété par des scores détaillés par référentiel (fonds source ET intermédiaires), calculés à partir du même catalogue d'indicateurs."

**État actuel** :
- Scoring **mono-référentiel** : un seul score ESG Mefali calculé via `compute_overall_score` (`backend/app/modules/esg/service.py:57-76`)
- Les 4 référentiels affichés dans le PDF (`templates/esg_report.html:124-165`) : Taxonomie UEMOA / Circulaire BCEAO / Directive CEDEAO / Gold Standard-Verra → **rebadge cosmétique** : c'est le score Mefali avec des seuils statiques (60, 50, 70) appliqués
- Aucune entité `Referentiel` en BDD (créée par F01)
- Aucun scoring décomposé fonds source / intermédiaire (Module 2.3.3)
- Aucun sélecteur multi-référentiels dans l'UI ESG
- Le tool `finalize_esg_assessment` (`esg_tools.py:199-259`) ne prend pas de `referentiel_id`

**Conséquences** :
- Impossible pour la PME de découvrir qu'elle est éligible GCF mais bloquée IFC (info actionnable)
- Pas d'avantage compétitif "scoring multi-référentiels avec activation contextuelle"
- Quand un projet cible une Offre, pas de calcul score fonds + score intermédiaire avec min(deux) (Module 2.3.3)
- Rapport ESG ne reflète pas la réalité multi-référentiels

## User stories

- **PME** : « Sur ma page `/esg`, je veux un sélecteur "Voir mon score selon ESG Mefali / GCF / IFC / BOAD / SUNREF / GRI / ODD" avec mise à jour instantanée du score, des critères couverts/manquants et de l'écart au seuil d'éligibilité. »
- **PME** : « Quand je consulte une Offre (GCF via BOAD), je veux voir **deux scores côte-à-côte** : score selon référentiel GCF (fonds source) + score selon référentiel BOAD (intermédiaire). Le min des deux = mon éligibilité réelle, avec identification du goulot d'étranglement. »
- **PME** : « Je veux pouvoir générer un rapport PDF en sélectionnant les référentiels à inclure (par défaut Mefali + tous ceux des offres ciblées). »
- **PME** : « Je découvre que je passe à 78/100 en ESG Mefali mais à 52/100 en IFC PS — clic sur les critères manquants IFC me montre lesquels et la source officielle de chaque exigence. »

## Périmètre fonctionnel

### Modèle de scoring multi-référentiels

Couche `Indicator/Referential` créée par F01.

Table `referential_scores` (résultats par évaluation × référentiel) :
- `id: UUID PK`
- `assessment_id: UUID FK esg_assessments.id`
- `referential_id: UUID FK referentials.id`
- `referential_version: str` (snapshot au moment du calcul)
- `overall_score: Numeric(5, 2)` (0..100)
- `pillar_scores: jsonb` (scores E/S/G ou autres piliers selon référentiel)
- `covered_criteria: jsonb` (liste {indicator_id, score, weight, source_id})
- `missing_criteria: jsonb` (liste {indicator_id, reason, source_id})
- `gap_to_threshold: Numeric(5, 2)` (positif si au-dessus, négatif si en-dessous)
- `eligibility: bool` (true si overall_score >= referential.threshold)
- `computed_at: datetime`
- `computed_by: enum('manual', 'llm', 'auto')` (qui a déclenché le calcul)

Index `(assessment_id, referential_id)` unique.

### Service de calcul multi-référentiels

`backend/app/modules/esg/multi_referential_service.py` :

```python
async def compute_all_referential_scores(assessment_id: UUID) -> list[ReferentialScore]:
    """Calcule un score pour chaque référentiel actif sur la base des indicateurs renseignés."""
    assessment = await get_assessment(assessment_id)
    indicators_values = assessment.indicator_values  # {indicator_id: value} déjà saisis
    
    referentials = await get_active_referentials()  # ESG Mefali, GCF, IFC, BOAD, SUNREF, GRI, ODD
    scores = []
    for ref in referentials:
        score = compute_score_for_referential(ref, indicators_values)
        scores.append(score)
    return scores

async def compute_referential_score_for_offer(
    assessment_id: UUID, offer_id: UUID
) -> tuple[ReferentialScore, ReferentialScore]:
    """Pour une Offre (Fonds × Intermédiaire), retourne (score_fonds, score_intermediaire)."""
    offer = await get_offer(offer_id)
    fund_referential = offer.fund.referential
    intermediary_referential = offer.intermediary.referential
    fund_score = compute_score_for_referential(fund_referential, ...)
    inter_score = compute_score_for_referential(intermediary_referential, ...)
    return fund_score, inter_score
```

Une seule réponse PME (saisie d'un indicateur) alimente N scores → pas de duplication de saisie (Module 0.7).

### Activation contextuelle (Module 2.3.3)

Quand un projet (F06) cible une Offre (F07), la page de détail offre `pages/financing/offers/[id].vue` affiche :
- Score selon référentiel **fonds source**
- Score selon référentiel **intermédiaire**
- Min des deux = éligibilité effective
- Le **goulot d'étranglement** est identifié visuellement (référentiel le plus faible)
- Liste des critères manquants par référentiel (cliquables vers source via F01)

### Refactor `esg_scoring_node`

`backend/app/graph/nodes.py:esg_scoring_node` doit :
- Calculer ESG Mefali (référentiel par défaut)
- Calculer **également** les autres référentiels actifs en parallèle
- Quand un Project cible une Offre, calculer les 2 scores côté Offre

### Sélecteur multi-référentiels UI

Page `pages/esg/results.vue` :
- Composant `<ReferentialSelector :options="referentials" v-model="selectedReferential">`
- Bascule entre référentiels avec mise à jour des charts/tables
- Card par référentiel avec score global + pilier breakdown
- Mode "vue côte-à-côte" pour comparer N référentiels

Page `pages/financing/offers/[id].vue` :
- Section "Mon éligibilité pour cette offre" avec deux scores côte-à-côte
- Highlight du goulot d'étranglement
- Liste critères manquants par couche

### Rapport PDF enrichi (Module 2.4)

Endpoint refactor : `POST /api/reports/esg/{assessment_id}/generate` body :
```json
{
  "referentials": ["esg_mefali", "gcf", "ifc"],
  "include_appendix_sources": true
}
```

Template `esg_report.html` :
- Section principale : scores par référentiel sélectionné
- Radar par référentiel
- Tableau : critère × référentiel (qui couvre quoi)
- Annexe technique : méthodologie de chaque référentiel + table indicateurs
- **Annexe "Sources et références"** auto-générée (F01)

### Versioning du score (Module 0.5)

Chaque `referential_scores` capture `referential_version` au moment du calcul → permet de défendre un score historique même si le référentiel évolue (cf. F04 snapshot candidature).

## Hors-scope (post-MVP)

- Référentiels custom par PME (auto-définis)
- Calcul de scores composites pondérés (somme pondérée de plusieurs référentiels)
- Recommandations IA priorisées par référentiel ciblé
- Alertes si un référentiel ajouté change un score significativement (delta > 10 points)
- Cohort comparison (votre score IFC vs autres PME du même secteur en pgvector)

## Exigences techniques

### Backend

- Migration Alembic `029_multi_referential_scoring.py` :
  - Table `referential_scores`
  - Indexes
- Modèle `app/models/referential_score.py`
- Service `app/modules/esg/multi_referential_service.py`
- Refactor `esg/service.py` : exposer `compute_all_referential_scores`
- Refactor `esg_scoring_node` (`backend/app/graph/nodes.py`)
- Tools LangChain (mise à jour) :
  - `finalize_esg_assessment` : prend `referentials_to_compute: list[str]` (default = tous actifs)
  - `recompute_score(entity_id, referentiel_id)` (Module 1.1.3)
  - `compare_referentials(assessment_id, referentials: list[str])`
- Endpoint `POST /api/reports/esg/{id}/generate` : accepter `referentials` body
- Refactor `app/modules/reports/templates/esg_report.html`
- Tests :
  - Test calcul multi-réf : 1 saisie d'indicateur alimente N scores
  - Test activation contextuelle : projet cible offre → 2 scores fonds+intermédiaire calculés
  - Test versioning : modifier le référentiel après calcul ne change pas l'historique
  - Test API report : sélection partielle référentiels reflétée dans PDF

### Frontend

- Composant `<ReferentialSelector>` dans `components/esg/`
- Composant `<ReferentialScoreCard>` (par réf)
- Composant `<DualReferentialView>` (fonds + intermediaire côte-à-côte)
- Composant `<MissingCriteriaList>` avec sources cliquables (F01)
- Page `pages/esg/results.vue` refactor
- Page `pages/financing/offers/[id].vue` ajout section éligibilité
- Composable `useEsgMultiReferential.ts`
- Mise à jour store `esg.ts`
- Dark mode

### Base de données

- Tables : `referential_scores`
- Indexes spécifiés
- Audit log via F03
- (lien F01) : `indicators`, `referentials`, `referential_indicators` sont des prérequis

## Critères d'acceptation

- [ ] Table `referential_scores` créée
- [ ] Service `compute_all_referential_scores` calcule au moins 5 référentiels (Mefali + GCF + IFC + BOAD + GRI)
- [ ] Une saisie d'indicateur alimente N scores sans duplication
- [ ] Page `/esg/results` permet de basculer entre référentiels via sélecteur
- [ ] Page `/financing/offers/[id]` affiche 2 scores côte-à-côte avec goulot d'étranglement
- [ ] Endpoint `POST /api/reports/esg/{id}/generate` accepte `referentials` et le PDF reflète la sélection
- [ ] Annexe "Sources et références" auto-générée dans le PDF
- [ ] Sources cliquables (F01) sur chaque indicateur, seuil, pondération
- [ ] Test E2E : saisir un indicateur "% déchets recyclés = 60" → vérifier que le score change pour ESG Mefali ET GCF ET BOAD
- [ ] Test E2E : projet cible Offre GCF/BOAD → score GCF affiché, score BOAD affiché, min identifié
- [ ] Test E2E : générer rapport avec [Mefali, IFC] → PDF contient les 2 référentiels avec radar et critères
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : sans F01 (catalogue Indicators), ce feature ne peut pas exister. **Garde-fou** : F01 est un prérequis bloquant. Définir les indicateurs en dur ou via seed admin.
- **Risque** : pondérations entre référentiels divergent significativement → un PME se retrouve à 80/100 ESG Mefali et 30/100 IFC. **Garde-fou** : c'est précisément le but (info actionnable) ; UI explique clairement les écarts ; documentation pédagogique.
- **Risque** : performance des recalculs pour N référentiels à chaque saisie. **Garde-fou** : recalcul async (background task), invalider le cache, n'afficher que les scores mis à jour.
- **Risque** : un référentiel manque d'indicateurs → score artificiellement bas. **Garde-fou** : exposer `coverage_rate` (% indicateurs renseignés) ; alerte si < 50 % ; pondération qui ignore les indicateurs non renseignés (pas zéro par défaut).
- **Risque** : seed des 5+ référentiels prend du temps (capture sources GCF, IFC PS, BOAD, GRI). **Garde-fou** : prioriser GCF + IFC + ODD pour MVP, ajouter les autres par F09 admin.
- **Risque** : la migration de l'ancien `compute_overall_score` (mono-référentiel) casse la rétrocompatibilité. **Garde-fou** : conserver l'API existante en parallèle, ajouter `?referential=mefali` (default), deprecate progressivement.
