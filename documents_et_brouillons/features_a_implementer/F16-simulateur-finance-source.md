# F16 — Simulateur Financement Sourcé + Comparateur Multi-Offres

**Module(s) source(s)** : Module 3.4 (Simulateur de Financement)
**Priorité** : P1 — crédibilité du chiffrage et différenciateur (comparateur)
**Dépendances** : F01 (sources facteurs), F04 (Money typed), F06 (Project), F07 (Offer)
**Estimation** : 1.5 sprints

## Contexte & motivation

**État actuel — constantes magiques non sourcées** :
- `_SAVINGS_RATE = 0.15` (`backend/app/modules/applications/simulation.py`) **inventé**
- `_CARBON_IMPACT_PER_MXOF = 1.7` (ligne 18) **inventé** — appliqué linéairement au montant
- `_DEFAULT_FEE_RATE = 0.03` **inventé**
- ROI calculé arbitrairement : payback fixe `12/0.15 ≈ 80 mois` indépendamment de l'instrument
- **Pas de différenciation** subvention vs prêt concessionnel vs blending (un don à 100% et un prêt à 12% donnent le même résultat)
- **Pas de coût total réel agrégé** (montant + marges + frais dossier + garanties)
- **Pas de comparateur multi-offres** (endpoint `/simulate` traite 1 dossier à la fois)
- Pas de Money typed F04
- Délai `intermediaire` = constante hardcodée "2-4" semaines, non lié à l'intermédiaire choisi

## User stories

- **PME** : « Quand je simule un financement, je veux voir le **coût total réel** : montant emprunté + marges intermédiaire + frais dossier + garanties, avec chaque chiffre cliquable vers sa source. »
- **PME** : « Pour un projet 5M FCFA, je veux comparer 3 offres concurrentes : GCF via BOAD vs GCF via UNDP vs SUNREF Ecobank — coût total, vitesse, taux de succès — et choisir la moins chère / la plus rapide. »
- **PME** : « Le calcul de l'impact carbone du projet doit utiliser un facteur sourcé (pas inventé) et différencier subvention vs prêt. »
- **PME** : « Le simulateur doit afficher la timeline réaliste = délais fonds + délais intermédiaire (issus de F07), pas une constante hardcodée. »

## Périmètre fonctionnel

### Migration des constantes vers `simulation_factors` (F01)

Toutes les constantes magiques migrent vers la table `simulation_factors` (créée par F01) :
- `roi_default`, `carbon_impact_per_mxof`, `default_fee_rate`, `payback_default`, etc.
- Chaque ligne avec FK `source_id NOT NULL` → en attendant les vraies sources, marquer `verification_status='pending'` (admin doit valider)

### Calcul du coût total réel

```python
async def compute_total_cost(application: FundApplication, target_amount: Money) -> dict:
    offer = application.offer  # F07
    
    # 1. Frais d'instruction fixes (intermediaire)
    doc_fee = offer.intermediary.fees_structured["doc_fee_amount"]  # Money
    
    # 2. Marge sur taux d'intérêt (si prêt) - seulement pour instruments non-grant
    if offer.fund.instruments contient "pret_concessionnel":
        rate = offer.intermediary.fees_structured["fee_rate_max"]  # 0.03
        annual_fees = target_amount * rate
        # cumulé sur la durée du prêt
        total_fees = annual_fees * application.project.duration_months / 12
    else:
        total_fees = Money(0, target_amount.currency)
    
    # 3. Garantie exigée
    guarantee = target_amount * offer.intermediary.fees_structured["guarantee_required_pct"]
    
    # 4. Marge FX si devise fonds != devise PME
    if offer.fund.currency != company.currency:
        fx_margin = target_amount * offer.intermediary.fees_structured["fx_margin"]
    else:
        fx_margin = Money(0, ...)
    
    return {
        "principal": target_amount,
        "doc_fee": doc_fee,
        "total_fees_over_duration": total_fees,
        "guarantee_required": guarantee,
        "fx_margin": fx_margin,
        "total_cost": principal + doc_fee + total_fees + fx_margin,  # garantie pas un coût mais immobilisation
        "all_money_typed": True,  # F04
    }
```

### Calcul ROI vert sourcé

Pour MVP, simple :
- Pour subvention : `ROI = ∞` (pas de remboursement)
- Pour prêt concessionnel : `ROI = (gains_estimés - coût_total) / coût_total` où gains = facteurs sourcés ADEME (économies énergie) + revenus carbone (Module 4)
- Marquer chaque facteur avec `cite_source` (F01)

Post-MVP : framework IRIS+ ou Verra complet.

### Impact environnemental sourcé

- Pas de constante `_CARBON_IMPACT_PER_MXOF = 1.7`
- Calcul basé sur le projet (Module 4 + F17) : `expected_impact_tco2e` du Project (F06) + ratio source ADEME/IPCC selon le secteur
- Affichage : "Réduction estimée : 12 tCO2e/an (basé sur ADEME Base Carbone v23, p.94, secteur énergie solaire)" + lien source cliquable

### Timeline réaliste

```python
def build_timeline(offer: Offer) -> list[Step]:
    return [
        Step("Préparation dossier", duration_weeks=(2, 4), source="ESG Mefali estimation"),
        Step("Instruction intermédiaire", 
             duration_weeks=(offer.intermediary.processing_time_days_min // 7, 
                             offer.intermediary.processing_time_days_max // 7),
             source=offer.intermediary.processing_time_source_id),  # F01
        Step("Validation fonds source",
             duration_weeks=(offer.fund.typical_timeline_months * 4 - 2,
                             offer.fund.typical_timeline_months * 4 + 2),
             source=offer.fund.source_id),
        Step("Décaissement",
             duration_weeks=(offer.intermediary.disbursement_time_days_min // 7,
                             offer.intermediary.disbursement_time_days_max // 7),
             source=offer.intermediary.disbursement_time_source_id),
    ]
```

### Comparateur multi-offres

Endpoint `POST /api/projects/{project_id}/simulate-multi` :
- Input : `[offer_id_1, offer_id_2, offer_id_3]` (jusqu'à 5)
- Output : tableau comparatif avec coût total, timeline, success_rate, score compatibilité (F14)
- Tool LangChain `compare_simulations` qui rend `<ComparisonTableBlock>` (F11)

Page `pages/financing/simulator.vue` (refactor) :
- Sélection projet
- Sélection 1..5 offres
- Affichage côte-à-côte (ComparisonTable F11)
- Highlight de la moins chère, de la plus rapide
- Sources cliquables sur chaque chiffre

## Hors-scope (post-MVP)

- Framework IRIS+ ou Verra complet
- Risque de change avancé (hedge fee, options)
- ML prédiction du taux de succès (basé sur historique)
- Intégration Open Banking pour réelle simulation de remboursement
- Sensitivity analysis (dérivée du coût face à variations taux)
- Stress test scenarios

## Exigences techniques

### Backend

- Migration des constantes vers `simulation_factors` (F01)
- Refactor `app/modules/applications/simulation.py` :
  - `compute_total_cost(...)` : Money typé, agrégation
  - `compute_roi(...)` : différencié par instrument
  - `compute_carbon_impact(...)` : sourcé via F01 + F17
  - `build_timeline(...)` : utilise délais réels offre
- Endpoint `POST /api/projects/{project_id}/simulate-multi`
- Tool LangChain `compare_simulations`
- Tests :
  - Test pas de constantes magiques inline (linter check)
  - Test ROI subvention vs prêt → résultats différenciés
  - Test timeline : délai depend de l'offre (changer d'offre → timeline change)
  - Test multi-simulate : 3 offres → tableau cohérent

### Frontend

- Refactor `pages/financing/simulator.vue`
- Composant `<ComparisonTableBlock>` (F11) intégré
- Affichage Money typed (F04) avec conversion équivalent PME
- Sources cliquables F01 sur chaque chiffre
- Dark mode

### Base de données

- Lien F01 (`simulation_factors` table)
- Pas de nouvelle table

## Critères d'acceptation

- [ ] Toutes les constantes magiques migrées vers `simulation_factors` avec `source_id`
- [ ] Coût total agrégé (Money typed F04)
- [ ] ROI différencié par instrument
- [ ] Timeline depend de l'offre (pas constante)
- [ ] Endpoint comparateur multi-offres fonctionnel
- [ ] Tool `compare_simulations` rend ComparisonTable
- [ ] Sources cliquables sur chaque chiffre
- [ ] Test E2E : simuler GCF/BOAD vs GCF/UNDP → différents
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : sources réelles pour ROI/carbone non disponibles immédiatement. **Garde-fou** : marquer les factors comme `pending`, label clair "estimation" jusqu'à validation admin.
- **Risque** : utilisateur PME confus par 5 colonnes. **Garde-fou** : limite 5 offres, interface claire, métrique clé "moins cher / plus rapide" en haut.
