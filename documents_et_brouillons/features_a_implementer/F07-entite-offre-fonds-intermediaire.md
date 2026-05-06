# F07 — Entité Offre = Couple Fonds × Intermédiaire

**Module(s) source(s)** : Module 3.1.3 (Offres = couples), Module 3.1.1 (Fonds source enrichi), Module 3.1.2 (Intermédiaires enrichis)
**Priorité** : P0 — bloquante pour matching Projet ↔ Offre (F14), génération dossier par Offre (F15), simulateur multi-offres (F16), extension Chrome (F24)
**Dépendances** : F01 (sources), F02 (multi-tenant Admin), F04 (versioning + Money), F06 (entité Projet)
**Estimation** : 2.5 sprints

## Contexte & motivation

**La promesse différenciante du brainstorming** : "la plupart des grands fonds verts ne décaissent **jamais directement** aux PME africaines. Le module est structuré autour de **trois entités** — Fonds source, Intermédiaire accrédité, Offre (couple Fonds × Intermédiaire) — où c'est l'**Offre** qui est l'unité commercialement accessible à une PME."

**État actuel** :
- `Fund` existe (`backend/app/models/financing.py:107-170`) mais pauvre :
  - Pas de champ `instruments` (subvention/prêt/garantie/equity/blending)
  - Pas de champ `theme` (mitigation/adaptation/biodiversité/...)
  - Pas de `submission_mode` (`rolling` vs `call_for_proposals`)
  - Plafonds en `min_amount_xof`/`max_amount_xof` (mono-devise, à refactor F04)
  - Pas de versioning F04
  - Pas de FK vers `Source` (F01)
- `Intermediary` existe (`backend/app/models/financing.py:173-215`) mais pauvre :
  - Pas de `required_documents` propres
  - `typical_fees` est un texte libre parsé par regex (non structuré, non sourcé)
  - Pas de `processing_time_days` / `disbursement_time_days`
  - Pas de `submission_portal_url`
  - Pas de `success_rate` / `total_funded_volume`
- `FundIntermediary` (jointure) existe MAIS :
  - Pas de date d'accréditation (`accredited_from` / `accredited_to`)
  - Pas de plafond par fonds
  - Pas de calcul d'intersection critères / union documents / somme frais / cumul délais
- **AUCUNE entité `Offer`** : pas de table `offers`. Le frontend `pages/financing/[id].vue` montre un fonds avec ses intermédiaires en modal — pas une Offre comme entité de premier plan.
- `accepted_languages` (FR/EN par offre, Module 3.1.3) : inexistant
- Pages frontend orientées "Fonds", pas "Offre"

## User stories

- **PME** : « Je veux pouvoir candidater à "GCF via BOAD" et "GCF via UNDP" comme **deux offres distinctes** pour le même fonds GCF, parce que les délais, frais, taux de succès et exigences documentaires diffèrent. »
- **PME** : « Quand je consulte une offre, je veux voir **les critères effectifs (intersection fonds + intermédiaire)**, **les documents requis (union)**, **les frais cumulés**, **les délais cumulés** et la **langue acceptée du dossier**. »
- **PME** : « Je veux comparer côte-à-côte les offres concurrentes pour le GCF (BOAD vs UNDP vs AFD) sur frais, vitesse, taux de succès. »
- **Admin Mefali** : « Je veux créer une nouvelle Offre depuis le back-office en sélectionnant un fonds + un intermédiaire actifs, et la plateforme me propose un calcul automatique des critères/documents/frais/délais effectifs (préfilling éditable). »

## Périmètre fonctionnel

### Enrichir `Fund`

Ajouter aux modèles existants :
- `instruments: jsonb NOT NULL DEFAULT '[]'` (liste : `subvention`, `pret_concessionnel`, `garantie`, `equity`, `blending`)
- `theme: jsonb NOT NULL DEFAULT '[]'` (liste : `mitigation`, `adaptation`, `biodiversity`, `circular_economy`, `mixed`)
- `submission_mode: enum('rolling', 'call_for_proposals') NOT NULL DEFAULT 'rolling'`
- `submission_calendar: jsonb | null` (sessions datées si call_for_proposals : `[{name, opens_at, closes_at, status}]`)
- `source_id: UUID FK sources.id NOT NULL` (F01)
- `version`, `valid_from`, `valid_to` (F04)
- `publication_status: enum('draft', 'published') DEFAULT 'draft'` (F09)
- Refactor `min_amount_xof`/`max_amount_xof` en Money typed (F04)
- Préciser le `fund_type` enum : actuellement `international/regional/national/carbon_market/local_bank_green_line` est un mélange type institution × instrument. Renommer/clarifier en :
  - `fund_type: enum('multilateral', 'bilateral', 'regional', 'national', 'private', 'carbon_marketplace')`
  - `provenance` (déjà existant) garde la dimension géographique

### Enrichir `Intermediary`

Ajouter :
- `required_documents: jsonb NOT NULL DEFAULT '[]'` (liste objets `{title, source_id, mandatory: bool, format_spec}`)
- `fees_structured: jsonb` (au lieu du `typical_fees` texte libre) :
  ```json
  {
    "doc_fee_amount": { "amount": 50000, "currency": "XOF" },
    "fee_rate_min": 0.02,
    "fee_rate_max": 0.05,
    "fx_margin": 0.01,
    "guarantee_required_pct": 0.10,
    "source_id": "uuid-here"
  }
  ```
- `processing_time_days_min: int | null`
- `processing_time_days_max: int | null`
- `disbursement_time_days_min: int | null`
- `disbursement_time_days_max: int | null`
- `submission_portal_url: str | null`
- `success_rate: Numeric(5, 4) | null` (0..1, post-mortem stats)
- `total_funded_volume_amount: Numeric(20, 2) | null`
- `total_funded_volume_currency: Char(3) | null`
- `source_id: UUID FK sources.id NOT NULL`
- `version`, `valid_from`, `valid_to`, `publication_status`

Garder `typical_fees` texte libre temporairement pendant la migration (deprecated).

### Enrichir `FundIntermediary` (relation N-N)

Ajouter :
- `accredited_from: date NOT NULL`
- `accredited_to: date | null` (null = encore accrédité)
- `max_amount_per_fund_amount: Numeric(20, 2) | null`
- `max_amount_per_fund_currency: Char(3) | null`
- `accreditation_source_id: UUID FK sources.id` (preuve documentaire de l'accréditation)

### Nouvelle entité `Offer`

Table `offers` :
- `id: UUID PK`
- `fund_id: UUID FK funds.id NOT NULL`
- `intermediary_id: UUID FK intermediaries.id NOT NULL`
- `name: str(200) NOT NULL` (ex : "GCF via BOAD - Mitigation Afrique Ouest")
- `accepted_languages: jsonb NOT NULL DEFAULT '["FR"]'` (liste ISO 639-1)
- `target_sector: jsonb` (peut être plus restrictif que les sectors du fund)
- `effective_criteria: jsonb` (intersection fund.eligibility + intermediary.eligibility — calculé/édité par admin, sourcé)
- `effective_required_documents: jsonb` (union fund.required_documents + intermediary.required_documents — sourcé)
- `effective_fees: jsonb` (combinaison fund.fees + intermediary.fees_structured)
- `effective_processing_time_days_min: int`
- `effective_processing_time_days_max: int`
- `effective_disbursement_time_days_min: int`
- `effective_disbursement_time_days_max: int`
- `notes: text | null` (notes admin contextuelles)
- `is_active: bool NOT NULL DEFAULT true`
- `version`, `valid_from`, `valid_to`, `publication_status`
- `source_id: UUID FK sources.id NOT NULL` (généralement = source de l'accréditation FundIntermediary)

Index unique `(fund_id, intermediary_id, version)`.

### Service de calcul automatique

`backend/app/modules/offers/calculator.py` :
- `compute_effective_offer(fund_id, intermediary_id) → OfferDraft`
  - Charge fund + intermediary actifs
  - `effective_criteria = intersection(fund.eligibility_criteria, intermediary.eligibility_for_sme)` avec règles métier (le plus restrictif gagne)
  - `effective_required_documents = union(fund.required_documents, intermediary.required_documents)` (déduplication)
  - `effective_fees = combine(fund.fees, intermediary.fees_structured)` (somme des frais cumulés)
  - `effective_processing_time = sum(fund.typical_timeline + intermediary.processing_time)`
  - Retourne un draft que l'admin peut ensuite éditer/valider

### Refactor `FundApplication` (candidature)

Migration vers le pivot Offre :
- Ajouter `offer_id: UUID FK offers.id NULL` (NULL transitoirement)
- Backfill : pour chaque application existante avec `(fund_id, intermediary_id)`, chercher/créer l'`Offer` correspondante, lier
- Après backfill : `offer_id NOT NULL`, deprecate `fund_id` et `intermediary_id` (les conserver pour `cascadeRead` mais marquer dans le code "use offer_id")
- Lier également au `project_id` (F06)

### API REST

Module `backend/app/modules/offers/` :
- `GET /api/offers` (liste publique, filtres : `fund_id`, `intermediary_id`, `theme`, `instrument`, `country`, `language`)
- `GET /api/offers/{id}`
- `GET /api/offers/comparator?fund_id=X` : retourne toutes les offres pour ce fonds (toutes les variantes via différents intermédiaires) avec scoring décomposé, frais effectifs, délais effectifs, success_rate côte à côte (utilisé par F14 matching)
- `POST /api/admin/offers` (admin only via F02)
- `PATCH /api/admin/offers/{id}`
- `POST /api/admin/offers/compute?fund_id=X&intermediary_id=Y` (preview du calcul effectif sans persister)

### Frontend

Pages :
- `pages/financing/index.vue` (existante) : refactor pour afficher des **Offres** (pas des fonds nus)
  - Cards d'offres avec score compatibilité décomposé (fund_score / intermediary_score)
  - Filtres : thème, instrument, pays, langue
- `pages/financing/funds/[fund_id].vue` : détail fonds + liste des offres associées
- `pages/financing/intermediaries/[intermediary_id].vue` : détail intermédiaire + offres
- `pages/financing/offers/[offer_id].vue` : détail offre = vue principale qui affiche :
  - Header : nom + score compatibilité + badge langue + statut soumission (rolling/CFP)
  - Section "Fonds source" cliquable
  - Section "Intermédiaire" cliquable
  - Section "Critères effectifs" (avec sources cliquables F01)
  - Section "Documents requis" (avec sources cliquables F01)
  - Section "Frais effectifs" (Money typed F04)
  - Section "Délais effectifs"
  - Bouton "Comparer avec autres offres pour ce fonds" → comparateur F14
  - Bouton "Candidater" → flow F15

Composants :
- `components/financing/OfferCard.vue`
- `components/financing/FundCard.vue`
- `components/financing/IntermediaryCard.vue`
- `components/financing/OfferDetail.vue`
- `components/financing/EffectiveCriteriaList.vue`
- `components/financing/EffectiveDocumentsList.vue`
- `components/financing/EffectiveFees.vue`
- `components/financing/SubmissionModeBadge.vue`

## Hors-scope (post-MVP)

- Marketplace d'offres tierces (consultants accréditants leurs propres offres)
- Versionning très fin par section d'une offre (overlay diff visuel)
- A/B testing de templates par offre
- API publique pour découvrir les offres ouvertes (à réfléchir, pose des questions de licence)

## Exigences techniques

### Backend

- Migration Alembic `024_offers_and_enrich_fund_intermediary.py` :
  - Enrichir `funds` (instruments, theme, submission_mode, submission_calendar, source_id, etc.)
  - Enrichir `intermediaries` (required_documents, fees_structured, timing, success_rate, etc.)
  - Enrichir `fund_intermediaries` (accredited_from, max_amount_per_fund, etc.)
  - Créer table `offers`
  - Ajouter `offer_id` sur `fund_applications` (NULL initialement)
  - Backfill offres : pour chaque (fund, intermediary) lié, créer une `Offer` avec calcul auto
  - Lier `fund_applications.offer_id`
- Modèles SQLAlchemy : `Offer`, mise à jour `Fund` / `Intermediary` / `FundIntermediary` / `FundApplication`
- Module `app/modules/offers/` : service, calculator, router, schemas
- Mise à jour `app/modules/financing/service.py` pour exposer offers + matching offre (préparer F14)
- Tools LangChain (mise à jour) :
  - `list_offers(filters) → list[OfferSummary]`
  - `get_offer(offer_id) → Offer`
  - `compare_offers_for_fund(fund_id) → list[OfferComparison]`
  - Updates des tools `create_fund_application` (préparer F15) pour prendre `offer_id` et `project_id`
- Tests :
  - Calcul effectif : intersection critères, union documents, somme frais/délais
  - Migration backfill : N applications existantes → N+ offres + applications relinkees
  - API : filtres marchent (par theme, instrument, language, country)
  - Test admin guard : seul admin peut créer/éditer offre

### Frontend

- Pages refactorées et nouvelles
- 8+ composants nouveaux dans `components/financing/`
- Composable `useFinancing.ts` étendu pour gérer offres
- Store `financing.ts` étendu
- Dark mode complet
- Accessibilité : navigation clavier, aria-label

### Base de données

- Tables : `offers`
- Colonnes ajoutées : ~20 sur `funds`, ~15 sur `intermediaries`, ~5 sur `fund_intermediaries`, 1 sur `fund_applications`
- Indexes : `offers(fund_id, intermediary_id, valid_to)`, `offers(theme @>)`, `offers(submission_mode)`, full-text sur `name`
- Contraintes : `offers.fund_id` actif et `offers.intermediary_id` actif au moment du publish

## Critères d'acceptation

- [ ] `Fund` enrichi avec `instruments`, `theme`, `submission_mode`, `source_id`, versioning, Money typed
- [ ] `Intermediary` enrichi avec `required_documents`, `fees_structured`, timing, source_id
- [ ] `FundIntermediary` enrichi avec dates d'accréditation et plafonds
- [ ] Table `offers` créée avec calcul automatique des effective_*
- [ ] Backfill : toutes les `FundApplication` liées à un `Offer` (via couple existant)
- [ ] CRUD Offers admin fonctionnel
- [ ] Pages `pages/financing/offers/[id].vue`, `pages/financing/funds/[id].vue` créées
- [ ] Composants `OfferCard`, `OfferDetail`, etc. implémentés
- [ ] Filtres et tri sur la liste d'offres fonctionnels
- [ ] Sourçage cliquable (F01) sur effective_criteria, effective_required_documents, effective_fees
- [ ] Test E2E : créer offre via admin → vérifier calcul auto → publier → visible côté PME
- [ ] Test E2E : un fonds GCF lié à 2 intermédiaires (BOAD + UNDP) → 2 offres distinctes visibles, comparables
- [ ] Test multi-tenant (F02) : la liste d'offres est publique (pas filtrée par account) mais leur publication_status doit être 'published'
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : la migration backfill crée des offres "fantômes" pour des couples qui ne sont pas réellement actifs. **Garde-fou** : marquer `is_active=false` par défaut sur le backfill, admin valide manuellement, publication uniquement après revue.
- **Risque** : le calcul `intersection(criteria)` est trompeur si les schémas de critères ne sont pas alignés (fund.eligibility_criteria vs intermediary.eligibility_for_sme — JSON libre actuellement). **Garde-fou** : F01 introduit la couche `Indicator/Criterion` typée → recalculer après F01 ; en attendant, présenter le calcul comme draft éditable.
- **Risque** : duplication entre `Fund.fund_type` et `Intermediary.intermediary_type` confuse pour les admins. **Garde-fou** : documenter la sémantique dans `docs/catalog-glossary.md`, ajouter tooltips UI.
- **Risque** : les frontend `pages/financing/*` actuelles (qui marchent en mono-fonds) cassent durant la migration. **Garde-fou** : feature flag `USE_OFFER_VIEW` pour bascule progressive ; garder la vue fonds-centric en parallèle pendant 2 sprints, puis deprecate.
- **Risque** : les `accepted_languages` de l'offre (Module 3.1.3) ne sont pas respectés par le générateur de dossier (F15) → texte FR alors que l'intermédiaire exige EN. **Garde-fou** : F15 lit explicitement `offer.accepted_languages` et bloque la soumission si la langue ne match pas, fallback sur le premier supporté.
- **Risque** : retraits/expirations d'accréditations non reflétés. **Garde-fou** : cron quotidien qui vérifie `accredited_to < today` et désactive l'offre, alerte admin.
