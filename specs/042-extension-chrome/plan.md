# Implementation Plan: Extension Chrome MV3 — MVP P1 (F24)

**Branch**: `feat/F24-extension-chrome` (numéro 042) | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/042-extension-chrome/spec.md`

## Summary

Livrer une extension Chrome Manifest V3 minimale, chargeable en mode développeur, qui (1) authentifie une PME via un token long-lived dédié extension obtenu en échangeant les identifiants existants F02, (2) détecte automatiquement, via matching côté serveur des `url_patterns` saisis sur Fund/Intermediary, qu'un site visité correspond à une offre cataloguée et affiche un bandeau « Offre détectée » avec lien profond vers l'application principale, et (3) expose dans la popup un dashboard read-only des candidatures actives de l'utilisateur. Backend : 1 migration Alembic 042 (ajout `url_patterns JSONB` sur funds + intermediaries, ajout colonne `scope` sur refresh_tokens, valeur enum `extension` ajoutée à `audit_source`), 1 sous-routeur `app/modules/extension/` avec 4 endpoints REST, et CORS étendu pour `chrome-extension://*`. Extension : nouveau dossier `extension/` à la racine, build Vite + @crxjs/vite-plugin + TypeScript strict, UI Vue 3 + Pinia, tests Vitest avec fakes `chrome.*`. Hors-scope MVP : pré-remplissage de formulaires, panneau latéral, notifications, multi-langue, soumission Chrome Web Store, recommandations multi-référentiels. Tous ces items sont explicitement listés dans la section « Out of scope » de la spec et seront livrés en tickets follow-up P2/P3/P4.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (extension), Vue 3 (extension popup/content)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async, Alembic, Pydantic v2 (existant)
- Extension : Vite ^5, @crxjs/vite-plugin ^2 (HMR Manifest V3), Vue ^3.4, Pinia ^2.1, @types/chrome
**Storage** :
- PostgreSQL 16 + pgvector — migration Alembic 042 minimale (1 nouvelle colonne `url_patterns JSONB` sur `funds`, idem sur `intermediaries`, 1 colonne `scope VARCHAR(20) DEFAULT 'web'` sur `refresh_tokens`, ajout valeur enum `extension` à `audit_source`)
- Extension : `chrome.storage.session` (token bearer, éphémère), `chrome.storage.local` (cache LRU 200 entrées détection, TTL 1 h)
**Testing** :
- Backend : pytest + pytest-asyncio (existant) — couverture ≥ 80 % sur `app/modules/extension/`
- Extension : Vitest avec fakes `chrome.*` via `@types/chrome` + helpers locaux — couverture ≥ 80 % sur api.ts, detector.ts, popup state, token store
- Playwright `--load-extension` : doc setup uniquement en MVP (skip auto-run en CI)
**Target Platform** :
- Backend : Linux server (existant)
- Extension : Chrome 120+ (Manifest V3 requis), Chromium-based browsers
**Project Type** : Web application (backend + frontend Nuxt existants) + nouveau module Browser Extension (`extension/` à la racine)
**Performance Goals** :
- Détection : bandeau affiché en < 2 s après chargement complet de la page (cache chaud) — SC-001
- Auth popup : < 1,5 s sur 4G — SC-003
- Endpoint `/detect` : p95 < 200 ms (matching regex sur ~50 patterns max au catalogue MVP)
**Constraints** :
- Manifest V3 strict : pas de remote code, pas d'`eval`, CSP par défaut, service worker éphémère
- CORS : ajout regex `chrome-extension://.*` dans `app/main.py` (zone `backend/app/core/config.py` à toucher minimalement)
- Multi-tenant F02 : tous les endpoints `/api/extension/v1/*` (sauf `auth/exchange`) appliquent RLS via `Depends(get_current_user)`
- Audit log F03 : nouveau `source_of_change='extension'` middleware ou ContextVar pour les requêtes provenant de l'extension
- Budget tokens shared types : copie manuelle Pydantic→TS en MVP (monorepo workspace différé)
**Scale/Scope** :
- Catalogue MVP : ≤ 50 url_patterns, ≤ 30 fonds publiés
- Utilisateurs simultanés : ≤ 100 PME beta (cohérent avec cap actuel)
- Lignes de code attendues : ~600 LOC backend (module extension + tests), ~1500 LOC extension (TS + Vue + tests)

## Constitution Check

*GATE : Doit passer avant Phase 0 research. Re-check après Phase 1 design.*

### I. Francophone-First & Contextualisation Africaine — ✅ PASS

- UI extension intégralement en français (FR-028).
- Code source en anglais (variables, fonctions, classes, types).
- Commentaires en français, documentation `docs/extension-chrome.md` en français.
- Sites prioritaires seedés couvrent les acteurs régionaux UEMOA (BOAD, SUNREF Ecobank, AFD) en complément des fonds globaux (GCF, PNUD).

### II. Architecture Modulaire — ✅ PASS

- Le Module 8 (Extension Chrome) est explicitement listé dans la constitution comme l'un des 8 modules indépendants.
- L'extension communique avec le backend via le sous-routeur dédié `/api/extension/v1/*` — frontière claire.
- Aucune dépendance circulaire avec Nuxt frontend (l'extension consomme l'API publique uniquement).
- Les types TypeScript sont copiés manuellement (cohérent YAGNI, monorepo différé).

### III. Conversation-Driven UX — ✅ PASS (non-applicable au scope MVP)

- L'extension MVP est read-only (détection + dashboard) ; l'expérience conversationnelle reste dans l'application web.
- Le bandeau « Offre détectée » redirige vers le chat de l'application si l'utilisateur veut approfondir.

### IV. Test-First (NON-NEGOTIABLE) — ✅ PASS

- Cycle TDD respecté : tests Vitest et pytest écrits avant implémentation.
- Couverture ≥ 80 % sur `app/modules/extension/` (backend) et `extension/src/` (logique métier).
- Tests E2E Playwright : doc setup uniquement en MVP (justification YAGNI : le coût d'infra `--load-extension` en CI n'est pas justifié pour un MVP minimal — sera ajouté P2).

### V. Sécurité & Protection des Données — ✅ PASS

- Aucun secret embarqué dans l'extension (FR-026).
- Token bearer en `chrome.storage.session` (éphémère, plus sûr que `local`).
- Toutes les entrées utilisateur validées par Pydantic v2 strict côté backend.
- CORS limité à `chrome-extension://*` + origines existantes.
- Sanitisation anti-XSS du bandeau injecté (FR-025).
- Pas de collecte DOM des sites externes en MVP (FR-012).
- Audit log F03 enrichi avec `source_of_change='extension'` (FR-027).
- Multi-tenant F02 via RLS PostgreSQL (FR-019).

### VI. Inclusivité & Accessibilité — ✅ PASS

- Bandeau affiché avec ARIA `role="status"` + `aria-live="polite"`, bouton fermeture clavier-accessible.
- Popup : labels `aria-label` sur tous les inputs, focus-trap natif HTML.
- Messages d'erreur en français clairs et actionnables.
- Optimisation assets : Vite + minification + tree-shaking par défaut.

### VII. Simplicité & YAGNI — ✅ PASS

- Aucune nouvelle table en MVP (réutilisation `refresh_tokens` F02 avec colonne `scope`).
- Pas de panneau latéral, pas de pré-remplissage, pas de notifications, pas de multi-langue MVP.
- Stack identique au frontend Nuxt (Vue 3 + Pinia) — pas d'écosystème dupliqué.
- Cache détection via `chrome.storage.local` natif (pas de IndexedDB ni Service Worker complexe).
- Tests E2E `--load-extension` différés : doc setup uniquement.

**Verdict** : ✅ Tous les principes validés. Aucune dérogation requise. Section Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/042-extension-chrome/
├── plan.md              # Ce fichier (sortie /speckit.plan)
├── spec.md              # Spec fonctionnelle
├── research.md          # Phase 0 (recherche technique MV3 + crxjs + Vite + auth bearer)
├── data-model.md        # Phase 1 (entités enrichies : Fund.url_patterns, Intermediary.url_patterns, RefreshToken.scope, AuditSource enum)
├── quickstart.md        # Phase 1 (setup dev + chargement extension Chrome dev mode)
├── contracts/           # Phase 1 (4 endpoints OpenAPI fragments)
│   ├── auth-exchange.md
│   ├── profile-snapshot.md
│   ├── detect.md
│   └── applications-active.md
├── checklists/
│   └── requirements.md  # Validation qualité spec (déjà créé)
└── tasks.md             # Phase 2 (sortie /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
└── app/
    ├── modules/
    │   └── extension/                # NOUVEAU
    │       ├── __init__.py
    │       ├── router.py             # 4 endpoints REST /api/extension/v1/*
    │       ├── service.py            # Logique de matching url_patterns + lookup offers
    │       ├── schemas.py            # Pydantic v2 strict (DetectRequest, DetectResponse, ProfileSnapshot, ActiveApplicationItem, AuthExchangeRequest, AuthExchangeResponse)
    │       └── dependencies.py       # Dependency get_current_extension_user (vérifie scope='extension' du token)
    ├── models/
    │   ├── fund.py                   # ENRICHI : ajout colonne url_patterns JSONB
    │   ├── intermediary.py           # ENRICHI : ajout colonne url_patterns JSONB
    │   └── refresh_token.py          # ENRICHI : ajout colonne scope (web|extension)
    ├── main.py                       # ENRICHI : montage extension_router + CORS chrome-extension://*
    └── core/
        └── audit_source.py           # ENRICHI : ajout valeur enum 'extension'

backend/alembic/versions/
└── 042_extension_url_patterns.py    # NOUVEAU — migration up/down + seed 5 patterns + valeur enum

extension/                            # NOUVEAU dossier à la racine du repo
├── manifest.json                     # MV3, permissions: storage, activeTab, scripting; host_permissions: <all_urls>
├── _locales/
│   └── fr/
│       └── messages.json             # i18n FR uniquement MVP
├── package.json                      # vite, @crxjs/vite-plugin, vue, pinia, vitest, @types/chrome, typescript
├── tsconfig.json                     # strict mode
├── vite.config.ts                    # config crxjs
├── public/
│   └── icons/                        # 16/48/128 px PNG (placeholder logo Mefali)
├── src/
│   ├── background/
│   │   └── service_worker.ts         # Auth state + dispatch detect requests + cache LRU
│   ├── content/
│   │   ├── detector.ts               # Émet detect message au service worker, gère cache local + LRU
│   │   └── overlay.ts                # Inject bandeau "Offre détectée" + sanitisation DOM
│   ├── popup/
│   │   ├── index.html
│   │   ├── main.ts                   # Bootstrap Vue + Pinia
│   │   ├── App.vue                   # Composant root popup (login | dashboard)
│   │   └── components/
│   │       ├── LoginForm.vue
│   │       ├── ApplicationsList.vue
│   │       └── EmptyState.vue
│   ├── stores/
│   │   ├── auth.ts                   # Pinia store : token, user, login(), logout()
│   │   └── applications.ts           # Pinia store : fetchActive()
│   ├── shared/
│   │   ├── api.ts                    # Client fetch wrapper + bearer + 401 handler
│   │   ├── types.ts                  # Mirror Pydantic types (copie manuelle MVP)
│   │   ├── i18n.ts                   # Wrapper chrome.i18n.getMessage avec fallback FR
│   │   └── lru.ts                    # Map LRU bornée 200 entrées + TTL
│   └── styles/
│       └── overlay.css               # Styles inline-friendly pour bandeau injecté
└── tests/
    ├── api.spec.ts
    ├── lru.spec.ts
    ├── detector.spec.ts
    ├── auth-store.spec.ts
    └── overlay.spec.ts

docs/
└── extension-chrome.md               # NOUVEAU — guide chargement dev mode + architecture + flux auth + dépannage
```

**Structure Decision** : Web application (backend + Nuxt frontend existants) avec un nouveau module sœur `extension/` à la racine, indépendant du frontend Nuxt. Les types TS sont copiés manuellement de Pydantic en MVP — un workspace pnpm partagé `packages/shared-types` est différé en post-MVP (justification : YAGNI, le coût d'orchestration npm/pnpm workspace dépasse le bénéfice avec ~5 types partagés).

## Complexity Tracking

> Aucune dérogation requise — toutes les portes Constitution passent.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (aucune) | (n/a) | (n/a) |

## Phase 0 — Research (livrable : research.md)

Sujets à éclaircir avant Phase 1 :

1. **@crxjs/vite-plugin maturité MV3** — versions stables, support HMR service worker, compatibilité Vue 3 SFC.
2. **Manifest V3 CSP** — directives `script-src` autorisées, comment injecter overlay sans inline scripts.
3. **Auth bearer long-lived** — réutilisation `refresh_tokens` F02 vs JWT dédié, rotation, révocation.
4. **CORS `chrome-extension://`** — regex correcte pour `allow_origin_regex` FastAPI, traitement preflight.
5. **Storage Chrome** — différences `session` vs `local`, quotas, latence.
6. **Audit log enrichi `extension`** — comment cabler le ContextVar `source_of_change='extension'` sur les requêtes du module extension.
7. **LRU TTL minimal** — implémentation Map borné en TypeScript ≤ 50 LOC.

## Phase 1 — Design & Contracts (livrables : data-model.md, contracts/, quickstart.md)

### Data Model (livré dans data-model.md)

- **Fund** (existante F07) : ajout `url_patterns: JSONB` (liste d'objets `{pattern: string, scope: "homepage" | "submission_portal"}`)
- **Intermediary** (existante F07) : idem
- **RefreshToken** (existante F02) : ajout `scope: VARCHAR(20) DEFAULT 'web' NOT NULL CHECK (scope IN ('web','extension'))`
- **audit_source** (enum F03) : ajout valeur `'extension'`
- Pas de nouvelle table.

### Contracts (livrés dans contracts/)

1. **POST `/api/extension/v1/auth/exchange`** — body `{email, password}` → `{access_token, refresh_token, scope:'extension', expires_in:2592000}`. Errors : 401 (creds invalides), 429 (rate limit).
2. **GET `/api/extension/v1/me/profile-snapshot`** — bearer requis → `{sector, country, projects:[{id, name, status}]}` (max 3).
3. **POST `/api/extension/v1/detect`** — bearer requis, body `{url}` → 200 `{offer_id, offer_name, source_id?, confidence}` ou 204.
4. **GET `/api/extension/v1/applications/active`** — bearer requis → `[{id, offer_name, status, status_label_fr, updated_at, deep_link}]` (max 50, tri date desc).

### Quickstart (livré dans quickstart.md)

- Pré-requis : Node ≥ 20, pnpm, Chrome 120+
- `cd extension && pnpm install && pnpm dev` → génère `extension/dist/`
- Chrome → `chrome://extensions` → mode développeur → « Charger l'extension non empaquetée » → sélectionner `extension/dist/`
- Lancer backend dev `uvicorn app.main:app --reload` (port 8000)
- Test US1 : ouvrir popup, login `pme.test@mefali.dev / Test123!`
- Test US2 : naviguer sur `https://sunref.boad.org/` → vérifier bandeau
- Test US3 : ouvrir popup → vérifier liste candidatures
- Test US4 : profil Chrome neuf → ouvrir popup → vérifier écran « Connectez-vous d'abord »

### Agent context update

- Ajouter au CLAUDE.md (section « Active Technologies » bullet F24) : `Python 3.12 (backend) ; TypeScript 5.x strict + Vue 3 + Pinia + Vite + @crxjs/vite-plugin (extension Chrome MV3)`.

## Phase 2 (hors-scope `/speckit.plan`) — Tasks

`/speckit.tasks` génère `tasks.md` avec ≤ 60 tâches structurées en :

- Setup (T001-T005) : branche, dépendances, dossier `extension/`, `vite.config.ts`, scripts npm
- Backend Phase A (T006-T020) : migration 042, modèles, schemas, service, router, tests pytest
- Extension Phase B (T021-T040) : manifest, build, popup, content scripts, stores, api client, tests Vitest
- Documentation & QA (T041-T050) : `docs/extension-chrome.md`, quickstart, validation manuelle 5 sites
- Cleanup (T051-T055) : couverture, lint, audit logs check, round-trip Alembic
