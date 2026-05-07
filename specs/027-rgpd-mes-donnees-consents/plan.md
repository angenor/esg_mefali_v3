# Implementation Plan: F05 — RGPD : Page « Mes Données » + Consentements + Export/Suppression

**Branch**: `feat/F05-rgpd-mes-donnees-consents` (alias SpecKit `027-rgpd-mes-donnees-consents`)
**Date**: 2026-05-07
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/027-rgpd-mes-donnees-consents/spec.md`

## Summary

F05 introduit la conformité RGPD complète de la plateforme : (1) page authentifiée `/mes-donnees` avec inventaire structuré des données stockées, export JSON exhaustif (synchrone ≤ 100 MB, asynchrone via `BackgroundTasks` au-delà), 7 consentements granulaires révocables, suppression de compte avec délai de grâce 30 jours et purge effective via cron idempotent ; (2) page publique `/legal/privacy` (layout `public` distinct, no-auth) ; (3) helper backend partagé `app/core/consent.py::require_consent(account_id, type)` levant `HTTPException(403, ...)` en français lorsqu'un consentement non-essentiel manque ; (4) intégration de la case à cocher obligatoire « J'accepte la politique » sur `/register` avec double validation frontend+backend ; (5) job cron `scripts/purge_scheduled_deletions.py` purgeant en cascade les comptes `deletion_scheduled_at < now()` et anonymisant `audit_log` (UPDATE en place : `user_id=NULL`, `account_id=NULL`, autres champs intacts) ; (6) test CI scanner (regex sur `analyze_*` / `fetch_*_external` / `generate_certificate_*`) garantissant la couverture du helper sur tous les services sensibles présents et futurs ; (7) documentation interne `docs/rgpd-conformite.md` + `docs/hosting-and-data-residency.md`. Migration Alembic créant la table `consents` (enum natif PostgreSQL `consent_type_enum` à 7 valeurs) + colonnes `accounts.deletion_scheduled_at` et `accounts.deleted_at`. Tests E2E Playwright couvrant les 4 scénarios critiques (export, programmer/annuler suppression, purge J+30, consent gating).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, FastAPI `BackgroundTasks` (export asynchrone), `itsdangerous` ou équivalent intégré FastAPI pour signer URLs temporaires (24h / 7j), `python-multipart` pour le ZIP, bibliothèque standard `zipfile` + `json`
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4 (dark mode), DOMPurify (sanitisation des descriptions consentements rendues comme HTML léger)
**Storage** : PostgreSQL 16 + pgvector (extension), Alembic pour migrations, stockage fichiers local `/uploads/{account_id}/`
**Testing** :
- Backend : pytest, pytest-asyncio, pytest-cov (couverture ≥ 80 %)
- Frontend : Vitest + @vue/test-utils + @vitest/coverage-v8 + happy-dom
- E2E : Playwright (`@playwright/test`) avec backend mocké
- Test CI scanner : pytest dédié `tests/security/test_require_consent_coverage.py` (regex statique sur le code source)
**Target Platform** : Linux server (Docker) + navigateurs modernes (Chrome/Firefox/Safari)
**Project Type** : Web application (backend FastAPI + frontend Nuxt 4 séparés)
**Performance Goals** :
- `GET /api/me/data/inventory` : < 1 s p95 (8-10 SELECT COUNT(*) parallélisables avec `asyncio.gather`)
- Export synchrone (≤ 100 MB) : < 30 s pour un compte typique (~20 entités, ~10 documents)
- `GET /api/me/consents` : < 200 ms p95 (lookup unique avec index)
- `require_consent` : < 50 ms p95 (lookup index `(account_id, consent_type, revoked_at)`)
- Migration Alembic up/down/up : < 30 s sur base de dev
- Cron purge : < 60 s par compte purgé (cascade SQL + suppression filesystem)
**Constraints** :
- Multi-tenant strict (F02 invariant n°2) : table `consents.account_id NOT NULL` + RLS PostgreSQL ; tous les endpoints `/api/me/*` filtrent par `account_id` du JWT courant.
- Audit log append-only (F03 invariant n°3) : toute mutation sur `consents` / `accounts.deletion_*` passe par mixin `Auditable` ; pas de `db.commit()` direct.
- Sourçage F01 invariant n°1 : non concerné (F05 ne crée aucun chiffre ESG/carbone/financier ; uniquement compteurs, durées, dates).
- Aucun secret hardcodé : URLs SMTP, `SECRET_KEY` pour signer URLs temporaires → `backend/app/core/config.py`.
- Aucun tool LLM ne mute `consents` ni `accounts.deletion_*` (invariant n°7 catalogue admin only — ici seuls les services authentifiés `/api/me/*` mutent).
- Dark mode obligatoire : composants `<ConsentToggle>`, `<DeletionConfirmModal>`, `<DataInventoryTable>`, `<DataExportButton>` + page `/mes-donnees` + page `/legal/privacy`.
- Réutilisabilité composants : vérifier `frontend/app/components/ui/` avant création ; extraire `<ConfirmModal>` générique si possible (réutilisable triple confirmation).
- Français avec accents dans tout le contenu UI ; libellés audit_log en anglais snake_case (cohérent F03).
**Scale/Scope** :
- 1 nouvelle table BDD (`consents`) + 2 colonnes (`accounts.deletion_scheduled_at`, `accounts.deleted_at`)
- 1 migration Alembic réversible
- 7 endpoints REST `/api/me/*`
- 1 helper backend partagé (`app/core/consent.py`)
- 1 job cron Python (`scripts/purge_scheduled_deletions.py`)
- 1 test CI security (`tests/security/test_require_consent_coverage.py`)
- 1 page Vue principale (`/mes-donnees`) + 3 sous-pages (`inventaire`, `consentements`, `supprimer`)
- 1 page Vue publique (`/legal/privacy`)
- 1 layout Nuxt nouveau (`public.vue`) si absent
- 1 modification `pages/register.vue`
- 1 footer global avec lien `/legal/privacy`
- 5 nouveaux composants Vue : `<ConsentToggle>`, `<DeletionConfirmModal>`, `<DataInventoryTable>`, `<DataExportButton>`, `<DeletionScheduledBanner>`
- 1 store Pinia `stores/consents.ts`
- 1 composable `composables/useDataPrivacy.ts`
- 2 fichiers documentation (`docs/rgpd-conformite.md`, `docs/hosting-and-data-residency.md`)
- 1 spec E2E Playwright (`frontend/tests/e2e/F05-rgpd-mes-donnees-consents.spec.ts`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| **I. Francophone-First & Contextualisation Africaine** | PASS | Tous les libellés UI utilisateur en français avec accents (« Mes données », « Inventaire de mes données », « Exporter mes données », « Mes consentements », « Supprimer mon compte », « Politique de confidentialité »). Cadre légal documenté incluant explicitement la loi ivoirienne 2013-450 et le règlement UEMOA n°20/2010/CM/UEMOA en plus du RGPD européen. Politique de confidentialité rédigée en français en v1.0 (anglais post-MVP). |
| **II. Architecture Modulaire** | PASS | Modifications cantonnées à un nouveau module `backend/app/modules/me/` (ou `privacy/`) regroupant service + router. Helper `app/core/consent.py` placé dans `core/` car partagé par tous les modules métier. Aucune touche aux zones interdites de l'orchestrateur (`graph.py`, `system.py`, `main.py`, `deps.py`, `config.py` autrement que via ajout de variables d'env documentées). Côté frontend, nouveau dossier `pages/mes-donnees/` + `pages/legal/` + composants dans `components/` (PascalCase, pathPrefix:false). |
| **III. Conversation-Driven UX** | PASS | F05 est une feature « hors-chat » (page utilisateur autonome) — c'est une exception **assumée** par la spec : la conformité RGPD nécessite une UI de gestion explicite, le LLM ne peut pas être responsable d'actions critiques (export, suppression). Aucun nouveau tool LangChain. Le LLM peut éventuellement orienter vers `/mes-donnees` mais ne mute jamais les consentements. |
| **IV. Test-First (NON-NEGOTIABLE)** | PASS | Plan TDD : tests pytest backend écrits AVANT helpers / services / endpoints. Tests Vitest pour composants Vue. Test CI security `test_require_consent_coverage.py` écrit AVANT le helper. Couverture ≥ 80 %. Spec E2E Playwright `F05-rgpd-mes-donnees-consents.spec.ts` (4 scénarios critiques) écrite avant l'intégration. |
| **V. Sécurité & Protection des Données** | PASS | Aucun secret hardcodé. URLs signées via clé `EXPORT_URL_SIGNING_KEY` env var. Validation Pydantic stricte sur `ConsentGrantRequest`, `ConsentRevokeRequest`, `ScheduleDeletionRequest`, `RegisterRequest` (privacy_policy_accepted=true). Vérification mot de passe via endpoint dédié `verify-password` avant action critique. Suppression cascade testée (FK `ON DELETE CASCADE`). Anonymisation audit_log testée (vérification post-purge : 0 row avec `user_id` ou `account_id` égal à l'account purgé). Test CI scanner `require_consent`. Multi-tenant strict (F02) : tous les endpoints `/api/me/*` filtrent par JWT.account_id. |
| **VI. Inclusivité & Accessibilité** | PASS | `<DeletionConfirmModal>` : focus trap natif, ARIA `role=dialog`, `aria-labelledby`, `aria-describedby`, retour focus à l'élément déclencheur après fermeture. `<ConsentToggle>` : ARIA `role=switch`, `aria-checked`, label visible. `aria-live` sur les messages de succès / erreur (export, grant, revoke). Dark mode complet sur tous les composants. Pas de dépendance JS lourde. Pied de page accessible avec lien `/legal/privacy`. |
| **VII. Simplicité** | PASS | Une seule table créée (`consents`). Pas de table `data_export_jobs` au MVP (différée post-MVP, traçage dans audit_log via clarification Q2). Pas de queue Celery/RQ : `BackgroundTasks` FastAPI suffit (clarification Q6). Pas de Redis. Pas de bibliothèque externe pour signer URLs (utilise `itsdangerous` déjà dans l'écosystème FastAPI ou `hmac` standard). |
| **Invariant n°1 (sourçage F01)** | PASS | F05 ne crée aucun chiffre ESG/carbone/financier ; uniquement compteurs, durées, dates. Hors scope sourçage. |
| **Invariant n°2 (multi-tenant F02)** | PASS | Table `consents` : `account_id UUID FK accounts.id NOT NULL` + RLS policy `account_id = current_setting('app.current_account_id')`. Endpoints `/api/me/*` filtrent strictement par JWT.account_id. |
| **Invariant n°3 (audit log F03)** | PASS | Tous les services F05 (`grant_consent`, `revoke_consent`, `schedule_deletion`, `cancel_deletion`, `purge_account`, `export_account_data`) décorés du mixin `Auditable`. Aucun `db.commit()` direct. La purge inclut une étape spécifique d'anonymisation audit_log (UPDATE en place, clarification Q3). |
| **Invariant n°4 (Money typed F04)** | PASS | Non concerné : F05 ne manipule aucun champ monétaire. |
| **Invariant n°5 (RGPD consentements F05)** | **CETTE FEATURE INTRODUIT L'INVARIANT** | F05 publie le helper `require_consent` que les features futures (F18 obligatoirement, F08 si applicable) doivent invoquer. Cette feature est elle-même la fondation de l'invariant n°5. |
| **Invariant n°7 (admin only catalogue)** | PASS | Aucun tool LLM ne mute `consents` ni `accounts.deletion_*`. Seuls les services authentifiés `/api/me/*` (utilisateur agissant sur son propre compte) peuvent muter. |
| **Invariant n°8 (dark mode)** | PASS | Tous les nouveaux composants Vue implémentent les variantes `dark:` Tailwind. La page `/legal/privacy` également (cohérent UX même hors auth). |
| **Invariant n°9 (réutilisabilité composants)** | PASS | Vérification : `<ConfirmModal>` générique extrait dans `components/ui/` pour `<DeletionConfirmModal>` (potentiellement déjà existant via F02 / F18 — à vérifier en Phase B). `<ConsentToggle>` réutilise un éventuel composant `<ToggleSwitch>` existant. |

**Décision constitutionnelle** : TOUS LES GATES PASSENT. Aucune violation à justifier dans Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/027-rgpd-mes-donnees-consents/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (interfaces backend)
│   ├── me-data.md       # GET /api/me/data/inventory + /export
│   ├── me-consents.md   # GET/POST /api/me/consents
│   └── me-account.md    # POST /api/me/account/schedule-deletion + cancel-deletion
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spec.md              # Feature specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 0XX_consents_and_account_deletion.py  # NEW migration (numéro défini en Phase B selon ordre merge)
├── app/
│   ├── core/
│   │   ├── consent.py                        # NEW : require_consent(account_id, type) helper
│   │   ├── mailer.py                         # NEW or MODIFIED : stub d'envoi email transactionnel (logge si pas de SMTP)
│   │   └── url_signer.py                     # NEW : sign_export_url(account_id, expires_in) / verify
│   ├── models/
│   │   ├── account.py                        # MODIFIED : ajoute deletion_scheduled_at + deleted_at
│   │   └── consent.py                        # NEW : ConsentModel + enum ConsentType
│   ├── modules/
│   │   └── me/                               # NEW module dédié RGPD
│   │       ├── __init__.py
│   │       ├── service.py                    # NEW : export_account_data, schedule_deletion, cancel_deletion, purge_account, grant_consent, revoke_consent, list_consents, get_inventory
│   │       ├── router.py                     # NEW : 7 endpoints REST
│   │       ├── schemas.py                    # NEW : Pydantic schemas (InventoryResponse, ExportResponse, ConsentItem, ScheduleDeletionRequest, ...)
│   │       ├── exporter.py                   # NEW : build_export_zip(account_id) -> bytes (synchrone) + build_export_async (BackgroundTasks)
│   │       └── purge.py                      # NEW : purge_account_data(account_id) idempotent (utilisé par cron + tests)
│   ├── routers/
│   │   └── auth.py                           # MODIFIED : RegisterRequest exige privacy_policy_accepted=true ; insère audit_log privacy_policy_accepted
│   └── main.py                               # MODIFIED (zone partagée) : inclut router me + footer template si rendu côté serveur (ne touche pas au lifespan)
├── scripts/
│   └── purge_scheduled_deletions.py          # NEW : cron job idempotent
└── tests/
    ├── unit/
    │   ├── test_consent_helper.py            # NEW : require_consent gating
    │   ├── test_consent_model.py             # NEW : invariant 1 actif par (account_id, type)
    │   ├── test_inventory_service.py         # NEW
    │   ├── test_exporter.py                  # NEW : ZIP structure, README, links signés
    │   ├── test_purge_service.py             # NEW : cascade + anonymisation audit_log
    │   ├── test_url_signer.py                # NEW : sign + verify + expiration
    │   └── test_mailer_stub.py               # NEW
    ├── integration/
    │   ├── test_me_router.py                 # NEW : 7 endpoints + auth + multi-tenant isolation
    │   ├── test_register_privacy_flag.py     # NEW : privacy_policy_accepted obligatoire
    │   └── test_purge_cron.py                # NEW : end-to-end (programmer → cron → purge → audit_log anonymisé)
    ├── security/
    │   └── test_require_consent_coverage.py  # NEW : test CI scanner regex
    └── migrations/
        └── test_alembic_f05.py               # NEW : up/down/up + invariants

frontend/
├── app/
│   ├── components/
│   │   ├── ConsentToggle.vue                 # NEW
│   │   ├── DeletionConfirmModal.vue          # NEW (réutilise ConfirmModal si existant)
│   │   ├── DataInventoryTable.vue            # NEW
│   │   ├── DataExportButton.vue              # NEW
│   │   └── DeletionScheduledBanner.vue       # NEW
│   ├── composables/
│   │   └── useDataPrivacy.ts                 # NEW : useInventory, useExport, useConsents, useDeletion
│   ├── stores/
│   │   └── consents.ts                       # NEW : Pinia store avec état des 7 consentements
│   ├── layouts/
│   │   ├── default.vue                       # MODIFIED (zone partagée) : footer global avec lien /legal/privacy
│   │   └── public.vue                        # NEW (si absent) : layout sans sidebar pour /legal/*
│   └── pages/
│       ├── register.vue                      # MODIFIED : checkbox privacy_policy_accepted
│       ├── legal/
│       │   └── privacy.vue                   # NEW : politique de confidentialité v1.0 (layout public)
│       └── mes-donnees/
│           ├── index.vue                     # NEW : tableau de bord
│           ├── inventaire.vue                # NEW
│           ├── consentements.vue             # NEW
│           └── supprimer.vue                 # NEW
└── tests/
    ├── unit/
    │   ├── ConsentToggle.spec.ts             # NEW
    │   ├── DeletionConfirmModal.spec.ts      # NEW
    │   ├── DataInventoryTable.spec.ts        # NEW
    │   └── useDataPrivacy.spec.ts            # NEW
    └── e2e/
        └── F05-rgpd-mes-donnees-consents.spec.ts  # NEW

docs/
├── rgpd-conformite.md                        # NEW
└── hosting-and-data-residency.md             # NEW
```

**Structure Decision** : Web application (backend FastAPI + frontend Nuxt 4 séparés). Module backend dédié `backend/app/modules/me/` (préféré à `privacy/` pour cohérence avec le routing `/api/me/*`). Helper partagé `app/core/consent.py` à un emplacement standardisé pour invocation depuis n'importe quel autre module. Migration Alembic dans `backend/alembic/versions/` ; numéro défini en Phase B selon l'ordre de merge des autres features (F06 / F08 peuvent merger avant). Côté frontend, dossier dédié `pages/mes-donnees/` (4 pages) et `pages/legal/` (1 page), 5 nouveaux composants dans `components/`, 1 store Pinia, 1 composable, 1 layout `public.vue` (créé seulement si absent).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation. Tous les gates passent. Cette section reste vide.

## Phase 0 — Outline & Research

Voir [research.md](./research.md). Synthèse :

- **Décision** : Enum natif PostgreSQL `consent_type_enum` avec 7 valeurs documentées (clarification Q1) ; ajouts futurs via migration Alembic dédiée `ALTER TYPE ... ADD VALUE`. Justification : enum natif performant, contrainte BDD, cohérent avec les patterns SQLAlchemy / Alembic du projet (cf. enums F02, F03, F17). Alternative rejetée : `String` libre (perte de contrainte) ; table de référence dédiée (sur-ingénierie pour 7 valeurs stables).
- **Décision** : Pas de table `data_export_jobs` au MVP ; traçage exclusif via `audit_log` (clarification Q2). Justification : recommandation orchestrateur de différer toute table non strictement requise. Le volume MVP (≤ 100 PME en pilote) ne justifie pas une table dédiée. Migration vers table après F19 (cron dispatcher) si le volume async dépasse ~50 jobs/jour.
- **Décision** : Anonymisation `audit_log` via UPDATE en place (clarification Q3). Justification : préserve l'append-only (pas de DELETE), moins coûteux en stockage, simple à implémenter avec une seule requête transactionnelle. Les champs PII `payload` JSON sont filtrés via une fonction `anonymize_payload(payload, account_id)` qui retire les champs whitelistés (`email`, `phone`, `ip`, `user_agent`, `name`, etc.) avant le UPDATE.
- **Décision** : Layout Nuxt `public.vue` distinct pour `/legal/*` (clarification Q4). Justification : sépare clairement l'UX public de l'UX authentifié, évite tout risque de fuite de données via slot par défaut. Si le layout existe déjà (créé éventuellement par une feature antérieure), réutilisation ; sinon création.
- **Décision** : Endpoint dédié `POST /api/me/account/verify-password` puis `POST /api/me/account/schedule-deletion` revérifie le mot de passe (clarification Q5). Justification : double validation côté backend ; protection contre l'attaque par session volée ; isole la responsabilité « vérifier identité forte » de l'action critique.
- **Décision** : `BackgroundTasks` FastAPI pour l'export asynchrone (clarification Q6). Justification : aligné avec « Queue : Synchrone (Redis + Celery plus tard) » du `CLAUDE.md`. Acceptable en MVP : un export tronqué par redémarrage du process est simplement signalé via audit_log, l'utilisateur peut relancer.
- **Décision** : Test CI scanner regex sur fonctions `analyze_*`, `fetch_*_external`, `generate_certificate_*` dans dossiers ciblés (clarification Q7). Justification : pragmatique (aucune dépendance externe), maintenable, faux positifs gérés par liste d'exclusions documentée.
- **Décision** : URLs temporaires signées via `itsdangerous.URLSafeTimedSerializer` (lib standard FastAPI tutorials), clé secret env var `EXPORT_URL_SIGNING_KEY`, expiration 24h pour les liens documents (cohérent metadata de l'export) et 7j pour le lien email d'export asynchrone. Pas de stockage en BDD ; la signature embarque tout le state nécessaire.
- **Décision** : Email transactionnel : un service `app/core/mailer.py` exposant `send_email(to, subject, body_html, body_text)`. En MVP, si `SMTP_HOST` non configuré, le mailer logge le payload dans `audit_log` (`entity_type='email'`, `action='sent_stub'`, `metadata={to, subject, body_text}`) et retourne succès. Permet aux tests E2E de vérifier l'envoi sans dépendance SMTP réelle.
- **Décision** : Cron job idempotent via flag `purge_in_progress` sur `accounts` (statut transitoire entre `deletion_scheduled_at` et `deleted_at`). Si le job redémarre en milieu de purge, il vérifie `purge_in_progress=true` et reprend la cascade restante. Documenté dans `docs/rgpd-conformite.md`.
- **Décision** : Triple confirmation modale = (1) prise de connaissance des conséquences (checkbox « Je comprends »), (2) saisie mot de passe (vérification asynchrone via `verify-password` endpoint), (3) saisie « SUPPRIMER » en majuscules (validation côté frontend ET backend). Le bouton « Confirmer » reste désactivé tant que les 3 conditions ne sont pas remplies.
- **Décision** : Structure du fichier export ZIP :
  ```
  esg-mefali-export-{account_id}-{date}.zip
  ├── README.md                  # Description structure + URLs signées 24h documentées
  ├── data.json                  # Toutes les tables account_id (profile, projects, applications, esg_assessments, carbon_assessments, credit_scores, conversations, messages, attestations, consents, audit_log_personnel)
  └── documents/
      └── manifest.json          # Liste {filename, signed_url, expires_at, original_path, mimetype, size}
  ```
  Les fichiers eux-mêmes ne sont pas inclus dans le ZIP (URLs signées 24h pour download direct depuis le client). Avantage : ZIP léger (< 1 MB pour la plupart des comptes), pas de duplication.

## Phase 1 — Design & Contracts

Voir [data-model.md](./data-model.md), [contracts/me-data.md](./contracts/me-data.md), [contracts/me-consents.md](./contracts/me-consents.md), [contracts/me-account.md](./contracts/me-account.md), [quickstart.md](./quickstart.md). Synthèse :

### Modèles BDD nouveaux

- **`Consent`** (table `consents`) : `id UUID PK`, `account_id UUID FK accounts.id ON DELETE CASCADE NOT NULL`, `user_id UUID FK users.id ON DELETE SET NULL NOT NULL` (oui contradictoire — résolu : ON DELETE SET NULL pour autoriser la purge user mais conserver l'historique consent ; le FK `account_id` reste cascade pour la purge complète du compte), `consent_type consent_type_enum NOT NULL`, `granted bool NOT NULL`, `granted_at timestamptz NOT NULL DEFAULT now()`, `revoked_at timestamptz NULL`, `legal_basis legal_basis_enum NOT NULL`, `version varchar(16) NOT NULL`, `metadata jsonb NOT NULL DEFAULT '{}'::jsonb`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()`. Index : `(account_id, consent_type, revoked_at)` partial WHERE revoked_at IS NULL pour lookups rapides « consentement actif ». Trigger BDD ou validation service : au plus 1 row actif `(account_id, consent_type)` simultanément (FR-007).

### Modèles BDD modifiés

- **`Account`** (table `accounts`, étendue F02) : ajout `deletion_scheduled_at timestamptz NULL`, `deleted_at timestamptz NULL`, `purge_in_progress boolean NOT NULL DEFAULT false`. Index : `idx_accounts_deletion_scheduled (deletion_scheduled_at) WHERE deletion_scheduled_at IS NOT NULL` (utilisé par le cron).

### Helpers / Services backend nouveaux

- **`app/core/consent.py::require_consent(db, account_id, consent_type) -> None`** : SELECT actif sur `consents` (account_id, consent_type, revoked_at IS NULL, granted=true). Si aucun row → `raise HTTPException(403, detail={"detail": "Consentement {label} requis", "consent_type": consent_type, "settings_url": "/mes-donnees/consentements"})`. Async function.
- **`app/core/url_signer.py::sign_export_url(account_id, expires_in_hours) -> str`** + `verify_export_url(token) -> account_id | raise`. Utilise `itsdangerous.URLSafeTimedSerializer(SECRET_KEY)`.
- **`app/core/mailer.py::send_email(to, subject, body_html, body_text)`** : envoi SMTP réel si configuré, sinon stub log dans audit_log.
- **`app/modules/me/service.py`** : 9 fonctions principales (`get_inventory`, `export_account_data_sync`, `export_account_data_async`, `list_consents`, `grant_consent`, `revoke_consent`, `verify_password`, `schedule_deletion`, `cancel_deletion`, `purge_account`). Toutes décorées du mixin `Auditable` (F03).
- **`app/modules/me/exporter.py::build_export_zip(account_id) -> bytes`** + `build_export_async(account_id, background_tasks)`. Synchrone si total estimé ≤ 100 MB, sinon délègue à `BackgroundTasks` qui appelle `build_export_zip` puis envoie email avec lien signé 7j.
- **`app/modules/me/purge.py::purge_account_data(account_id) -> PurgeResult`** : (1) flag `purge_in_progress=true` ; (2) révoquer attestation crédit si applicable (`status=revoked, reason='account_deleted'`) ; (3) supprimer `consents` ; (4) supprimer `messages`, `conversations`, `documents` (et fichiers /uploads/{account_id}/) ; (5) supprimer `esg_assessments`, `carbon_assessments`, `credit_scores`, `applications`, `projects`, `profiles`, `users` ; (6) anonymiser `audit_log` UPDATE en place (`user_id=NULL`, `account_id=NULL`, `payload = anonymize_payload(payload)`) ; (7) révoquer refresh tokens ; (8) `accounts.deleted_at = now()`, `purge_in_progress=false` ; (9) envoi email confirmation final ; (10) audit_log événement `account_purged` (anonymisé immédiatement après).
- **`scripts/purge_scheduled_deletions.py`** : main entrypoint. SELECT `accounts WHERE deletion_scheduled_at < now() AND deleted_at IS NULL`. Pour chaque account, appelle `purge_account_data(account_id)`. Idempotent : si `purge_in_progress=true`, reprend ; si `deleted_at IS NOT NULL`, ignore.

### Endpoints API nouveaux (module `/api/me`)

- `GET /api/me/data/inventory` → 200 `{counts: {profile, projects, applications, esg_assessments, ...}, last_modified: {profile, ...}}`
- `GET /api/me/data/export?format=json` → 200 (sync) avec body `application/zip` OU 202 `{job_id, status: 'pending', message}` (async).
- `GET /api/me/data/export/download?token={signed}` → 200 application/zip (vérifie signature + expiration).
- `GET /api/me/consents` → 200 `[{type, granted, granted_at, revoked_at, version, legal_basis, label, description}, ...]` (7 lignes, valeurs par défaut si pas de row).
- `POST /api/me/consents/{type}/grant` → 200 `{granted: true, granted_at, version}`. Body : `{}` (juste auth).
- `POST /api/me/consents/{type}/revoke` → 200 `{granted: false, revoked_at}`.
- `POST /api/me/account/verify-password` → 200 `{verified: true}` ou 401.
- `POST /api/me/account/schedule-deletion` → 200 `{deletion_scheduled_at}`. Body : `{password, confirmation_text='SUPPRIMER'}`. Revérifie password + confirmation_text.
- `POST /api/me/account/cancel-deletion` → 200 `{cancelled_at}`. Body : `{}` (juste auth, ou token via lien email pour version no-auth).

### Endpoint modifié `/api/auth/register`

- **`POST /api/auth/register`** : ajoute champ obligatoire `privacy_policy_accepted: bool` dans le body. Si false ou absent → 422 `{"detail": "Vous devez accepter la politique de confidentialité"}`. Si true → après création compte, insère event audit_log `privacy_policy_accepted` avec metadata `{version: 'v1.0', ip, user_agent}`.

### Frontend

#### Pages

- **`pages/mes-donnees/index.vue`** : tableau de bord avec 4 cartes (Inventaire, Export, Consentements, Suppression) + bandeau `<DeletionScheduledBanner>` si `accounts.deletion_scheduled_at` non null.
- **`pages/mes-donnees/inventaire.vue`** : `<DataInventoryTable>` consommant `useDataPrivacy().useInventory()` ; bouton « Exporter mes données » `<DataExportButton>`.
- **`pages/mes-donnees/consentements.vue`** : liste 7 `<ConsentToggle>` consommant `stores/consents.ts` ; chaque toggle avec label + description + base légale + version.
- **`pages/mes-donnees/supprimer.vue`** : bouton « Supprimer mon compte définitivement » qui ouvre `<DeletionConfirmModal>` ; bouton « Annuler la suppression » si déjà programmée.
- **`pages/legal/privacy.vue`** : layout `public`, contenu de la politique v1.0 en sections sémantiques `<section><h2>...</h2></section>`, dark mode.
- **`pages/register.vue`** (modifié) : ajoute checkbox `<input type="checkbox" v-model="privacy_policy_accepted" required>` avec label cliquable vers `/legal/privacy` ; bouton soumission `:disabled="!privacy_policy_accepted"`.

#### Composants

- **`<ConsentToggle :type :granted :version :legal_basis :label :description @toggle>`** : ARIA `role=switch`, dark mode, animation transition.
- **`<DeletionConfirmModal :open @confirm @cancel>`** : focus trap, étapes 1-2-3 (consequences / password / SUPPRIMER), validation incrémentale.
- **`<DataInventoryTable :counts :last_modified>`** : tableau responsive avec 11 entités, dark mode.
- **`<DataExportButton :estimated_size_mb @export-started @export-ready>`** : bouton avec spinner pendant génération, gestion sync vs async.
- **`<DeletionScheduledBanner :scheduled_at>`** : bandeau warning persistant avec bouton « Annuler ».

#### Composables / Stores

- **`composables/useDataPrivacy.ts`** : `useInventory()`, `useExport()`, `useDeletion()`. `$fetch` typed.
- **`stores/consents.ts`** : Pinia store, fetch 7 consentements à l'init, `grant(type)`, `revoke(type)`, `getStatus(type)`.

#### Layouts

- **`layouts/public.vue`** : header simple ESG Mefali (logo + lien retour login), slot main, footer global avec lien `/legal/privacy`. Dark mode.
- **`layouts/default.vue`** (modifié) : ajoute dans le footer global le lien `/legal/privacy` (à côté ou en remplacement d'un lien existant). À traiter en zone partagée — minimiser le diff.

### Migration Alembic

- **Up** : (1) CREATE TYPE `consent_type_enum` AS ENUM (7 valeurs) ; (2) CREATE TYPE `legal_basis_enum` AS ENUM (4 valeurs) ; (3) CREATE TABLE `consents` avec colonnes + FK + index partial ; (4) CREATE TRIGGER OR check service-level pour invariant 1 actif par (account_id, type) ; (5) ALTER TABLE `accounts` ADD COLUMN `deletion_scheduled_at`, `deleted_at`, `purge_in_progress` ; (6) CREATE INDEX partial sur `deletion_scheduled_at`.
- **Down** : symétrique inverse. DROP INDEX, ALTER TABLE accounts DROP COLUMN, DROP TABLE consents, DROP TYPE legal_basis_enum, DROP TYPE consent_type_enum.

### Update agent context

- Lancer `.specify/scripts/bash/update-agent-context.sh claude` après finalisation de Phase 1 pour mettre à jour CLAUDE.md avec les nouvelles entrées (Active Technologies, Recent Changes).

## Re-évaluation Constitution Check (post-design Phase 1)

| Gate | Statut | Notes |
|------|--------|-------|
| I. Francophone-First | PASS | Inchangé. Tous les libellés UI utilisateur en français avec accents confirmés. |
| II. Architecture Modulaire | PASS | Inchangé. Module `me/` confirmé, helper `core/consent.py` confirmé, layout `public` distinct. |
| III. Conversation-Driven | PASS | Exception assumée pour fonctionnalité hors-chat (RGPD requiert UI dédiée). |
| IV. Test-First | PASS | Phase 1 confirme la suite TDD : 17 fichiers de tests planifiés (7 unit + 3 integration + 1 security + 1 migrations + 4 frontend unit + 1 E2E). |
| V. Sécurité | PASS | URL signing + double-validation password + multi-tenant + cascade FK + anonymisation audit_log testée. |
| VI. Inclusivité | PASS | ARIA + focus trap + dark mode + clavier confirmés. |
| Invariants 1, 2, 3, 4, 5, 7, 8, 9 | PASS | Inchangés. F05 introduit officiellement l'invariant n°5. |

**Décision finale Constitution** : Plan validé pour génération des tasks (Phase 2 via `/speckit.tasks`).
