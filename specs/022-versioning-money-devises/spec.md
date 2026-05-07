# Feature Specification: F04 — Versioning + Money Type + Multi-devises

**Feature Branch**: `feat/F04-versioning-money-devises`
**Spec Directory**: `specs/022-versioning-money-devises/`
**Created**: 2026-05-06
**Status**: Draft
**Module(s) source(s)** : Module 0.5 (Versioning), Module 0.6 (Devises)
**Priorité** : P0 — bloquante pour la défense de candidatures soumises et la cohérence multi-devises
**Dépendances** : F01 (sources versionnées), F02 (multi-tenant)
**Estimation** : 2 sprints

**Input**: Versioning des entités catalogue (sources, indicators, referentials, criteria, formulas, thresholds, emission_factors, required_documents, simulation_factors, funds, intermediaries, fund_intermediaries) avec champs version/valid_from/valid_to/superseded_by. Snapshot immuable JSONB sur FundApplication à la transition draft→submitted. Type Money typed (amount Decimal + currency Char3) Pydantic v2 strict. Currency enum strict XOF/EUR/USD/GBP/JPY. Constante FCFA_EUR_PEG=655.957. Service exchangerate-api.com avec cap 1 fetch/jour. Table `exchange_rates`. Refactor des champs `*_xof` / `*_fcfa` en paires `(amount, currency)`. Endpoint `POST /api/applications/{id}/recompute-against-snapshot`. Composants Vue `MoneyDisplay` et `ReferentialBadge` avec dark mode.

---

## Clarifications

### Session 2026-05-06

- Q : Algorithme de bump version (semver-like) pour les entités catalogue : quand bumper major vs minor lors d'une édition ? → A : Bump minor automatique par défaut (ex 1.0 → 1.1) à chaque édition publiée ; bump major manuel via paramètre admin explicite `bump_major=true` (ex 1.0 → 2.0) lorsque la modification est structurellement incompatible (suppression d'indicateur, changement de calcul, refonte de seuil).
- Q : La devise PME (utilisée comme cible par défaut dans `<MoneyDisplay>` mode `pme`/`both`) doit-elle être stockée par compte (champ `accounts.preferred_currency`) ou rester implicite XOF ? → A : Hors scope F04. La devise PME est figée à `XOF` par défaut côté UI/composable. Le champ `accounts.preferred_currency` sera ajouté post-MVP via une feature dédiée (préférences utilisateur). FR-066 (`displayCurrencyMode`) suffit pour le MVP.
- Q : Conversion entre deux devises non peggées sans paire directe (ex EUR → JPY) : algorithme exact ? → A : Pivot via USD systématiquement (EUR → USD → JPY en deux étapes, en multipliant les taux). Si l'un des deux taux pivot est indisponible, lever une exception métier explicite « conversion path X→Y unavailable via USD pivot ». Pas d'interpolation, pas d'autres pivots (CHF/EUR seraient hors scope).
- Q : Mode de notification de l'échec de fetch exchangerate-api.com (FR-034 « log d'alerte admin ») ? → A : Pour le MVP, deux canaux : (1) log structuré niveau ERROR avec message normalisé `EXCHANGERATE_FETCH_FAILED` (jamais swallowed), (2) endpoint `GET /api/admin/currency/fetch-status` (auth admin) qui retourne `{last_success_at, last_failure_at, last_error_message, daily_quota_used}`. L'envoi email/notif est hors scope F04 (sera porté par F19 scheduler/notifs).
- Q : Format de versioning `version: VARCHAR(50)` — string libre semver-like ou semver strict 3 composantes (MAJOR.MINOR.PATCH) ? → A : Format `MAJOR.MINOR` à 2 composantes (ex « 1.0 », « 1.1 », « 2.0 »). Pas de PATCH pour le MVP (les hotfixes catalogue sont rares et déclencheront un bump minor). Validation regex CHECK constraint `^\d+\.\d+$` côté base.

---

## Contexte & motivation

**Module 0.5 — Versioning**

Le brainstorming exige que les référentiels et critères soient versionnés avec `version`, `valid_from`, `valid_to`, et que les candidatures stockent un snapshot JSON immuable au moment de la soumission. Sans cela, si la taxonomie GCF évolue après le dépôt d'un dossier, on perd la capacité de défendre la candidature face à un auditeur externe ou à un comité d'instruction du fonds.

**État actuel** :
- Aucun champ `version`, `valid_from`, `valid_to`, `superseded_by` sur les entités catalogue créées par F01 (`sources`, `indicators`, `criteria`, `formulas`, `thresholds`, `referentials`, `referential_indicators`, `emission_factors`, `required_documents`, `simulation_factors`) ni sur les entités historiques (`funds`, `intermediaries`, `fund_intermediaries`).
- `FundApplication` (`backend/app/models/application.py`) possède `sections`, `checklist`, `intermediary_prep`, `simulation` mais **aucun snapshot du référentiel ou de l'offre** au moment de la soumission. Si le catalogue change après `submitted_to_intermediary` ou `submitted_to_fund`, le score n'est plus reproductible.
- Aucun badge « Évalué selon Référentiel GCF v2.3 du 15/03/2026 » dans l'UI : la PME ignore la version du référentiel mobilisée pour son score.

**Module 0.6 — Devises**

Le brainstorming exige un type `Money = {amount, currency}` typé partout, avec peg fixe FCFA-EUR (655,957) et API exchangerate-api.com pour USD et autres devises non peggées.

**État actuel** :
- Aucun type `Money` composé. Toutes les colonnes financières sont des `BigInteger` / `Float` simples : `min_amount_xof`, `max_amount_xof`, `annual_revenue_xof`, `estimated_cost_xof`, `savings_fcfa`. La devise est encodée dans le **nom de la colonne**, ce qui interdit toute multi-devise.
- Constante peg 655,957 absente du code (`grep "655.957"` → 0).
- Aucune dépendance ni appel à exchangerate-api.com.
- Affichage UI mono-devise XOF / FCFA partout.
- Le tool `application_tools._simulate_financing` lit `fund.max_amount` / `fund.min_amount` (non typés Money) — ces attributs **n'existent pas** sur le modèle `Fund` qui a `max_amount_xof` / `min_amount_xof` : bug `AttributeError` silencieux à corriger en même temps.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Snapshot immuable de candidature pour audit (Priority: P1)

Une PME soumet une candidature à GCF via BOAD le 15 mars. GCF publie une nouvelle taxonomie le 30 mars. Lorsque la PME (ou un auditeur externe) consulte ou défend le dossier soumis, le score, les critères, les seuils et les documents requis affichés sont ceux de la version active au moment de la soumission, pas la nouvelle.

**Why this priority** : sans snapshot, toute évolution du catalogue rend la candidature indéfendable face au fonds ou à un auditeur. C'est l'invariant principal de la traçabilité ESG, bloquant pour le MVP de la finance verte sérieuse.

**Independent Test** : créer une candidature, soumettre (transition `draft → submitted_to_intermediary` ou `submitted_to_fund`), modifier ensuite un poids de critère ou un seuil dans le référentiel ou un montant dans le fonds source, puis appeler l'endpoint de recalcul contre le snapshot et vérifier que le score retourné est identique au score d'origine.

**Acceptance Scenarios** :

1. **Given** une candidature en `draft` rattachée à un référentiel ESG v1.2 et un fonds GCF, **When** la PME passe la candidature à `submitted_to_intermediary`, **Then** le système crée automatiquement un snapshot JSONB contenant le référentiel complet (indicateurs + poids + seuils + documents requis), l'offre (fonds + intermédiaire) et les scores calculés ; les champs `snapshot_at` et `snapshot_data` sont renseignés.
2. **Given** une candidature soumise avec son snapshot, **When** un admin met à jour le référentiel (nouvelle version, anciens seuils archivés), **Then** la consultation de la candidature affiche toujours les valeurs du snapshot.
3. **Given** une candidature soumise, **When** un auditeur appelle `POST /api/applications/{id}/recompute-against-snapshot`, **Then** la réponse contient le score recalculé selon les indicateurs/seuils du `snapshot_data` et il est strictement égal au score initial.
4. **Given** une candidature en `draft`, **When** la PME consulte son détail, **Then** `snapshot_at` et `snapshot_data` sont vides.

---

### User Story 2 — Type Money typé partout, peg FCFA-EUR fixe (Priority: P1)

La PME consulte un fonds GCF qui finance « 5 000 000 USD à 10 000 000 USD ». Elle souhaite voir simultanément l'équivalent en FCFA pour comparer avec son chiffre d'affaires local. Pour la conversion FCFA ↔ EUR, le peg fixe 655,957 (Banque de France / BCEAO) doit être utilisé sans appel API externe.

**Why this priority** : sans typage Money strict, le système ne peut afficher que XOF, ce qui exclut toute présentation crédible des fonds internationaux (GCF, FEM, BAD, IFC, banque mondiale) qui opèrent en USD ou EUR. La conformité Money typée bloque aussi tous les workflows simulation, recalcul de scoring, plan d'action, et expose à l'AttributeError silencieux dans le tool `simulate_financing`.

**Independent Test** : créer une instance `Money(amount=655_957, currency="XOF")`, appeler `convert(money, target="EUR")` sans accès réseau, vérifier que le résultat est `Money(amount=1_000.00, currency="EUR")` (avec arrondi 2 décimales). Idem avec une conversion USD → XOF qui doit lire la dernière entrée valide de la table `exchange_rates`.

**Acceptance Scenarios** :

1. **Given** un montant `Money(655_957, "XOF")`, **When** on appelle `convert(money, "EUR")`, **Then** le résultat est `Money(1_000.00, "EUR")` sans appel à exchangerate-api.com (peg fixe).
2. **Given** un montant `Money(1_000, "EUR")`, **When** on appelle `convert(money, "XOF")`, **Then** le résultat est `Money(655_957.00, "XOF")` (peg inverse).
3. **Given** une PME consultant un fonds GCF avec `min_amount=5_000_000 USD` et un mode d'affichage `both`, **When** la card du fonds est rendue, **Then** elle affiche « 5 000 000 USD (≈ 3 000 000 000 FCFA) » avec symbole de devise explicite et tooltip d'explication.
4. **Given** un fonds avec `currency="XOF"` et l'utilisateur en mode d'affichage `pme` (devise PME = XOF), **When** la card est rendue, **Then** seul le montant natif en FCFA est affiché (pas d'équivalent redondant).
5. **Given** une devise hors enum (ex : « ABC »), **When** on essaie d'instancier `Money(100, "ABC")`, **Then** Pydantic lève une `ValidationError` et la valeur n'entre jamais en BDD.
6. **Given** le tool LangChain `simulate_financing` invoqué pour un fonds GCF, **When** le tool s'exécute, **Then** il retourne des objets `Money` typés (et non plus `AttributeError` sur `fund.max_amount`).

---

### User Story 3 — Versioning du catalogue avec chaîne `superseded_by` (Priority: P2)

L'admin édite un fonds publié pour mettre à jour son montant maximum. Le système crée une nouvelle version : l'ancienne reçoit `valid_to = today` et `superseded_by = new.id`, la nouvelle est insérée avec `version` incrémenté et `valid_from = today + 1`. Les candidatures et conversations en cours conservent l'ancienne version via leur snapshot ou leur référence directe.

**Why this priority** : permet l'évolution du catalogue (changement de seuils, ajout d'indicateurs, mise à jour de fonds) sans rompre la cohérence des candidatures historiques. Indispensable pour l'opérabilité long terme du catalogue.

**Independent Test** : créer un fonds publié, l'éditer via l'API admin, vérifier que (a) une nouvelle ligne est insérée avec version incrémentée et `valid_from` correct, (b) l'ancienne reçoit `valid_to = today` et `superseded_by = new.id`, (c) une chaîne A → B → A est rejetée par le trigger anti-cycle PostgreSQL.

**Acceptance Scenarios** :

1. **Given** un fonds publié `(version="1.0", valid_from="2026-01-01", valid_to=NULL)`, **When** l'admin met à jour son montant max, **Then** la base contient deux lignes : ancienne `(version="1.0", valid_to=today, superseded_by=new.id)` et nouvelle `(version="1.1", valid_from=today+1, valid_to=NULL, superseded_by=NULL)`.
2. **Given** une chaîne `A → B`, **When** un admin tente de définir `A.superseded_by = B` alors que `B.superseded_by = A` (cycle), **Then** le trigger PostgreSQL `prevent_supersede_cycle_trg` lève une exception et la transaction est annulée.
3. **Given** un référentiel ESG modifié après qu'une PME ait reçu un score, **When** la PME consulte son score, **Then** un badge `<ReferentialBadge>` affiche « Évalué selon Référentiel ESG Mefali v1.2 du 10/02/2026 » avec lien cliquable vers la version archivée.
4. **Given** un objet en `draft` (jamais publié), **When** l'admin l'édite, **Then** la même ligne est mise à jour en place (pas de nouvelle version créée).

---

### User Story 4 — Conversion USD via table `exchange_rates` avec fallback (Priority: P2)

Le service de conversion utilise la table `exchange_rates` pour les paires non peggées (USD↔XOF, USD↔EUR, GBP↔XOF, JPY↔XOF, etc.). Lorsqu'aucun taux n'existe pour la date demandée, le système prend le taux le plus récent disponible (fallback ascendant). Le cron quotidien fetche les taux via exchangerate-api.com en respectant le cap dur 1 fetch/jour.

**Why this priority** : indispensable pour afficher les montants USD des fonds internationaux et calculer les marges de change dans le simulateur. Le cap 1/jour préserve le tier gratuit (1500 req/mois).

**Independent Test** : insérer manuellement un taux USD→XOF pour la date du 2026-01-15, demander une conversion à la date du 2026-02-01 sans taux pour cette date, vérifier que le service utilise le taux du 2026-01-15. Vérifier également que deux tentatives de fetch dans la même journée ne déclenchent qu'un seul appel HTTP.

**Acceptance Scenarios** :

1. **Given** une entrée dans `exchange_rates` `(USD, XOF, 615.20, 2026-04-15)`, **When** on appelle `convert(Money(1_000, "USD"), "XOF", date=2026-04-15)`, **Then** le résultat est `Money(615_200.00, "XOF")`.
2. **Given** aucune entrée dans `exchange_rates` pour le 2026-05-01, mais une pour le 2026-04-15, **When** on appelle `convert(Money(1_000, "USD"), "XOF", date=2026-05-01)`, **Then** le service utilise le taux du 2026-04-15 (fallback ascendant) et retourne le résultat.
3. **Given** la table `exchange_rates` vide, **When** on appelle une conversion non peggée, **Then** le service lève une exception métier explicite « no exchange rate available for pair X/Y », et un fetch one-shot est déclenché en arrière-plan.
4. **Given** un cron qui s'exécute deux fois dans la journée, **When** le second cron tourne, **Then** aucun appel HTTP n'est émis (un cap interne 1/jour bloque le fetch).
5. **Given** un appel HTTP exchangerate-api.com en échec (timeout, 503), **When** le cron termine, **Then** les anciens taux restent en place, un log d'alerte est émis et le statut est consultable via une route admin.

---

### User Story 5 — Composants UI MoneyDisplay et ReferentialBadge (Priority: P2)

L'utilisateur PME voit chaque montant via le composant `<MoneyDisplay>` qui affiche le natif et l'équivalent dans sa devise PME selon `displayCurrencyMode` (`native` | `pme` | `both`). Chaque score persisté affiche un `<ReferentialBadge>` cliquable indiquant la version du référentiel mobilisée.

**Why this priority** : la lisibilité et la traçabilité côté UI sont des prérequis fonctionnels du MVP. Sans ces composants, on ne peut pas démontrer la conformité du système devant un auditeur.

**Independent Test** : monter un composant `<MoneyDisplay :money="{amount: 1000000, currency: 'XOF'}" :show-pme-currency="true" />` avec mode `both`, vérifier qu'il rend « 1 000 000 FCFA (≈ 1 524 €) ». Cliquer sur `<ReferentialBadge>` ouvre la modale détaillant la version. Tester la compatibilité dark mode.

**Acceptance Scenarios** :

1. **Given** un composant `<MoneyDisplay>` avec `money={amount: 5_000_000, currency: "USD"}` et `displayCurrencyMode="both"` et devise PME = XOF, **When** rendu, **Then** affiche « 5 000 000 USD (≈ 3 000 000 000 FCFA) » avec espace insécable comme séparateur de milliers et symbole `$` ou `USD`.
2. **Given** un composant `<MoneyDisplay>` avec `money={amount: 1000, currency: "XOF"}` et devise PME = XOF (mêmes devises), **When** rendu, **Then** seul le natif « 1 000 FCFA » est affiché, sans équivalent redondant.
3. **Given** un score ESG persisté avec `referential_id` et `referential_version_at`, **When** le `<ReferentialBadge>` est rendu, **Then** il affiche « Évalué selon Référentiel ESG Mefali v1.2 du 10/02/2026 » et est cliquable.
4. **Given** un clic sur `<ReferentialBadge>`, **When** l'utilisateur clique, **Then** une modale `<SourceModal>` s'ouvre avec les détails de la version (publisher, version, date_publi, lien URL).
5. **Given** le mode dark activé, **When** `<MoneyDisplay>` et `<ReferentialBadge>` sont rendus, **Then** ils utilisent les variantes `dark:` Tailwind (`dark:bg-dark-card`, `dark:text-surface-dark-text`, etc.) et restent lisibles.

---

### Edge Cases

- **Snapshot manquant** : que se passe-t-il si on appelle `recompute-against-snapshot` sur une candidature en `draft` (sans snapshot) ? → réponse HTTP 409 « Application must be submitted before recompute ».
- **Snapshot trop volumineux** : si le snapshot dépasse 100 KB, le système log un warning sans rejeter (post-MVP : compression gzip applicative).
- **Devise PME non détectable** : si `account.preferred_currency` est nul, devise PME = XOF par défaut.
- **Conversion entre deux devises non peggées sans paire directe** : ex EUR → JPY → algorithme USD pivot systématique (FR-023a) ; si l'un des deux taux est manquant, exception métier explicite.
- **Édition d'un objet `draft`** : pas de versioning (mise à jour en place).
- **Cycle dans `superseded_by`** : trigger PostgreSQL anti-cycle bloque l'INSERT/UPDATE.
- **Migration legacy** : services qui n'ont pas encore migré vers Money typé doivent continuer à fonctionner pendant la phase 1 (anciennes colonnes `*_xof` conservées). Phase 2 (drop) dans une migration séparée hors-scope F04.
- **Tier gratuit exchangerate-api dépassé (HTTP 429)** : log d'alerte admin, conservation des anciens taux, retry à J+1.
- **Snapshot d'une candidature dont le référentiel d'origine est supprimé** : le snapshot reste valide (auto-portant), pas de FK qui casse.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Versioning catalogue

- **FR-001** : Le système MUST ajouter quatre colonnes `version: VARCHAR(50) NOT NULL DEFAULT '1.0'`, `valid_from: DATE NOT NULL DEFAULT CURRENT_DATE`, `valid_to: DATE NULL`, `superseded_by: UUID NULL FK self.id` sur les tables `sources`, `indicators`, `criteria`, `formulas`, `thresholds`, `referentials`, `referential_indicators`, `emission_factors`, `required_documents`, `simulation_factors`, `funds`, `intermediaries`, `fund_intermediaries`.
- **FR-002** : Lorsqu'un admin édite une entité « publiée » (`publication_status='published'` lorsque la table le supporte, sinon `valid_to IS NULL`), le système MUST créer une nouvelle ligne avec `version` incrémenté au format `MAJOR.MINOR` (`bump minor` par défaut, ex 1.0 → 1.1 ; `bump major` activable via paramètre admin explicite `bump_major=true` lors d'une modification structurellement incompatible : suppression d'indicateur, refonte de seuil, changement de calcul), `valid_from = today + 1`, `valid_to = NULL`, `superseded_by = NULL` ; et MUST mettre à jour l'ancienne ligne avec `valid_to = today` et `superseded_by = new.id`. Le champ `version` MUST respecter la regex `^\d+\.\d+$` (validée par CHECK constraint base).
- **FR-003** : Lorsqu'un admin édite une entité en `draft` ou non publiée (`valid_from > today` non encore active), le système MUST mettre à jour la même ligne en place sans créer de nouvelle version.
- **FR-004** : Le système MUST empêcher tout cycle dans `superseded_by` via un trigger PostgreSQL `prevent_supersede_cycle_trg` exécuté avant INSERT/UPDATE sur chaque table concernée, qui parcourt la chaîne et lève une exception si l'identifiant courant est rencontré.
- **FR-005** : Le système MUST exposer des index sur `valid_to`, `superseded_by` pour chaque table catalogue afin que les requêtes de version active (`WHERE valid_to IS NULL`) restent performantes.
- **FR-006** : Aucune entité versionnée ne MUST permettre la suppression physique (soft delete via `valid_to`).

#### Snapshot candidature

- **FR-010** : Le système MUST ajouter deux colonnes `snapshot_at: TIMESTAMPTZ NULL` et `snapshot_data: JSONB NULL` sur la table `fund_applications`.
- **FR-011** : Lorsqu'une candidature transitionne vers `submitted_to_intermediary` ou `submitted_to_fund`, le système MUST capturer dans `snapshot_data` un JSON deepcopy contenant : (a) `referential` complet (id, version, valid_from, indicateurs avec poids et seuils, documents requis), (b) `fund` (tous les champs publics), (c) `intermediary` si présent, (d) `offer` (couple fonds+intermédiaire), (e) `scores` calculés (avec leurs `source_id` cités), (f) `documents_requis` à la version active. La valeur `snapshot_at` MUST être renseignée à `now()`.
- **FR-012** : Le snapshot MUST être immuable après création : aucun service métier ne MUST autoriser sa modification a posteriori (lecture seule applicative). Toute tentative de mise à jour MUST être rejetée par le service `applications/service.py`.
- **FR-013** : Le système MUST exposer l'endpoint `POST /api/applications/{id}/recompute-against-snapshot` qui charge les indicateurs et seuils depuis `snapshot_data` (et non depuis la version courante du catalogue), recalcule le score et retourne le résultat. La cohérence MUST être stricte : le score recalculé MUST être strictement égal au score d'origine pour les mêmes données d'entrée.
- **FR-014** : Si la candidature n'est pas encore soumise (`snapshot_at IS NULL`), l'endpoint `recompute-against-snapshot` MUST répondre HTTP 409 avec un message « Application must be submitted before recompute ».

#### Type Money

- **FR-020** : Le système MUST définir un type Pydantic v2 strict `Money` avec deux attributs : `amount: Decimal` (deux décimales, ≥ 0) et `currency: Currency` (`Literal["XOF", "EUR", "USD", "GBP", "JPY"]`).
- **FR-021** : Le système MUST définir la constante `FCFA_EUR_PEG: Decimal = Decimal("655.957")` dans `backend/app/core/constants.py`.
- **FR-022** : Le service `currency_service.convert(money, target_currency, date=None)` MUST utiliser le peg fixe pour les paires `(XOF, EUR)` et `(EUR, XOF)` sans appeler aucune API externe.
- **FR-023** : Pour toute autre paire de devises, le service MUST consulter la table `exchange_rates` et appliquer un fallback ascendant : taux à la date demandée, sinon taux le plus récent < date demandée. Si aucun taux n'existe, MUST lever une exception métier explicite et déclencher un fetch one-shot en arrière-plan.
- **FR-023a** : Pour deux devises non peggées sans paire directe en table (ex EUR → JPY), le service MUST utiliser USD comme pivot systématique (étape 1 : EUR → USD ; étape 2 : USD → JPY ; produit des taux). Si l'un des deux taux pivot est indisponible, MUST lever une exception métier explicite « conversion path X→Y unavailable via USD pivot ». Pas d'autres pivots ni d'interpolation.
- **FR-024** : Le service MUST refuser à l'INSERT toute valeur `currency` hors enum (validation Pydantic + CHECK contraint base).
- **FR-025** : Tous les schémas Pydantic API exposant des montants MUST utiliser le type `Money` (jamais d'`int` ou `float` brut représentant un montant).

#### Table exchange_rates et cron

- **FR-030** : Le système MUST créer la table `exchange_rates` avec les colonnes : `id UUID PK`, `base_currency CHAR(3)`, `quote_currency CHAR(3)`, `rate NUMERIC(20, 10)`, `as_of DATE`, `source VARCHAR(100)` (ex : « exchangerate-api.com », « ECB », « BCEAO »), `fetched_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ`. Une contrainte UNIQUE sur `(base_currency, quote_currency, as_of)` MUST être présente.
- **FR-031** : Un index `(base_currency, quote_currency, as_of DESC)` MUST permettre les recherches avec fallback ascendant.
- **FR-032** : Le script `scripts/fetch_exchange_rates.py` MUST appeler exchangerate-api.com (free tier) en respectant un cap dur 1 appel HTTP global / jour (vérification via `MAX(fetched_at)` < 24h avant tout appel). Un seul appel HTTP retourne toutes les paires USD→XYZ ; les paires inverses (XYZ→USD) sont dérivées et insérées sans appel supplémentaire.
- **FR-033** : Au démarrage de l'application, si la table `exchange_rates` est vide ou si le `MAX(fetched_at) > 7 jours`, un fetch one-shot MUST être déclenché en arrière-plan (best effort).
- **FR-034** : Si la requête HTTP échoue (timeout, 4xx, 5xx), le système MUST conserver les anciens taux et émettre un log structuré niveau ERROR avec le message normalisé `EXCHANGERATE_FETCH_FAILED` (jamais swallowed). L'envoi d'email/notification est hors scope F04 (sera porté par F19 scheduler/notifications).
- **FR-034a** : Le système MUST exposer `GET /api/admin/currency/fetch-status` (auth admin via `get_current_admin`) qui retourne `{last_success_at, last_failure_at, last_error_message, daily_quota_used, daily_quota_max}` afin de permettre à l'admin de surveiller l'état du fetch.
- **FR-035** : Le seed initial MUST inclure au minimum les paires `USD↔XOF`, `USD↔EUR`, `GBP↔XOF`, `JPY↔XOF` à une date de référence connue (ex : 2026-04-15, valeurs documentées) pour les tests reproductibles.

#### API Currency

- **FR-040** : Le système MUST exposer `GET /api/currency/rates/latest` qui retourne la liste des taux les plus récents pour toutes les paires connues, accessible sans authentification (lecture publique).
- **FR-041** : Le système MUST exposer `POST /api/currency/convert` qui prend `{amount, source_currency, target_currency, date?}` et retourne `Money` après conversion. Réponse 422 si validation Pydantic échoue, 404 si aucun taux disponible.

#### Tools LangChain

- **FR-050** : Le tool `simulate_financing` MUST retourner des objets `Money` typés et MUST accéder aux montants des fonds via les nouveaux champs `min_amount` / `max_amount` (paire amount+currency), supprimant le bug AttributeError sur `fund.max_amount`.
- **FR-051** : Pour le MVP F04, seul `simulate_financing` est garanti Money-typé (FR-050). Les autres tools manipulant des montants (`update_company_profile`, `record_action_item_cost`, `compute_carbon_savings`, etc.) seront migrés progressivement dans des features ultérieures (post-MVP). Un audit `grep` sur les tools restants devra être effectué en Polish (T708) pour documenter la dette technique restante.

#### Frontend

- **FR-060** : Le système MUST fournir un composant Vue `<MoneyDisplay>` dans `frontend/app/components/ui/MoneyDisplay.vue` acceptant les props `money: Money`, `showPmeCurrency?: boolean` (défaut true) et lisant la préférence `displayCurrencyMode` du store `ui` (`'native' | 'pme' | 'both'`, défaut `'both'`).
- **FR-061** : `<MoneyDisplay>` MUST afficher le symbole de devise explicite (« FCFA », « € », « $ », « £ », « ¥ »), un séparateur de milliers ` ` (espace insécable) et un tooltip d'explication en français.
- **FR-062** : `<MoneyDisplay>` MUST omettre l'équivalent quand la devise native est la même que la devise PME.
- **FR-063** : Le système MUST fournir un composant Vue `<ReferentialBadge>` dans `frontend/app/components/ui/ReferentialBadge.vue` acceptant les props `referential: { id, name, version, valid_from }` et un emit pour ouvrir une modale `<SourceModal>` (réutilisée depuis F01).
- **FR-064** : `<ReferentialBadge>` MUST être rendu sur chaque score persisté affiché côté UI (ESG, carbone, credit, score d'éligibilité offre).
- **FR-065** : Le composable `useCurrency` (`frontend/app/composables/useCurrency.ts`) MUST exposer `format(money)`, `convert(money, target)`, `getRate(base, quote)` en s'appuyant sur l'API backend.
- **FR-066** : Le store Pinia `ui` MUST exposer un nouveau champ `displayCurrencyMode: 'native' | 'pme' | 'both'` persistant dans `localStorage` avec défaut `'both'`.
- **FR-067** : Tous les composants existants utilisant `formatXof()` ou `${amount} XOF` (`ScoreCard`, `FinancingCard`, pages `/financing`, `/dashboard`, `/action-plan`, `/applications/[id]`) MUST migrer vers `<MoneyDisplay>`.
- **FR-068** : Tous les nouveaux composants MUST respecter le mode dark via les variantes Tailwind (`dark:bg-dark-card`, `dark:text-surface-dark-text`, etc.).

#### Migration BDD (phase 1, en parallèle de l'existant)

- **FR-070** : La migration Alembic 022 MUST ajouter pour chaque champ legacy `*_xof` ou `*_fcfa` une paire `<field>_amount: NUMERIC(20,2)` + `<field>_currency: CHAR(3)` sans dropper les anciennes colonnes. Champs concernés : `funds.min_amount_xof`, `funds.max_amount_xof`, `company_profiles.annual_revenue_xof`, `action_items.estimated_cost_xof`, `carbon_assessments.savings_fcfa` (si présent ; sinon hors scope), `applications.intermediary_fees_xof` (dans `simulation` JSON, refactor applicatif uniquement).
- **FR-071** : Un backfill SQL MUST initialiser `<field>_amount = <field>_xof` et `<field>_currency = 'XOF'` pour toutes les lignes existantes.
- **FR-072** : La phase 2 (drop des anciennes colonnes `*_xof`) est HORS-SCOPE F04 (migration séparée à planifier après refactor exhaustif des services consommateurs).
- **FR-073** : La migration MUST avoir `revision = '022_money_and_versioning'` et `down_revision = '021_create_audit_log'` si F03 (`021`) est mergé avant F04, sinon `down_revision = '020_sources'`. La valeur exacte sera fixée au moment de l'implémentation (Phase B).

#### Multi-tenant et compatibilité F02

- **FR-080** : Toute nouvelle table (`exchange_rates`) MUST disposer d'un mécanisme d'isolation cohérent. La table `exchange_rates` étant un référentiel public partagé entre tous les comptes, elle MUST être lecture publique sans `account_id` (référentiel global, équivalent aux sources verified F01).
- **FR-081** : Le snapshot `snapshot_data` étant déjà rattaché à une `fund_application` qui porte `account_id`, l'isolation multi-tenant est héritée. Aucune action supplémentaire requise.
- **FR-082** : Toute mutation du catalogue (versioning) MUST être réservée aux utilisateurs `role=ADMIN` via les guardrails F02 (`get_current_admin`).

#### Compatibilité F01 (sourçage)

- **FR-090** : Toute nouvelle ligne créée par le versioning (nouvelle version d'une entité catalogue) MUST conserver les références `source_id` ou les recopier de l'ancienne version, garantissant la traçabilité F01.
- **FR-091** : Le snapshot `snapshot_data` MUST inclure les `source_id` mobilisés dans le calcul des scores (pour reproductibilité des références).

### Key Entities

- **ExchangeRate** : taux de change pour une paire de devises à une date donnée. Attributs : `id`, `base_currency`, `quote_currency`, `rate`, `as_of`, `source`, `fetched_at`. Référentiel public global (sans `account_id`).
- **CatalogVersion** (champs ajoutés à 13 tables) : `version`, `valid_from`, `valid_to`, `superseded_by`. Définit la temporalité d'une entité catalogue.
- **ApplicationSnapshot** (champs ajoutés à `fund_applications`) : `snapshot_at`, `snapshot_data` (JSONB autoportant). Capture immuable au moment de la soumission.
- **Money** (type Pydantic, pas de table dédiée) : `amount: Decimal(20,2)`, `currency: Currency` (enum `XOF, EUR, USD, GBP, JPY`).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des candidatures soumises (`status` ∈ {`submitted_to_intermediary`, `submitted_to_fund`}) ont un `snapshot_at` non NULL et un `snapshot_data` non vide.
- **SC-002** : Le recalcul d'une candidature contre son snapshot retourne un score strictement identique au score d'origine, mesuré sur 100 % des cas testés sur le golden set ESG (incluant les cas après modification du référentiel).
- **SC-003** : 100 % des champs financiers anciennement `*_xof` ou `*_fcfa` disposent désormais d'une paire `<field>_amount` + `<field>_currency` correctement initialisée par le backfill (`amount = ancien_xof`, `currency = 'XOF'`).
- **SC-004** : La conversion FCFA ↔ EUR ne génère 0 appel HTTP exchangerate-api.com (utilise toujours le peg fixe 655,957).
- **SC-005** : Le cron `fetch_exchange_rates` ne déclenche JAMAIS plus d'un appel HTTP par paire et par jour, contrôlable via `MAX(fetched_at)` < 24h.
- **SC-006** : Couverture de tests unitaires + intégration ≥ 80 % sur les nouveaux modules (`app.core.money`, `app.modules.currency`, `app.models.exchange_rate`, services de versioning, snapshot creation, recompute endpoint).
- **SC-007** : Le composant `<MoneyDisplay>` rend les montants en moins de 50 ms (mesure performance UI sur Vitest).
- **SC-008** : 100 % des scores affichés en UI portent un `<ReferentialBadge>` cliquable.
- **SC-009** : Aucune AttributeError sur `fund.max_amount` ou `fund.min_amount` n'apparaît dans les logs après déploiement (le tool `simulate_financing` retourne des Money typés).
- **SC-010** : Tous les nouveaux composants Vue passent l'audit dark mode (test visuel manuel + assertion DOM sur classe `dark` parent).

---

## Assumptions

- **A-1** : F01 (catalogue de sources) est mergé avant F04 ; les modèles `Source`, `Indicator`, `Criterion`, `Formula`, `Threshold`, `Referential`, `EmissionFactor`, `RequiredDocument`, `SimulationFactor` existent et sont importables.
- **A-2** : F02 (multi-tenant + RLS) est mergé ; le décorateur `get_current_admin` existe et la fonction `set_rls_context` est invoquée par `get_current_user`.
- **A-3** : F03 (audit log) peut être mergé avant ou après F04. Si avant, `down_revision = '021_create_audit_log'` ; sinon `down_revision = '020_sources'`. La valeur exacte est fixée au moment de la Phase B (implémentation).
- **A-4** : Devise PME par défaut = XOF (zone UEMOA/CEDEAO). Le champ `accounts.preferred_currency` est HORS-SCOPE F04 (post-MVP, feature dédiée préférences utilisateur). La devise PME est hardcodée à `XOF` dans le composable `useCurrency` côté frontend pour le MVP. Le mode d'affichage `displayCurrencyMode` (FR-066) suffit pour gérer la préférence locale via `localStorage`.
- **A-5** : Les fonds, indicateurs et seeds existants démarrent avec `version = '1.0'`, `valid_from = '2026-01-01'`, `valid_to = NULL`, `superseded_by = NULL`.
- **A-6** : Le service exchangerate-api.com (free tier 1500 req/mois) est disponible et stable. Une clé API est gérée via env var `EXCHANGERATE_API_KEY` (vide accepté pour mode dégradé / dev).
- **A-7** : La compression gzip applicative du `snapshot_data` est hors-scope F04 (post-MVP, dépend du benchmark de taille).
- **A-8** : Hedging FX automatique, devises CEMAC, MAD, NGN, EGP, ZAR, conversion historique avec interpolation, et workflow editorial pré-publication sont hors-scope F04 (post-MVP).
- **A-9** : Le cron quotidien sera intégré au scheduler F19 (`apscheduler` ou cron Docker) ; pour MVP, l'invocation manuelle via CLI `python -m app.scripts.fetch_exchange_rates` suffit.
- **A-10** : La table `templates_dossier` (créée par F15) et `skills` (créée par F23) ne sont PAS concernées par cette migration : leur versioning sera ajouté dans leurs propres features.

---

## Dépendances et risques

### Dépendances

- F01 (`020_sources`) — modèles catalogue à étendre.
- F02 (`019_multitenant`) — RLS, `get_current_admin`, `account_id`.
- F03 (`021_create_audit_log`) — facultatif au moment de l'implémentation, mais pris en compte dans `down_revision`.

### Risques & garde-fous

- **R-1** (Migration legacy casse les services) : phase 2 (drop) hors-scope, seules les nouvelles colonnes sont ajoutées en parallèle. Backfill systématique. → **Garde-fou** : tests d'intégration vérifient que les services historiques fonctionnent encore avec les anciennes colonnes pendant la cohabitation.
- **R-2** (exchangerate-api dépassement quota) : **Garde-fou** : cap dur 1 fetch/jour/paire vérifié en BDD via `MAX(fetched_at)`, mode best effort.
- **R-3** (snapshot trop volumineux) : **Garde-fou** : log d'alerte si > 100 KB ; compression gzip post-MVP.
- **R-4** (cycle dans `superseded_by`) : **Garde-fou** : trigger PostgreSQL `prevent_supersede_cycle_trg` levé avant INSERT/UPDATE.
- **R-5** (devise hors enum injectée) : **Garde-fou** : enum strict Pydantic + CHECK constraint base + tests négatifs.
- **R-6** (UI confusion native vs PME) : **Garde-fou** : symbole de devise toujours explicite, tooltip d'explication, omission de l'équivalent quand redondant.
- **R-7** (recalcul snapshot incohérent) : **Garde-fou** : test de fidélité bit-à-bit sur le golden set ESG (snapshot → recalcul → assertion `score_recalculé == score_initial`).
