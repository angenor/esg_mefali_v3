---

description: "Task list — F08 Attestation Vérifiable Ed25519 + QR + Page publique + Révocation (Module 5.3)"
---

# Tasks: F08 — Attestation Vérifiable Ed25519 + QR + Page publique `/verify/{id}` + Révocation (Module 5.3)

**Input** : Design documents from `/specs/026-attestation-verifiable-ed25519/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Branch** : `feat/F08-attestation-verifiable-ed25519` (alias SpecKit `026-attestation-verifiable-ed25519`)

**Tests** : Tests TDD obligatoires (cycle Red-Green-Refactor enforce, couverture cible ≥ 85 % sur `signing.py`/`qr.py`/`service.py`, ≥ 80 % global F08).

**Organization** : Tasks groupées par user story (US1, US2, US3, US4, US5, US6) pour livraison incrémentale.

## Format : `[ID] [P?] [Story] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance bloquante)
- **[Story]** : Rattachement user story (US1, US2, US3, US4, US5, US6) ; absent pour Setup/Foundational/Polish
- Chemins absolus depuis racine repo

## Path Conventions

- **Backend** : `backend/app/`, `backend/tests/`, `backend/alembic/versions/`, `backend/scripts/`
- **Frontend** : `frontend/app/`, `frontend/tests/`
- **Specs** : `specs/026-attestation-verifiable-ed25519/`
- **Docs** : `docs/`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer l'environnement de développement et vérifier les prérequis (F01, F02, F03, F04 mergés).

- [ ] T001 Vérifier l'activation du venv backend (`source backend/venv/bin/activate`) et que `which python` pointe vers `backend/venv/bin/python`.
- [ ] T002 Ajouter `cryptography>=41.0` et `segno>=1.5` à `backend/requirements.txt` (zone interdite — modification minimale, vérifier qu'aucune autre feature ne touche ce fichier en parallèle).
- [ ] T003 [P] Installer les nouvelles dépendances : `cd backend && source venv/bin/activate && pip install -r requirements.txt`. Vérifier `python -c "import cryptography, segno; print(cryptography.__version__, segno.__version__)"`.
- [ ] T004 Vérifier que les migrations F01/F02/F03/F04/F12/F17 sont appliquées localement (`cd backend && alembic current` doit afficher au moins `024_carbone_mix_uemoa`) et que les tables F02 (`accounts`, `refresh_tokens`, `account_invitations`) existent ainsi que la table `audit_log` (F03).
- [ ] T005 [P] Vérifier que les dépendances frontend sont à jour (`cd frontend && npm install`) et que Playwright est installé (`npx playwright install`).
- [ ] T006 Créer le dossier `backend/uploads/attestations/{pdfs,qr}/` (gitignored). Vérifier les permissions d'écriture.

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Migration Alembic, modèle SQLAlchemy, schémas Pydantic, modules cryptographiques (signing, qr) et configuration — prérequis bloquants pour toutes les user stories.

**⚠️ CRITICAL** : Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Foundational (TDD — écrire AVANT implémentation, vérifier qu'ils ÉCHOUENT)

- [ ] T007 [P] Écrire `backend/tests/unit/test_attestation_model.py` : modèle `Attestation` avec contraintes CHECK (`attestation_type_chk`, `pdf_hash_sha256_format_chk`, `valid_until_after_from_chk`, `revoked_consistency_chk`, `display_id_format_chk`, `public_key_id_format_chk`) ; UNIQUE constraint sur `display_id` ; relations `user`, `revoked_by_user`, `account` lazy=noload.
- [ ] T008 [P] Écrire `backend/tests/unit/test_attestation_schemas.py` : schémas Pydantic `AttestationCreate`, `AttestationRevoke`, `AttestationRead`, `AttestationSummary`, `VerificationResult` (discriminated union par `status` avec 4 variantes : `AuthenticVerification`, `RevokedVerification`, `ExpiredVerification`, `InvalidVerification`).
- [ ] T009 [P] Écrire `backend/tests/migrations/test_alembic_f08.py` : (a) up/down/up sans erreur ; (b) table `attestations` créée avec 21 colonnes, 6 contraintes CHECK, 5 indexes ; (c) RLS policies créées (`pme_access_own_account`, `admin_full_access`) ; (d) sur SQLite (tests CI), skip RLS et CHECK ~regex (fallback applicatif Pydantic).
- [ ] T010 [P] Écrire `backend/tests/unit/test_attestation_signing.py` : `SigningKeyStore` charge clé depuis env, `sign_payload(canonical: str) -> str` retourne signature base64 ; `verify_signature(signature_b64, canonical: str) -> bool` valide ; `build_canonical_payload(attestation_data: dict) -> str` produit JSON canonique (sort_keys, separators) ; idempotence (signature stable pour même payload).
- [ ] T011 [P] Écrire `backend/tests/unit/test_attestation_qr.py` : `generate_qr_code(verification_url: str, output_path: Path) -> Path` produit un PNG valide via `segno`, lecture du PNG retourne bien l'URL (test avec lib de décodage QR `pyzbar` en fixture optionnelle, sinon vérifier la taille du fichier > 100 bytes et le magic byte PNG).

### Implementation Foundational

- [ ] T012 Créer `backend/app/models/attestation.py` avec classe `Attestation(Auditable, UUIDMixin, TimestampMixin, Base)` selon `data-model.md` § Modèle SQLAlchemy (toutes colonnes, indexes, CHECK contraintes, relations).
- [ ] T013 Modifier `backend/app/core/auditable.py` : ajouter `"Attestation"` dans `AUDITABLE_MODELS`.
- [ ] T014 Modifier `backend/app/core/config.py` (zone interdite — modification minimale) : ajouter 4 variables `ATTESTATION_PRIVATE_KEY_PEM` (str, default=""), `ATTESTATION_PUBLIC_KEY_ID` (str, default="v1"), `ATTESTATION_VALIDITY_DAYS` (int, default=365), `ATTESTATION_VERIFICATION_BASE_URL` (str, default="https://esg-mefali.com") avec validateur `field_validator` qui exige `ATTESTATION_PRIVATE_KEY_PEM` non vide en production.
- [ ] T015 Créer la migration Alembic `backend/alembic/versions/026_create_attestations.py` (revision=`026_create_attestations`, down_revision=`025_create_projects` si F06 mergé en parallèle, sinon `024_carbone_mix_uemoa` — décidé au merge orchestrateur) selon `data-model.md` § Migration. Tester localement `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.
- [ ] T016 Créer `backend/app/modules/attestations/__init__.py` (vide).
- [ ] T017 Créer `backend/app/modules/attestations/schemas.py` avec tous les schémas Pydantic v2 strict de `data-model.md` § Schémas Pydantic (AttestationCreate, AttestationRevoke, AttestationRead, AttestationSummary, VerificationResult discriminated union).
- [ ] T018 Créer `backend/app/modules/attestations/signing.py` avec :
  - Classe `SigningKeyStore` singleton chargeant `ATTESTATION_PRIVATE_KEY_PEM` au startup, exposant `sign(canonical: bytes) -> bytes` et `verify(signature: bytes, canonical: bytes) -> bool` via `cryptography.hazmat.primitives.asymmetric.ed25519`.
  - Fonction `build_canonical_payload(attestation_id, scores, referential_snapshot, pdf_hash_sha256, valid_from, valid_until) -> str` produisant JSON canonique (`json.dumps(..., sort_keys=True, separators=(",", ":"))`, encoding UTF-8).
  - Fonction `sign_payload(canonical: str) -> str` retournant base64 de la signature.
  - Fonction `verify_signature(signature_b64: str, canonical: str) -> bool` (catch `InvalidSignature` → False).
  - Fonction `get_public_key_pem() -> str` exposant la clé publique PEM.
- [ ] T019 Créer `backend/app/modules/attestations/qr.py` avec fonction `generate_qr_code(verification_url: str, output_path: Path) -> Path` utilisant `segno.make(verification_url, error="M")` puis `.save(output_path, scale=10)`.
- [ ] T020 Créer `backend/scripts/generate_attestation_keypair.py` : script one-shot qui génère une paire Ed25519 via `cryptography`, imprime sur stdout les 3 lignes `ATTESTATION_PRIVATE_KEY_PEM=...`, `ATTESTATION_PUBLIC_KEY_ID=v1`, `ATTESTATION_PUBLIC_KEY_PEM=...` (clé publique informative pour mémoire) ; usage : `python backend/scripts/generate_attestation_keypair.py`.
- [ ] T021 Modifier `backend/app/main.py` (zone interdite — modification minimale) : ajouter au `lifespan` startup un appel à `SigningKeyStore.initialize()` qui valide que la clé privée est chargeable (en production, `raise SystemExit(1)` si `ATTESTATION_PRIVATE_KEY_PEM` vide).

**Checkpoint** : Foundational complet. Tests T007-T011 passent. Migration `up/down/up` OK.

---

## Phase 3 : User Story 1 — Une PME génère une attestation signée et l'envoie à son banquier (Priority: P1)

**Goal** : Permettre la génération d'une attestation complète (PDF + signature + QR + persistence) via UI directe et la lister sur la page `/attestations`.

**Independent Test** : se connecter en PME, accéder à `/attestations`, cliquer « Générer », confirmer type `combined`, vérifier ligne `attestations` créée et PDF/QR sur disque, télécharger le PDF, vérifier qu'il contient le QR + le hash SHA-256 + l'identifiant `ATT-YYYY-NNNNN`.

### Tests for User Story 1 (TDD — écrire AVANT implémentation)

- [ ] T022 [P] [US1] Écrire `backend/tests/unit/test_attestation_pdf.py` : `build_attestation_pdf(attestation_data, template_path) -> (pdf_bytes, pdf_hash_sha256)` produit un PDF non vide, hash SHA-256 hex 64 chars lowercase ; vérifier que l'identifiant `ATT-YYYY-NNNNN` apparaît dans le contenu du PDF (extraction via PyMuPDF en test) ; vérifier que le QR base64 est embarqué.
- [ ] T023 [P] [US1] Écrire `backend/tests/integration/test_attestation_create_flow.py` : POST /api/attestations avec `attestation_type='combined'` → 201 avec tous les champs ; ligne `attestations` insérée avec `signature_ed25519` non vide, `pdf_hash_sha256` 64 chars hex, `display_id` au format `ATT-YYYY-NNNNN`, `valid_from=now()`, `valid_until=now()+365d` ; fichier PDF existe sur disque à `pdf_path` ; fichier PNG QR existe sur disque à `qr_code_path` ; audit log F03 contient 1 entrée `action='create' source_of_change='manual'`.
- [ ] T024 [P] [US1] Écrire `backend/tests/integration/test_attestation_audit_log.py` : (a) génération manuelle UI → audit_log create source='manual' actor_role='pme' ; (b) après revoke (US3) → audit_log revoke ; (c) admin revoke (US4) → audit_log revoke source='manual' actor_role='admin'.
- [ ] T025 [P] [US1] Écrire `backend/tests/integration/test_attestation_rls_cross_tenant.py` : 4 cas (PME-A liste / get / download PDF / revoke sur attestation PME-B) → 0 résultat ou 404 ; admin contourne (admin_full_access).
- [ ] T026 [P] [US1] Écrire `frontend/tests/unit/AttestationCard.spec.ts` : props (attestation), affichage display_id/type/status/valid_from/valid_until, badges status via `<AttestationStatusBadge>` (mock), boutons (Télécharger PDF, Copier URL, Révoquer si non révoquée) ; emits ; dark mode.
- [ ] T027 [P] [US1] Écrire `frontend/tests/unit/AttestationStatusBadge.spec.ts` : props `:status` (4 valeurs), classes Tailwind correctes (vert/rouge/orange/rouge), texte FR, ARIA `role="status"` `aria-live="polite"`.
- [ ] T028 [P] [US1] Écrire `frontend/tests/unit/useAttestations.spec.ts` : composable `generateAttestation(type)`, `listAttestations(filters)`, `getAttestation(id)`, `revokeAttestation(id, reason)`, `downloadPdf(id)` ; mock `$fetch`.

### Implementation for User Story 1

- [ ] T029 [US1] Créer `backend/app/modules/attestations/pdf.py` avec fonction `build_attestation_pdf(attestation_data: dict, qr_path: Path, output_pdf_path: Path) -> tuple[Path, str]` utilisant WeasyPrint + Jinja2 sur `templates/attestation_template.html` ; calcule SHA-256 après écriture finale.
- [ ] T030 [US1] Créer `backend/app/modules/attestations/templates/attestation_template.html` : template enrichi (refactor de `credit/certificate_template.html`) avec QR embarqué (`<img src="data:image/png;base64,{{qr_b64}}">`), display_id, scores, référentiels avec versions, hash SHA-256 en pied de page, annexe sources F01.
- [ ] T031 [US1] Créer `backend/app/modules/attestations/service.py` avec fonctions async (utilisant `AsyncSession`) :
  - `generate_attestation(db, account_id, user_id, attestation_type, source_of_change='manual') -> Attestation` orchestrant : (1) load scores depuis CreditScore + EsgAssessment, (2) compute display_id via COUNT(*), (3) generate QR temporaire, (4) build PDF, (5) compute SHA-256, (6) build canonical payload, (7) sign via SigningKeyStore, (8) persist row + audit log, (9) move temp QR/PDF vers final paths.
  - `revoke_attestation(db, account_id, user_id, attestation_id, reason, actor_role='pme') -> Attestation`.
  - `verify_attestation(db, attestation_id) -> VerificationResult` (calcule status authentic/revoked/expired/invalid).
  - `list_attestations_for_user(db, account_id, filters) -> list[AttestationSummary]`.
  - `list_all_attestations_admin(db, filters) -> list[AttestationSummary]` (avec account_id).
- [ ] T032 [US1] Créer `backend/app/modules/attestations/router.py` avec 4 endpoints PME (POST génération, GET liste, POST id/revoke, GET id/download) protégés par `Depends(get_current_user)`.
- [ ] T033 [US1] Modifier `backend/app/main.py` (zone interdite) : ajouter `from app.modules.attestations.router import router as attestations_router` et `app.include_router(attestations_router, prefix="/api/attestations", tags=["attestations"])`.
- [ ] T034 [US1] Vérifier en local : démarrer backend + tester via curl POST /api/attestations selon `quickstart.md` § Étape 1.
- [ ] T035 [US1] [P] Créer `frontend/app/types/attestation.ts` avec types TypeScript `Attestation`, `AttestationSummary`, `VerificationResult` (discriminated union TS par `status`).
- [ ] T036 [US1] Créer `frontend/app/composables/useAttestations.ts` avec 5 méthodes (generateAttestation, listAttestations, getAttestation, revokeAttestation, downloadPdf) via `useFetchAuth`.
- [ ] T037 [US1] [P] Créer `frontend/app/components/attestations/AttestationStatusBadge.vue` : badge paramétrable via prop `:status: 'authentic' | 'revoked' | 'expired' | 'invalid'`, classes Tailwind dark mode complet, ARIA `role="status"`.
- [ ] T038 [US1] Créer `frontend/app/components/attestations/AttestationCard.vue` : card complète avec display_id, type, status badge, dates, 3 boutons (Télécharger / Copier URL / Révoquer si non révoquée) ; emits `revoke`, `download` ; dark mode.
- [ ] T039 [US1] Créer `frontend/app/pages/attestations/index.vue` : page liste authentifiée des attestations PME ; bouton CTA « Générer une attestation vérifiable » ouvrant un modal de choix (`credit_score | esg_assessment | combined`) ; affiche les attestations via `<AttestationCard>` triées par created_at DESC ; dark mode complet.
- [ ] T040 [US1] Modifier `frontend/app/pages/credit-score/index.vue` : remplacer le bouton « Générer attestation » placeholder par un appel réel à `useAttestations.generateAttestation()` ; après succès, afficher l'URL de vérification + bouton « Copier en presse-papier » + lien « Voir mes attestations » → `/attestations`.

**Checkpoint** : User story 1 testable indépendamment. Backend POST /api/attestations + GET /api/attestations + GET /api/attestations/{id}/download fonctionnels. Pages `/attestations` et `/credit-score` opérationnelles.

---

## Phase 4 : User Story 2 — Un fund officer scanne le QR avec son téléphone et lit la page publique (Priority: P1)

**Goal** : Exposer un endpoint backend public no-auth `GET /api/public/verify/{id}` et une page Vue `/verify/[id]` accessible sans authentification, mobile-first responsive.

**Independent Test** : générer attestation via US1, ouvrir verification_url dans onglet privé sans cookies → page se charge sans redirect login, badge AUTHENTIQUE affiché, hash visible match hash PDF imprimé.

### Tests for User Story 2 (TDD)

- [ ] T041 [P] [US2] Écrire `backend/tests/integration/test_attestation_verify_public.py` : (a) GET /api/public/verify/{id} sans token → 200 avec status='authentic' et tous champs whitelistés ; (b) GET avec UUID inexistant → 200 status='invalid' (pas 404, pas de leak) ; (c) GET avec UUID valide mais signature corrompue (mock SQL UPDATE pour tester) → 200 status='invalid' ; (d) GET sur attestation révoquée → 200 status='revoked' avec revoked_at, revoked_reason, revoked_by_role='pme' (sans nom) ; (e) GET sur attestation expirée → 200 status='expired' ; (f) `Accept-Language: en` → message en anglais.
- [ ] T042 [P] [US2] Écrire `backend/tests/integration/test_public_key_endpoint.py` : GET /api/public/attestation-public-key sans token → 200 avec `{public_key_id, algorithm, public_key_pem, canonical_format_doc_url, issued_at}`.
- [ ] T043 [P] [US2] Écrire `backend/tests/integration/test_attestation_rate_limit.py` : 15 requêtes en 30 sec depuis même IP → ≥ 95 % retournent 429 après le 10e hit ; vérifier header `Retry-After: 60`.
- [ ] T044 [P] [US2] Écrire `backend/tests/integration/test_verify_timing_uniformity.py` (SC-006) : 100 requêtes par classe (authentic / invalid_uuid_inexistant / invalid_signature_corrompue), mesurer latence p50/p95, test Mann-Whitney U → p > 0.1 confirmé (pas de différence statistiquement significative).
- [ ] T045 [P] [US2] Écrire `frontend/tests/unit/HashCompareInput.spec.ts` : props `:expected: string`, comparaison stricte case-sensitive ; emit `compared` avec `{match: boolean}` ; dark mode (mais layout public clair).
- [ ] T046 [P] [US2] Écrire `frontend/tests/unit/PublicLayout.spec.ts` : layout `public.vue` rend `<header>` simple (« ESG Mefali — Vérification d'attestation »), pas de sidebar, pas de user menu, footer minimaliste.

### Implementation for User Story 2

- [ ] T047 [US2] Créer `backend/app/middleware/rate_limit.py` : middleware FastAPI rate limiting via cache LRU local (clé = IP, TTL 60s, capacity 10000 IPs) ; appliqué uniquement aux routes matching `/api/public/verify/*` ; au-delà du seuil → HTTPException(429, {"error": "rate_limit_exceeded", "retry_after": 60}) avec header.
- [ ] T048 [US2] Créer `backend/app/api/public.py` : router public no-auth avec 2 endpoints (`GET /verify/{attestation_id}`, `GET /attestation-public-key`) qui renvoient le DTO discriminated union ; whitelist explicite des champs côté serveur (jamais de sérialisation auto SQLAlchemy → JSON).
- [ ] T049 [US2] Modifier `backend/app/main.py` (zone interdite) : ajouter `from app.api.public import router as public_router` et `app.include_router(public_router, prefix="/api/public", tags=["public"])` AVANT le middleware d'auth global ; ajouter le middleware rate_limit pour les routes `/api/public/verify/*`.
- [ ] T050 [US2] Modifier `frontend/app/middleware/auth.global.ts` (zone interdite) : ajouter exception regex pour `/^\/verify\/[^\/]+/` et `/^\/legal\//` (pages publiques). Vérifier que l'exception ne breaks pas les routes auth existantes (`/login`, `/register`).
- [ ] T051 [US2] Créer `frontend/app/layouts/public.vue` : layout réutilisable (header simple « ESG Mefali — Vérification d'attestation », pas de sidebar, pas de user menu, footer minimaliste « © ESG Mefali — Plateforme de finance durable », design clair par défaut, mobile-first).
- [ ] T052 [US2] Créer `frontend/app/i18n/verify.ts` : libellés FR/EN pour les 4 statuts (`AUTHENTIQUE/AUTHENTIC`, `RÉVOQUÉE/REVOKED`, `EXPIRÉE/EXPIRED`, `INVALIDE/INVALID`) + boutons (« Comparer avec votre PDF / Compare with your PDF », « Copier l'identifiant / Copy ID », messages d'aide).
- [ ] T053 [US2] [P] Créer `frontend/app/components/attestations/HashCompareInput.vue` : input texte pour coller le hash du PDF reçu, comparaison stricte avec `:expected` prop, feedback visuel (vert si match, rouge si non) ; ARIA `aria-describedby` pour message ; mobile-first (touch ≥ 44x44 px).
- [ ] T054 [US2] Créer `frontend/app/pages/verify/[id].vue` : page publique no-auth utilisant layout `public.vue` ; fetch côté serveur (SSR) `GET /api/public/verify/{id}` ; affichage selon `status` (4 variantes via discriminated union TS) ; badge `<AttestationStatusBadge>` ; pour `status='authentic'`, affichage scores en cartes empilées + référentiels + `<HashCompareInput :expected="hash">` ; pour `revoked` affichage `revoked_at`, `revoked_reason`, `revoked_by_role` ; détection `Accept-Language` ou `?lang=en` ; mobile-first responsive ; pas de toggle dark/light (design clair par défaut).
- [ ] T055 [US2] Vérifier en local : démarrer backend + frontend + ouvrir `http://localhost:3000/verify/{attestation_id}` dans onglet privé → page charge sans redirect login, badge AUTHENTIQUE affiché.

**Checkpoint** : User story 2 testable indépendamment. Endpoint public + page publique fonctionnels, mobile-first OK, rate limiting OK, uniformité timing validée (T044).

---

## Phase 5 : User Story 3 — La PME révoque une attestation devenue obsolète (Priority: P1)

**Goal** : Permettre à la PME propriétaire de révoquer son attestation via UI ; la page publique reflète le statut RÉVOQUÉE immédiatement.

**Independent Test** : créer attestation, accéder `/attestations`, cliquer « Révoquer », saisir raison, valider. Vérifier `revoked_at`/`revoked_reason`/`revoked_by_user_id` peuplés. Recharger `/verify/{id}` → RÉVOQUÉE.

### Tests for User Story 3 (TDD)

- [ ] T056 [P] [US3] Écrire `backend/tests/integration/test_attestation_revoke.py` : (a) PME révoque sa propre attestation avec raison ≥ 10 chars → 200 + audit log ; (b) PME tente révoquer attestation autre tenant → 404 (RLS) ; (c) PME tente révoquer attestation déjà révoquée → 409 already_revoked ; (d) raison < 10 chars → 400 validation_error ; (e) après revoke, GET /api/public/verify/{id} retourne `status='revoked'`.
- [ ] T057 [P] [US3] Écrire `frontend/tests/unit/RevokeAttestationModal.spec.ts` : modal confirmation avec input raison (min 10 chars validation côté client), boutons « Annuler » / « Confirmer la révocation » ; ARIA `role="dialog"` `aria-modal="true"` ; focus trap (réutilise `useFocusTrap`) ; emit `confirm` avec raison ; dark mode complet.

### Implementation for User Story 3

- [ ] T058 [US3] Étendre `backend/app/modules/attestations/router.py` avec endpoint `POST /attestations/{id}/revoke` (déjà tracé dans phase 3 mais pas implémenté) : valide AttestationRevoke schema, appelle `service.revoke_attestation(...)`, gère 404/409.
- [ ] T059 [US3] [P] Créer `frontend/app/components/attestations/RevokeAttestationModal.vue` : modal de confirmation avec input raison + validation min 10 chars + boutons ; focus trap réutilisant `useFocusTrap` (héritage F18) ; dark mode complet.
- [ ] T060 [US3] Modifier `frontend/app/pages/attestations/index.vue` : intégrer `<RevokeAttestationModal>` ; au clic « Révoquer » sur `<AttestationCard>`, ouvre la modal ; après confirmation, appelle `useAttestations.revokeAttestation(id, reason)` puis recharge la liste.
- [ ] T061 [US3] Vérifier en local : créer une attestation, accéder `/attestations`, cliquer « Révoquer », saisir une raison, valider. Recharger `/verify/{id}` → badge rouge **RÉVOQUÉE** affiché avec date et raison.

**Checkpoint** : User story 3 testable indépendamment. Révocation PME complète (backend + UI), page publique reflète le statut.

---

## Phase 6 : User Story 4 — Un admin révoque une attestation suite à un signalement de fraude (Priority: P2)

**Goal** : Permettre à un admin (rôle Admin F02) de lister cross-tenant et de révoquer toute attestation.

**Independent Test** : créer attestation en PME-A, se connecter en admin, accéder `/admin/attestations`, révoquer cross-tenant avec raison, vérifier audit_log avec `actor_role='admin'`.

### Tests for User Story 4 (TDD)

- [ ] T062 [P] [US4] Écrire `backend/tests/integration/test_attestation_admin_revoke.py` : (a) GET /api/admin/attestations cross-tenant en tant qu'admin → 200 avec toutes les attestations ; (b) PME tente accéder GET /api/admin/attestations → 403 ; (c) admin POST /api/admin/attestations/{id}/revoke → 200 + audit_log actor_role='admin'.
- [ ] T063 [P] [US4] Écrire `frontend/tests/unit/AdminAttestationsPage.spec.ts` : page liste admin avec colonnes account_id/user_id, filtrage par status/tenant, action « Révoquer » par ligne ; redirige vers /dashboard si user non admin (mock).

### Implementation for User Story 4

- [ ] T064 [US4] Créer `backend/app/modules/attestations/admin_router.py` avec 2 endpoints : `GET /attestations` (liste cross-tenant, filtre par account_id/status/period) et `POST /attestations/{id}/revoke` (révocation admin) ; protégé par `Depends(get_current_admin)` (F02).
- [ ] T065 [US4] Modifier `backend/app/main.py` (zone interdite) : ajouter `app.include_router(admin_router, prefix="/api/admin/attestations", tags=["admin", "attestations"])`.
- [ ] T066 [US4] Créer `frontend/app/pages/admin/attestations/index.vue` : page admin avec table complète (account_id, user_id, type, status, dates), filtres (status, tenant, période), bouton « Révoquer » par ligne ouvrant `<RevokeAttestationModal>` ; redirection vers /dashboard si non admin ; dark mode complet.
- [ ] T067 [US4] Vérifier en local : se connecter en admin, accéder /admin/attestations, révoquer une attestation cross-tenant, vérifier audit_log F03 (`actor_role='admin'`).

**Checkpoint** : User story 4 testable indépendamment. Admin peut lister et révoquer cross-tenant.

---

## Phase 7 : User Story 5 — Le LLM génère une attestation depuis le chat (refactor du tool placeholder) (Priority: P2)

**Goal** : Refactorer le tool LangChain `generate_credit_certificate` (placeholder → réel) pour qu'il appelle effectivement le service `attestations.service.generate_attestation`.

**Independent Test** : démarrer chat, demander « génère mon attestation », observer SSE event `tool_call_start` avec `name=generate_credit_certificate`, vérifier ligne `attestations` créée en base avec `source_of_change='llm'`, vérifier que le LLM affiche `verification_url` réel dans sa réponse.

### Tests for User Story 5 (TDD)

- [ ] T068 [P] [US5] Écrire `backend/tests/unit/test_attestation_tools_unit.py` : tool `generate_credit_certificate` avec mocks → retourne `{ok, attestation_id, display_id, verification_url, pdf_path}` ; cas pré-condition manquante (`credit_score_missing`) → `{ok: false, error}` ; cas `pdf_generation_failed` → `{ok: false, error}`.
- [ ] T069 [P] [US5] Écrire `backend/tests/integration/test_attestation_tool_integration.py` : appel réel au tool via le graph → ligne `attestations` créée en base, audit log F03 avec `source_of_change='llm'` ; verification_url pointe vers attestation réelle (pas fictive comme avant F08).

### Implementation for User Story 5

- [ ] T070 [US5] Refactorer `backend/app/graph/tools/credit_tools.py:generate_credit_certificate` : remplacer le placeholder par un appel réel à `AttestationService.generate_attestation(...)` avec `source_of_change='llm'` ; conserver le nom et le schema d'entrée pour rétrocompatibilité ; gérer les erreurs `CreditScoreMissingError`, `EsgAssessmentMissingError`, `PdfGenerationError`.
- [ ] T071 [US5] Modifier `backend/app/prompts/credit.py` : ajouter une mention dans le prompt « Le tool `generate_credit_certificate` retourne maintenant une URL de vérification publique (`verification_url`) que tu DOIS communiquer à l'utilisateur dans ta réponse texte. ».
- [ ] T072 [US5] Vérifier en local : démarrer chat en PME, saisir « génère mon attestation », observer SSE event `tool_call_start` puis réponse contenant `verification_url` réelle.

**Checkpoint** : User story 5 testable indépendamment. Le tool LLM génère réellement, plus de placeholder.

---

## Phase 8 : User Story 6 — Une attestation expire automatiquement après 1 an (Priority: P3)

**Goal** : Le service de vérification calcule `status='expired'` quand `valid_until < now()` ; UI affiche badge orange et alerte « expire bientôt ».

**Independent Test** : créer attestation, manipuler manuellement `valid_until = now() - 1d` en base, recharger /verify/{id} → EXPIRÉE affiché.

### Tests for User Story 6 (TDD)

- [ ] T073 [P] [US6] Écrire `backend/tests/integration/test_attestation_expiration.py` : (a) attestation avec `valid_until < now()` non révoquée → GET /api/public/verify/{id} retourne `status='expired'` avec `expired_since` ; (b) priorité statuts : `revoked` > `expired` > `authentic` (attestation expirée ET révoquée → status='revoked') ; (c) tentative revoke d'une attestation expirée → 200 (idempotente), mais public verify reste `status='revoked'` après.
- [ ] T074 [P] [US6] Écrire `frontend/tests/unit/AttestationCardExpiringSoon.spec.ts` : si `valid_until - now() < 30 jours`, afficher badge « expire bientôt — N jours » + bouton « Renouveler ».

### Implementation for User Story 6

- [ ] T075 [US6] Modifier `backend/app/modules/attestations/service.py:verify_attestation` : appliquer la priorité `revoked > expired > authentic` ; calculer `expired_since` quand applicable.
- [ ] T076 [US6] Modifier `frontend/app/components/attestations/AttestationCard.vue` : ajouter affichage conditionnel « expire bientôt » + bouton « Renouveler » qui ouvre la modal de génération avec le même type pré-sélectionné.

**Checkpoint** : User story 6 testable. Expiration auto fonctionne, UI alerte renouvellement.

---

## Phase 9 : Tests E2E Playwright

**Purpose** : Valider l'intégralité du parcours via tests E2E Playwright executables (`F08-attestation-verifiable-ed25519.spec.ts`).

- [ ] T077 Créer `frontend/tests/e2e/F08-helpers.ts` : helpers pour mock backend (créer une PME avec scores, générer une attestation programmatiquement, manipuler `valid_until` via SQL fixture).
- [ ] T078 Créer `frontend/tests/e2e/F08-attestation-verifiable-ed25519.spec.ts` avec 5 scénarios :
  1. **Scenario 1 — Generate authentic** : login PME, naviguer `/credit-score`, cliquer « Générer attestation », confirmer type `combined` ; attendre la création ; télécharger le PDF (vérifier qu'il est non vide) ; ouvrir verification_url dans un browser context séparé sans cookies → vérifier le badge **AUTHENTIQUE** + scores affichés + hash visible.
  2. **Scenario 2 — Tampered PDF detection** : générer attestation, simuler altération du PDF (modifier un byte via fixture), recharger /verify/{id} → attendu : page affiche **AUTHENTIQUE** mais le hash visible ne match plus le hash du PDF altéré ; le test colle le hash altéré dans `<HashCompareInput>` → message rouge « Hash non conforme ».
  3. **Scenario 3 — Revoke** : générer attestation, accéder `/attestations`, cliquer « Révoquer » sur la card, saisir raison « Test révocation E2E », confirmer ; attendre la mise à jour ; recharger /verify/{id} dans le browser context séparé → badge rouge **RÉVOQUÉE** affiché avec raison.
  4. **Scenario 4 — Expired** : générer attestation, manipuler `valid_until` à `now() - 1d` via fixture SQL ; recharger /verify/{id} → badge orange **EXPIRÉE** affiché avec `expired_since`.
  5. **Scenario 5 — Invalid UUID** : ouvrir /verify/00000000-0000-0000-0000-000000000000 (UUID inexistant) → badge rouge **INVALIDE** affiché ; vérifier qu'aucun champ technique (signature, etc.) n'est exposé ; vérifier que la latence est comparable à un UUID existant (tolérance 100 ms).

**Note** : ces tests doivent passer en CI sur 5 runs consécutifs sans flaky (SC-008).

**Checkpoint** : tous les tests E2E passent localement. Artefacts dans `frontend/playwright-report/`.

---

## Phase 10 : Polish & Documentation

**Purpose** : finitions, documentation, vérifications finales.

- [ ] T079 [P] Créer `docs/attestations-and-verification.md` : documentation utilisateur expliquant : (1) comment ça marche (architecture signature Ed25519 + QR + page publique), (2) format canonique JSON utilisé pour la signature, (3) algorithme de vérification offline (snippets Python, Node.js, Go, Rust), (4) procédure de rotation des clés post-MVP, (5) bonnes pratiques pour le fund officer (toujours scanner le QR, vérifier le hash visible).
- [ ] T080 [P] Vérifier la couverture de tests : `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app/modules/attestations --cov=app/api/public --cov-report=term-missing` → couverture ≥ 85 % sur signing, qr, service ; ≥ 80 % global.
- [ ] T081 [P] Vérifier le type-check frontend : `cd frontend && npx nuxt typecheck` (ou `npm run build` à défaut) → 0 erreur.
- [ ] T082 Vérifier les imports `cryptography` et `segno` ne fuient pas dans la couche LLM (les tools doivent dépendre uniquement de `attestations.service`, jamais de `signing.py` ou `qr.py` directement).
- [ ] T083 Vérifier que tous les libellés UI sont en français avec accents corrects (é, è, ê, à, ç, ù) — recherche `grep -r "[a-z]e\b" frontend/app/components/attestations/` → suspecter les manques d'accents (« délivrée », « révoquée », « expirée », « générée »).
- [ ] T084 Vérifier dark mode : visiter `/attestations` et `/admin/attestations` en mode dark ; vérifier que toutes les classes `dark:` sont présentes sur les composants nouveaux.
- [ ] T085 Vérifier la page publique mobile (DevTools viewport 375x667) : `/verify/{id}` charge sans débordement horizontal, boutons touch ≥ 44x44 px, hash en monospace wrappable, scores en cartes empilées.
- [ ] T086 Vérifier rate limiting en local avec script `for i in {1..15}; do curl ...; done` selon `quickstart.md` § Étape 9 → premières 10 requêtes 200, suivantes 429.
- [ ] T087 Vérifier vérification offline : utiliser le snippet Python de `quickstart.md` § Étape 5 sur une attestation locale → signature valide.
- [ ] T088 Vérifier qu'aucun secret n'est hardcodé : `grep -rE '(ATTESTATION_PRIVATE_KEY|api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/ specs/` → 0 hits.
- [ ] T089 Vérifier que `backend/.env.example` documente les nouvelles variables `ATTESTATION_PRIVATE_KEY_PEM`, `ATTESTATION_PUBLIC_KEY_ID`, `ATTESTATION_VALIDITY_DAYS`, `ATTESTATION_VERIFICATION_BASE_URL`.

**Checkpoint final** : tous les tests passent (unit + integration + E2E), couverture ≥ 80 %, dark mode validé, mobile-first validé, rate limiting OK, vérification offline OK.

---

## Récap dépendances entre phases

```
Phase 1 (Setup)
  └→ Phase 2 (Foundational)
       └→ Phase 3 (US1) ──┐
            └→ Phase 4 (US2) ─┐
                 └→ Phase 5 (US3) ─┐
                      └→ Phase 6 (US4) ──┐
                           └→ Phase 7 (US5) ─┐
                                └→ Phase 8 (US6) ──┐
                                                    └→ Phase 9 (E2E) ──┐
                                                                        └→ Phase 10 (Polish)
```

**Total tasks** : 89 (T001..T089)

**Parallèles maximales** : Phase 2 tests (T007-T011 en parallèle), Phase 3 tests (T022-T028 en parallèle), Phase 4 tests (T041-T046 en parallèle), Phase 9-10 polish (multiples [P]).

**Couverture cible** : ≥ 85 % sur les modules cryptographiques (`signing.py`, `qr.py`, `service.py`), ≥ 80 % global F08.

**Test E2E exécutable** : `frontend/tests/e2e/F08-attestation-verifiable-ed25519.spec.ts` avec 5 scénarios + `F08-helpers.ts`. Lancer via `cd frontend && npx playwright test tests/e2e/F08-attestation-verifiable-ed25519.spec.ts --reporter=html`.
