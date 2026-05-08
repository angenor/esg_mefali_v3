---
description: "Task list — F24 Extension Chrome MV3 (MVP P1)"
---

# Tasks: Extension Chrome MV3 — MVP P1 (F24)

**Input**: Design documents from `/specs/042-extension-chrome/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Branche** : `feat/F24-extension-chrome` (numéro 042)

## Format: `[ID] [P?] [Story] Description`

- **[P]** : peut tourner en parallèle (fichiers indépendants)
- **[USx]** : story de référence
- TDD strict : tests avant implémentation pour chaque sous-bloc

---

## Phase 1 — Setup (T001-T005)

- [ ] T001 Vérifier branche `feat/F24-extension-chrome` active et HEAD à jour avec main (`git status` propre, base 6f63fe1)
- [ ] T002 Créer le dossier racine `extension/` avec arborescence : `extension/src/{background,content,popup,stores,shared,styles}`, `extension/_locales/fr/`, `extension/public/icons/`, `extension/tests/`
- [ ] T003 [P] Initialiser `extension/package.json` avec dépendances (`vite ^5`, `@crxjs/vite-plugin ^2`, `vue ^3.4`, `pinia ^2.1`, `@vitejs/plugin-vue`, `typescript ^5`, `@types/chrome`, `vitest`, `@vitest/coverage-v8`, `jsdom`)
- [ ] T004 [P] Créer `extension/tsconfig.json` (mode strict, target ES2022, module ESNext, types `chrome` + `vite/client`)
- [ ] T005 [P] Créer `extension/vite.config.ts` avec `@crxjs/vite-plugin` lisant `manifest.json`, plugin Vue, alias `@/` → `src/`, build target `extension/dist/`

---

## Phase 2 — Backend (Phase A) : migration + module extension (T006-T030)

**Objectif** : livrer la migration 042 et le sous-routeur `/api/extension/v1/*` avec couverture pytest ≥ 80 %.

### 2.1 Migration & modèles (TDD)

- [ ] T006 [P] [US1,US2,US3] Test pytest `backend/tests/migrations/test_042_extension_url_patterns.py` : valider présence colonnes `funds.url_patterns`, `intermediaries.url_patterns`, `refresh_tokens.scope`, valeur enum `audit_source.extension`, round-trip up/down/up sur PostgreSQL et SQLite (FR-022, FR-023, SC-010)
- [ ] T007 [US1,US2,US3] Créer `backend/alembic/versions/042_extension_url_patterns.py` (down_revision=`041_dossiers_offre`) : ALTER TABLE `funds` ADD COLUMN `url_patterns JSONB DEFAULT '[]'`, idem `intermediaries`, ALTER TABLE `refresh_tokens` ADD COLUMN `scope VARCHAR(20) DEFAULT 'web' NOT NULL` + CHECK constraint, ALTER TYPE `audit_source` ADD VALUE `'extension'` (PG-only via `op.get_bind().dialect.name == 'postgresql'`), seed UPSERT 5 url_patterns prioritaires (FR-022, FR-023)
- [ ] T008 [P] [US1] Étendre `backend/app/models/refresh_token.py` avec colonne `scope: Mapped[str]` + import enum, valeur par défaut `'web'`
- [ ] T009 [P] [US2] Étendre `backend/app/models/fund.py` et `backend/app/models/intermediary.py` avec colonne `url_patterns: Mapped[list[dict]]` (JSONB)
- [ ] T010 [P] [US1,US2] Étendre `backend/app/core/audit_source.py` (ou enum équivalent) avec valeur `EXTENSION = "extension"` (FR-027)

### 2.2 Schémas Pydantic v2 (TDD)

- [ ] T011 [P] [US1] Test `backend/tests/modules/extension/test_schemas.py::test_auth_exchange_request_strict` : rejet de champ extra, email valide, password ≥ 8 chars
- [ ] T012 [P] [US2] Test `backend/tests/modules/extension/test_schemas.py::test_detect_request_strict` : rejet URL malformée, max 2000 chars
- [ ] T013 [P] [US1,US2,US3] Créer `backend/app/modules/extension/schemas.py` avec `AuthExchangeRequest`, `AuthExchangeResponse`, `DetectRequest`, `DetectResponse`, `ProfileSnapshot`, `ProjectSnapshotItem`, `ActiveApplicationItem`, `FundUrlPattern` (Pydantic v2 strict, `extra='forbid'`)

### 2.3 Service de matching url_patterns (TDD)

- [ ] T014 [US2] Test `backend/tests/modules/extension/test_service.py::test_match_url_patterns_single_match` : un pattern matche → confidence 1.0, retourne offer_id correct
- [ ] T015 [US2] Test `backend/tests/modules/extension/test_service.py::test_match_url_patterns_no_match` : aucune URL ne matche → renvoie `None`
- [ ] T016 [US2] Test `backend/tests/modules/extension/test_service.py::test_match_url_patterns_multi_match_priority_direct` : plusieurs matches, priorité au couple intermediary `code='DIRECT'` (cf. F07)
- [ ] T017 [US2] Test `backend/tests/modules/extension/test_service.py::test_match_url_patterns_invalid_regex_skipped` : un pattern invalide est silencieusement skipé (log warning) sans planter le matching
- [ ] T018 [US2] Test `backend/tests/modules/extension/test_service.py::test_match_url_patterns_only_published_offers` : ignore offres `publication_status != 'published'` (FR-009)
- [ ] T019 [US2] Créer `backend/app/modules/extension/service.py` avec `match_url(db, url: str) -> DetectResponse | None` : SELECT offers published + funds + intermediaries, compile patterns, teste, applique priorité DIRECT, retourne DetectResponse ou None (FR-007, FR-018, FR-021)
- [ ] T020 [P] [US3] Créer fonction `list_active_applications(db, account_id) -> list[ActiveApplicationItem]` dans `service.py` : query FundApplication WHERE status NOT IN ('approved','rejected','disbursed','cancelled'), tri updated_at desc, limit 50, mapping status→status_label_fr (FR-013, FR-015)
- [ ] T021 [P] [US3] Créer fonction `build_profile_snapshot(db, user) -> ProfileSnapshot` : sector + country du CompanyProfile + 3 derniers projets actifs (clarification spec)

### 2.4 Auth & dépendances (TDD)

- [ ] T022 [US1] Test `backend/tests/modules/extension/test_auth.py::test_exchange_creates_extension_scoped_refresh_token` : POST /auth/exchange avec creds valides → 200, row inséré avec `scope='extension'`
- [ ] T023 [US1] Test `backend/tests/modules/extension/test_auth.py::test_exchange_invalid_credentials_returns_401` (FR-001, FR-006)
- [ ] T024 [US1,US2,US3] Créer `backend/app/modules/extension/dependencies.py` avec `get_current_extension_user`: vérifie bearer + décode JWT + valide `scope='extension'` (FR-019)

### 2.5 Router & middleware audit (TDD)

- [ ] T025 [US1,US2,US3] Test `backend/tests/modules/extension/test_router.py::test_all_endpoints_require_bearer` : 401 sans header Authorization (sauf /auth/exchange)
- [ ] T026 [US2] Test `backend/tests/modules/extension/test_router.py::test_detect_returns_204_on_no_match`
- [ ] T027 [US3] Test `backend/tests/modules/extension/test_router.py::test_applications_active_filters_inactive_statuses` (FR-013)
- [ ] T028 [US1,US2,US3] Créer `backend/app/modules/extension/router.py` avec 4 endpoints (`/auth/exchange`, `/me/profile-snapshot`, `/detect`, `/applications/active`) prefix `/api/extension/v1` ; appliquer `Depends(get_current_extension_user)` sauf sur `/auth/exchange` (FR-017, FR-019)
- [ ] T029 [US1,US2,US3] Modifier `backend/app/main.py` : (a) inclure `extension_router`, (b) ajouter `chrome-extension://.*` à `allow_origin_regex` du CORSMiddleware, (c) monter `ExtensionAuditContextMiddleware` (set ContextVar `current_source_of_change='extension'` pour les requêtes `/api/extension/*`) — pattern identique à `AdminAuditContextMiddleware` F03 (FR-020, FR-027)
- [ ] T030 [US1,US2,US3] Test integration `backend/tests/modules/extension/test_audit_context.py` : appel à `/api/extension/v1/applications/active` génère un audit log entry avec `source_of_change='extension'`

---

## Phase 3 — Extension (Phase B) : MV3 squelette + features (T031-T055)

**Objectif** : extension chargeable Chrome dev mode, 4 user stories fonctionnelles, couverture Vitest ≥ 80 %.

### 3.1 Manifest & i18n

- [ ] T031 [P] [US1,US2,US3,US4] Créer `extension/manifest.json` (Manifest V3) : name, version 0.1.0, description FR, default_locale `fr`, permissions `["storage","activeTab","scripting"]`, host_permissions `["<all_urls>"]`, background.service_worker `src/background/service_worker.ts`, content_scripts matching `<all_urls>` avec `src/content/detector.ts`, action.default_popup `src/popup/index.html`, icons 16/48/128 (FR-024)
- [ ] T032 [P] [US1,US4] Créer `extension/_locales/fr/messages.json` : clés `app_name`, `popup_login_title`, `popup_login_email`, `popup_login_password`, `popup_login_submit`, `popup_login_error_invalid`, `popup_logged_out_title`, `popup_register_link`, `dashboard_empty_state`, `dashboard_status_*`, `overlay_offer_detected`, `overlay_view_button`, `overlay_close_button`, `overlay_source_link` (FR-028)
- [ ] T033 [P] Créer placeholders icônes `extension/public/icons/icon-{16,48,128}.png` (logo Mefali ou placeholder vert)

### 3.2 Shared utilities (TDD)

- [ ] T034 [P] [US1,US2,US3] Test `extension/tests/lru.spec.ts` (Vitest) : LRU bornée 200, éviction FIFO, TTL 1 h expiration (FR-008)
- [ ] T035 [P] [US1,US2,US3] Implémenter `extension/src/shared/lru.ts` (≤ 50 LOC, Map ordonnée + timestamp expires_at)
- [ ] T036 [P] [US1,US2,US3] Test `extension/tests/api.spec.ts` : wrapper fetch ajoute Bearer header, retourne JSON, sur 401 émet event `auth:expired`, sur réseau down rejette `NetworkError` (FR-005, FR-006)
- [ ] T037 [P] [US1,US2,US3] Implémenter `extension/src/shared/api.ts` : fonction `apiFetch(path, opts)` avec injection bearer depuis `chrome.storage.session`, base URL configurable via `import.meta.env.VITE_API_BASE_URL` (default `http://localhost:8000`)
- [ ] T038 [P] [US1,US2,US3] Créer `extension/src/shared/types.ts` : copies manuelles des types Pydantic (DetectResponse, AuthExchangeResponse, ProfileSnapshot, ActiveApplicationItem)
- [ ] T039 [P] [US1,US4] Créer `extension/src/shared/i18n.ts` : wrapper `t(key, fallback)` autour de `chrome.i18n.getMessage` (FR-028)

### 3.3 Auth store (TDD US1, US4)

- [ ] T040 [US1,US4] Test `extension/tests/auth-store.spec.ts` : `login(email, pwd)` appelle /auth/exchange, stocke token via `chrome.storage.session.set({extension_token})`, met `state.user`, `state.isAuthenticated=true`. `logout()` clear storage + révoque côté serveur. `loadFromStorage()` au boot popup (FR-001 à FR-006)
- [ ] T041 [US1,US4] Implémenter `extension/src/stores/auth.ts` (Pinia) : state `{token, user, status}`, actions `login`, `logout`, `loadFromStorage`, listener `auth:expired` → clear

### 3.4 Popup (TDD US1, US3, US4)

- [ ] T042 [P] [US1,US4] Test `extension/tests/popup-login.spec.ts` (component test Vitest + @vue/test-utils) : `LoginForm.vue` valide email + password, soumet sur Enter, affiche error sur 401
- [ ] T043 [P] [US3] Test `extension/tests/popup-applications.spec.ts` : `ApplicationsList.vue` affiche statuts français, max 50 entrées, état vide affiché si liste vide (FR-013, FR-015)
- [ ] T044 [US1,US4] Créer `extension/src/popup/index.html` + `extension/src/popup/main.ts` (bootstrap Vue+Pinia)
- [ ] T045 [US1,US4] Créer `extension/src/popup/App.vue` (root) — switch `LoginForm` vs `ApplicationsList` selon `auth.isAuthenticated`
- [ ] T046 [US1,US4] Créer `extension/src/popup/components/LoginForm.vue` avec inputs email + password, bouton soumettre, message d'erreur FR, lien « Pas encore de compte ? » → `chrome.tabs.create({url: register_url})` (FR-001, US4)
- [ ] T047 [US3] Créer `extension/src/popup/components/ApplicationsList.vue` + `EmptyState.vue` ; chaque ligne ouvre `application.deep_link` dans nouvel onglet ; libellés statuts via i18n (FR-013, FR-014, FR-015, FR-016)
- [ ] T048 [US3] Créer `extension/src/stores/applications.ts` (Pinia) : action `fetchActive()` + state `{items, loading, error}`

### 3.5 Background service worker (TDD US2)

- [ ] T049 [US2] Test `extension/tests/service-worker.spec.ts` : message `DETECT_URL` → consulte cache LRU local → si miss, appelle `/detect` → cache 1 h → retourne payload au content script (FR-007, FR-008)
- [ ] T050 [US2] Implémenter `extension/src/background/service_worker.ts` : listener `chrome.runtime.onMessage`, dispatch DETECT_URL avec gestion cache LRU stockée dans `chrome.storage.local`, no-op si pas authentifié (FR-009)

### 3.6 Content scripts : detector + overlay (TDD US2)

- [ ] T051 [US2] Test `extension/tests/detector.spec.ts` : sur load page, envoie message DETECT_URL au SW avec `window.location.href`, sur réponse appelle overlay si confidence ≥ 0.8 (FR-009)
- [ ] T052 [US2] Implémenter `extension/src/content/detector.ts` : send message au SW au `window.addEventListener('load')` + sur `popstate` (SPA navigation), guard `sessionStorage` pour ne pas réafficher après fermeture manuelle (FR-011)
- [ ] T053 [US2] Test `extension/tests/overlay.spec.ts` : `injectOverlay(payload)` crée éléments via `document.createElement` + `textContent` (anti-XSS), bouton fermeture supprime + persiste fermeture en sessionStorage, lien source ouvre `<app_url>/sources/<source_id>` (FR-010, FR-011, FR-025)
- [ ] T054 [US2] Implémenter `extension/src/content/overlay.ts` + `extension/src/styles/overlay.css` : bandeau top fixed, ARIA `role="status"` + `aria-live="polite"`, dark mode neutre (couleurs Mefali emerald), sanitisation stricte (FR-010, FR-025)
- [ ] T055 [US2] Test E2E manuel documenté : naviguer sur `https://sunref.boad.org/`, `https://greenclimate.fund/`, `https://afd.fr/`, `https://undp.org/africa`, `https://ecobank.com/sunref` → bandeau s'affiche avec lien correct (SC-001)

---

## Phase 4 — Documentation & validation manuelle (T056-T058)

- [ ] T056 [US1,US2,US3,US4] Créer `docs/extension-chrome.md` : architecture (popup / content / SW), flux auth, modèle de menaces, dépannage CORS, procédure ajout `url_patterns` (SQL/seed MVP), procédure mise à jour version, setup Playwright `--load-extension` (doc only, skip CI MVP)
- [ ] T057 [US1,US2,US3,US4] Mettre à jour `CLAUDE.md` section « Active Technologies » avec entrée F24 : `Python 3.12 (backend) ; TypeScript 5.x strict + Vue 3 + Pinia + Vite + @crxjs/vite-plugin (extension Chrome MV3)` et ligne « Recent Changes » résumé F24 MVP P1
- [ ] T058 [US1,US2,US3,US4] Validation manuelle SC-009 : un développeur charge l'extension en mode dev et reproduit US1+US2+US3+US4 en < 10 min suivant `docs/extension-chrome.md`

---

## Phase 5 — Cleanup & coverage (T059-T060)

- [ ] T059 Vérifier round-trip Alembic `up/down/up` sur PostgreSQL (`alembic downgrade -1 && alembic upgrade head`), vérifier couverture pytest ≥ 80 % sur `backend/app/modules/extension/`, vérifier 0 régression (`pytest tests/`) (SC-006, SC-008, SC-010)
- [ ] T060 Vérifier couverture Vitest ≥ 80 % sur `extension/src/{shared,stores,content,background}` (`pnpm test --coverage`), lint TypeScript strict sans erreur, build production OK (`pnpm build` génère `extension/dist/` sans warning critique) (SC-005, SC-007)

---

## Dependency graph (résumé)

- T006-T010 (migration + modèles) : pré-requis pour T011-T030
- T011-T013 (schemas) : pré-requis pour T014-T030
- T014-T021 (services) : pré-requis pour T022-T030
- T022-T030 (auth + router) : déblouqent les tests E2E manuels US1-US3
- Phase 3 (extension) dépend uniquement des contracts (peut démarrer en parallèle Phase 2.4-2.5 une fois schemas T013 figés)
- Phase 4-5 : après Phases 2 + 3 complètes

## Parallel execution opportunities

- T003, T004, T005 indépendants
- T008, T009, T010 indépendants (modèles différents)
- T011, T012 indépendants (schemas différents)
- T014-T021 dans un même fichier (`service.py`) → séquentiels mais tests sur fichiers de tests séparés
- T031, T032, T033 indépendants (manifest, locales, icônes)
- T034, T036, T038, T039 indépendants (utilities différents)
- T042 et T043 sur composants Vue différents → parallèles

## MVP scope reminder

US1 (auth) + US2 (détection) + US3 (dashboard) + US4 (onboarding) = MVP P1 complet, tous P1.
Aucun report de US dans une phase ultérieure ; tout est P1 pour ce ticket.

**Total : 60 tâches**.
