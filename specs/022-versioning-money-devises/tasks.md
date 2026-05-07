---
description: "Task list for F04 Versioning + Money Type + Multi-devises"
---

# Tasks: F04 — Versioning + Money Type + Multi-devises

**Input** : Design documents from `/specs/022-versioning-money-devises/`
**Prerequisites** : [plan.md](./plan.md) ✅, [spec.md](./spec.md) ✅, [research.md](./research.md) ✅, [data-model.md](./data-model.md) ✅, [contracts/](./contracts/) ✅, [quickstart.md](./quickstart.md) ✅

**Tests** : OBLIGATOIRES (constitution principle IV — Test-First NON-NEGOTIABLE). Tous les tests sont écrits AVANT l'implémentation.

**Organization** : Tasks grouped by user story (US1 à US5) pour permettre l'implémentation et la validation indépendantes.

---

## Format: `[ID] [P?] [Story?] Description`

- **[P]** : Parallélisable (fichier différent, aucune dépendance non résolue)
- **[Story]** : Tag user story (US1 à US5) ou aucun (Setup/Foundational/Polish)
- Chemins absolus à partir de la racine `/Users/mac/Documents/projets/2025/esg_mefali_v3/`

---

## Phase 1 : Setup (infrastructure partagée)

**Purpose** : initialisation de la branche, dépendances, structure dossiers.

- [ ] T001 Vérifier que la branche `feat/F04-versioning-money-devises` est checkée out, à jour avec `main`, et que `backend/venv/` est activé.
- [ ] T002 [P] Ajouter `httpx>=0.27.0` à `backend/requirements.txt` si absent (utilisé pour exchangerate-api).
- [ ] T003 [P] Créer la structure dossiers `backend/app/modules/currency/` (vide avec `__init__.py`) et `backend/app/modules/versioning/` (vide avec `__init__.py`).
- [ ] T004 [P] Créer la structure dossiers `backend/tests/test_core/`, `backend/tests/test_currency/`, `backend/tests/test_versioning/`, `backend/tests/test_models/` avec `__init__.py` vide.
- [ ] T005 [P] Créer le dossier `backend/app/scripts/` si absent (avec `__init__.py`).
- [ ] T006 Vérifier que les variables d'env `EXCHANGERATE_API_KEY`, `EXCHANGERATE_API_BASE_URL`, `CURRENCY_FETCH_DAILY_QUOTA` sont déclarées dans `backend/app/core/config.py` (ZONE INTERDITE — modifier uniquement après confirmation qu'aucune autre feature n'écrit en parallèle).
- [ ] T007 Lire l'état des migrations Alembic actuelles (`cd backend && source venv/bin/activate && alembic heads`) pour fixer la valeur de `down_revision` de la migration 022 : `021_create_audit_log` si F03 mergé, sinon `020_sources`.

---

## Phase 2 : Foundational (prérequis bloquants)

**Purpose** : créer les fondations Money + ExchangeRate + versioning service AVANT toute user story. Aucune US ne peut démarrer tant que cette phase n'est pas complète.

⚠️ CRITICAL : aucun travail US ne commence avant la fin de cette phase.

### Tests fondations (RED first)

- [ ] T010 [P] Écrire `backend/tests/test_core/test_money.py` : test type `Money` (champs valides, champs invalides → ValidationError, immutabilité `frozen=True`, `model_dump(mode='json')` produit string Decimal, factory `Money.from_columns(amount, currency)`, refus devise hors enum, refus amount négatif, refus amount avec > 2 décimales). 8 cas minimum.
- [ ] T011 [P] Écrire `backend/tests/test_core/test_constants.py` : test `FCFA_EUR_PEG == Decimal("655.957")`, type `Decimal`, immuabilité.
- [ ] T012 [P] Écrire `backend/tests/test_models/test_exchange_rate.py` : test création `ExchangeRate`, contrainte unique `(base, quote, as_of)`, CHECK enum currencies, CHECK `rate > 0`, index lookup.
- [ ] T013 [P] Écrire `backend/tests/test_versioning/test_supersede.py` : test `bump_version("1.0")=="1.1"`, `bump_version("1.0", force_major=True)=="2.0"`, `bump_version("invalid")` lève `VersioningError`. Test `supersede(old, new)` met à jour `valid_to`, `superseded_by` ; refuse les cycles applicatifs.
- [ ] T014 [P] Écrire `backend/tests/test_versioning/test_cycle_trigger.py` : test trigger PostgreSQL anti-cycle (skip sur SQLite, scénario A→B→A doit lever `IntegrityError`). Test fallback applicatif sur SQLite.

### Implémentation fondations (GREEN)

- [ ] T020 [P] Implémenter `backend/app/core/money.py` : type Pydantic v2 `Money(amount: Decimal, currency: Currency)`, alias `Currency = Literal["XOF", "EUR", "USD", "GBP", "JPY"]`, `frozen=True`, `strict=True`, `decimal_places=2`, classmethod `from_columns(amount, currency)`. Faire passer T010.
- [ ] T021 [P] Compléter `backend/app/core/constants.py` : ajouter `FCFA_EUR_PEG: Decimal = Decimal("655.957")` (sans casser les constantes existantes). Faire passer T011.
- [ ] T022 [P] Implémenter `backend/app/models/exchange_rate.py` : modèle SQLAlchemy `ExchangeRate` (UUIDMixin + colonnes décrites en data-model.md), avec CHECK constraints, index lookup. Inscrire dans `backend/app/models/__init__.py`. Faire passer T012.
- [ ] T023 Implémenter `backend/app/modules/versioning/exceptions.py` : `VersioningError`, `SupersedeCycleError` (héritent de `Exception`).
- [ ] T024 Implémenter `backend/app/modules/versioning/service.py` : fonctions `bump_version(current, force_major=False)`, `supersede(session, model, old_id, new_id)`, `is_published(entity)`, `_check_no_cycle_applicative(session, model, new_id, candidate_supersede_id)`. Faire passer T013, T014.

### Migration 022 (à isoler en sérialisation Alembic)

- [ ] T030 Écrire `backend/tests/test_migrations/test_022_money_and_versioning.py` : test up/down/up sur SQLite et PostgreSQL ; vérifier création table `exchange_rates`, ajout 4 colonnes versioning sur 13 tables, ajout snapshot fields sur `fund_applications`, ajout paires Money sur 5 tables, backfill XOF, idempotence backfill.
- [ ] T031 Écrire `backend/alembic/versions/022_money_and_versioning.py` : migration complète. `revision = '022_money_and_versioning'`, `down_revision = ...` (résolu en T007). Inclut :
  - `CREATE TABLE exchange_rates` + index + CHECK
  - 13 × `ALTER TABLE` pour ajouter `version`, `valid_from`, `valid_to`, `superseded_by` + index
  - `CREATE FUNCTION prevent_supersede_cycle()` + 13 triggers (PostgreSQL only via `if op.get_bind().dialect.name == 'postgresql'`)
  - 5 × `ALTER TABLE` pour ajouter paires Money (`<field>_amount`, `<field>_currency`) + CHECK
  - `ALTER TABLE fund_applications` ajouter `snapshot_at`, `snapshot_data`
  - Backfill SQL : `UPDATE ... SET <field>_amount = <field>_xof, <field>_currency = 'XOF' WHERE <field>_xof IS NOT NULL`
  - Seed initial 8 lignes `exchange_rates` (USD↔{XOF,EUR,GBP,JPY} + inverses) — voir data-model.md §1
  - `downgrade()` symétrique : drop columns, drop table, drop function/triggers
- [ ] T032 Vérifier la migration : `cd backend && source venv/bin/activate && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` sans erreur. Faire passer T030.

### Modèles SQLAlchemy mis à jour (versioning + Money columns)

- [ ] T040 [P] Étendre `backend/app/models/source.py` : ajouter `version`, `valid_from`, `valid_to`, `superseded_by` (UUID FK self).
- [ ] T041 [P] Étendre `backend/app/models/indicator.py` : idem (et entités liées).
- [ ] T042 [P] Étendre `backend/app/models/referential.py` : idem (`Referential`, `ReferentialIndicator`, `Criterion`, `Formula`, `Threshold` — toutes les classes du fichier).
- [ ] T043 [P] Étendre `backend/app/models/emission_factor.py` : idem.
- [ ] T044 [P] Étendre `backend/app/models/required_document.py` : idem.
- [ ] T045 [P] Étendre `backend/app/models/simulation_factor.py` : idem.
- [ ] T046 [P] Étendre `backend/app/models/financing.py` : `Fund`, `Intermediary`, `FundIntermediary` reçoivent les 4 colonnes versioning. `Fund` reçoit `min_amount: Numeric(20,2)`, `min_amount_currency: String(3)`, `max_amount`, `max_amount_currency` + property `min_amount_money`, `max_amount_money` (cf. R-08, R-11).
- [ ] T047 [P] Étendre `backend/app/models/company.py` : `CompanyProfile` reçoit `annual_revenue_amount`, `annual_revenue_currency` + property `annual_revenue_money`.
- [ ] T048 [P] Étendre `backend/app/models/action_plan.py` : `ActionItem` reçoit `estimated_cost_amount`, `estimated_cost_currency` + property `estimated_cost_money`.
- [ ] T049 [P] Étendre `backend/app/models/carbon.py` : `CarbonAssessment` reçoit `savings_amount`, `savings_currency` + property `savings_money` SI `savings_fcfa` existe (vérifier en B). Sinon, ignorer cette tâche.
- [ ] T050 [P] Étendre `backend/app/models/application.py` : `FundApplication` reçoit `snapshot_at: DateTime(timezone=True)`, `snapshot_data: JSON/JSONB` (utiliser `JSONType` du fichier `source.py`).
- [ ] T051 Écrire `backend/tests/test_models/test_versioning_columns.py` : test que les 13 modèles exposent bien `version`, `valid_from`, `valid_to`, `superseded_by` ; test des 5 modèles avec paires Money + property `_money`. Faire passer en parallèle des T040-T050.

**Checkpoint** : foundation prête → les 5 user stories peuvent démarrer (en série ou en parallèle si plusieurs développeurs).

---

## Phase 3 : User Story 1 — Snapshot immuable de candidature pour audit (P1) 🎯 MVP

**Goal** : permettre la création automatique d'un snapshot JSONB autoportant à la transition `submitted_*` et exposer un endpoint de recompute qui produit un score reproductible.

**Independent Test** : créer une candidature, soumettre, modifier le référentiel en BDD, appeler l'endpoint recompute → score identique au score d'origine.

### Tests US1 (RED first)

- [ ] T100 [P] [US1] Écrire `backend/tests/test_applications/test_snapshot_creation.py` : test création snapshot à la transition `draft → submitted_to_intermediary` ; test transition `draft → submitted_to_fund` ; test contenu `snapshot_data` (referential, fund, intermediary, scores, source_ids_cited) ; test que `snapshot_at` est renseigné. 5 cas minimum.
- [ ] T101 [P] [US1] Écrire `backend/tests/test_applications/test_snapshot_immutable.py` : test que `service.update_application(...)` rejette toute tentative de mutation de `snapshot_data` après création. Test que `snapshot_at` ne peut pas être réinitialisé.
- [ ] T102 [P] [US1] Écrire `backend/tests/test_applications/test_recompute_against_snapshot.py` : test que le recompute produit `comparison_with_origin.match=True, delta=0.0` ; test après modification du référentiel en BDD → recompute identique au score d'origine ; test 409 si candidature en `draft` ; test 403 si compte différent ; test 404 si UUID inexistant.
- [ ] T103 [P] [US1] Écrire test contract `backend/tests/contract/test_application_recompute_contract.py` : valider la réponse de `POST /api/applications/{id}/recompute-against-snapshot` contre `contracts/application_recompute.yaml` (status codes, schéma response).

### Implémentation US1 (GREEN)

- [ ] T110 [US1] Implémenter `backend/app/modules/applications/snapshot.py` : fonctions `build_snapshot_data(application_id, session) -> dict` qui construit le JSON conforme à data-model.md §3 ; `validate_immutable(existing_snapshot, new_snapshot)` qui lève si différents.
- [ ] T111 [US1] Modifier `backend/app/modules/applications/service.py` : ajouter `create_snapshot(application_id, session)` appelée automatiquement dans `transition()` lors du passage à `submitted_to_intermediary` ou `submitted_to_fund`. Ajouter garde anti-mutation dans `update()`.
- [ ] T112 [US1] Implémenter `backend/app/modules/applications/recompute.py` : fonction `recompute_against_snapshot(application_id, session)` qui charge `snapshot_data`, reconstruit les indicateurs/seuils en mémoire (sans toucher la BDD catalogue), recalcule le score et compare au score d'origine.
- [ ] T113 [US1] Modifier `backend/app/modules/applications/router.py` : ajouter `POST /{application_id}/recompute-against-snapshot` (auth user via `get_current_user`, vérification `account_id`). Retours : 200 RecomputeResponse, 403, 404, 409. Faire passer T100-T103.
- [ ] T114 [US1] Ajouter schéma Pydantic `RecomputeResponse`, `SnapshotData`, `SnapshotReferential`, `SnapshotFund`, `SnapshotIntermediary`, `SnapshotOffer`, `SnapshotScores` dans `backend/app/modules/applications/schemas.py` ou nouveau fichier `snapshot_schemas.py`.

### Frontend US1 (badge sur candidature)

- [ ] T120 [P] [US1] Modifier `frontend/app/pages/applications/[id].vue` : ajouter bouton « Recalculer contre snapshot » (visible si `snapshot_at !== null`), appel `POST /api/applications/{id}/recompute-against-snapshot`, affichage modal résultat avec `comparison_with_origin`. Dark mode complet.

**Checkpoint US1** : le MVP est validé quand un E2E peut soumettre une candidature, modifier le référentiel et constater que le recompute renvoie le même score.

---

## Phase 4 : User Story 2 — Type Money typé partout, peg FCFA-EUR fixe (P1)

**Goal** : exposer un type Money strict côté backend + UI, avec conversion FCFA↔EUR sans appel HTTP, et fixer l'AttributeError `fund.max_amount` du tool `simulate_financing`.

**Independent Test** : `convert(Money(655_957, "XOF"), "EUR")` retourne `Money(1_000.00, "EUR")` sans accès réseau ; le tool `simulate_financing` produit une réponse Money valide pour un fonds GCF.

### Tests US2 (RED first)

- [ ] T200 [P] [US2] Écrire `backend/tests/test_currency/test_service.py` : test `convert` peg FCFA→EUR sans HTTP, test peg EUR→FCFA sans HTTP, test arrondi 2 décimales. 6 cas minimum.
- [ ] T201 [P] [US2] Modifier `backend/tests/test_applications/test_simulation.py` : ajouter test que `simulate_financing` retourne des `Money` typés ; ajouter test de régression contre AttributeError `fund.max_amount` (assert pas d'exception).
- [ ] T202 [P] [US2] Écrire test négatif `backend/tests/test_core/test_money.py` (compléter T010) : test `Money(amount=100, currency="ABC")` lève `ValidationError`.

### Implémentation US2 (GREEN)

- [ ] T210 [US2] Implémenter `backend/app/modules/currency/exceptions.py` : `NoRateAvailableError`, `ConversionPathUnavailableError` (héritent de `Exception`).
- [ ] T211 [US2] Implémenter `backend/app/modules/currency/service.py` (partie peg uniquement pour US2) : `convert_peg_only(money, target)` pour FCFA↔EUR ; `convert(money, target, date=None)` qui délègue au peg ou lève `NoRateAvailableError` si non-peg (US4 complétera). Faire passer T200, T202.
- [ ] T212 [US2] Modifier `backend/app/modules/applications/simulation.py` : remplacer `fund.max_amount` / `fund.min_amount` par `fund.max_amount_money` / `fund.min_amount_money` (property). Si `None`, message d'erreur explicite. Retourner Money typé dans le dict simulation. Faire passer T201.
- [ ] T213 [US2] Modifier `backend/app/graph/tools/application_tools.py` : `simulate_financing` reçoit/retourne Money typé, plus d'AttributeError. Sérialisation JSON via `model_dump(mode='json')` pour le passage LangChain.

### Frontend US2 (composant MoneyDisplay + composable)

- [ ] T220 [P] [US2] Écrire `frontend/tests/unit/components/MoneyDisplay.spec.ts` : test rendu mode `native`, mode `pme`, mode `both` ; test omission équivalent quand devises identiques ; test dark mode (assertion classes Tailwind `dark:`) ; test accessibilité tooltip ; test format espace insécable.
- [ ] T221 [P] [US2] Écrire `frontend/tests/unit/composables/useCurrency.spec.ts` : test `format`, `convert` (mock fetch), `getPmeCurrency() === 'XOF'`.
- [ ] T222 [P] [US2] Écrire `frontend/tests/unit/stores/ui.spec.ts` : test ajout `displayCurrencyMode`, persistance localStorage, validation enum.
- [ ] T230 [P] [US2] Implémenter `frontend/app/types/currency.ts` : `Currency = 'XOF' | 'EUR' | 'USD' | 'GBP' | 'JPY'`, interface `Money { amount: string; currency: Currency }`, interface `ExchangeRate`.
- [ ] T231 [P] [US2] Implémenter `frontend/app/composables/useCurrency.ts` : `format(money)`, `convert(money, target)`, `getRate(base, quote)`, `getPmeCurrency()` (constante `'XOF'`). Faire passer T221.
- [ ] T232 [P] [US2] Modifier `frontend/app/stores/ui.ts` : ajouter état `displayCurrencyMode: 'native' | 'pme' | 'both'` (défaut `'both'`), persistance localStorage clé `mefali.ui.displayCurrencyMode`, setter validé. Faire passer T222.
- [ ] T233 [US2] Implémenter `frontend/app/components/ui/MoneyDisplay.vue` : props `money`, `showPmeCurrency`, lecture `displayCurrencyMode` ; format espace insécable ; symboles devise ; tooltip explication FR ; dark mode. Faire passer T220.

**Checkpoint US2** : type Money utilisable, peg fonctionnel, tool `simulate_financing` corrigé, composant `<MoneyDisplay>` présent et testé.

---

## Phase 5 : User Story 3 — Versioning du catalogue avec chaîne `superseded_by` (P2)

**Goal** : éditer une entité publiée crée une nouvelle version (l'ancienne reçoit `valid_to`, la nouvelle `version` incrémenté), avec trigger anti-cycle. Composant `<ReferentialBadge>` affiché sur chaque score persisté.

**Independent Test** : créer un fund publié, l'éditer via API admin, vérifier 2 lignes en BDD avec versioning correct ; tenter cycle A→B→A → exception.

### Tests US3 (RED first)

- [ ] T300 [P] [US3] Écrire `backend/tests/test_versioning/test_supersede.py` (compléter T013) : test scénario complet sur Fund publié — édition crée nouvelle version, ancienne reçoit `valid_to=today` et `superseded_by=new.id` ; test édition sur draft ne crée pas de nouvelle version (mise à jour en place).
- [ ] T301 [P] [US3] Écrire `frontend/tests/unit/components/ReferentialBadge.spec.ts` : test rendu badge avec libellé français ; test click → emit événement d'ouverture modale ; dark mode.

### Implémentation US3 (GREEN)

- [ ] T310 [US3] Compléter `backend/app/modules/versioning/service.py` : fonction `create_new_version(session, entity, force_major=False, **updates)` qui (1) bump version, (2) insère nouvelle ligne avec valid_from=today+1, (3) update ancienne avec valid_to=today, superseded_by=new.id ; vérification `is_published()` ; rollback si échec. Faire passer T300.
- [ ] T311 [US3] Câbler les services admin existants (Fund, Intermediary, Source, Indicator, etc.) pour utiliser `create_new_version` lors d'une édition publiée. Cette tâche peut être étalée sur plusieurs sous-tâches à l'implémentation, ou laissée comme stub minimal pour MVP (les routes admin de mutation arrivent en F09).
- [ ] T312 [US3] Vérifier en exécution que le trigger PL/pgSQL `prevent_supersede_cycle()` est bien créé sur les 13 tables (post-migration T032).

### Frontend US3 (ReferentialBadge)

- [ ] T320 [US3] Implémenter `frontend/app/components/ui/ReferentialBadge.vue` : props `referential: { id, name, version, valid_from }`, libellé « Évalué selon Référentiel <name> v<version> du <valid_from formaté FR> », click → emit `open-source-modal`, dark mode complet, ARIA. Faire passer T301.
- [ ] T321 [P] [US3] Câbler `<ReferentialBadge>` dans les composants de score : `frontend/app/components/ScoreCard.vue` (ou équivalent), pages `/esg`, `/carbon/results`, `/credit`, `/financing/[id]`. Réutiliser `<SourceModal>` de F01 pour l'affichage détaillé.

**Checkpoint US3** : versioning fonctionnel, badge présent sur chaque score persisté.

---

## Phase 6 : User Story 4 — Conversion USD via table `exchange_rates` avec fallback (P2)

**Goal** : permettre les conversions non-peggées via la table `exchange_rates` avec fallback ascendant et pivot USD ; cap dur 1 fetch/jour.

**Independent Test** : insérer un taux USD→XOF pour 2026-04-15, demander conversion à 2026-05-01 sans entrée pour cette date → utilise le taux du 2026-04-15 ; deux tentatives de fetch / jour → un seul appel HTTP.

### Tests US4 (RED first)

- [ ] T400 [P] [US4] Compléter `backend/tests/test_currency/test_service.py` : test `get_rate(USD, XOF, date=today)` lit la table ; test fallback ascendant (date sans entrée → entrée la plus récente avant) ; test exception `NoRateAvailableError` quand table vide ; test arrondis Decimal.
- [ ] T401 [P] [US4] Écrire `backend/tests/test_currency/test_pivot.py` : test pivot USD pour EUR→JPY (calcul `convert(USD,JPY) * convert(EUR,USD)`) ; test exception `ConversionPathUnavailableError` quand pivot manquant.
- [ ] T402 [P] [US4] Écrire `backend/tests/test_currency/test_fetch_script.py` : test cap 1 fetch/jour (mock `httpx.AsyncClient` ; second appel dans la même journée → skip silencieux) ; test mode dégradé (clé API vide → skip) ; test parsing réponse exchangerate-api.com (USD→{XOF,EUR,GBP,JPY}) + dérivation paires inverses ; test gestion erreur HTTP (timeout, 503).
- [ ] T403 [P] [US4] Écrire `backend/tests/test_currency/test_router.py` : test `GET /api/currency/rates/latest` (200, structure response) ; test `POST /api/currency/convert` (200 peg, 200 table, 200 pivot, 404 path unavailable, 422 validation).
- [ ] T404 [P] [US4] Écrire test contract `backend/tests/contract/test_currency_api_contract.py` : valider response format vs `contracts/currency_api.yaml`.

### Implémentation US4 (GREEN)

- [ ] T410 [US4] Compléter `backend/app/modules/currency/service.py` : fonctions `get_rate(session, base, quote, date=None)` avec fallback ascendant ; `convert(money, target, session, date=None)` qui orchestre peg / direct table / pivot USD ; `_try_direct(session, base, quote, date)` ; `_convert_with_pivot(session, money, target, date)`. Faire passer T400-T403.
- [ ] T411 [US4] Implémenter `backend/app/modules/currency/schemas.py` : Pydantic `ConvertRequest`, `ConvertResponse`, `RatesLatestResponse`, `RateEntry`, `PegEntry`, `FetchStatusResponse`.
- [ ] T412 [US4] Implémenter `backend/app/modules/currency/router.py` : routes `GET /api/currency/rates/latest`, `POST /api/currency/convert`. Lecture publique (pas d'auth). Faire passer T403, T404.
- [ ] T413 [US4] Implémenter `backend/app/modules/currency/admin_router.py` : route `GET /api/admin/currency/fetch-status` protégée par `Depends(get_current_admin)`. Lecture des dernières valeurs depuis `exchange_rates`.
- [ ] T414 [US4] Implémenter `backend/app/scripts/fetch_exchange_rates.py` : CLI exécutable via `python -m app.scripts.fetch_exchange_rates [--force]`. Vérifie cap 1/jour (sauf `--force`), call exchangerate-api.com, parse, insère dans `exchange_rates`. Mode dégradé si clé absente. Logs structurés ERROR `EXCHANGERATE_FETCH_FAILED` en échec. Faire passer T402.
- [ ] T415 [US4] Modifier `backend/app/main.py` (ZONE INTERDITE — sérialiser) : enregistrer router currency + admin currency dans l'app FastAPI ; ajouter lifespan startup hook qui déclenche fetch one-shot si table vide ou trop ancienne (> 7 jours).

**Checkpoint US4** : conversion non-peggée fonctionnelle, cap 1/jour respecté, admin peut consulter le statut.

---

## Phase 7 : User Story 5 — Composants UI MoneyDisplay et ReferentialBadge intégrés (P2)

**Goal** : tous les montants UI passent par `<MoneyDisplay>` (mode native/pme/both selon préférence), tous les scores affichent `<ReferentialBadge>`. Settings utilisateur accessible.

**Independent Test** : page `/financing` affiche cards avec `<MoneyDisplay>`, le toggle de mode dans Settings change l'affichage live, dark mode reste lisible.

### Tests US5 (RED first)

- [ ] T500 [P] [US5] Étendre `frontend/tests/unit/components/MoneyDisplay.spec.ts` (compléter T220) : test composant intégré dans une card de fonds (props depuis ressource API mockée).

### Implémentation US5 (GREEN)

- [ ] T510 [US5] Migrer `frontend/app/components/FinancingCard.vue` (ou équivalent) : remplacer `formatXof()` ou `${amount} XOF` par `<MoneyDisplay :money="..."/>`.
- [ ] T511 [US5] Migrer page `frontend/app/pages/financing/index.vue` ou `frontend/app/pages/financing.vue` : idem.
- [ ] T512 [US5] Migrer `frontend/app/pages/financing/[id].vue` : idem + ajouter `<ReferentialBadge>` sur le score d'éligibilité.
- [ ] T513 [US5] Migrer `frontend/app/pages/dashboard.vue` (ou `dashboard/index.vue`) : idem.
- [ ] T514 [US5] Migrer `frontend/app/pages/action-plan.vue` : idem (ActionItem.estimated_cost).
- [ ] T515 [US5] Migrer `frontend/app/pages/applications/[id].vue` : idem (`intermediary_fees` simulation).
- [ ] T516 [US5] Migrer `frontend/app/components/ScoreCard.vue` (et composants ESG, carbone, credit) : ajouter `<ReferentialBadge>`.
- [ ] T517 [US5] Ajouter section Settings dans page utilisateur existante (ou créer `frontend/app/pages/settings/preferences.vue`) : choix `displayCurrencyMode` via radio buttons. Persistance via store ui.

**Checkpoint US5** : tous les montants utilisent `<MoneyDisplay>`, tous les scores ont `<ReferentialBadge>`.

---

## Phase 8 : E2E Playwright (validation transverse)

- [ ] T600 [P] Écrire `frontend/tests/e2e/F04-versioning-money-devises.spec.ts` : 4 scénarios obligatoires (briefing orchestrateur).
  - **Scénario 1** : `<MoneyDisplay>` rend « 1 000 000 FCFA (≈ 1 524 €) » lorsque le mode est `both` et qu'un montant USD ou EUR est affiché. Assertion DOM sur le contenu textuel.
  - **Scénario 2** : `<ReferentialBadge>` cliquable ouvre `<SourceModal>` avec les détails de la version. Vérifier l'apparition de la modale et le focus piégé.
  - **Scénario 3** : snapshot de candidature — soumettre une candidature, modifier (via API admin mockée ou stub) le référentiel, recharger la page candidature, vérifier que les valeurs affichées correspondent au snapshot d'origine, pas au référentiel modifié.
  - **Scénario 4** : appel `POST /api/applications/{id}/recompute-against-snapshot` via le bouton UI, vérifier la modale résultat affiche `match: true` et `delta: 0.0`.

---

## Phase 9 : Polish & cross-cutting

- [ ] T700 [P] Documentation : mise à jour `CLAUDE.md` (section Active Technologies) avec mention F04 — peg FCFA-EUR, table `exchange_rates`, type `Money`, snapshot JSONB.
- [ ] T701 [P] Documentation : créer/mettre à jour `docs/money-and-versioning.md` (architecture, exemples API, comment ajouter une devise).
- [ ] T702 [P] Vérifier la couverture tests : `cd backend && source venv/bin/activate && pytest tests/ --cov=app --cov-report=term-missing` doit montrer ≥ 80 % sur `app.core.money`, `app.modules.currency`, `app.modules.versioning`, `app.modules.applications.snapshot`, `app.modules.applications.recompute`, `app.models.exchange_rate`.
- [ ] T703 [P] Vérifier lint + py_compile : `cd backend && source venv/bin/activate && python -m py_compile $(find app -name '*.py')` sans erreur.
- [ ] T704 [P] Vérifier compilation TypeScript : `cd frontend && npx nuxt typecheck` (ou `npm run build`) sans erreur.
- [ ] T705 Exécuter quickstart.md de A à Z (depuis venv frais) pour valider le parcours développeur. Corriger toute friction.
- [ ] T706 Sécurité : vérifier qu'aucun secret n'a été ajouté en dur (`grep -rE "(api_key|secret|password|token)\s*=\s*[\"\047][A-Za-z0-9]" backend/ frontend/`).
- [ ] T707 [P] Métrique observabilité : ajouter un log structuré INFO à chaque snapshot créé (taille en bytes, application_id) pour benchmark futur de la compression gzip post-MVP.
- [ ] T708 [P] Audit dette tools Money : `grep -rn "_xof\|_fcfa\|fund\.max_amount\|fund\.min_amount" backend/app/graph/tools/` puis documenter dans `docs/money-and-versioning.md` la liste des tools restant à migrer post-MVP (FR-051).
- [ ] T709 [P] Audit résiduels frontend : `grep -rn "formatXof\|XOF\b" frontend/app` pour vérifier qu'aucun usage legacy ne reste après US5 (FR-067).
- [ ] T710 [P] Audit ReferentialBadge sur tous les ScoreCard : vérifier visuellement (ou via grep `<ReferentialBadge` dans les composants ESG/carbone/credit/financing) que SC-008 est respecté.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** : aucune dépendance, démarrage immédiat.
- **Phase 2 (Foundational)** : dépend de Phase 1. **BLOQUE TOUTES LES USER STORIES**.
- **Phase 3 (US1 — P1 Snapshot)** : dépend de Phase 2.
- **Phase 4 (US2 — P1 Money + peg + simulate fix)** : dépend de Phase 2.
- **Phase 5 (US3 — P2 Versioning)** : dépend de Phase 2.
- **Phase 6 (US4 — P2 Conversion USD + pivot)** : dépend de Phase 2.
- **Phase 7 (US5 — P2 UI intégration)** : dépend de Phase 4 (composant MoneyDisplay) ET Phase 5 (composant ReferentialBadge).
- **Phase 8 (E2E)** : dépend de Phase 7 (UI complète).
- **Phase 9 (Polish)** : dépend de Phase 8 (validation complète).

### User Story Dependencies

- **US1 (P1)** : démarre après Phase 2. Indépendante des autres.
- **US2 (P1)** : démarre après Phase 2. Indépendante.
- **US3 (P2)** : démarre après Phase 2. Indépendante.
- **US4 (P2)** : démarre après Phase 2. Indépendante (utilise les modèles ExchangeRate de Phase 2).
- **US5 (P2)** : démarre après US2 et US3 (besoin des composants UI).

### Within Each User Story

- Tests RED écrits d'abord (constitution principle IV).
- Modèles/services/router avant intégration frontend.
- Frontend après backend disponible (ou avec mock fetch pour US2 si parallélisation).

### Parallel Opportunities

- Setup : T002, T003, T004, T005 sont parallèles.
- Foundational : T010-T014 (tests) parallèles ; T020-T024 (impl) parallèles entre eux ; T040-T050 (extension modèles) parallèles entre eux.
- US1 / US2 / US3 / US4 peuvent être développées en parallèle par différents devs après Phase 2.
- US5 nécessite US2 + US3 (composants UI prêts).
- Polish : T700-T707 majoritairement parallèles.

---

## Parallel Example : User Story 2 (P1 Money + peg)

```bash
# Tests US2 en parallèle :
Task: "T200 [P] tests test_currency/test_service.py — peg FCFA↔EUR"
Task: "T201 [P] tests test_applications/test_simulation.py — Money typés + régression AttributeError"
Task: "T202 [P] tests test_core/test_money.py — devise hors enum"

# Implémentation backend US2 :
Task: "T210 modules/currency/exceptions.py"
Task: "T211 modules/currency/service.py partie peg"
Task: "T212 modules/applications/simulation.py"
Task: "T213 graph/tools/application_tools.py"

# Frontend US2 en parallèle :
Task: "T220 [P] tests Vitest MoneyDisplay"
Task: "T221 [P] tests Vitest useCurrency"
Task: "T222 [P] tests Vitest store ui"
Task: "T230 [P] types/currency.ts"
Task: "T231 [P] composables/useCurrency.ts"
Task: "T232 [P] stores/ui.ts"
Task: "T233 components/ui/MoneyDisplay.vue (depend on T220, T230, T231, T232)"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Compléter Phase 1 (Setup).
2. Compléter Phase 2 (Foundational) — **CRITICAL**, blocs tout le reste.
3. Compléter Phase 3 (US1 Snapshot) ET Phase 4 (US2 Money) en parallèle si bandwidth.
4. **STOP & VALIDATE** : tester US1 et US2 indépendamment. Démontrer le peg FCFA-EUR et la reproduction de score via snapshot.
5. Déployer le MVP.

### Incremental Delivery

1. Setup + Foundational → fondations posées.
2. US1 (Snapshot) → MVP partie 1, déploiement possible.
3. US2 (Money + peg + simulate fix) → MVP partie 2, fix de bug critique en prod.
4. US3 (Versioning) → catalogue évolutif.
5. US4 (Conversion USD via table) → multi-devises complet.
6. US5 (UI intégration) → expérience utilisateur enrichie.
7. E2E Playwright → validation transverse.
8. Polish → couverture, doc, métriques.

### Parallel Team Strategy

Avec plusieurs développeurs après Phase 2 :

- Dev A : US1 (Snapshot)
- Dev B : US2 (Money + peg) puis aide US5 frontend
- Dev C : US3 (Versioning) puis aide US5 frontend
- Dev D : US4 (Conversion USD)
- Tous : convergence sur Phase 8 E2E + Phase 9 Polish.

---

## Notes

- [P] = fichier différent, pas de dépendance bloquante.
- Chaque user story doit être indépendamment livrable et testable.
- Tests RED écrits AVANT implémentation (constitution principle IV).
- Couverture cible 80 % minimum sur les nouveaux modules.
- Commit après chaque tâche ou groupe logique cohérent.
- Stop à chaque checkpoint pour valider la story indépendamment.
- Éviter : tâches vagues, conflits sur le même fichier, dépendances cross-story qui cassent l'indépendance.
- Migration Alembic 022 : sérialiser strictement (zone interdite). UNE migration en flight max.
- `backend/app/main.py`, `backend/app/core/config.py` : zones interdites — modifier qu'avec confirmation orchestrateur.
- Phase 2 (drop legacy `*_xof`) HORS-SCOPE F04 : sera planifiée comme migration séparée 02X.
