# Tasks: F18 — Mobile Money + Photos IA + Données Publiques (avec Consentements)

**Branch**: `feat/F18-mobile-money-photos-ia-public-data` (spec `037`)
**Plan**: [plan.md](plan.md) — **Spec**: [spec.md](spec.md)

Tâches ordonnées par dépendance (TDD : tests AVANT code). Notation `[Px]` = priorité (P1 critique, P2 important, P3 confort).

---

## Phase 0 — Préparation

- **T001** [P1] Configurer environnement venv backend + installer dépendances supplémentaires (`Pillow`, `python-magic`, `chardet` si non présents).
- **T002** [P1] Vérifier état des modules F05 (`require_consent` helper), F01 (sources verified), F02 (`set_rls_context`), F03 (`Auditable`), F04 (`Money`) — créer notes d'adaptation si signatures diffèrent.
- **T003** [P1] Créer dossiers `/uploads/{account_id}/credit/{photos,mobile_money}/` (gitignore + `.gitkeep`).
- **T004** [P1] Seeder dans la migration 037 les sources F01 nécessaires (BCEAO Mobile Money Study, méthodologie scoring crédit Mefali, source IPCC/ADEME pour signaux verts photos) — référencer source_id dans `credit_methodology_factors`.

---

## Phase 1 — Migration & modèles BDD

- **T010** [P1] Tests Alembic round-trip up/down/up sur PostgreSQL test container (RED puis GREEN).
- **T011** [P1] Écrire migration `backend/alembic/versions/037_alternative_credit_data.py` :
  - down_revision=`035_admin_publication_status_workflow`
  - ALTER TYPE `credit_category` ADD VALUE × 3
  - CREATE TABLE × 6 (`mobile_money_imports`, `mobile_money_transactions`, `mobile_money_analyses`, `credit_photos`, `public_data_sources`, `credit_methodology_factors`)
  - CHECK constraints + indexes + UNIQUE
  - RLS ENABLE+FORCE + 2 policies par table tenant
  - Seed `credit_methodology_factors` v1.2 (5 facteurs initiaux) + sources F01 associées
- **T012** [P1] Tests modèles SQLAlchemy : champs, contraintes, FK, multi-tenant, mixin `Auditable`, exemption `MobileMoneyAnalysis` à valider.
- **T013** [P1] Implémenter modèles `app/models/credit_alternative.py` : `MobileMoneyImport`, `MobileMoneyTransaction`, `MobileMoneyAnalysis`, `CreditPhoto`, `PublicDataSource`, `CreditMethodologyFactor`. Ajouter à `AUDITABLE_MODELS` / `EXEMPT_MODELS` selon plan.
- **T014** [P1] Étendre enum Python `CreditCategory` (`backend/app/models/credit.py`) avec `mobile_money_flux`, `photos_ia`, `public_data`.

---

## Phase 2 — Schemas Pydantic

- **T020** [P1] Tests schemas (validations strictes : URL, MIME, taille, énumérations, bornes 0..5 rating, etc.).
- **T021** [P1] Implémenter `schemas/mobile_money.py` (`MobileMoneyImportCreate`, `MobileMoneyImportRead`, `MobileMoneyKpis`, `MobileMoneyAnalysisRead`).
- **T022** [P1] Implémenter `schemas/credit_photo.py` (`CreditPhotoRead`, `PhotoAnalysisResult`, `PhotoQualityStatus` Literal).
- **T023** [P1] Implémenter `schemas/public_data.py` (`PublicDataSourceCreate`, `PublicDataSourceRead`, `SourceType` Literal).
- **T024** [P1] Implémenter `schemas/methodology.py` (`MethodologyFactor`, `MethodologyResponse`, `MethodologyVersion`).

---

## Phase 3 — Garde-fou consentement

- **T030** [P1] Tests `consent_guard.require_consent(account_id, type)` : 403 si absent, OK si actif, retour `ConsentReference` ; mock F05.
- **T031** [P1] Implémenter `app/modules/credit/alternative/consent_guard.py` avec `Depends`-compatible FastAPI ; messages d'erreur structurés `{"error":"consent_required","consent_type":...}`.
- **T032** [P1] Tests d'intégration : appel d'un endpoint sans consent → 403 ; avec consent → 200.

---

## Phase 4 — Mobile Money

### Parsers

- **T040** [P1] Tests parsers (4 fournisseurs, fixtures CSV `tests/fixtures/mobile_money/{wave,om,mtn,moov}.csv`) avec ≥ 95 % lignes valides (SC-002).
- **T041** [P1] Implémenter `mobile_money_parser.py` : détection encodage (chardet), séparateur, mapping colonnes par fournisseur, normalisation `MobileMoneyTransactionRow`, hash counterparty SHA-256.
- **T042** [P1] Tests cas limites : CSV chiffré (rejet), > 5 Mo (rejet), > 50 000 lignes (rejet), encoding non-UTF8 (fallback), doublons (fusion idempotente UNIQUE).

### Analyzer

- **T043** [P1] Tests analyzer KPIs : ≥ 5 KPIs distincts, calculs corrects (volume, écart-type, régularité 30j, solde estimé, tendance 12m, top counterparties anonymisées).
- **T044** [P1] Implémenter `mobile_money_analyzer.py` (calculs purs, déterministes).

### Endpoints

- **T045** [P1] Tests endpoints `/api/credit/mobile-money/upload`, `/analysis`, `/imports` (auth + consent + RLS + audit).
- **T046** [P1] Implémenter `routers/credit_alternative.py` (sous-router monté sur `/api/credit/mobile-money`) avec `Depends(require_consent("mobile_money_analysis"))`.
- **T047** [P1] Storage handler : sauvegarde fichier `/uploads/{account_id}/credit/mobile_money/{uuid}.csv`, permissions 600.

---

## Phase 5 — Méthodologie publique

- **T050** [P1] Tests `methodology_service.list_published_factors()` : filtre publication_status=published + source_id NOT NULL ; SC-010.
- **T051** [P1] Implémenter `methodology_service.py`.
- **T052** [P1] Tests endpoint public `GET /api/credit/methodology` (sans auth, no Bearer).
- **T053** [P1] Implémenter route publique (montée hors `Depends(get_current_user)`).

---

## Phase 6 — Photos IA

### Upload + sécurité

- **T060** [P2] Tests upload : MIME magic bytes (rejet PDF/HEIC/vidéo), taille > 5 Mo (rejet), 11ᵉ photo (rejet), EXIF strip, `content_hash` dedup.
- **T061** [P2] Implémenter handler upload `photo_uploader.py` avec Pillow (strip EXIF) + python-magic + SHA-256.
- **T062** [P2] Tests endpoints `/api/credit/photos/upload`, `/photos`, `/photos/{id}`.
- **T063** [P2] Implémenter routes photos (multipart, multi-fichiers max 10).

### Analyzer Claude Vision

- **T064** [P2] Tests `photo_analyzer.analyze(photo_id)` avec mock OpenRouter Vision : retourne 5 scores + observations + red/green signals + détection `low_quality` ; idempotence (analyse cachée si déjà analysée).
- **T065** [P2] Implémenter `photo_analyzer.py` : prompt français explicite (pas de reconnaissance faciale, pas de description de personnes), parsing JSON robuste, statut qualité.
- **T066** [P2] Tests endpoint `/api/credit/photos/{id}/analyze` : 1ʳᵉ fois → analyse exécutée ; 2ᵉ fois → cache (idempotent) ; quality_status=low_quality → exclu du score.

---

## Phase 7 — Données publiques

- **T070** [P3] Tests `public_data_collector` : validation URL, plafond 5 sources / PME, statuts `declared`/`evidence_attached`/`pending_review`.
- **T071** [P3] Implémenter `public_data_collector.py` (déclaratif, capture optionnelle, hash signaux verts).
- **T072** [P3] Tests endpoints `/api/credit/public-data/declare`, `/public-data`, `/public-data/{id}` (DELETE soft).
- **T073** [P3] Implémenter routes.

---

## Phase 8 — Scoring combiné refactor

- **T080** [P1] Tests `compute_combined_score` : 8 cas (sans / avec MM / avec Photos / avec Public + combinaisons), pondérations dynamiques redistribuées, plafond public ≤ 10 % strict (SC-005).
- **T081** [P1] Implémenter refactor dans `app/modules/credit/service.py` avec lecture `credit_methodology_factors` v courante.
- **T082** [P1] Tests : la version méthodologie est persistée sur chaque ligne `credit_scores`.
- **T083** [P1] Tests : aucun chiffre affiché sans source F01 (audit automatique des réponses API méthodologie + KPIs) — SC-010.

---

## Phase 9 — Hook révocation consentement + purge

- **T090** [P1] Tests hook : événement `consent_revoked(account_id, type)` → marque `unused=true` + `purge_after = now() + 30j` sur entités concernées + recalcul score sans la catégorie.
- **T091** [P1] Implémenter listener (selon API F05 — soit event subscriber, soit polling cron).
- **T092** [P1] Tests cron `scripts/purge_revoked_credit_data.py` (idempotent) : supprime les lignes `purge_after < now()` + fichiers associés.
- **T093** [P1] Implémenter cron + entrée dans la documentation ops.

---

## Phase 10 — LangChain tools (optionnel P3)

- **T100** [P3] Tests tools `get_mobile_money_kpis`, `get_photo_analyses`, `get_public_data_sources` : RLS respecté, retour structuré, pas de mutation.
- **T101** [P3] Implémenter tools dans `app/graph/tools/credit_alternative_tools.py` ; injecter dans nœud `credit` (LangGraph).

---

## Phase 11 — Frontend Nuxt 4

### Types & composables & store

- **T110** [P1] Implémenter `types/creditAlternative.ts` (miroir backend).
- **T111** [P1] Tests Vitest `composables/useCreditAlternativeData.ts` (mocks API).
- **T112** [P1] Implémenter `useCreditAlternativeData.ts` + `useConsent.ts` (extension F05).
- **T113** [P1] Implémenter `stores/creditAlternative.ts` (Pinia).

### Composants

- **T120** [P1] `ConsentRequestModal.vue` (réutilisable) + tests Vitest (dark mode, ARIA dialog, focus trap).
- **T121** [P1] `MobileMoneyUpload.vue` + `MobileMoneyKpiCard.vue` + tests (états vide/loading/erreur, `<SourceLink>`, dark mode).
- **T122** [P2] `PhotoUpload.vue` + `PhotoAnalysisCard.vue` + tests (limite 10, MIME, scores radar/bars, dark mode).
- **T123** [P3] `PublicDataForm.vue` + `PublicDataSourceCard.vue` + tests (validation URL, capture optionnelle, badge « non vérifié »).
- **T124** [P1] `ConsentRevokeButton.vue` + tests (confirmation + appel F05).

### Pages

- **T130** [P1] Refactor `pages/credit-score/index.vue` : 3 sections (MM, Photos, Public) avec gating consentement → modale ; appels store.
- **T131** [P1] `pages/legal/methodology-credit.vue` (no-auth) : version, facteurs, `<SourceLink>` sur sources F01 ; dark mode ; ARIA.

---

## Phase 12 — Tests E2E

- **T140** [P1] Helpers Playwright `frontend/tests/e2e/F18-helpers.ts` (mock backend + consent + upload fixtures).
- **T141** [P1] Spec `frontend/tests/e2e/F18-mobile-money-photos-ia-public-data.spec.ts` (6 scénarios — voir plan §7.3).

---

## Phase 13 — Observabilité & documentation

- **T150** [P2] Logs structurés (compteurs in-memory) : `mm_imports_total`, `photo_analyses_total`, `consent_blocked_total{type}`.
- **T151** [P1] Documentation `docs/credit-alternative-data.md` (architecture, garde-fous, ajout fournisseur MM, troubleshooting).
- **T152** [P1] Mise à jour `CLAUDE.md` (Active Technologies + Recent Changes) après merge.

---

## Phase 14 — Vérification finale

- **T160** [P1] Couverture ≥ 80 % sur modules F18 (backend + frontend).
- **T161** [P1] Round-trip Alembic up/down/up validé sur PostgreSQL.
- **T162** [P1] Aucune régression sur les tests baseline.
- **T163** [P1] Manual smoke-test : 3 user stories P1 (US1, US4, US5) + dark mode + accessibilité (Lighthouse).

---

**Total** : ~70 tâches, 3 sprints, blocages potentiels = signature `require_consent` F05 et disponibilité OpenRouter Vision.
