# Glossaire du Catalogue Mefali

Ce glossaire définit les termes clés du catalogue de financements vert
mobilisés par les modules F08 (matching) et F07 (offres).

## Entités principales

### Fund (Fonds)

Un **Fund** représente un fonds vert listé au catalogue Mefali (ex : GCF,
FEM, BOAD, BAD). C'est l'**entité émettrice du financement**, mais elle
n'est généralement **pas commercialement actionnable directement** par une
PME africaine — la plupart des grands fonds verts ne décaissent qu'à des
intermédiaires accrédités.

**Champs clés** : `name`, `organization`, `fund_type`, `instruments` (F07),
`theme` (F07), `submission_mode` (F07), `min_amount`/`max_amount`
(Money typed F04), `source_id` (F01), `publication_status`.

**Énumération `fund_type` (F07)** :
- `multilateral` : ex. GCF, FEM (anciennement `international`)
- `bilateral` : ex. AFD, GIZ
- `regional` : ex. BOAD, BAD
- `national` : ex. FNDE
- `private` : ex. lignes vertes bancaires (anciennement `local_bank_green_line`)
- `carbon_marketplace` : ex. plateformes carbone (anciennement `carbon_market`)

### Intermediary (Intermédiaire)

Un **Intermediary** est une organisation accréditée pour distribuer les
fonds d'un Fund à des PME : banque locale, agence de développement, ONG,
développeur de projet, agence ONU, etc. C'est l'**interlocuteur direct**
de la PME.

**Champs clés F07** : `code`, `required_documents`, `fees_structured`,
`processing_time_days_min/max`, `disbursement_time_days_min/max`,
`success_rate`, `total_funded_volume`, `source_id`, `publication_status`.

**Singleton DIRECT** : un intermédiaire spécial avec `code='DIRECT'`,
créé en migration 028, représente la « soumission directe au fonds sans
intermédiaire ». Utilisé pour uniformiser les `Offers` quand un Fund a
`access_type='direct'`.

### FundIntermediary (Liaison)

Liaison N-N entre un Fund et un Intermediary, attestant qu'un
intermédiaire est accrédité pour distribuer un fonds donné.

**Champs F07** : `accredited_from` (NOT NULL), `accredited_to`,
`max_amount_per_fund`, `accreditation_source_id`. Le cron quotidien
`check_expired_accreditations.py` désactive les offres dont
`accredited_to < today`.

### Offer (Offre — F07)

Une **Offer** représente le **couple commercialement actionnable** vu par
une PME : c'est cette entité qui peut être candidatée. Elle contient les
champs effectifs résultant de la fusion des règles du Fund et de
l'Intermediary :

- `effective_criteria` : intersection critères avec règle « le plus
  restrictif gagne ».
- `effective_required_documents` : union dédupliquée par
  `(title.lower().strip(), source_id)` ; `mandatory=true` écrase
  `mandatory=false`.
- `effective_fees` : somme cumulée Money typed (conversion XOF si
  devises différentes).
- `effective_processing_time_days_min/max` et
  `effective_disbursement_time_days_min/max` : somme des délais.
- `accepted_languages` : default `["FR"]`, hint inféré depuis
  `intermediary.country` (anglophone → `["EN"]`).

**Unicité** : `UNIQUE (fund_id, intermediary_id, version)`. Pour créer
une « v2 », l'admin doit incrémenter `version` (workflow F04).

**Statut** : `is_active` (bool) + `publication_status` (`draft|published`).
Une offre n'est visible côté PME que si `publication_status='published'`
ET `is_active=TRUE`.

### OfferDraft

Structure Pydantic non persistée, retournée par
`compute_effective_offer(fund_id, intermediary_id)`. L'admin l'édite
puis appelle `POST /api/admin/offers` pour créer l'offre réelle.

## Patterns spécifiques

### Pattern singleton DIRECT

Un Fund avec `access_type='direct'` est uniformisé via une `Offer`
liée à l'intermédiaire singleton `code='DIRECT'`. Tous les flows
applicatifs pointent ainsi systématiquement vers une `offer_id NOT NULL`,
simplifiant la modélisation.

### Pattern de feature flag `USE_OFFER_VIEW`

Le flag (env var `NUXT_PUBLIC_USE_OFFER_VIEW`) contrôle si la home
`/financing` affiche les Cards Offres (true) ou les Cards Fonds legacy
(false). Default `false` en MVP F07. Bascule effective post-F14 (matching
offre mature).

## Référentiel

- **F07** : `specs/028-entite-offre-fonds-intermediaire/`
- **F08** : `specs/008-conseiller-financement-vert/` (matching legacy)
- **F09** : `specs/009-fund-application-generator/`
- Migration : `backend/alembic/versions/028_offers_and_enrich_fund_intermediary.py`
