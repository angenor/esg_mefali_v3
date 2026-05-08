# Phase 1 — Data Model : F16

**Date** : 2026-05-08
**Persistence** : aucune. F16 ne crée et ne mute aucune table. Toutes les entités décrites ci-dessous sont **volatiles** (in-memory pendant la requête) ou **lues** depuis tables existantes.

## 1. Entités volatiles (calcul à la demande)

### 1.1 FactorSnapshot (frozen dataclass)

Représente un instantané cohérent des facteurs de simulation chargés au début d'un appel multi-simulate. Sert toutes les offres comparées dans cet appel.

| Champ | Type | Description |
|-------|------|-------------|
| factors | `Mapping[str, FactorEntry]` | Dict immuable indexé par nom logique (ex. `default_loan_rate`, `default_fee_rate`, `payback_default_months`, `sector_carbon_factor_<sector>`). |
| sources | `Mapping[UUID, SourceRef]` | Dict immuable indexé par `source_id`, chargé via JOIN unique. |
| loaded_at | `datetime` (UTC) | Horodatage du snapshot, pour debug/observabilité. |

Invariant : `frozen=True` (Python `dataclass(frozen=True)`) — le snapshot est non mutable après chargement.

#### FactorEntry

| Champ | Type | Description |
|-------|------|-------------|
| name | `str` | Nom logique. |
| value | `Decimal` | Valeur numérique. |
| unit | `str` | `'rate'` / `'months'` / `'tco2e_per_mxof'` / etc. |
| status | `Literal['draft','pending','verified','outdated']` | Statut F01. |
| source_id | `UUID` | FK obligatoire vers `sources` (NOT NULL en BDD F01). |
| applies_to | `dict[str, Any] | None` | Filtre éventuel (ex. `{'sector':'energy'}`, `{'instrument':'pret_concessionnel'}`). |

#### SourceRef

Projection légère de la table `sources` (lecture seule) : `id`, `title`, `publisher`, `url`, `published_at`, `verification_status`.

### 1.2 SimulationResult (Pydantic v2 schema, response)

Résultat d'une simulation pour **une** offre + un projet.

| Champ | Type | Description |
|-------|------|-------------|
| offer_id | `UUID` | Offre simulée (FK F07, lecture). |
| project_id | `UUID` | Projet (FK F06, lecture). |
| principal | `Money` (F04) | Montant cible du projet, devise du fonds. |
| principal_pme_equivalent | `Money | None` | Conversion via F04 vers devise PME. |
| cost_breakdown | `CostBreakdown` | Décomposition (FR-004). |
| roi | `RoiBreakdown` | ROI différencié par instrument (FR-005). |
| carbon_impact | `CarbonImpact` | Impact carbone sourcé (FR-006). |
| timeline | `list[TimelineStep]` | Étapes datées de l'offre (FR-007). |
| sources_used | `list[UUID]` | Liste dédupliquée des `source_id` mobilisés. |
| degraded | `bool` | True si au moins un sous-champ est en mode dégradé. |
| computed_at | `datetime` | Horodatage du calcul (UTC). |

### 1.3 CostBreakdown

| Champ | Type | Description |
|-------|------|-------------|
| principal | `Money` | Montant cible. |
| doc_fee | `MonetaryFigure` | Frais d'instruction. |
| total_fees_over_duration | `MonetaryFigure` | Frais cumulés sur durée du prêt (0 si subvention). |
| guarantee_required | `MonetaryFigure` | Garantie immobilisée. |
| fx_margin | `MonetaryFigure` | Marge change si devises différentes. |
| total_cost | `Money` | Agrégat principal + doc_fee + total_fees_over_duration + fx_margin (la garantie est immobilisée mais pas un coût net). |

#### MonetaryFigure

Wrapper Money typed avec métadonnées de sourçage :

| Champ | Type | Description |
|-------|------|-------------|
| amount | `Money` (F04) | Valeur typée. |
| amount_pme_equivalent | `Money | None` | Conversion devise PME. |
| source_id | `UUID | None` | Source du facteur ayant servi au calcul. |
| factor_name | `str | None` | Nom logique du facteur (`default_fee_rate`, etc.). |
| factor_status | `Literal['verified','pending','outdated'] | None` | Statut F01 — déclenche affichage avertissement si `pending`/`outdated` (FR-003 + SC-007). |
| degraded_reason | `str | None` | Si `None` → calcul nominal ; sinon explication FR (`'facteur_introuvable'`, `'devise_fonds_inconnue'`). |

### 1.4 RoiBreakdown

| Champ | Type | Description |
|-------|------|-------------|
| instrument | `Literal['subvention','pret_concessionnel','equity','blending']` | Instrument retenu. |
| formula_id | `str` | Identifiant lisible de la formule appliquée (`'roi.subvention.no_repayment'`, `'roi.loan.gain_minus_cost_ratio'`, etc.). |
| gain_estimated | `Money | None` | Gains projetés (économies énergie + revenus carbone), `None` pour subvention. |
| payback_months | `int | None` | Durée d'amortissement, `None` pour subvention. |
| ratio | `Decimal | None` | Ratio gains/coût total. |
| notes_fr | `str` | Phrase explicative en français à afficher (« pas de remboursement », « ratio gains/coût total = X », etc.). |
| sources | `list[UUID]` | Sources des facteurs utilisés (taux, durée par défaut, ratio gain par défaut). |

### 1.5 CarbonImpact

| Champ | Type | Description |
|-------|------|-------------|
| tco2e_per_year | `Decimal | None` | Réduction estimée annuelle. |
| sector_factor | `Decimal | None` | Coefficient sectoriel appliqué. |
| factor_source_id | `UUID | None` | Source du `sector_factor` (ADEME/IPCC via F17). |
| project_estimate_used | `Decimal | None` | `project.expected_impact_tco2e` lu côté entrée. |
| is_approximate | `bool` | True si fallback (année antérieure ou pays global). |
| degraded_reason | `str | None` | Si projet sans estimation ou facteur introuvable. |

### 1.6 TimelineStep

| Champ | Type | Description |
|-------|------|-------------|
| step_id | `Literal['preparation','instruction_intermediaire','validation_fonds','decaissement']` | Identifiant logique. |
| label_fr | `str` | Libellé affiché. |
| weeks_min | `int | None` | Borne basse semaines. |
| weeks_max | `int | None` | Borne haute semaines. |
| source_id | `UUID | None` | Source du délai (offer.intermediary.* ou fund.*). |
| degraded_reason | `str | None` | Ex. `'delai_intermediaire_non_renseigne'`. |

### 1.7 MultiSimulateRequest

| Champ | Type | Validation |
|-------|------|-----------|
| offer_ids | `list[UUID]` | `min_length=1`, `max_length=5`, validator pour dedup applicatif (les doublons sont silencieusement réduits avant calcul). |

### 1.8 MultiSimulateResponse

| Champ | Type | Description |
|-------|------|-------------|
| project_id | `UUID` | Echo du paramètre d'URL. |
| per_offer | `dict[UUID, SimulationResult \| DegradedColumn]` | Une entrée par offre comparée. Clé = offer_id. |
| comparison_metadata | `ComparisonMetadata` | Méta-infos cross-offres. |
| factor_snapshot_loaded_at | `datetime` | Horodatage du snapshot de facteurs (cohérence FR-017). |

#### DegradedColumn

| Champ | Type | Description |
|-------|------|-------------|
| offer_id | `UUID` | Offre. |
| degraded | `Literal[True]` | Discriminator. |
| reason | `str` | Cause synthétique en FR (`'facteur_critique_introuvable'`, `'offre_sans_taux_publie'`). |
| computed_at | `datetime` | Horodatage. |

#### ComparisonMetadata

| Champ | Type | Description |
|-------|------|-------------|
| cheapest_offer_id | `UUID | None` | Offre de coût total minimal parmi celles non-dégradées. `None` si toutes dégradées ou si une seule offre. |
| fastest_offer_id | `UUID | None` | Offre de timeline totale (somme weeks_max) minimale parmi non-dégradées. `None` même condition. |
| degraded_offers | `list[UUID]` | Liste des offres en mode dégradé. |
| total_offers | `int` | Cardinal après dedup (1..5). |

## 2. Entités lues (read-only) — tables existantes

| Table | Origine | Colonnes utilisées |
|-------|---------|---------------------|
| `simulation_factors` | F01 | id, name, value, unit, status, source_id, applies_to |
| `sources` | F01 | id, title, publisher, url, published_at, verification_status |
| `projects` | F06 | id, account_id, name, sector, country, target_amount_*, expected_impact_tco2e, duration_months |
| `offers` | F07 | id, fund_id, intermediary_id, effective_min_amount_*, effective_max_amount_*, effective_interest_rate, effective_duration_months, source_id |
| `funds` | F07 | id, instruments (JSONB), currency, typical_timeline_months, source_id |
| `intermediaries` | F07 | id, fees_structured (JSONB), processing_time_days_min/max + source_ids, disbursement_time_days_min/max + source_ids |
| `emission_factors` | F01/F17 | id, category, country, year, value, source_id, sector |
| `exchange_rates` | F04 | base, quote, rate, as_of |

## 3. Lifecycle / state transitions

Aucune entité F16 n'a de cycle de vie persisté. La seule transition d'état concernant F16 est l'évolution du statut d'un facteur dans `simulation_factors` (gérée par F01/F09 admin), à laquelle F16 réagit en lecture en marquant les `MonetaryFigure.factor_status = 'pending'/'outdated'` pour affichage UI.

## 4. Règles de validation transversales

- **VR-001** : `MultiSimulateRequest.offer_ids` après dedup doit avoir `1 ≤ len ≤ 5` (FR-014). 422 sinon.
- **VR-002** : Tous les `offer_ids` doivent être lisibles par le compte appelant (vérification post-RLS). 403 si refus implicite.
- **VR-003** : `project_id` doit appartenir au compte appelant. 404 (et non 403, pour ne pas révéler l'existence) si refus.
- **VR-004** : Toute valeur `Money` exposée par l'API a une `currency` ∈ `{'XOF','EUR','USD','GBP','JPY'}` (validation F04).
- **VR-005** : Toute `MonetaryFigure` non-dégradée a `source_id IS NOT NULL` (invariant F01).
- **VR-006** : `total_cost = principal + doc_fee.amount + total_fees_over_duration.amount + fx_margin.amount` (la garantie n'entre pas dans le coût net). Vérifié par test unitaire.
- **VR-007** : Quand `instrument == 'subvention'`, `RoiBreakdown.payback_months IS NULL` et `gain_estimated` peut être renseigné si gains économiques sourcés. `notes_fr` contient « Pas de remboursement ».
- **VR-008** : `CarbonImpact.tco2e_per_year` n'est jamais calculé comme `target_amount × constante_uniforme` (testé par AST sur `simulation.py`).

## 5. Volume / scale

Aucun stockage. Mémoire par requête : O(N_offres × N_facteurs) avec N_offres ≤ 5, N_facteurs ≤ ~30 → empreinte négligeable (< 50 KB par appel).
