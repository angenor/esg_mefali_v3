---

description: "Task list — F07 Entité Offre = Couple Fonds × Intermédiaire"
---

# Tasks: F07 — Entité Offre = Couple Fonds × Intermédiaire

**Input** : Design documents from `/specs/028-entite-offre-fonds-intermediaire/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Branch** : `feat/F07-entite-offre-fonds-intermediaire` (alias SpecKit `028-entite-offre-fonds-intermediaire`)

**Tests** : Tests TDD obligatoires (cycle Red-Green-Refactor enforcé, couverture ≥ 80 %).

**Organization** : Tasks groupées par user story (US1, US2, US3, US4, US5, US6) pour livraison incrémentale.

## Format : `[ID] [P?] [Story] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance bloquante)
- **[Story]** : Rattachement user story (US1, US2, US3, US4, US5, US6) ; absent pour Setup/Foundational/Polish
- Chemins absolus depuis racine repo

## Path Conventions

- **Backend** : `backend/app/`, `backend/tests/`, `backend/alembic/versions/`, `backend/scripts/`
- **Frontend** : `frontend/app/`, `frontend/tests/`
- **Specs** : `specs/028-entite-offre-fonds-intermediaire/`
- **Docs** : `docs/`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer l'environnement et vérifier les prérequis F01 + F02 + F04 + F06.

- [ ] T001 Vérifier l'activation du venv backend (`source backend/venv/bin/activate`) et que `which python` pointe vers `backend/venv/bin/python`. Vérifier dépendances installées (`pip install -r backend/requirements.txt`).
- [ ] T002 Vérifier que les migrations F01 (`020_create_sources_catalog`), F02 (`019_multitenant_and_roles`), F04 (`022_money_and_versioning`), F06 (`025_create_projects`), F05 (`027_consents_and_account_deletion`) sont appliquées localement (`cd backend && alembic current` doit montrer `027_consents_and_account_deletion`).
- [ ] T003 [P] Vérifier l'existence et l'état actuel des modèles concernés : `backend/app/models/financing.py` (Fund, Intermediary, FundIntermediary, FundMatch, FinancingChunk), `backend/app/models/application.py` (FundApplication), `backend/app/models/source.py` (Source, PublicationStatus), `backend/app/models/versioning_mixin.py` (VersioningMixin), `backend/app/core/money.py` (Money), `backend/app/models/required_document.py` (RequiredDocument). Pas de modification, juste vérification.
- [ ] T004 [P] Audit `frontend/app/components/ui/` pour identifier les composants génériques réutilisables (`<MoneyDisplay>`, `<DurationRange>`, `<SourceBadge>`). Documenter dans `frontend/app/components/ui/README.md` (si absent, le créer) la liste des composants à extraire potentiellement après plus de 2 occurrences.
- [ ] T005 [P] Ajouter env var `USE_OFFER_VIEW=false` dans `frontend/.env.example` et déclarer `runtimeConfig.public.useOfferView` dans `frontend/nuxt.config.ts` (zone protégée — modification minimale d'1 ligne).

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Mise en place de la migration Alembic, des modèles, du service calculator et du seed singleton DIRECT — prérequis bloquants pour toutes les user stories.

**⚠️ CRITICAL** : Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Foundational (TDD — écrire AVANT implémentation, vérifier qu'ils ÉCHOUENT)

- [ ] T006 [P] Écrire test unitaire `backend/tests/unit/test_offer_model.py` : invariants table `offers` (FK fund/intermediary CASCADE, FK source RESTRICT, contraintes CHECK : publication_status, processing_time_consistency, disbursement_time_consistency, published_active_chk, unique fund_intermediary_version, default values is_active=true et publication_status='draft' et accepted_languages='["FR"]').
- [ ] T007 [P] Écrire test unitaire `backend/tests/unit/test_offer_calculator.py` : `compute_effective_offer` (intersection critères avec règle « le plus restrictif gagne », union documents avec dédup exact `(title, source_id)`, somme frais Money typed avec conversion XOF, somme délais, hint langues anglophones, détection incohérence `min_amount > max_amount_per_fund`).
- [ ] T008 [P] Écrire test unitaire `backend/tests/unit/test_seed_direct.py` : seed singleton DIRECT (idempotent : 2 appels successifs n'insèrent qu'une seule ligne ; le `code='DIRECT'` est unique ; intermédiaire est créé en `publication_status='published'` car attendu accessible immédiatement).
- [ ] T009 [P] Écrire test migration `backend/tests/migrations/test_alembic_028.py` : up/down/up sans erreur ; vérifier création table `offers` avec contraintes/indexes ; vérifier ajout colonnes sur `funds`/`intermediaries`/`fund_intermediaries`/`fund_applications` ; vérifier renommage enum `fund_type` (valeurs migrées : `international` → `multilateral`, `carbon_market` → `carbon_marketplace`, `local_bank_green_line` → `private`) ; vérifier seed singleton DIRECT créé ; vérifier backfill : count `offers` ≥ count `fund_intermediaries` + count `funds where access_type='direct'`, `SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL = 0`. Idempotence : `alembic upgrade head` 2 fois sans erreur.

### Implementation Foundational

- [ ] T010 Créer la migration `backend/alembic/versions/028_offers_and_enrich_fund_intermediary.py` avec `down_revision='027_consents_and_account_deletion'`. Implémenter :
  - `op.create_table('offers', ...)` : 16 colonnes business + 4 versioning + 2 timestamps + 5 indexes + 4 contraintes CHECK (cf. data-model.md).
  - `op.add_column('funds', ...)` × 6 + `op.add_column('intermediaries', ...)` × 13 + `op.add_column('fund_intermediaries', ...)` × 5 + `op.add_column('fund_applications', 'offer_id')`.
  - Création nouveaux types ENUM PostgreSQL `submission_mode_enum` ; renommage `fund_type_enum` via étape `fund_type_v2_enum` puis swap.
  - Indexes complémentaires : `idx_funds_theme_gin`, `idx_funds_instruments_gin`, `idx_intermediaries_country`, `idx_fund_intermediaries_accredited_to`, `uq_intermediaries_code`.
  - Contraintes CHECK : `funds_submission_mode_chk`, `funds_publication_status_chk`, `intermediaries_*_chk`, `fund_intermediaries_*_chk`.
  - Phase backfill (DML) : seed `Source` `system://mefali/direct-singleton`, seed singleton intermédiaire `code='DIRECT'`, création offres pour chaque paire fund_intermediaries existante + chaque fonds direct, liaison `fund_applications.offer_id` via 2 UPDATEs (intermediary_id renseigné OU fallback DIRECT).
  - `op.alter_column` sur `funds.source_id`, `intermediaries.source_id`, `fund_intermediaries.accredited_from`, `fund_applications.offer_id` pour passer en NOT NULL post-backfill.
  - Implémenter `downgrade()` complet et réversible : DROP indexes, DROP CHECK constraints, DROP enum `submission_mode`, swap inverse `fund_type` enum, DROP colonnes ajoutées, DROP table `offers`. NE PAS supprimer le singleton DIRECT (résiduel sans impact).
- [ ] T011 Créer le modèle SQLAlchemy `backend/app/models/offer.py` (classe `Offer(UUIDMixin, TimestampMixin, VersioningMixin, Base)`) avec toutes les colonnes/contraintes/indexes/relations selon data-model.md. Référencer dans `backend/app/models/__init__.py`.
- [ ] T012 Étendre le modèle `Fund` dans `backend/app/models/financing.py` : ajouter `instruments` (JSONType), `theme` (JSONType), `submission_mode` (String 30 + check), `submission_calendar` (JSONType nullable), `source_id` (UUID FK NOT NULL), `publication_status` (String 20). Renommer enum `FundType` valeurs en `multilateral|bilateral|regional|national|private|carbon_marketplace`. Marquer `min_amount_xof` / `max_amount_xof` comme deprecated dans docstring.
- [ ] T013 Étendre le modèle `Intermediary` dans `backend/app/models/financing.py` : ajouter `code` (String 50 nullable, unique sparse), `required_documents` (JSONType default `[]`), `fees_structured` (JSONType nullable), `processing_time_days_min/max` (Integer nullable), `disbursement_time_days_min/max` (Integer nullable), `submission_portal_url` (String 500 nullable), `success_rate` (Numeric 5,4 nullable + check 0..1), `total_funded_volume_amount/currency` (Numeric 20,2 + String 3 + check pair), `source_id` (UUID FK NOT NULL), `publication_status` (String 20 + check). Marquer `typical_fees` comme deprecated.
- [ ] T014 Étendre le modèle `FundIntermediary` dans `backend/app/models/financing.py` : ajouter `accredited_from` (Date NOT NULL post-backfill), `accredited_to` (Date nullable), `max_amount_per_fund_amount/currency` (Numeric 20,2 + String 3 + check pair), `accreditation_source_id` (UUID FK nullable). Ajouter contraintes CHECK `accreditation_dates_chk` et `max_amount_pair_chk`.
- [ ] T015 Étendre le modèle `FundApplication` dans `backend/app/models/application.py` : ajouter `offer_id` (UUID FK `offers.id` NOT NULL post-backfill, RESTRICT). Ajouter relation `offer: Mapped["Offer"]`. Marquer `fund_id` et `intermediary_id` comme deprecated dans docstring (« utiliser `offer.fund_id` et `offer.intermediary_id` »).
- [ ] T016 Créer le service `backend/app/modules/offers/calculator.py` avec `compute_effective_offer(session, fund_id, intermediary_id) → OfferDraft`. Implémenter : `_intersect_criteria` (règle « le plus restrictif gagne »), `_union_documents` (dédup exacte sur `(title.lower().strip(), source_id)`, mandatory=true écrase), `_combine_fees` (somme Money typed avec conversion XOF via `app.modules.currency.convert`), `_infer_languages_from_country` (heuristique pays anglophones `['UK', 'US', 'CA', 'KE', 'GH', 'NG', 'ZA', 'DE', 'JP', 'AU', 'NZ', 'IE']`), `_detect_inconsistencies` (warnings dans `notes` du draft).
- [ ] T017 Créer le seed `backend/app/modules/offers/seed_direct.py` : fonction `seed_direct_intermediary(session) → Intermediary` idempotente. Crée la source `system://mefali/direct-singleton` si absente (avec `verification_status='verified'`, `verified_by=captured_by` impossible — utiliser un user système dédié ou contourner via SQL direct dans la migration). Crée l'intermédiaire avec `code='DIRECT'` si absent.
- [ ] T018 Créer les schémas Pydantic `backend/app/modules/offers/schemas.py` : `OfferDraft`, `OfferRead`, `OfferCreate`, `OfferUpdate`, `OfferComparison`, `OfferSummary`, `FundSummary`, `IntermediarySummary`, `EffectiveDocument`, `EffectiveCriterion`, `EffectiveFees` (cf. contracts/openapi-offers.yaml et openapi-admin-offers.yaml).

**Checkpoint** : tous les tests T006-T009 passent ; `alembic upgrade head` réussit ; `compute_effective_offer` peut être appelé en interactif Python.

---

## Phase 3 : User Story 1 — PME compare deux offres concurrentes pour un même fonds (P1) 🎯

**Goal** : permettre à une PME de voir et comparer plusieurs offres distinctes pour un même fonds.

**Independent Test** : Seeder 2 offres GCF (BOAD + UNDP) en `publication_status='published'`, ouvrir `/financing` (avec `USE_OFFER_VIEW=true`), voir les 2 Cards Offres distinctes, ouvrir le détail de l'une, cliquer sur « Comparer », vérifier le tableau côte-à-côte.

### Tests US1 (TDD)

- [ ] T019 [P] [US1] Écrire test intégration `backend/tests/integration/test_offers_router.py::test_list_offers_returns_published_only` : seed 1 offre published + 2 drafts → `GET /api/offers` retourne 1 résultat.
- [ ] T020 [P] [US1] Écrire test intégration `backend/tests/integration/test_offers_router.py::test_list_offers_filters_by_fund_id` : 2 offres pour fund_A + 1 offre pour fund_B → `GET /api/offers?fund_id=fund_A` retourne 2 résultats.
- [ ] T021 [P] [US1] Écrire test intégration `backend/tests/integration/test_offers_router.py::test_get_offer_returns_404_for_draft` : 1 offre draft → `GET /api/offers/{id}` retourne 404.
- [ ] T022 [P] [US1] Écrire test intégration `backend/tests/integration/test_offers_router.py::test_comparator_returns_all_published_for_fund` : 2 offres published + 1 draft pour même fonds → `GET /api/offers/comparator?fund_id=X` retourne 2 résultats avec champs comparables.
- [ ] T023 [P] [US1] Écrire test composant `frontend/tests/components/OfferCard.spec.ts` : rendu avec props (offer mock), vérification dark mode (variantes `dark:`), vérification ARIA (`aria-label` sur boutons), affichage badge langue + frais effectifs + délais.
- [ ] T024 [P] [US1] Écrire test composant `frontend/tests/components/OfferDetail.spec.ts` : rendu détail avec sections (header, fund cliquable, intermediary cliquable, EffectiveCriteriaList, EffectiveDocumentsList, EffectiveFees), bouton « Comparer » présent, bouton « Candidater » présent.

### Implementation US1

- [ ] T025 [US1] Créer le service `backend/app/modules/offers/service.py::list_offers(session, filters, limit, offset, sort)` : query Offer avec filtres (`fund_id`, `intermediary_id`, `theme`, `instrument`, `country`, `language`), filtre strict `publication_status='published' AND is_active=true`, jointures eager fund/intermediary/source. Retourne `(items, total)`.
- [ ] T026 [US1] Créer le service `backend/app/modules/offers/service.py::get_offer(session, offer_id) → OfferRead | None` : query 1 offre avec jointures, retourne None si non trouvée OU si `publication_status='draft'` (cohérent règle anti-fuite).
- [ ] T027 [US1] Créer le service `backend/app/modules/offers/service.py::compare_offers_for_fund(session, fund_id) → list[OfferComparison]` : query toutes les offres `published+active` pour ce fonds, structure tableau côte-à-côte.
- [ ] T028 [US1] Créer le router public `backend/app/modules/offers/router.py` avec endpoints `GET /api/offers`, `GET /api/offers/{id}`, `GET /api/offers/comparator`. Pagination via `limit/offset` (max 100). Réponses Pydantic. Enregistrer le router dans `backend/app/main.py` (zone protégée, ajout d'une seule ligne `app.include_router(offers_router, prefix="/api", tags=["offers"])`).
- [ ] T029 [US1] Créer le composant `frontend/app/components/financing/OfferCard.vue` : Card cliquable, dark mode complet, affiche `name`, `fund.name + organization`, `intermediary.name + country`, badge langue, `effective_fees` (composant `<MoneyDisplay>`), `effective_processing_time` (composant `<DurationRange>`), score décomposé (calculé côté frontend depuis l'offre — fund_score = 80 placeholder, intermediary_score = success_rate * 100 placeholder pour MVP F07).
- [ ] T030 [US1] Créer le composant `frontend/app/components/financing/OfferDetail.vue` : layout sections, dark mode complet, ARIA roles, intègre `<EffectiveCriteriaList>`, `<EffectiveDocumentsList>`, `<EffectiveFees>`, `<SubmissionModeBadge>`. Boutons « Comparer avec autres offres pour ce fonds » → `/financing/offers?fund_id=X&compare=true` ; « Candidater » → `/financing/offers/{id}/apply` (route préparée pour F15).
- [ ] T031 [US1] Créer le composant `frontend/app/components/financing/EffectiveCriteriaList.vue` : tableau ou liste de critères avec `<SourceBadge>` cliquable pour chaque entrée, dark mode.
- [ ] T032 [US1] Créer le composant `frontend/app/components/financing/EffectiveDocumentsList.vue` : liste de documents avec mandatory en évidence, format_spec affiché, `<SourceBadge>` cliquable, dark mode.
- [ ] T033 [US1] Créer le composant `frontend/app/components/financing/EffectiveFees.vue` : breakdown Money typed avec total min/max, taux %, `<SourceBadge>` par ligne, dark mode.
- [ ] T034 [US1] Créer le composant `frontend/app/components/financing/SubmissionModeBadge.vue` : badge `Rolling` (vert) ou `Appel à projets` (orange) avec icône, dark mode.
- [ ] T035 [US1] Créer la page `frontend/app/pages/financing/offers/[offer_id].vue` : SSR fetch via `useFinancing().getOffer(id)`, rendu via `<OfferDetail>`, gestion loading/error states.
- [ ] T036 [US1] Créer la page comparateur `frontend/app/pages/financing/offers/index.vue` (avec query param `?fund_id=X`) : tableau côte-à-côte des offres comparables, fetch via `useFinancing().compareOffersForFund(fundId)`.
- [ ] T037 [US1] Étendre le composable `frontend/app/composables/useFinancing.ts` : méthodes `listOffers(filters)`, `getOffer(id)`, `compareOffersForFund(fundId)`. Utiliser `$fetch` typé.
- [ ] T038 [US1] Étendre le store `frontend/app/stores/financing.ts` : state `offers: OfferSummary[]`, action `fetchOffers(filters)`, getter `offersForFund(fundId)`.
- [ ] T039 [US1] Étendre les types `frontend/app/types/financing.ts` : interfaces `Offer`, `OfferSummary`, `OfferDetail`, `OfferComparison`, `EffectiveDocument`, `EffectiveCriterion`, `EffectiveFees`, `SubmissionMode`.
- [ ] T040 [US1] Refactor `frontend/app/pages/financing/index.vue` : lecture `useRuntimeConfig().public.useOfferView`. Si `true`, rendre le grid `<OfferCard>` avec filtres (Theme, Instrument, Country, Language). Sinon, conserver le rendu actuel (Cards Fonds avec modal). Dark mode complet sur les filtres.

**Checkpoint** : tous les tests T019-T024 passent ; on peut consulter manuellement `/financing/offers/{id}` et le comparateur.

---

## Phase 4 : User Story 2 — Admin crée une nouvelle Offre via calcul automatique (P1) 🎯

**Goal** : permettre à un admin de créer une offre via le calcul automatique + édition + publication.

**Independent Test** : Authentifier en tant qu'admin, appeler `POST /api/admin/offers/compute?fund_id=X&intermediary_id=Y`, vérifier le draft, appeler `POST /api/admin/offers` avec le payload édité, vérifier la persistance, basculer en `published` via `PATCH`.

### Tests US2 (TDD)

- [ ] T041 [P] [US2] Écrire test intégration `backend/tests/integration/test_admin_offers_router.py::test_compute_endpoint_returns_draft` : admin authentifié, fund + intermediary actifs avec critères/documents/frais → `POST /api/admin/offers/compute` retourne 200 avec OfferDraft (sans persistance en base, vérifier count `offers` inchangé).
- [ ] T042 [P] [US2] Écrire test intégration `backend/tests/integration/test_admin_offers_router.py::test_compute_endpoint_403_for_pme` : utilisateur non-admin → `POST /api/admin/offers/compute` retourne 403 avec message FR.
- [ ] T043 [P] [US2] Écrire test intégration `backend/tests/integration/test_admin_offers_router.py::test_create_offer_persists_in_draft` : admin appelle `POST /api/admin/offers` avec payload valide → 201 + ligne créée en `publication_status='draft'`, `is_active=false` par défaut, `version='1.0'`, `valid_from=today`.
- [ ] T044 [P] [US2] Écrire test intégration `backend/tests/integration/test_admin_offers_router.py::test_patch_publication_status_blocks_unmet_prerequisites` : offre draft + fund en draft → `PATCH /api/admin/offers/{id}` avec `publication_status='published'` retourne 422 avec `missing_prerequisites=['fund_not_published']`.
- [ ] T045 [P] [US2] Écrire test intégration `backend/tests/integration/test_admin_offers_router.py::test_patch_publication_status_blocks_unverified_source` : offre draft + source en `verification_status='draft'` → `PATCH` retourne 422 avec `missing_prerequisites=['source_not_verified']`.
- [ ] T046 [P] [US2] Écrire test intégration `backend/tests/integration/test_admin_offers_router.py::test_patch_publication_status_succeeds_when_all_ok` : tous prérequis OK → `PATCH` réussit, retourne 200, offre devient `published+active`.

### Implementation US2

- [ ] T047 [US2] Créer le router admin `backend/app/modules/offers/admin_router.py` : endpoints `GET /api/admin/offers`, `POST /api/admin/offers`, `PATCH /api/admin/offers/{id}`, `POST /api/admin/offers/compute`. Tous protégés par dépendance `Depends(require_admin)` (helper F02).
- [ ] T048 [US2] Étendre `backend/app/modules/offers/service.py::create_offer(session, payload, current_user)` : valide qu'aucune offre `(fund_id, intermediary_id, version)` n'existe déjà ; insère ligne en draft ; pas d'audit_log mixin (catalogue exempt).
- [ ] T049 [US2] Étendre `backend/app/modules/offers/service.py::update_offer(session, offer_id, payload, current_user)` : update partiel ; si transition `draft→published` détectée, vérifier prérequis (`fund.publication_status='published'`, `intermediary.publication_status='published'`, `fund_intermediary.accredited_to IS NULL OR > today`, `source.verification_status='verified'`), sinon lever 422 avec `missing_prerequisites`.
- [ ] T050 [US2] Étendre `backend/app/modules/offers/service.py::compute_offer_preview(session, fund_id, intermediary_id) → OfferDraft` : wrapper du calculator + lookup fund_intermediary + suggestion `source_id` depuis `accreditation_source_id`. Lever 404 si fund/intermediary introuvable, 422 si pas de fund_intermediary actif (sauf cas DIRECT).
- [ ] T051 [US2] Enregistrer le router admin dans `backend/app/main.py` (zone protégée, 1 ligne ajoutée `app.include_router(admin_offers_router, prefix="/api", tags=["admin-offers"])`).

**Checkpoint** : tous les tests T041-T046 passent ; un admin peut créer une offre depuis curl.

---

## Phase 5 : User Story 3 — Migration et backfill : zéro perte de données (P1) 🎯

**Goal** : garantir que la migration 028 préserve toutes les données existantes et lie chaque FundApplication à une Offer.

**Independent Test** : Appliquer migration sur base avec données ; vérifier 0 fund_application orpheline.

### Tests US3 (TDD)

- [ ] T052 [P] [US3] Étendre `backend/tests/migrations/test_alembic_028.py::test_backfill_no_orphan_fund_applications` : seed 3 fund_applications avant migration ; après migration, `SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL = 0`.
- [ ] T053 [P] [US3] Étendre `backend/tests/migrations/test_alembic_028.py::test_backfill_creates_offers_for_all_fund_intermediaries` : seed 50 fund_intermediaries ; après migration, count `offers` ≥ 50 + count `funds where access_type='direct'`, toutes en `is_active=false, publication_status='draft'`.
- [ ] T054 [P] [US3] Étendre `backend/tests/migrations/test_alembic_028.py::test_alembic_down_up_idempotent` : `alembic upgrade head; alembic downgrade -1; alembic upgrade head` doit produire counts identiques.
- [ ] T055 [P] [US3] Étendre `backend/tests/migrations/test_alembic_028.py::test_fund_type_enum_values_migrated` : seed funds avec valeurs ancien enum (`international`, `carbon_market`, `local_bank_green_line`) ; après migration, valeurs sont (`multilateral`, `carbon_marketplace`, `private`).
- [ ] T056 [P] [US3] Étendre `backend/tests/migrations/test_alembic_028.py::test_singleton_direct_seeded` : après migration, `SELECT * FROM intermediaries WHERE code='DIRECT'` retourne 1 ligne en `publication_status='published'`.

### Implementation US3

(Déjà couvert par T010 dans Phase 2 — Foundational. Cette phase US3 est essentiellement la validation de la migration via ses tests.)

- [ ] T057 [US3] Documenter le runbook de migration dans `specs/028-entite-offre-fonds-intermediaire/quickstart.md` (déjà fait — section « 1. Appliquer la migration 028 ») et ajouter une note d'avertissement dans `docs/migrations.md` (créer si absent) avec recommandation de backup pre-migration.

**Checkpoint** : tous les tests T052-T056 passent ; on peut migrer une base de prod sans perte.

---

## Phase 6 : User Story 4 — Calcul effectif respecte la sémantique métier (P2)

**Goal** : garantir l'exactitude du calculator sur intersection critères, union documents, somme frais/délais, hint langues.

**Independent Test** : 6 jeux de tests synthétiques avec assertions précises sur chaque champ du draft.

### Tests US4 (TDD)

- [ ] T058 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_intersect_criteria_max_for_min_keys` : fonds `min_company_age=3` + intermediary `min_company_age=5` → résultat 5.
- [ ] T059 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_intersect_criteria_min_for_max_keys` : fonds `max_company_revenue=100M` + intermediary `max_company_revenue=50M` → résultat 50M.
- [ ] T060 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_intersect_criteria_intersection_for_lists` : fonds `sectors=[A,B,C]` + intermediary `sectors=[B,C,D]` → résultat [B, C].
- [ ] T061 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_union_documents_dedup_exact` : 2 docs avec même `(title, source_id)` mais mandatory différents → 1 doc avec `mandatory=true`.
- [ ] T062 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_union_documents_keep_distinct_titles` : 2 docs avec titres différents (« Statuts juridiques » vs « Statuts de l'entreprise ») et même source → 2 docs distincts (pas de fuzzy).
- [ ] T063 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_combine_fees_money_typed_xof_conversion` : fonds frais 0.5% + intermediary doc_fee 50000 XOF + fee_rate 2% → total min/max calculé en Money typed XOF.
- [ ] T064 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_sum_processing_time` : fund timeline 18 mois (= 540 jours) + intermediary processing 90-180 jours → effective 630-720 jours.
- [ ] T065 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_infer_languages_french_country` : intermediary country='SN' → hint=['FR'].
- [ ] T066 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_infer_languages_english_country` : intermediary country='UK' → hint=['EN'].
- [ ] T067 [P] [US4] Étendre `backend/tests/unit/test_offer_calculator.py::test_detect_inconsistency_min_amount_above_max` : fund.min_amount=10M + intermediary.max_amount_per_fund=5M → notes contient « Avertissement : le plafond de l'intermédiaire (5M) est inférieur au minimum du fonds (10M). »

### Implementation US4

(Déjà couvert par T016 dans Phase 2. Les tests US4 sont la validation détaillée.)

**Checkpoint** : tous les tests T058-T067 passent ; couverture calculator ≥ 95 %.

---

## Phase 7 : User Story 5 — Cron quotidien désactive les offres expirées (P2)

**Goal** : garantir la cohérence du catalogue (0 offre publiée avec accréditation expirée).

**Independent Test** : seed accréditation expirée + offre published ; exécuter cron ; vérifier offre désactivée + audit_log enrichi.

### Tests US5 (TDD)

- [ ] T068 [P] [US5] Écrire test intégration `backend/tests/integration/test_check_expired_accreditations.py::test_deactivates_expired_offer` : seed fund_intermediary `accredited_to='2026-04-01'` + offre `published+active` ; exécuter `check_expired_accreditations.run()` ; assert offre devient `draft+inactive`.
- [ ] T069 [P] [US5] Écrire test intégration `backend/tests/integration/test_check_expired_accreditations.py::test_idempotent` : 2 exécutions consécutives → seul 1 audit_log créé.
- [ ] T070 [P] [US5] Écrire test intégration `backend/tests/integration/test_check_expired_accreditations.py::test_keeps_valid_offers_unchanged` : fund_intermediary `accredited_to='2027-01-01'` (futur) → offre reste `published+active`.
- [ ] T071 [P] [US5] Écrire test intégration `backend/tests/integration/test_check_expired_accreditations.py::test_keeps_null_accredited_to_unchanged` : fund_intermediary `accredited_to=NULL` → offre reste `published+active`.
- [ ] T072 [P] [US5] Écrire test intégration `backend/tests/integration/test_check_expired_accreditations.py::test_audit_log_metadata_complete` : assertions sur metadata `{accreditation_source_id, accredited_to, fund_id, intermediary_id}`.

### Implementation US5

- [ ] T073 [US5] Créer le script `backend/scripts/check_expired_accreditations.py` : fonction `async def run()` qui (a) requête `fund_intermediaries WHERE accredited_to < CURRENT_DATE`, (b) pour chaque, find `offers` avec `(fund_id, intermediary_id)` où `is_active=true OR publication_status='published'`, (c) UPDATE `is_active=false, publication_status='draft'`, (d) INSERT audit_log via `app/core/audit_context.set_current_source_of_change('cron_accreditation_expiry')` avec `entity_type='offer', action='auto_unpublished_accreditation_expired', metadata={accreditation_source_id, accredited_to, fund_id, intermediary_id}`. Idempotent. Loggue résultat. Point d'entrée CLI : `if __name__ == '__main__': asyncio.run(run())`.

**Checkpoint** : tous les tests T068-T072 passent ; le cron est exécutable manuellement.

---

## Phase 8 : User Story 6 — Multi-tenant : la liste publique filtre strictement (P3)

**Goal** : garantir 0 fuite de drafts côté API publique.

**Independent Test** : seed 1 published + 5 drafts ; `GET /api/offers` retourne 1 ; `GET /api/admin/offers` (sans auth) retourne 401/403.

### Tests US6 (TDD)

- [ ] T074 [P] [US6] Écrire test sécurité `backend/tests/security/test_offers_publication_filter.py::test_public_endpoint_filters_drafts` : seed 1 published + 5 drafts → `GET /api/offers` retourne `total=1`. SC-007.
- [ ] T075 [P] [US6] Écrire test sécurité `backend/tests/security/test_offers_publication_filter.py::test_public_endpoint_excludes_inactive_published` : seed 1 offre `published+inactive` → `GET /api/offers` retourne 0.
- [ ] T076 [P] [US6] Écrire test sécurité `backend/tests/security/test_offers_publication_filter.py::test_get_offer_404_for_draft` : 1 draft → `GET /api/offers/{id}` retourne 404.
- [ ] T077 [P] [US6] Écrire test sécurité `backend/tests/security/test_offers_publication_filter.py::test_admin_endpoint_403_without_auth` : `GET /api/admin/offers?include_drafts=true` sans JWT → 401 ou 403.
- [ ] T078 [P] [US6] Écrire test sécurité `backend/tests/security/test_offers_publication_filter.py::test_admin_endpoint_403_for_pme_role` : utilisateur PME (non-admin) → 403.

### Implementation US6

(Déjà couvert par T028 et T047 dans Phase 3 et 4 — les filtres `publication_status='published' AND is_active=true` sont implémentés et la dépendance `require_admin` est appliquée. Cette phase US6 est essentiellement la validation par tests sécurité.)

**Checkpoint** : tous les tests T074-T078 passent ; SC-007 satisfait (0 fuite drafts).

---

## Phase 9 : Tools LangChain & Frontend complémentaires

**Purpose** : exposer les nouvelles capacités via LangChain et rendre l'interface utilisateur complète.

### Tests Tools LangChain (TDD)

- [ ] T079 [P] Écrire test intégration `backend/tests/integration/test_financing_tools_offers.py::test_list_offers_tool_returns_published_only` : tool `list_offers` retourne uniquement offres published+active.
- [ ] T080 [P] Écrire test intégration `backend/tests/integration/test_financing_tools_offers.py::test_get_offer_tool_returns_404_for_draft`.
- [ ] T081 [P] Écrire test intégration `backend/tests/integration/test_financing_tools_offers.py::test_compare_offers_for_fund_tool_returns_published_only`.
- [ ] T082 [P] Écrire test intégration `backend/tests/integration/test_financing_tools_offers.py::test_create_fund_application_with_offer_id` : tool étendu accepte `offer_id` et persiste correctement.
- [ ] T083 [P] Écrire test intégration `backend/tests/integration/test_financing_tools_offers.py::test_create_fund_application_legacy_mode_warning` : fallback `fund_id+intermediary_id` ajoute warning et legacy_mode=true dans metadata.
- [ ] T084 [P] Écrire test intégration `backend/tests/integration/test_financing_tools_offers.py::test_tools_are_read_only_on_catalog` : verify aucun tool ne mute funds/intermediaries/offers (snapshot count avant/après).

### Implementation Tools LangChain

- [ ] T085 Étendre `backend/app/graph/tools/financing_tools.py` : ajouter `list_offers` (avec schéma Pydantic `ListOffersInput` + description française). Wrap le service `list_offers` du module offers.
- [ ] T086 Étendre `backend/app/graph/tools/financing_tools.py` : ajouter `get_offer` (avec schéma `GetOfferInput`). Wrap `get_offer` du service.
- [ ] T087 Étendre `backend/app/graph/tools/financing_tools.py` : ajouter `compare_offers_for_fund` (avec schéma `CompareOffersInput`). Wrap `compare_offers_for_fund` du service.
- [ ] T088 Étendre le tool existant `create_fund_application` (probablement dans `backend/app/graph/tools/application_tools.py`) : accepter `offer_id` (priorité) ou `fund_id+intermediary_id` (legacy). Si `offer_id` fourni, dériver `fund_id` et `intermediary_id` depuis l'offre. Si legacy, ajouter warning + `legacy_mode=true` dans metadata audit_log.
- [ ] T089 Mettre à jour `backend/app/graph/tool_selector_config.py` (zone protégée — ajouter 3 entrées dans la config tools du nœud financing + chat). Si zone protégée : signaler `zone_conflict` à l'orchestrateur.
- [ ] T090 [P] Créer le composant `frontend/app/components/financing/FundCard.vue` : Card simplifiée pour vue legacy (utilisée par `pages/financing/index.vue` quand `USE_OFFER_VIEW=false`). Dark mode complet.
- [ ] T091 [P] Créer le composant `frontend/app/components/financing/IntermediaryCard.vue` : Card simplifiée pour pages intermédiaire. Dark mode complet.
- [ ] T092 [P] Créer la page `frontend/app/pages/financing/funds/[fund_id].vue` : SSR fetch fund + offres associées via `useFinancing().getOffer*()`. Affichage `<FundCard>` + liste d'`<OfferCard>` filtrée par fund.
- [ ] T093 [P] Créer la page `frontend/app/pages/financing/intermediaries/[intermediary_id].vue` : SSR fetch intermediary + offres associées. Affichage `<IntermediaryCard>` + liste d'`<OfferCard>` filtrée par intermediary.
- [ ] T094 [P] Créer test composant `frontend/tests/components/EffectiveCriteriaList.spec.ts`.
- [ ] T095 [P] Créer test composant `frontend/tests/components/EffectiveDocumentsList.spec.ts`.
- [ ] T096 [P] Créer test composant `frontend/tests/components/EffectiveFees.spec.ts`.
- [ ] T097 [P] Créer test composant `frontend/tests/components/SubmissionModeBadge.spec.ts`.
- [ ] T098 [P] Créer test composant `frontend/tests/components/FundCard.spec.ts`.
- [ ] T099 [P] Créer test composant `frontend/tests/components/IntermediaryCard.spec.ts`.

**Checkpoint** : tous les tests T079-T084 passent ; les tools sont appelables depuis le chat (test manuel).

---

## Phase 10 : Tests E2E Playwright (obligatoire)

**Purpose** : valider 4 scénarios E2E complets selon SC-010.

### Implementation E2E

- [ ] T100 Créer le fichier `frontend/tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts` avec 4 scénarios :
  - **Scénario 1 — Admin crée offre via calcul auto puis publie** :
    - login en tant qu'admin (helper E2E existant ou créer fixture admin)
    - via API ou UI (curl si UI back-office absente — voir docs/devops-e2e.md), appeler `POST /api/admin/offers/compute?fund_id=X&intermediary_id=Y`
    - vérifier la structure du draft retourné
    - appeler `POST /api/admin/offers` avec payload édité
    - appeler `PATCH /api/admin/offers/{id}` avec `publication_status='published'`
    - login en tant que PME
    - aller sur `/financing/offers/{id}` et vérifier que l'offre s'affiche
  - **Scénario 2 — PME compare 2 offres GCF (BOAD + UNDP)** :
    - seed via fixture : 2 offres GCF (`GCF via BOAD`, `GCF via UNDP`) en `published`
    - login en tant que PME, activer `USE_OFFER_VIEW=true` (env localStorage ou env runtime)
    - aller sur `/financing` et vérifier les 2 Cards Offres distinctes
    - cliquer sur l'une, vérifier la page détail
    - cliquer sur « Comparer avec autres offres pour ce fonds »
    - vérifier le tableau côte-à-côte avec les 2 offres
  - **Scénario 3 — PME tente d'accéder à `/api/admin/offers?include_drafts=true` → 403** :
    - seed 1 offre published + 5 drafts
    - login en tant que PME
    - via `request` Playwright, appeler `GET /api/admin/offers?include_drafts=true` → assert status 403
    - via `request`, appeler `GET /api/offers` → assert `total=1` (filtre publication_status strict)
    - via `request`, appeler `GET /api/offers/{draft_id}` → assert status 404
  - **Scénario 4 — Cron expiration désactive offre → invisible côté PME** :
    - seed fund_intermediary `accredited_to='2026-04-01'` + offre `published+active`
    - login en tant que PME, vérifier que l'offre est visible sur `/financing/offers/{id}`
    - exécuter le cron via `request.post('/api/admin/test/run-cron-check-expired')` (endpoint test-only, ou via shell command si disponible) — sinon via `await page.evaluate()` sur un endpoint stub. Alternative : créer un endpoint test-only `/api/admin/test/check-expired` qui invoke `check_expired_accreditations.run()` et qui n'est exposé qu'en environnement test.
    - rafraîchir `/financing/offers/{id}` → assert 404 (offre désormais draft)
    - via `request`, `GET /api/offers` → assert l'offre n'apparaît plus
- [ ] T101 Tester les 4 scénarios localement : `cd frontend && npx playwright test tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts --reporter=list`. Itérer jusqu'à ce que les 4 scénarios soient verts.

**Checkpoint** : `npx playwright test tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts` passe avec 4/4 scénarios verts.

---

## Phase 11 : Documentation & Polish

**Purpose** : documentation finale, vérifications de couverture, glossaire catalogue.

- [ ] T102 [P] Créer/Mettre à jour `docs/catalog-glossary.md` (créer si absent) : définir clairement les termes `Fund`, `Intermediary`, `FundIntermediary`, `Offer`, `OfferDraft`, expliquer la sémantique `fund_type` vs `intermediary_type`, expliquer le pattern singleton `DIRECT`. Tooltips UI référencent ce glossaire.
- [ ] T103 [P] Créer/Mettre à jour `docs/feature-flags.md` : documenter `USE_OFFER_VIEW` (env var, default false, comportement, plan de bascule post-F14).
- [ ] T104 [P] Créer/Mettre à jour `docs/migrations.md` : ajouter section « Migration 028 — F07 Entité Offre » avec runbook pre/post-migration, vérifications counts, plan de rollback.
- [ ] T105 [P] Mettre à jour `CLAUDE.md` : ajouter ligne dans la section « Active Technologies » (`028-entite-offre-fonds-intermediaire`). **Zone protégée** — modification minimale 1 ligne, signaler `zone_conflict` si conflit.
- [ ] T106 Vérifier la couverture tests backend : `cd backend && pytest tests/ -v --cov=app --cov-report=term-missing | grep "TOTAL"`. Doit être ≥ 80 % sur les modules `app/modules/offers/`, `app/models/financing.py`, `app/graph/tools/financing_tools.py`. Si < 80 %, ajouter tests manquants.
- [ ] T107 Vérifier la couverture tests frontend : `cd frontend && npm run test -- --coverage`. Doit être ≥ 80 % sur les 8 nouveaux composants. Si < 80 %, ajouter tests manquants.
- [ ] T108 Lint backend : `cd backend && source venv/bin/activate && python -m py_compile $(find app -name '*.py')` doit passer sans erreur.
- [ ] T109 Lint frontend : `cd frontend && npm run build` doit passer (typecheck inclus).
- [ ] T110 Vérifier qu'aucun secret n'a été hardcodé : `grep -rE '(api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/ | grep -v test | grep -v node_modules`.

---

## Dépendances entre phases

- **Phase 1 (Setup)** : indépendante, peut commencer en premier.
- **Phase 2 (Foundational)** : dépend de Phase 1. Bloque Phases 3-10. **Plus longue phase, à paralléliser au max.**
- **Phase 3 (US1)**, **Phase 4 (US2)**, **Phase 5 (US3)** : peuvent commencer en parallèle après Phase 2 (3 P1 indépendantes).
- **Phase 6 (US4)** : dépend du calculator (Phase 2/T016) — peut commencer en parallèle avec Phase 3/4/5 dès que T016 est livré.
- **Phase 7 (US5)** : dépend de Phase 2 (modèle Offer + migration). Peut commencer en parallèle.
- **Phase 8 (US6)** : dépend de Phase 3 + Phase 4 (endpoints implémentés). Suit l'ordre.
- **Phase 9 (Tools LangChain & Frontend complémentaire)** : dépend de Phase 2 + Phase 3.
- **Phase 10 (E2E Playwright)** : dépend de Phase 9 (UI complète) + Phase 4 (admin endpoints) + Phase 7 (cron).
- **Phase 11 (Polish)** : dernière phase, après toutes les autres.

## Tâches parallélisables

- T003, T004, T005 (Phase 1) en parallèle.
- T006, T007, T008, T009 (tests Foundational) en parallèle.
- T011, T012, T013, T014, T015 (modèles SQLAlchemy) en parallèle après T010 (migration).
- T016, T017, T018 (calculator, seed, schemas) en parallèle.
- T019-T024 (tests US1) en parallèle.
- T029-T034 (composants Vue) en parallèle.
- T041-T046 (tests US2) en parallèle.
- T052-T056 (tests US3) en parallèle.
- T058-T067 (tests US4) en parallèle (calculator déjà implémenté).
- T068-T072 (tests US5) en parallèle.
- T074-T078 (tests US6 sécurité) en parallèle.
- T079-T084 (tests Tools LangChain) en parallèle.
- T090-T099 (composants frontend complémentaires + tests) en parallèle.
- T102-T105 (docs Polish) en parallèle.

**Total tasks** : 110 (T001-T110).
