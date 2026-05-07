# Implementation Plan: F08 — Attestation Vérifiable Ed25519 + QR + Page Publique `/verify/{id}` + Révocation (Module 5.3)

**Branch** : `feat/F08-attestation-verifiable-ed25519` (alias SpecKit `026-attestation-verifiable-ed25519`)
**Date** : 2026-05-07
**Spec** : [spec.md](./spec.md)
**Input** : Feature specification from `/specs/026-attestation-verifiable-ed25519/spec.md`

## Summary

F08 livre l'attestation vérifiable signée Ed25519 (différenciateur produit n°2) en construisant : (1) un nouveau modèle `Attestation` premier rang (multi-tenant F02, Auditable F03) ; (2) une couche cryptographique `signing.py` autour de `cryptography>=41.0` avec singleton `SigningKeyStore` chargeant la clé privée depuis `ATTESTATION_PRIVATE_KEY_PEM` ; (3) une couche `qr.py` autour de `segno>=1.5` ; (4) un service `service.py` orchestrant la génération atomique (PDF → hash SHA-256 → signature → QR → persistance + audit log F03) ; (5) un router authentifié `/api/attestations/*` (génération, liste, révocation) + un router public no-auth `/api/public/*` (vérification, clé publique) monté AVANT le middleware d'auth dans `app/main.py` ; (6) le refactor du tool LangChain `generate_credit_certificate` pour appel réel au service ; (7) un layout Nuxt `public.vue` réutilisable, une page `pages/verify/[id].vue` accessible sans auth, une page `pages/attestations/index.vue` (PME) et une page `pages/admin/attestations/index.vue` (admin) ; (8) modification du middleware `auth.global.ts` pour autoriser `/verify/` et `/legal/`. Migration Alembic `026_create_attestations.py` (down_revision conditionnelle = `025_create_projects` si F06 mergé en parallèle, sinon `024_carbone_mix_uemoa`). Tests TDD ≥ 85 % de couverture sur `signing.py`, `qr.py`, `service.py`. 5 scénarios E2E Playwright (`F08-attestation-verifiable-ed25519.spec.ts`) couvrant : génération+vérification authentique, altération PDF (hash mismatch détecté), révocation, expiration, UUID invalide.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, LangGraph (≥0.2.0), LangChain (≥0.3.0), langchain-openai, WeasyPrint (déjà présent), Jinja2 (déjà présent), **cryptography>=41.0** (NEW), **segno>=1.5** (NEW)
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4, DOMPurify
**Storage** : PostgreSQL 16 + pgvector (extension), Alembic pour migrations, RLS PostgreSQL héritée F02 ; stockage local fichiers `/uploads/attestations/pdfs/` et `/uploads/attestations/qr/`
**Testing** :
- Backend : pytest, pytest-asyncio, pytest-cov (couverture cible ≥ 85 % sur `signing.py`/`qr.py`/`service.py`, ≥ 80 % global F08)
- Frontend : Vitest + @vue/test-utils + @vitest/coverage-v8 + happy-dom
- E2E : Playwright (`@playwright/test`) avec backend mocké
**Target Platform** : Linux server (Docker) + navigateurs modernes (Chrome 90+, Safari 14+, Firefox 90+, Edge 90+) ; mobile iOS 14+ et Android 10+ pour scan QR
**Project Type** : Web application (backend + frontend séparés)
**Performance Goals** :
- `POST /api/attestations` (génération PDF + signature + QR + persistance) en < 5 s p95 (génération PDF WeasyPrint dominante)
- `GET /api/public/verify/{id}` en < 200 ms p95 (lecture indexée + vérification signature pure CPU)
- Page `/verify/[id]` Time-to-Interactive < 2 s sur 3G simulée
- Migration Alembic `up/down/up` en < 5 s sur base de dev
- Aucune régression sur `POST /api/messages` (latence chat inchangée ± 10 %)
**Constraints** :
- Multi-tenant strict (F02) : `attestations.account_id` NOT NULL, RLS PostgreSQL ENABLE+FORCE + 2 policies (`pme_access_own_account`, `admin_full_access`)
- Auditable (F03) : `Attestation` hérite du mixin `Auditable` ; tout `create`/`revoke` tracé automatiquement avec `source_of_change ∈ {manual, llm}` et `actor_role ∈ {pme, admin}`
- Money typed (F04) : les scores ne sont pas des montants monétaires mais le `payload` JSONB stocke les structures Money complètes pour `target_amount` projets associés (snapshot au moment de la génération)
- Sourçage (F01) : si le tool LLM `generate_credit_certificate` cite des chiffres dans la conversation (ex. « votre score est de 73/100 issu de … »), le validator `source_required.py` post-tour s'applique. L'annexe sources F01 est intégrée dans le PDF généré.
- Aucun secret hardcodé : `ATTESTATION_PRIVATE_KEY_PEM` chargé depuis env var, jamais checké en git (cf. invariant `.cc-orchestrator.md` #6)
- RGPD minimisation : la page publique `/verify/{id}` n'expose JAMAIS le nom d'entreprise, les coordonnées, le détail des indicateurs ESG. Whitelist explicite côté serveur.
- Rate limiting `/api/public/verify/{id}` : 10 req/IP/min (FR-015) pour empêcher l'énumération
- Dark mode obligatoire sur les composants Vue authentifiés. Page publique `/verify/[id]` neutre (pas de toggle dark/light, design clair par défaut pour fund officer non habitué).
- Français avec accents dans tous les contenus utilisateur ; i18n FR/EN limitée à la page publique (4 statuts + libellés boutons)
**Scale/Scope** :
- 1 nouvelle table métier (`attestations`)
- 2 nouveaux routers : `app/modules/attestations/router.py` (auth) + `app/api/public.py` (no-auth)
- 1 nouveau module métier `app/modules/attestations/` (service.py, signing.py, qr.py, schemas.py, templates/)
- 1 nouveau modèle `app/models/attestation.py`
- 1 nouvelle config `core/config.py` (3 nouvelles variables : `ATTESTATION_PRIVATE_KEY_PEM`, `ATTESTATION_PUBLIC_KEY_ID`, `ATTESTATION_VALIDITY_DAYS`, `ATTESTATION_VERIFICATION_BASE_URL`)
- 1 script bootstrap `scripts/generate_attestation_keypair.py` (one-shot)
- 1 tool LangChain refactoré `generate_credit_certificate` dans `app/graph/tools/credit_tools.py` (placeholder → réel)
- 4 nouvelles pages frontend (`pages/verify/[id].vue`, `pages/attestations/index.vue`, `pages/admin/attestations/index.vue`, `pages/credit-score/index.vue` mise à jour)
- 1 nouveau layout `layouts/public.vue`
- 4 nouveaux composants Vue dans `components/attestations/` (`AttestationCard.vue`, `AttestationStatusBadge.vue`, `RevokeAttestationModal.vue`, `HashCompareInput.vue`)
- 1 composable `composables/useAttestations.ts`
- 1 spec E2E Playwright avec 5 scénarios

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| **I. Francophone-First & Contextualisation Africaine** | PASS | Tous les libellés UI authentifiés en français avec accents (« Générer une attestation vérifiable », « Révoquer », « Authentique », « Révoquée », « Expirée », « Invalide », « Hash conforme — le PDF n'a pas été altéré »). Page publique en FR par défaut + EN sur header `Accept-Language: en` (fund officer GCF/anglophones). |
| **II. Architecture Modulaire** | PASS | Modifications cantonnées à un nouveau module isolé `app/modules/attestations/` + un nouveau router public `app/api/public.py` + un nouveau modèle `app/models/attestation.py`. Modification minimale de `app/main.py` (ajout `include_router(public.router)` AVANT le middleware d'auth + `include_router(attestations.router)`). Modification de `app/core/config.py` réservée aux 4 nouvelles variables d'env. Refactor isolé du tool `credit_tools.py:generate_credit_certificate` (signature inchangée, comportement réel). |
| **III. Conversation-Driven UX** | PASS | Le tool LangChain `generate_credit_certificate` reste exposé au LLM (pas seulement via UI directe). L'utilisateur peut générer une attestation par chat (US5). La proposition de génération intègre F18 `ask_interactive_question` si la PME hésite sur le type (`credit_score | esg_assessment | combined`). |
| **IV. Test-First (NON-NEGOTIABLE)** | PASS | Plan TDD : tests pytest écrits AVANT le service `AttestationService`, le `SigningKeyStore`, la génération QR, la migration. Tests Vitest pour les 4 composants Vue. Couverture cible ≥ 85 % sur les couches cryptographiques. Migration testée via `test_alembic_f08.py` (round-trip up/down/up). Test E2E Playwright `F08-attestation-verifiable-ed25519.spec.ts` avec 5 scénarios. |
| **V. Sécurité & Protection des Données** | PASS | `ATTESTATION_PRIVATE_KEY_PEM` chargé depuis env var (jamais hardcodé). Validation Pydantic stricte sur tous les schemas (`AttestationCreate`, `AttestationRevoke`, `VerificationResult` discriminated union par `status`). Whitelist explicite côté serveur sur les métadonnées exposées publiquement (jamais de sérialisation auto SQLAlchemy → DTO). RLS PostgreSQL F02 honorée. Tools LangChain protégés par scope `source_of_change_scope('llm')` (F03). Rate limiting 10 req/IP/min sur endpoint public (FR-015). Pas de leak timing entre les 4 statuts (FR-016 + SC-006). HTTPS strict en production (HSTS via reverse proxy nginx, hors-scope F08 mais documenté). |
| **VI. Inclusivité & Accessibilité** | PASS | Page publique mobile-first responsive (viewport 375x667 OK, boutons ≥ 44x44 px ARIA conformes). 4 composants ARIA : `AttestationCard` avec `role="article"` + `aria-label`, `AttestationStatusBadge` avec `role="status"` + `aria-live="polite"`, `RevokeAttestationModal` avec `role="dialog"` + `aria-modal="true"` + focus trap (réutilise `useFocusTrap`), `HashCompareInput` avec `aria-describedby` pour message comparaison. Lecture native QR par appareil photo iOS/Android. Aucun JS bloquant en page publique (Time-to-Interactive < 2 s sur 3G). Dark mode complet sur les pages authentifiées ; page publique conserve un design clair neutre. |
| **VII. Simplicité** | PASS | Réutilise le pattern modulaire des modules `audit`, `financing`, `credit`. Pas d'introduction de Vault/AWS Secrets Manager pour le MVP (env var suffit, rotation post-MVP). Pas de Redis (rate limiting via cache LRU local FastAPI + slowapi candidate). Pas de Celery (génération synchrone < 5 s). Pas d'extension PostgreSQL nouvelle. Pas de signature multi-clés / HSM (rotation par `public_key_id` versionné). Le PDF reste produit par WeasyPrint déjà en place. |
| **Invariant projet n°1 (sourçage F01)** | PASS | Le tool LLM `generate_credit_certificate` instruit dans son docstring qu'il ne cite aucun chiffre — il retourne uniquement un objet structuré `{ok, attestation_id, verification_url, pdf_path}`. Si le LLM mentionne des scores en réponse à l'utilisateur (« votre score est de 73 »), le validator post-tour applique la discipline F01. L'annexe sources F01 est intégrée dans le PDF (référence aux Sources `verified` mobilisées pour les scores ESG/crédit). |
| **Invariant projet n°2 (multi-tenant F02)** | PASS | `attestations.account_id` UUID FK accounts.id NOT NULL. RLS PostgreSQL ENABLE+FORCE + 2 policies. Test `test_attestation_rls_cross_tenant.py` couvre 4 opérations cross-tenant (list, get, revoke par PME, revoke par admin). L'admin contourne le RLS via la policy `admin_full_access`. |
| **Invariant projet n°3 (audit log F03)** | PASS | `Attestation` hérite de `Auditable`. Listener `before_flush` global capture create/revoke. Tests `test_attestation_audit_log.py` couvrent les 4 cas (create_manual, create_llm, revoke_pme, revoke_admin). |
| **Invariant projet n°4 (Money typed F04)** | PASS | Pas de champ monétaire direct sur `attestations`. Le `payload` JSONB stocke les snapshots Money complets pour les `target_amount` des projets associés (paire amount/currency). Pas de `*_xof` simple. |
| **Invariant projet n°7 (admin only catalogue)** | PASS | Aucun tool LLM ne mute le catalogue. Le tool `generate_credit_certificate` mute l'entité métier `Attestation` (donnée user), pas le catalogue. Le tool `revoke_attestation` (futur, hors-scope F08 si pas demandé) ne sera pas exposé au LLM dans cette feature — la révocation passe uniquement par UI explicite. |
| **Invariant projet n°8 (dark mode)** | PASS | Les 4 composants authentifiés implémentent toutes les variantes `dark:` (`dark:bg-dark-card`, `dark:text-surface-dark-text`, `dark:border-dark-border`, `dark:hover:bg-dark-hover`). Layout `public.vue` neutre (clair par défaut, pas de toggle — design soigné mobile-first). |
| **Invariant projet n°9 (réutilisabilité composants)** | PASS | Audit pré-implémentation : aucun composant équivalent dans `frontend/app/components/`. Réutilise `<MoneyDisplay>` (F04) si scores monétaires affichés, `<SourceLink>` (F01) dans l'annexe sources du PDF, `useFocusTrap` (F18 héritage). Crée des composants génériques : `AttestationStatusBadge` paramétrable via prop `status`, `HashCompareInput` paramétrable via prop `expected`. |
| **Invariant projet n°10 (français accents)** | PASS | Tous les libellés UI, messages d'erreur, prompts et docstrings français contiennent les accents (é, è, ê, à, ç, ù) : « Générer », « Révoquée », « Authentifiée », « Délivrée », « Vérification ». |
| **Invariant projet n°11 (tests E2E exécutables)** | PASS | Spec Playwright `frontend/tests/e2e/F08-attestation-verifiable-ed25519.spec.ts` avec 5 scénarios (générer authentique, altération PDF, révocation, expiration, UUID invalide) ; helpers `F08-helpers.ts` pour mock backend. |
| **Invariant projet n°12 (couverture ≥ 80 %)** | PASS | Couverture cible ≥ 85 % sur les modules cryptographiques (`signing.py`, `qr.py`, `service.py`) ; ≥ 80 % global F08 (frontend + backend). |

**Décision constitutionnelle** : ✅ TOUS LES GATES PASSENT. Aucune violation à justifier dans Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/026-attestation-verifiable-ed25519/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (interfaces backend)
│   ├── attestations-api.md
│   ├── public-api.md
│   └── attestations-tools-langchain.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spec.md              # Feature specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 026_create_attestations.py          # Migration F08 (down_revision=025_create_projects si F06 mergé, sinon 024_carbone_mix_uemoa — décidé au moment du merge orchestrateur)
├── app/
│   ├── core/
│   │   ├── config.py                       # +ATTESTATION_PRIVATE_KEY_PEM, +ATTESTATION_PUBLIC_KEY_ID, +ATTESTATION_VALIDITY_DAYS, +ATTESTATION_VERIFICATION_BASE_URL
│   │   └── auditable.py                    # +Attestation dans AUDITABLE_MODELS
│   ├── models/
│   │   └── attestation.py                  # NEW — Modèle SQLAlchemy Attestation (Auditable, UUIDMixin, TimestampMixin)
│   ├── modules/
│   │   └── attestations/                   # NEW — Module métier complet
│   │       ├── __init__.py
│   │       ├── service.py                  # generate_attestation, revoke_attestation, verify_attestation, list_attestations_for_user, list_all_attestations_admin
│   │       ├── signing.py                  # SigningKeyStore singleton, sign_payload, verify_signature, build_canonical_payload
│   │       ├── qr.py                       # generate_qr_code (segno → PNG)
│   │       ├── pdf.py                      # build_attestation_pdf (WeasyPrint avec template enrichi)
│   │       ├── router.py                   # 4 endpoints API REST authentifiés (POST génération, GET liste PME, POST id/revoke, GET id/download)
│   │       ├── admin_router.py             # 2 endpoints admin (GET liste cross-tenant, POST id/revoke)
│   │       ├── schemas.py                  # Pydantic v2 strict : AttestationCreate, AttestationRead, AttestationSummary, AttestationRevoke, VerificationResult (discriminated union par status)
│   │       └── templates/
│   │           └── attestation_template.html  # NEW — Template enrichi (refactor de credit/certificate_template.html)
│   ├── api/
│   │   ├── public.py                       # NEW — Router public (no-auth) : GET /api/public/verify/{id}, GET /api/public/attestation-public-key, RATE LIMITING 10 req/IP/min
│   │   └── deps.py                         # Inchangé (auth + RLS héritées F02 + get_current_admin F02)
│   ├── graph/tools/
│   │   └── credit_tools.py                 # Refactor generate_credit_certificate placeholder → appel réel attestations.service.generate_attestation
│   ├── prompts/
│   │   └── credit.py                       # +mention « le tool generate_credit_certificate retourne maintenant une URL de vérification publique »
│   ├── main.py                             # +include_router(public.router, prefix='/api/public', tags=['public']) AVANT middleware auth + include_router(attestations.router, prefix='/api/attestations') + include_router(attestations.admin_router, prefix='/api/admin/attestations') + lifespan startup check ATTESTATION_PRIVATE_KEY_PEM
│   └── middleware/
│       └── rate_limit.py                   # NEW — middleware FastAPI rate limiting 10 req/IP/min sur /api/public/verify/* (cache LRU local)
├── scripts/
│   └── generate_attestation_keypair.py     # NEW — one-shot bootstrap : génère paire Ed25519 (PEM + public_key_id) à imprimer sur stdout
└── tests/
    ├── unit/
    │   ├── test_attestation_signing.py     # Tests SigningKeyStore (chargement, sign, verify, canonical JSON, idempotence)
    │   ├── test_attestation_qr.py          # Tests segno → PNG valide + URL correcte
    │   ├── test_attestation_pdf.py         # Tests WeasyPrint hash SHA-256 stable + contenu (QR, hash, identifiant visible)
    │   ├── test_attestation_schemas.py     # Tests Pydantic strict (AttestationCreate, VerificationResult discriminated union)
    │   └── test_attestation_tools_unit.py  # Tests tool generate_credit_certificate (mock service)
    ├── integration/
    │   ├── test_attestation_create_flow.py # Tests POST /api/attestations (génération complète : PDF + signature + QR + persistance + audit log)
    │   ├── test_attestation_verify_public.py # Tests GET /api/public/verify/{id} (4 statuts : authentic, revoked, expired, invalid + uniformité timing)
    │   ├── test_attestation_revoke.py      # Tests POST /api/attestations/{id}/revoke (PME) + admin_router (admin)
    │   ├── test_attestation_rls_cross_tenant.py # Tests RLS isolation 2 comptes
    │   ├── test_attestation_audit_log.py   # Tests audit log F03 (manual/llm/admin)
    │   ├── test_attestation_rate_limit.py  # Tests rate limiting 10 req/IP/min sur public verify
    │   ├── test_public_key_endpoint.py     # Tests GET /api/public/attestation-public-key
    │   └── test_attestation_tool_integration.py # Tests tool generate_credit_certificate via graph
    └── migrations/
        └── test_alembic_f08.py             # Tests up/down/up

frontend/
├── app/
│   ├── pages/
│   │   ├── verify/
│   │   │   └── [id].vue                    # NEW — Page publique no-auth (layout: 'public') affiche 4 statuts + comparaison hash
│   │   ├── attestations/
│   │   │   └── index.vue                   # NEW — Liste des attestations PME + actions (télécharger, copier URL, révoquer)
│   │   ├── admin/
│   │   │   └── attestations/
│   │   │       └── index.vue               # NEW — Liste admin cross-tenant + révocation
│   │   └── credit-score/
│   │       └── index.vue                   # MODIFIÉ — bouton « Générer attestation » appelle réellement le service
│   ├── layouts/
│   │   └── public.vue                      # NEW — Layout réutilisable (header simple, pas de sidebar, pas de auth)
│   ├── middleware/
│   │   └── auth.global.ts                  # MODIFIÉ — Autoriser /verify/, /legal/ en pages publiques (REGEX exception)
│   ├── components/
│   │   └── attestations/
│   │       ├── AttestationCard.vue         # NEW
│   │       ├── AttestationStatusBadge.vue  # NEW (paramétrable via prop status)
│   │       ├── RevokeAttestationModal.vue  # NEW (focus trap)
│   │       └── HashCompareInput.vue        # NEW (comparaison hash visible/PDF)
│   ├── composables/
│   │   └── useAttestations.ts              # NEW
│   ├── i18n/
│   │   └── verify.ts                       # NEW — Libellés FR/EN pour la page publique (4 statuts + boutons)
│   └── types/
│       └── attestation.ts                  # NEW — Types TS Attestation, VerificationResult (discriminated union TS)
└── tests/
    ├── unit/
    │   ├── AttestationCard.spec.ts         # Vitest
    │   ├── AttestationStatusBadge.spec.ts  # Vitest
    │   ├── RevokeAttestationModal.spec.ts  # Vitest (focus trap)
    │   ├── HashCompareInput.spec.ts        # Vitest (comparaison strict)
    │   └── useAttestations.spec.ts         # Vitest (composable)
    └── e2e/
        ├── F08-attestation-verifiable-ed25519.spec.ts  # Playwright 5 scénarios
        └── F08-helpers.ts                  # Helpers mock backend

docs/
└── attestations-and-verification.md        # NEW — Documentation : how it works, format canonique JSON, vérification offline avec clé publique, procédure rotation post-MVP
```

**Structure Decision** : Architecture modulaire stricte respectant le pattern existant `app/modules/<feature>/` (cf. modules `audit`, `financing`, `applications`, `credit`). Le router public `app/api/public.py` est un router transverse (pas dans un module métier) car il doit être monté AVANT le middleware d'auth dans `app/main.py` — cette zone est interdite en parallèle (cf. `.cc-orchestrator.md` ZONES INTERDITES) mais F08 est seul à toucher cette zone donc pas de conflit. La modification de `auth.global.ts` est zone interdite mais isolée à F08 (autres features ne touchent pas ce middleware en parallèle).

## Phase 0 : Outline & Research

Voir `research.md` pour les décisions de design technique :

1. **Choix `cryptography>=41.0` vs `pynacl>=1.5`** : décision `cryptography` (clarification Q1).
2. **Choix `segno>=1.5` vs `qrcode>=7.4`** : décision `segno` (clarification Q2).
3. **Stockage clé privée** : décision env var + `SigningKeyStore` singleton (clarification Q3).
4. **Énumération uniforme** : décision statut uniforme + rate limiting + pas de différenciation timing (clarification Q4).
5. **Whitelist métadonnées publiques** : décision RGPD-minimaliste (clarification Q5).
6. **Format canonique JSON pour signature** : `json.dumps(..., sort_keys=True, separators=(",", ":"))` UTF-8 — déterministe, reproductible offline.
7. **Pattern compteur séquentiel `ATT-YYYY-NNNNN`** : compteur scopé `account_id + année` (pas de table `attestation_counters` ; calcul via `SELECT COUNT(*) FROM attestations WHERE account_id=? AND date_part('year', valid_from)=?` + 1, à la création de la ligne).
8. **Réutilisation composants** : `<SourceLink>` (F01), `useFocusTrap` (F18 héritage), `<MoneyDisplay>` (F04) si scores monétaires.

## Phase 1 : Design & Contracts

Voir :
- `data-model.md` : schéma SQL complet (table `attestations`), modèle SQLAlchemy, contraintes CHECK, indexes (sur `(account_id, valid_until)` et `(revoked_at)`), RLS policies.
- `contracts/attestations-api.md` : 4 endpoints REST authentifiés (POST génération, GET liste PME, POST id/revoke, GET id/download) avec request/response schemas Pydantic, codes HTTP, exemples curl.
- `contracts/public-api.md` : 2 endpoints publics no-auth (GET verify/{id} avec discriminated union par status, GET attestation-public-key) + détail des 4 statuts + détail rate limiting.
- `contracts/attestations-tools-langchain.md` : 1 tool LangChain refactoré `generate_credit_certificate` avec schema Pydantic `GenerateCertificateArgs`, exemples d'invocation et exemples de réponses.
- `quickstart.md` : guide de démarrage local (générer paire de clés Ed25519, injecter en .env, migrer DB, créer une attestation via API, vérifier via page publique, révoquer, vérifier la révocation).

## Phase 2 : Tasks

Voir `tasks.md` (généré par `/speckit.tasks`).

## Complexity Tracking

| Sujet | Choix retenu | Alternative écartée | Rationale |
|-------|-------------|---------------------|-----------|
| Lib crypto | `cryptography>=41.0` | `pynacl>=1.5` | Lib mainstream PyCA, déjà transitivement présente, API simple. `pynacl` éligible post-MVP si HSM. |
| Lib QR | `segno>=1.5` | `qrcode>=7.4` (avec Pillow) | `segno` plus léger, pas de dépendance Pillow obligatoire. `qrcode` éligible si overlay logo post-MVP. |
| Stockage clé privée | Env var + `SigningKeyStore` singleton | Vault / AWS Secrets Manager | MVP minimal, env var suffit avec secret manager d'infra prod. Vault/AWS post-MVP. |
| Distinction `invalid` (UUID inexistant vs signature corrompue) | Aucune (statut uniforme) | 404 vs 200 invalid | Anti-énumération : pas de leak de l'existence d'un UUID. SC-006 valide statistiquement la non-distinction de timing. |
| Whitelist métadonnées publiques | DTO explicite côté serveur | Sérialisation auto SQLAlchemy → JSON | Principe RGPD minimisation. Pas de fuite par oubli de filtrage. Code review-friendly. |
| Compteur `ATT-YYYY-NNNNN` | Calcul à la volée via `COUNT(*)` | Table dédiée `attestation_counters` | Volumétrie attendue ~1000/mois → COUNT scalable. Pas de table satellite supplémentaire. |
| Rate limiting | Cache LRU local FastAPI (slowapi-style) | Redis | MVP sans Redis. Acceptable car clé = IP, durée = 1 min, déclenchement max ~600 hits/min global. Migration Redis post-MVP si scaling. |
| Génération PDF | Synchrone (< 5 s) | Async via Celery | MVP sans Celery. Acceptable car latence acceptable côté UX (message de patience). Bascule background task si > 10 s. |
| Layout `public.vue` | Réutilisable (`/legal/*`, `/verify/*`) | Hardcodé dans la page | Anticipation F09 (Legal pages). Layout neutre clair, pas de toggle dark/light. |
| Page publique design | Mobile-first | Desktop-first | Le fund officer scanne avec un téléphone (cas d'usage primaire). SC-002/003 valident scan QR + chargement < 2 s sur 3G. |
| i18n FR/EN | Limitée à la page publique | Globale tout le projet | i18n globale = scope inflation (autres features non internationalisées). MVP : 4 statuts + libellés boutons sur `/verify/[id]` uniquement. Détection via `Accept-Language` ou `?lang=en`. |
| Down_revision Alembic | Conditionnelle (`025_create_projects` ou `024_carbone_mix_uemoa`) | Fixe | F06 (`025`) en cours en parallèle (branche `feat/F06`). L'orchestrateur sérialise les merges Alembic. La migration `026` sera ajustée au moment du merge selon l'état de `main`. |
| Référence depuis F15 (FundApplication.attestation_id) | Différé F15 | FK ajoutée maintenant nullable | Hors-scope F08 strict. F15 ajoutera la colonne `fund_applications.attestation_id` quand le besoin sera concrétisé. Pas de pré-câblage spéculatif. |
