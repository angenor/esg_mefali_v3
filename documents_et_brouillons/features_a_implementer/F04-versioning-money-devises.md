# F04 — Versioning + Money Type + Multi-devises

**Module(s) source(s)** : Module 0.5 (Versioning), Module 0.6 (Devises)
**Priorité** : P0 — bloquante pour la défense de candidatures soumises et la cohérence multi-devises
**Dépendances** : F01 (sources versionnées), F02 (multi-tenant)
**Estimation** : 2 sprints

## Contexte & motivation

**Module 0.5 — Versioning**
Le brainstorming exige que les référentiels et critères soient versionnés avec `version`, `valid_from`, `valid_to`, et que les candidatures stockent un snapshot JSON immuable au moment de la soumission. Sans ça, si la taxonomie GCF évolue après le dépôt d'un dossier, on perd la capacité de défendre la candidature.

**État actuel** :
- Aucune table `referentiels` (cf. F01)
- Aucun champ `version`, `valid_from`, `valid_to` sur `funds`, `intermediaries`
- `FundApplication` (`backend/app/models/application.py:117-128`) a des champs `sections`, `checklist`, `intermediary_prep`, `simulation` mais **aucun snapshot du référentiel ou de l'offre** au moment de la soumission
- Aucun badge "Évalué selon Référentiel GCF v2.3 du 15/03/2026" dans l'UI

**Module 0.6 — Devises**
Le brainstorming exige un type `Money = {amount, currency}` typé partout, avec peg fixe FCFA-EUR 655.957 et API exchangerate-api.com pour USD/autres.

**État actuel** :
- Aucun type `Money` composé. Toutes les colonnes financières sont des `BigInteger`/`Float` simples : `min_amount_xof`, `max_amount_xof`, `annual_revenue_xof`, `estimated_cost_xof`, `savings_fcfa`. La devise est encodée dans le **nom de la colonne**, ce qui interdit toute multi-devise.
- Constante peg 655.957 absente du code (`grep "655.957"` → 0)
- Aucune dépendance/call exchangerate-api
- Affichage UI mono-devise XOF/FCFA partout
- Le tool `application_tools._simulate_financing` lit `fund.max_amount`/`fund.min_amount` (non typés Money, et de plus ces attributs **n'existent pas** sur le modèle qui a `max_amount_xof`/`min_amount_xof` — bug AttributeError silencieux)

## User stories

- **PME** : « En tant que PME, quand je vois un fonds GCF qui finance "5 000 000 USD à 10 000 000 USD", je veux voir simultanément l'équivalent en FCFA pour comparer avec mon CA local. »
- **PME** : « Quand je soumets une candidature à GCF via BOAD le 15/03/2026, et que GCF publie une nouvelle taxonomie le 30/03/2026, je veux que mon dossier soit défendable selon **la version active au moment de ma soumission**, pas la nouvelle. »
- **PME** : « Quand je consulte un score ESG ancien, je veux voir un badge "Évalué selon Référentiel ESG Mefali v1.2 du 10/02/2026" pour savoir s'il faut relancer une évaluation à jour. »
- **Auditeur externe** : « Je veux pouvoir reproduire le score d'une candidature à partir du snapshot stocké, indépendamment de l'évolution du référentiel après. »

## Périmètre fonctionnel

### Versioning des entités catalogue

Champs à ajouter (sur les entités créées par F01 et les existantes) :
- `version: str NOT NULL DEFAULT '1.0'` (semver-like, géré par admin)
- `valid_from: date NOT NULL DEFAULT CURRENT_DATE`
- `valid_to: date | null` (null = encore en vigueur)
- `superseded_by: UUID FK self.id | null` (chaîne de versions)

Tables concernées :
- `sources` (déjà créé en F01, ajouter)
- `indicators`, `referentials`, `referential_indicators`, `criteria`, `formulas`, `thresholds`, `emission_factors`, `required_documents`, `simulation_factors` (créés en F01)
- `funds`, `intermediaries`, `fund_intermediaries`
- `templates_dossier` (créé en F15)
- `skills` (créé en F23)

Quand un admin édite un objet "publié", il **crée une nouvelle version** :
- `valid_to = today` sur l'ancienne, `superseded_by = new.id`
- Nouvelle row insérée avec `version` incrémenté, `valid_from = today + 1`
- Les conversations en cours conservent l'ancienne version (snapshot, voir ci-dessous)

### Snapshot immuable sur Candidature

Modifier `FundApplication` :
- Ajouter `snapshot_at: datetime | null` (date de capture)
- Ajouter `snapshot_data: jsonb | null` qui capture **deepcopy** au moment du `submitted_*` :
  - `referential` (collection d'indicators avec poids/seuils, à la version active)
  - `fund` (tous les champs)
  - `intermediary` (tous les champs)
  - `offer` (couple, créé en F07)
  - `scores_calculés` (avec leurs source_id)
  - `documents_requis` (liste à la version active)

Le snapshot est créé automatiquement lors de la transition `draft → submitted_to_intermediary` ou `submitted_to_fund`.

Le score peut être **recalculé contre le snapshot historique** pour audit/défense :
- Endpoint `POST /api/applications/{id}/recompute-against-snapshot` qui charge les indicateurs/seuils depuis le `snapshot_data` (pas la version courante).

### Type `Money` typé

Créer `backend/app/core/money.py` :

```python
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal

Currency = Literal["XOF", "EUR", "USD", "GBP", "JPY"]  # extensible

class Money(BaseModel):
    amount: Decimal = Field(..., decimal_places=2, ge=0)
    currency: Currency
    
    def converted_to(self, target: Currency, snapshot_date: date | None = None) -> "Money":
        ...  # délègue au service exchange_rates
```

Représentation BDD : 2 colonnes par champ Money (`<field>_amount: Numeric(20, 2)`, `<field>_currency: Char(3)`).

### Migration des champs financiers existants

Refactor BDD pour remplacer les `*_xof` / `*_fcfa` par paires `(amount, currency)` :

| Avant | Après |
|---|---|
| `funds.min_amount_xof: BigInteger` | `funds.min_amount: Numeric(20,2)`, `funds.min_amount_currency: Char(3)` |
| `funds.max_amount_xof: BigInteger` | idem |
| `company_profiles.annual_revenue_xof: BigInteger` | `annual_revenue_amount`, `annual_revenue_currency` |
| `action_items.estimated_cost_xof: int` | `estimated_cost_amount`, `estimated_cost_currency` |
| `carbon_assessments.savings_fcfa: float` | `savings_amount`, `savings_currency` |
| `applications.intermediary_fees_xof: int` (dans `simulation` JSON) | refactor en Money |

Migration Alembic avec backfill : `UPDATE funds SET min_amount = min_amount_xof, min_amount_currency = 'XOF'`.

### Constante peg FCFA-EUR

Dans `backend/app/core/constants.py` :
```python
FCFA_EUR_PEG = Decimal("655.957")
```

### Service `currency_service`

`backend/app/modules/currency/service.py` :
- `convert(money: Money, target: Currency, date: date | None = None) -> Money`
  - Si pair = `(XOF, EUR)` → utilise le peg fixe
  - Sinon → utilise la table `exchange_rates`
- `get_rate(base: Currency, quote: Currency, date: date) -> Decimal` (avec fallback à la date la plus récente disponible)

Table `exchange_rates` :
- `id: UUID PK`
- `base_currency: Char(3)`
- `quote_currency: Char(3)`
- `rate: Numeric(20, 10)`
- `as_of: date` (date du taux)
- `source: str` (ex : "exchangerate-api.com", "ECB", "BCEAO")
- `fetched_at: datetime`

Index unique `(base_currency, quote_currency, as_of)`.

### Cron / task de fetch des taux

- `backend/app/scripts/fetch_exchange_rates.py` : appelle exchangerate-api.com (free tier, 1500 req/mois suffisent), parse les paires (USD→XOF, USD→EUR, USD→GBP, etc.), insère dans `exchange_rates`.
- À exécuter une fois par jour (cron système ou APScheduler ; le cron est aussi le prérequis F19).
- Au démarrage de l'app si la table est vide ou trop ancienne, déclencher un fetch one-shot.

### Affichage UI

Composant `<MoneyDisplay :money="..." :show-pme-currency="true" />` :
- Affiche `1 000 000 FCFA (≈ 1 524 €)` quand la devise du fonds n'est pas la devise PME
- Switch user-preference dans `stores/ui.ts` : `displayCurrencyMode: 'native' | 'pme' | 'both'`
- Dark mode

À utiliser partout où un montant s'affiche (cards fonds, simulateur, dashboard, action plan, candidatures, attestation).

### Badge `<ReferentialBadge>` (versioning)

Composant `<ReferentialBadge :referential="..." :date="..." />` :
- Affiche : « Évalué selon Référentiel GCF v2.3 du 15/03/2026 »
- Cliquable → ouvre `<SourceModal>` avec détail de la version
- Sur chaque score persisté : ESG, carbone, credit, score d'éligibilité offre

### Différenciation devise emprunt vs remboursement (Module 3.4)

Pour le simulateur de financement F16 :
- Devise d'emprunt = devise du fonds source (ex : USD pour GCF)
- Devise de remboursement = devise PME (ex : XOF)
- Marge de change = écart entre taux du jour de l'emprunt et taux de remboursement
- Affichage explicite du **risque de change** dans le simulateur (post-MVP : hedge fee suggéré)

## Hors-scope (post-MVP)

- Hedging FX automatique
- Devises moins courantes (CFA central CEMAC, MAD, NGN, EGP, ZAR) — facile à ajouter une fois l'infra en place
- Conversion historique avec interpolation entre points
- Préférence utilisateur de devise principale (toujours XOF par défaut)
- Versioning workflow editorial (pre-publication, branches) — pour MVP, juste linéaire

## Exigences techniques

### Backend

- `core/money.py` : type Pydantic `Money` + alias type Currency
- `core/constants.py` : `FCFA_EUR_PEG`
- Migration Alembic `021_money_and_versioning.py` :
  - Tables `exchange_rates`
  - Ajouter `version`, `valid_from`, `valid_to`, `superseded_by` sur les entités catalogue
  - Refactor des champs `*_xof` / `*_fcfa` en paires `<field>_amount` + `<field>_currency` (backfill avec XOF)
  - Ajouter `snapshot_at`, `snapshot_data` sur `fund_applications`
- Modèle `app/models/exchange_rate.py`
- Module `app/modules/currency/` : service, router (`GET /api/currency/rates/latest`, `POST /api/currency/convert`)
- Script `scripts/fetch_exchange_rates.py`
- Modifications services :
  - `applications/service.py` : créer `snapshot_data` à la transition vers submitted
  - Refactor des accès `*_xof` → Money typé
- Tools LangChain mis à jour : `simulate_financing` retourne des Money typés
- Tests :
  - Test peg FCFA-EUR : `convert(Money(655_957, 'XOF'), 'EUR') == Money(1_000, 'EUR')` (avec arrondis)
  - Test snapshot : créer application, mettre à jour le référentiel, recompute against snapshot doit retourner le score d'origine
  - Test versioning : éditer un fund publié → ancienne version reçoit `valid_to`, nouvelle créée

### Frontend

- Composant `<MoneyDisplay>` dans `components/ui/`
- Composant `<ReferentialBadge>` dans `components/ui/`
- Composable `composables/useCurrency.ts` (`format`, `convert`, `getRate`)
- Store `stores/ui.ts` : ajouter `displayCurrencyMode`
- Page settings utilisateur : choix devise d'affichage préférée
- Migration : remplacer toutes les occurrences `formatXof()` ou `${amount} XOF` par `<MoneyDisplay :money="..." />`
- Dark mode

### Base de données

- Table `exchange_rates` (1 fetch quotidien, ~10 KB par jour)
- Modifications schema sur ~10 tables pour Money typé
- Modifications schema pour versioning (4 colonnes additionnelles sur ~8 tables)
- Index : `exchange_rates(base_currency, quote_currency, as_of DESC)`, `*.valid_to`, `*.superseded_by`

## Critères d'acceptation

- [ ] Type `Money` Pydantic créé, validé, utilisé dans les schemas API
- [ ] Constante `FCFA_EUR_PEG = 655.957` définie
- [ ] Table `exchange_rates` créée + cron de fetch quotidien fonctionnel
- [ ] Tous les champs `*_xof` / `*_fcfa` migrés en paires `(amount, currency)`
- [ ] Versioning actif sur catalogue : éditer un objet publié crée une nouvelle version, l'ancienne garde `valid_to`
- [ ] Snapshot immuable créé sur transition `draft → submitted` d'une candidature
- [ ] Endpoint `recompute-against-snapshot` fonctionnel
- [ ] Composant `<MoneyDisplay>` rend les montants en native + équivalent PME
- [ ] Composant `<ReferentialBadge>` affiché sur chaque score persisté
- [ ] Test snapshot : modifier le catalogue après soumission ne change pas le score reproductible
- [ ] Test peg : conversion FCFA↔EUR utilise toujours 655.957 sans appel API
- [ ] Test conversion USD : utilise les rates de la table, fallback à la date la plus récente disponible
- [ ] Couverture tests ≥ 80 % sur `currency`, `versioning`, `money`
- [ ] Tool `simulate_financing` retourne des Money typés (et plus l'AttributeError sur `fund.max_amount`)

## Risques & garde-fous

- **Risque** : la migration Alembic des champs `*_xof` casse les services qui n'ont pas été refactorés. **Garde-fou** : migration en 2 phases : (1) ajouter les nouvelles colonnes en parallèle, backfill ; (2) après refactor de tous les services, drop les anciennes colonnes. Phase 2 dans une migration séparée.
- **Risque** : exchangerate-api.com tier gratuit a 1500 req/mois → si le cron tourne plusieurs fois par jour, on dépasse. **Garde-fou** : cap dur 1 fetch/jour, mode "best effort" (si la requête échoue, garder le taux précédent), alerte admin.
- **Risque** : un user PME ne comprend pas la différence "native" vs "PME" dans `<MoneyDisplay>`. **Garde-fou** : toujours afficher le symbole de devise explicite, tooltip d'explication, ne pas afficher l'équivalent si la devise est déjà la devise PME.
- **Risque** : le snapshot JSON devient énorme (référentiel + fund + intermediary + indicators avec sources = 100 KB+). **Garde-fou** : compresser avec gzip avant stockage (pgcrypto ou applicatif), benchmarker la taille moyenne sur le golden set.
- **Risque** : la chaîne `superseded_by` permet une attaque DoS via cycle (A → B → A). **Garde-fou** : trigger PostgreSQL qui détecte les cycles avant INSERT.
- **Risque** : dérive de devises (admin oublie de mettre à jour la liste `Currency`). **Garde-fou** : enum strict, refus à l'INSERT si currency hors enum, alerte si une PME affiche un montant dans une devise non standard.
