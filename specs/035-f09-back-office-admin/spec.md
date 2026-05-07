# Feature Specification: F09 — Back-Office Admin Complet (Module 9)

**Feature Branch**: `feat/F09-back-office-admin`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F09 — Back-Office Admin Complet : module `app/modules/admin/` étendu avec ~15 sous-routers (funds, intermediaries, offers, referentials, indicators, criteria, templates, sources, emission_factors, simulation_factors, users, attestations, metrics, audit, skills), workflow draft → published transversal sur ~10 entités catalogue, workflow 4-yeux validation source via 2 triggers PostgreSQL, ~17 pages frontend admin avec layout dédié, composants partagés (EntityCRUDTable, SourcePicker, PublishButton, badges, ImpactAnalysisModal, MetricsCard), endpoints administration utilisateurs (reset-password, toggle-active), endpoint révocation attestations, métriques admin, suppression anti-pattern email whitelist `financing/router.py:118`."

## Clarifications

### Session 2026-05-07

- **Module backend `app/modules/admin/`** : déjà initialisé par F02 (router central + middleware `require_admin_role`). F09 étend avec 15 sous-routers : `funds_router.py`, `intermediaries_router.py`, `offers_router.py`, `referentials_router.py`, `indicators_router.py`, `criteria_router.py`, `templates_router.py`, `sources_router.py`, `emission_factors_router.py`, `simulation_factors_router.py`, `users_router.py`, `attestations_router.py`, `metrics_router.py`, `audit_router.py` (créé par F03, simplement validé/raffiné), `skills_router.py` (créé par F23, simplement validé/raffiné). Tous protégés par `Depends(get_current_admin)`.
- **Workflow `draft → published` transversal** : colonne `publication_status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK IN ('draft','published')` ajoutée sur 10 tables catalogue : `funds`, `intermediaries`, `offers`, `referentials`, `indicators`, `criteria`, `templates`, `emission_factors`, `simulation_factors`, `skills`. Le LLM (loader F23, matching F14, RAG) ne consomme **que** les entités `published`. Les services de lecture publique (page PME `/financing`) filtrent automatiquement `publication_status='published'`.
- **Trigger PostgreSQL `before_publish_check_sources_verified`** : un trigger BEFORE UPDATE sur les 10 tables catalogue qui, lorsque `publication_status` passe de `draft` à `published`, vérifie que toutes les sources liées (directes via FK, ou via `entity_sources`) ont `verification_status='verified'`. Si au moins une source n'est pas verified, lève une exception SQLSTATE custom (`P0001`) avec message `"cannot publish: source <source_id> has verification_status=<current>"`. Le service backend catch cette exception et retourne 400 avec la liste des sources bloquantes.
- **Workflow 4-yeux validation source** : Admin A saisit Source → status `pending`, `captured_by_user_id=A`. Admin B (≠ A) clique "Vérifier" → status `verified`, `verified_by_user_id=B`, `verified_at=now()`. Trigger `before_verify_source_check_different_admin` BEFORE UPDATE sur `sources` lorsque `verification_status` passe de `pending` à `verified` : si `NEW.verified_by_user_id = NEW.captured_by_user_id`, lève `P0001` avec message `"4-eyes principle violated: verifier must differ from creator"`. Aucun bypass admin (même un super-admin ne peut pas valider sa propre source).
- **Frontend layout `layouts/admin.vue`** : étendu de F02 (qui a posé le squelette : sidebar gauche avec items navigation, header avec badge "Mode Admin" rouge, footer minimal). F09 finalise le contenu : sidebar avec sections Catalogue / Sources / Comptes / Métriques / Audit, dark mode complet, palette accentuée admin (bordures `dark:border-admin-accent` rouge foncé), toggle theme partagé avec PME. Pages admin n'ont AUCUN lien vers les pages PME (séparation visuelle stricte).
- **Pages frontend (~17)** :
  - `pages/admin/index.vue` (dashboard métriques agrégées)
  - `pages/admin/funds/{index,new,[id]}.vue` (3 pages CRUD)
  - `pages/admin/intermediaries/{index,new,[id]}.vue` (3 pages CRUD)
  - `pages/admin/offers/{index,new,[id]}.vue` (3 pages CRUD)
  - `pages/admin/referentials/{index,new,[id]}.vue`
  - `pages/admin/indicators/{index,new,[id]}.vue`
  - `pages/admin/criteria/{index,new,[id]}.vue`
  - `pages/admin/templates/{index,new,[id]}.vue`
  - `pages/admin/emission-factors/{index,new,[id]}.vue`
  - `pages/admin/simulation-factors/{index,new,[id]}.vue`
  - `pages/admin/sources/{index,new,[id]}.vue` (3 pages, tabs Pending/Verified/Outdated, impact analysis)
  - `pages/admin/companies/{index,[account_id]}.vue` (2 pages, lecture seule + actions)
  - `pages/admin/attestations/index.vue` (liste + révocation)
  - `pages/admin/audit/index.vue` (validation/raffinement F03)
  - `pages/admin/metrics/index.vue` (KPIs détaillés)
  - `pages/admin/skills/{index,new,[id]}.vue` (validation/raffinement F23)
- **Composants partagés `components/admin/`** :
  - `<EntityCRUDTable>` : table générique avec slots header/row/actions, pagination, recherche full-text, tri. Props : `columns`, `dataLoader`, `actions` (delete/edit/duplicate), `bulkActions` (post-MVP).
  - `<SourcePicker>` : modal pour sélectionner une Source `verified` parmi le catalogue, avec recherche par publisher/title, prévisualisation URL.
  - `<PublishButton>` : bouton "Publier" avec disabled state si conditions non remplies, tooltip d'explication ("Source X non vérifiée"). Au clic, appelle `POST /api/admin/<entity>/{id}/publish` et gère erreur 400.
  - Badges status : `<DraftBadge>` (gris), `<PublishedBadge>` (vert), `<PendingBadge>` (jaune), `<VerifiedBadge>` (bleu), `<OutdatedBadge>` (rouge).
  - `<ImpactAnalysisModal>` : modal affichant les entités dépendantes avant suppression / modification (ex source liée à 5 indicators + 12 criteria). Bloque ou demande confirmation force.
  - `<MetricsCard>` : carte KPI réutilisable (titre, valeur principale, sub-metrics, trend 30j sparkline).
- **Endpoint `POST /api/admin/users/{id}/reset-password`** : génère un token aléatoire (32 bytes URL-safe), hashe (sha256), insère dans table `password_reset_tokens(token_hash, user_id, expires_at, used_at, created_at)` avec `expires_at = now() + 1h`. Envoie email "Cliquez ici pour définir un nouveau mot de passe" avec lien `https://app.esg-mefali.com/auth/reset?token=<plain_token>`. Endpoint public `POST /api/auth/reset-password` valide le token (hash match, non utilisé, non expiré), met à jour le password, marque token utilisé. Token à usage unique. Audit log F03 : `password_reset_initiated_by_admin` + `password_reset_completed`.
- **Endpoint `POST /api/admin/users/{id}/toggle-active`** : bascule `is_active` (true ↔ false). Body : `{reason: string}` obligatoire (raison logguée). Audit log F03 entry `user_toggled_active` avec `metadata={previous: bool, new: bool, reason: str}`. Si désactivation, le user perd accès immédiatement (les sessions existantes restent valides jusqu'à expiration JWT — clarification : MVP ne révoque pas les JWT, les nouveaux refresh sont bloqués via check `is_active` sur `get_current_user`).
- **Endpoint `POST /api/admin/attestations/{id}/revoke`** : déjà partiellement défini en F08. F09 expose cet endpoint depuis le router admin avec body `{reason: str}` obligatoire (≥ 10 chars). Met à jour `attestations.revoked_at=now()`, `revoked_by_user_id=current_admin.id`, `revocation_reason=reason`. La signature ed25519 reste valide cryptographiquement mais l'endpoint public de vérification renvoie `{valid: false, revoked: true, reason}`. Audit log F03 entry `attestation_revoked`.
- **Endpoint `GET /api/admin/metrics/overview`** : agrège en une seule requête : (a) Sources : `total/pending/verified/outdated` + trend 30j (count par jour des transitions), (b) Comptes PME : `total_active/total_inactive/new_30d`, (c) Candidatures (post-MVP placeholder : `total/by_status`), (d) Attestations : `total_emitted/total_revoked/total_active`, (e) Coûts LLM (post-MVP placeholder : `total_tokens_in/total_tokens_out/total_cost_usd_estimated_30d`). Utilise des agrégations SQL avec CTE pour performance (P95 < 500ms). Cache 5 min via `@cache_async` (post-MVP, sinon recalcul à chaque requête en MVP).
- **Suppression anti-pattern email whitelist** : la consigne précise que F02 a déjà supprimé `admin_emails = {"admin@esg-mefali.com", "admin@mefali.org"}` dans `backend/app/modules/financing/router.py:118` et migré les endpoints `/funds`, `/intermediaries` du router public vers le router admin (`/api/admin/funds`, `/api/admin/intermediaries`). F09 valide ce changement et garantit qu'aucune référence à cette whitelist ne subsiste (test conformity grep `admin_emails` → 0 match).
- **Pages admin/audit (F03) et admin/skills (F23)** : déjà créées par leurs features respectives. F09 valide les liens dans la sidebar `layouts/admin.vue` et fournit un page wrapper qui hérite du layout admin. Aucune duplication de logique : les routers `audit_router.py` et `skills_router.py` restent montés sous `/api/admin/*`.
- **Migration Alembic `035_admin_publication_status_workflow.py`** : `revision="035_admin_publication_status_workflow"`, `down_revision="033_create_skills"` (F23 est la dernière migration mergée — la consigne le confirme). Crée :
  1. Colonne `publication_status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK IN ('draft','published')` sur 10 tables (funds, intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills). Pour les tables où la colonne existe déjà via une feature antérieure (ex skills), pas d'erreur (vérifie via `op.execute("ALTER TABLE ... ADD COLUMN IF NOT EXISTS")`).
  2. Trigger PostgreSQL `before_publish_check_sources_verified` (fonction PL/pgSQL + 10 triggers TABLE-spécifiques BEFORE UPDATE).
  3. Trigger PostgreSQL `before_verify_source_check_different_admin` (BEFORE UPDATE sur `sources`).
  4. Table `password_reset_tokens(id UUID PK, user_id FK users.id NOT NULL, token_hash VARCHAR(128) UNIQUE NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())` avec index sur `(user_id, expires_at)`.
- **Sécurité reset password** : token à usage unique (after `used_at` set, refus). Token hashé en BDD (jamais stocké en clair). Lien envoyé par email seulement (pas par SMS en MVP). Email envoyé via service `app/core/email_service.py` (templated, à utiliser ou créer si absent — assumption : F02 ou F08 a déjà initialisé un service email pour notifications). En dev, log le lien dans la console plutôt que d'envoyer un vrai email (env var `EMAIL_BACKEND=console`).
- **Tests E2E (4 obligatoires)** :
  1. **Test 4-yeux source** : Admin A crée Source → status `pending` → Admin A tente verify (PATCH `/api/admin/sources/{id}` avec `verification_status=verified`) → 400 trigger violation. Admin B verify → 200, status `verified`.
  2. **Test publish gating** : Admin crée Fund avec source `pending` → tente publish (POST `/api/admin/funds/{id}/publish`) → 400 trigger violation, liste sources bloquantes. Admin verify la source via Admin B → re-publish Fund → 200, status `published`.
  3. **Test isolation user PME** : User PME (rôle `user`) tente GET `/api/admin/funds` → 403. Tente accès page `/admin/funds` → middleware redirect vers `/dashboard` ou affiche 403 page.
  4. **Test reset password** : Admin POST `/api/admin/users/{id}/reset-password` → email envoyé (vérifier console log en dev), token créé en BDD avec `expires_at = now() + 1h`. User clique le lien dans email, POST `/api/auth/reset-password` avec nouveau pw → 200, token marqué `used_at`. User login avec nouveau pw → succès.
- **Audit log automatique sur consultation admin** : la consigne F09 exige qu'une consultation admin d'un compte PME (page `/admin/companies/[account_id]`) génère une entrée audit_log F03 visible côté PME. Implémentation : middleware backend sur les endpoints `GET /api/admin/companies/{id}/*` qui appelle `audit_log_entry(action="view_admin", entity_type="account", entity_id=account_id, actor_id=admin.id, metadata={...})`. La page PME `/account/audit` (créée par F03) affiche ces entrées avec un badge spécifique "Consulté par administrateur".
- **Permissions granulaires intra-admin (post-MVP)** : MVP utilise `role IN ('admin','user')` binaire. Post-MVP : roles fins (`dpo`, `catalog_editor`, `support`) avec policies par sous-router. F09 prévoit l'extensibilité : `Depends(get_current_admin)` accepte un paramètre optionnel `required_permissions: list[str]` pour future granularité, mais MVP ignore ce param.

## User Scenarios & Testing

### User Story 1 — CRUD Catalogue Fonds + Workflow Publication (Priority: P1)

En tant qu'**Admin Mefali**, je veux créer un nouveau Fonds (ex GCF Adaptation Window), l'attacher à plusieurs Intermédiaires accrédités (BOAD, BAD, CSE), définir ses critères ESG/secteur/taille, uploader son logo, lier ses sources officielles, et publier le fonds une fois toutes les sources vérifiées par un autre admin. Cela permet de peupler le catalogue qui alimente la fonctionnalité de matching pour les PME.

**Why this priority** : sans CRUD catalogue, la plateforme est inopérable en production. Tous les fonds visibles côté PME doivent passer par cette interface.

**Independent Test** : peut être validé en (a) créant un fund via `POST /api/admin/funds`, (b) liant 2 sources verified via `PATCH /api/admin/funds/{id}` (sources jsonb), (c) tentant publish avec 1 source pending → 400, (d) verify la source via 4-yeux, (e) re-publish → 200, (f) vérifiant côté PME que le fund est listé.

**Acceptance Scenarios** :

1. **Given** un Admin est authentifié, **When** il accède à `/admin/funds/new` et soumet le formulaire avec name, fund_type, theme, montants, **Then** un Fund est créé en BDD avec `publication_status='draft'`, audit log F03 entry `fund_created`.
2. **Given** un Fund draft existe avec 2 sources liées (1 verified, 1 pending), **When** l'admin clique `<PublishButton>`, **Then** le bouton est disabled avec tooltip listant la source pending. Si l'admin force POST `/api/admin/funds/{id}/publish`, le trigger `before_publish_check_sources_verified` lève `P0001`, l'API retourne 400 avec `{error: "publish_blocked", blocking_sources: [{id, title, verification_status}]}`.
3. **Given** toutes les sources d'un Fund sont verified, **When** l'admin clique `<PublishButton>`, **Then** `publication_status='published'`, audit log entry `fund_published`, le fund devient visible côté PME via `/api/financing/funds`.
4. **Given** un Fund publié, **When** l'admin l'édite (PATCH), **Then** une nouvelle version est créée via VersioningMixin (F04), l'ancienne reçoit `valid_to=today()`. Le LLM consomme la nouvelle version au prochain match.
5. **Given** un Admin tente de supprimer un Fund (DELETE `/api/admin/funds/{id}`) qui a des candidatures liées, **When** la requête est traitée, **Then** un `<ImpactAnalysisModal>` s'affiche listant les 3 candidatures associées, l'admin peut soit cancel soit force soft-delete (`valid_to=today()`).

---

### User Story 2 — Workflow Validation 4-Yeux des Sources (Priority: P1)

En tant qu'**Admin**, je veux saisir une nouvelle Source (URL d'un document officiel ADEME, GCF Investment Framework, etc.) avec status `pending`, et qu'un autre Admin (≠ moi) puisse la passer en `verified`. Cela garantit qu'aucune source ne peut être validée par son propre saisisseur (4-yeux), évitant les fraudes ou erreurs internes.

**Why this priority** : la qualité du sourcing est le pilier de la crédibilité de la plateforme. Un workflow 4-yeux est exigé par les standards de gouvernance ESG (cf. F01 audit + F03 audit log).

**Independent Test** : peut être validé en (a) Admin A POST `/api/admin/sources` → status pending, captured_by=A. (b) Admin A tente PATCH `/api/admin/sources/{id}` avec `verification_status=verified` → 400 trigger violation. (c) Admin B PATCH avec `verification_status=verified` → 200, status verified, verified_by=B, audit log entry.

**Acceptance Scenarios** :

1. **Given** un Admin A est authentifié, **When** il POST `/api/admin/sources` avec URL, title, publisher, version, date, page, **Then** une Source est créée avec `verification_status='pending'`, `captured_by_user_id=A.id`, audit log entry `source_created`.
2. **Given** une Source en `pending` et `captured_by_user_id=A`, **When** l'Admin A tente PATCH `/api/admin/sources/{id}` avec `verification_status='verified'`, **Then** le trigger `before_verify_source_check_different_admin` lève `P0001`, l'API retourne 400 avec `{error: "4_eyes_violation", message: "Cannot verify your own source"}`.
3. **Given** une Source en `pending` saisie par Admin A, **When** l'Admin B (≠ A) PATCH avec `verification_status='verified'`, **Then** la Source passe `verified`, `verified_by_user_id=B.id`, `verified_at=now()`, audit log entry `source_verified`.
4. **Given** une Source `verified`, **When** elle devient obsolète (ex nouveau document officiel publié), **Then** un Admin PATCH avec `verification_status='outdated'` + `obsolescence_reason` (autorisé sans 4-yeux car non-promotion), audit log entry `source_outdated`.
5. **Given** une Source `verified` est référencée par 5 Indicators et 3 Criteria, **When** un Admin tente DELETE, **Then** `<ImpactAnalysisModal>` liste les 8 entités dépendantes, force delete = soft delete (`valid_to=today()`) avec cascade `valid_to` sur dépendants.

---

### User Story 3 — Support PME (Lecture, Reset Password, Toggle Active, Révocation Attestation) (Priority: P1)

En tant qu'**Admin**, je veux consulter un compte PME en lecture seule (profile, projets, candidatures, ESG/Carbon scores, attestations), reset son mot de passe en cas de blocage, désactiver son compte si fraude détectée, et révoquer une attestation émise par erreur. Toute consultation est tracée et visible côté PME.

**Why this priority** : sans support PME, la plateforme ne peut pas gérer les incidents (mot de passe oublié sans accès email, comptes frauduleux, attestations erronées). Bloquant en production.

**Independent Test** : peut être validé en (a) Admin GET `/api/admin/companies/{account_id}` → audit log entry `view_admin` créée. (b) PME GET `/api/account/audit` → voit l'entrée "Consulté par administrateur". (c) Admin POST reset-password → token créé, email envoyé (console log dev). (d) PME POST `/api/auth/reset-password` avec token → password mis à jour. (e) Admin POST toggle-active → user désactivé, ne peut plus se logger.

**Acceptance Scenarios** :

1. **Given** un Admin accède à `/admin/companies/[account_id]`, **When** la page charge (`GET /api/admin/companies/{id}`), **Then** elle affiche le profil PME en lecture seule (formulaires disabled), un audit log entry `view_admin` est créé visible côté PME via `/account/audit`.
2. **Given** un Admin POST `/api/admin/users/{user_id}/reset-password`, **When** la requête est traitée, **Then** un token est créé en BDD (`password_reset_tokens` table), email envoyé au user (en dev : console log), audit log entry `password_reset_initiated_by_admin`. Le PME reçoit lien valide 1h.
3. **Given** un user reçoit le lien, **When** il POST `/api/auth/reset-password` avec `{token, new_password}`, **Then** le password est mis à jour (bcrypt hash), token marqué `used_at`, audit log entry `password_reset_completed`. Le user peut se logger avec le nouveau pw.
4. **Given** un Admin POST `/api/admin/users/{user_id}/toggle-active` avec `{reason: "fraud detected"}`, **When** la requête est traitée, **Then** `users.is_active` est toggle, audit log entry `user_toggled_active` avec `metadata={previous, new, reason}`. Le user désactivé voit ses prochaines requêtes refusées avec 403.
5. **Given** un Admin POST `/api/admin/attestations/{id}/revoke` avec `{reason: "data error"}`, **When** la requête est traitée, **Then** `attestations.revoked_at=now()`, `revoked_by_user_id=admin.id`, `revocation_reason=reason`, audit log entry `attestation_revoked`. L'endpoint public `/api/attestations/verify/{id}` retourne `{valid: false, revoked: true, reason}`.

---

### User Story 4 — Gestion Sources avec Impact Analysis (Priority: P1)

En tant qu'**Admin**, je veux comprendre l'impact d'une modification ou suppression de Source sur les entités qui en dépendent (indicators, criteria, formulas, emission_factors, simulation_factors, skills.sources). Le `<ImpactAnalysisModal>` me liste tous les dépendants avant action destructive.

**Why this priority** : sans impact analysis, un admin peut casser silencieusement le système (ex supprimer la source ADEME → 50 emission_factors orphelins → calculs carbone faussés). Critique pour l'intégrité.

**Independent Test** : peut être validé en (a) créant une Source liée à 3 Indicators + 2 Criteria + 1 emission_factor. (b) GET `/api/admin/sources/{id}/dependents` → retourne `{indicators: [...], criteria: [...], emission_factors: [...], total: 6}`. (c) Tentative DELETE → `<ImpactAnalysisModal>` affiche les 6 dépendants. (d) Force delete → soft delete cascade sur dépendants.

**Acceptance Scenarios** :

1. **Given** une Source liée à plusieurs entités catalogue, **When** un Admin GET `/api/admin/sources/{id}/dependents`, **Then** le service `sources_service.get_dependents()` retourne un dict groupé par type d'entité avec count + liste des entités (id, name, status).
2. **Given** un Admin tente DELETE `/api/admin/sources/{id}` avec dépendants existants, **When** le frontend affiche `<ImpactAnalysisModal>`, **Then** la modal liste les entités dépendantes avec lien vers leur page admin. Admin peut soit cancel, soit force delete (cascade soft delete via `valid_to=today()`).
3. **Given** un Admin modifie une Source (ex change l'URL après mise à jour du document officiel), **When** la modification est validée, **Then** un audit log entry `source_modified` est créé avec diff. Aucun cascade automatique : les entités dépendantes restent liées à la même Source.id (URL mise à jour reflète automatiquement).
4. **Given** une Source verified passe `outdated`, **When** le statut change, **Then** les entités catalogue qui en dépendent ne sont PAS automatiquement dépublies, mais un warning admin apparait sur leurs pages indiquant "Source X obsolète". Admin doit manuellement remplacer la source ou accepter le risque.

---

### User Story 5 — Métriques Admin Dashboard (Priority: P2)

En tant qu'**Admin Mefali**, je veux un dashboard `/admin/metrics` qui agrège en temps réel : nombre de sources pending/verified/outdated, comptes PME actives/désactivées/nouveaux 30j, candidatures par statut, attestations émises/révoquées/actives, coûts LLM agrégés. Cela me permet de monitorer la santé opérationnelle de la plateforme.

**Why this priority** : nécessaire pour la gouvernance produit, mais pas bloquant si les données sont accessibles via SQL direct en MVP. Priorité P2.

**Independent Test** : peut être validé en (a) seedant fixtures (10 sources, 50 PME, 5 attestations), (b) GET `/api/admin/metrics/overview` → vérifier réponse contient toutes les sections agrégées avec counts corrects, (c) navigation `/admin/metrics` → cards affichent les valeurs.

**Acceptance Scenarios** :

1. **Given** la BDD contient 10 sources (3 pending, 5 verified, 2 outdated), **When** un Admin GET `/api/admin/metrics/overview`, **Then** la réponse contient `{sources: {total: 10, pending: 3, verified: 5, outdated: 2, trend_30d: [...]}}`.
2. **Given** la BDD contient 50 PME (45 actives, 5 désactivées, 8 nouvelles 30j), **When** GET metrics, **Then** la section `accounts: {total_active: 45, total_inactive: 5, new_30d: 8}` est correcte.
3. **Given** la page `/admin/metrics` charge, **When** le rendu termine, **Then** des `<MetricsCard>` affichent chaque section avec sparkline trend 30j, dark mode appliqué.
4. **Given** un grand volume de données (1000+ sources, 5000+ users), **When** GET metrics, **Then** la réponse arrive en P95 < 500ms grâce aux agrégations SQL avec CTE et index appropriés.
5. **Given** une section post-MVP (ex coûts LLM), **When** GET metrics, **Then** le placeholder retourne `{total_tokens_in: 0, total_tokens_out: 0, total_cost_usd_estimated_30d: 0, status: "post_mvp"}` sans casser la requête.

---

### User Story 6 — CRUD Référentiels + Indicateurs + Critères (Priority: P2)

En tant qu'**Admin expert ESG**, je veux gérer les référentiels (ESG Mefali, GCF Investment Framework, IFC Performance Standards, BOAD Green Taxonomy, GRI, ODD), leurs indicateurs atomiques (% déchets recyclés, tCO2e Scope 1, % femmes en gouvernance) et leurs critères (conditions logiques sur indicateurs). Toute modification crée une nouvelle version (F04 versioning).

**Why this priority** : nécessaire pour la rigueur ESG, mais le seed initial F01 fournit un MVP utilisable. Édition fine = Priority P2 post-launch.

**Independent Test** : peut être validé en (a) créant un nouveau référentiel "GCF v3.2", (b) ajoutant 5 indicators avec poids/seuil, (c) éditant un indicator → nouvelle version créée, (d) vérifiant la nouvelle version est utilisée par le scoring multi-référentiels (F13).

**Acceptance Scenarios** :

1. **Given** un Admin POST `/api/admin/referentials` avec name, version, description, **Then** un référentiel est créé en `draft`.
2. **Given** un référentiel `draft` avec 5 indicators et 0 source, **When** Admin tente publish, **Then** 400 (chaque indicator doit avoir au moins 1 source verified, contrainte business cohérente avec F01).
3. **Given** un référentiel `published`, **When** un Admin l'édite (PATCH), **Then** une nouvelle version est créée via VersioningMixin, l'ancienne `valid_to=today()`, le scoring F13 utilise la nouvelle version.
4. **Given** un Indicator est référencé par 10 critères, **When** un Admin tente DELETE, **Then** `<ImpactAnalysisModal>` liste les 10 critères, force delete = cascade soft delete.

---

### User Story 7 — CRUD Offres (Couples Fund + Intermediary) (Priority: P2)

En tant qu'**Admin**, je veux créer une Offre = couple Fund + Intermediary (ex "GCF via BOAD"), avec calcul automatique des `effective_*` (effective_min_amount, effective_max_amount, effective_processing_time, effective_success_rate) via `compute_effective_offer` (F07), et possibilité d'ajuster manuellement.

**Why this priority** : le concept Offre est défini par F07, F09 expose simplement le CRUD admin. Priority P2 car F07 fournit déjà le service.

**Independent Test** : peut être validé en (a) créant Fund X et Intermediary Y, (b) POST `/api/admin/offers` avec `{fund_id: X, intermediary_id: Y}`, (c) bouton "Calcul auto" → effective_* pré-remplis, (d) ajustement manuel + save, (e) publish → 200 si toutes sources verified.

**Acceptance Scenarios** :

1. **Given** Fund X et Intermediary Y sont publiés, **When** Admin POST `/api/admin/offers` avec leurs IDs, **Then** une Offer est créée en `draft`. L'admin clique "Calcul auto" → frontend appelle `compute_effective_offer(fund_id, intermediary_id)` (F07) qui retourne les effective_* pré-calculés.
2. **Given** une Offer draft avec effective_* renseignés et toutes sources verified, **When** Admin clique Publish, **Then** trigger gating valide → published. Visible côté PME via matching F14.
3. **Given** un Fund X passe `outdated`, **When** une Offer existante (Fund X + Y) est consultée, **Then** un warning apparait "Fund obsolète, veuillez créer une nouvelle Offer avec une version actualisée".

---

### User Story 8 — CRUD Templates + Emission Factors + Simulation Factors (Priority: P3)

En tant qu'**Admin spécialisé**, je veux gérer les templates de dossier (lien F15/F23), les facteurs d'émission ADEME/IPCC (lien F17), et les constantes du simulateur (lien F16). Chaque modification est sourcée et versionnée.

**Why this priority** : ces entités sont déjà initialisées via seed Python par leurs features respectives. Édition admin = besoin avancé, post-MVP launch.

**Independent Test** : peut être validé en (a) créant un emission_factor (country=SN, year=2024, factor_value=0.83, source_id=ADEME_UUID), (b) éditant un template (DOCX upload), (c) éditant un simulation_factor (carbon_impact_ratio=0.45, source_id=...).

**Acceptance Scenarios** :

1. **Given** un Admin POST `/api/admin/emission-factors` avec country, year, factor_value, source_id, **Then** créé en draft. Publish nécessite source verified.
2. **Given** un Admin PATCH `/api/admin/templates/{id}` avec un nouveau DOCX uploadé, **Then** une nouvelle version est créée, l'ancienne `valid_to=today()`. F15 utilise la nouvelle version.
3. **Given** un Admin POST `/api/admin/simulation-factors` avec carbon_impact_ratio=0.45 et source_id, **Then** créé en draft. F16 ne consomme que les `published`.

---

### User Story 9 — Isolation Admin / PME (Frontend + Backend) (Priority: P1)

En tant qu'**Architecte sécurité**, je veux que les routes `/api/admin/*` (backend) et `/admin/*` (frontend) soient strictement isolées des PME. Un user `role=user` qui tente d'accéder reçoit 403 backend et redirect frontend.

**Why this priority** : sans isolation, fuite de données ou élévation de privilèges. Critique sécurité.

**Independent Test** : peut être validé en (a) login en tant que PME (role=user), (b) GET `/api/admin/funds` → 403, (c) navigation `/admin/funds` → middleware bloque, (d) repeat avec admin → 200 et page accessible.

**Acceptance Scenarios** :

1. **Given** un user `role=user` est authentifié, **When** il GET `/api/admin/funds`, **Then** 403 Forbidden avec `{error: "admin_required"}`. Audit log entry optionnel `unauthorized_admin_access_attempt`.
2. **Given** un user PME tente d'accéder à `/admin/funds` via navigation directe, **When** le middleware Vue `middleware/admin.ts` (créé F02) s'exécute, **Then** redirect vers `/dashboard` ou affiche une page 403 friendly.
3. **Given** un Admin est authentifié, **When** il GET `/api/admin/funds`, **Then** 200 avec liste paginée.
4. **Given** un Admin est désactivé (`is_active=false`) puis tente accès admin, **When** la requête arrive, **Then** 401 (token devient invalide à la prochaine validation refresh).

---

### Edge Cases

- **Suppression d'une Source verified référencée par 100+ entités** : le `<ImpactAnalysisModal>` doit gérer le grand volume avec pagination interne. Force delete avec cascade peut prendre plusieurs secondes (transaction longue) — afficher un spinner + désactiver le bouton.
- **Race condition publication concurrente** : 2 admins tentent publish du même Fund simultanément → la 2e requête échoue car `publication_status` déjà à `published` (idempotent OK).
- **Token reset password expiré juste pendant l'utilisation** : si user clique le lien à 59:59, l'API peut accepter ou refuser selon la latence — refus strict (timestamp comparé à now()).
- **Email service indisponible (dev/staging)** : fallback à console log. Logger un WARNING niveau ERROR si SMTP timeout en prod.
- **Trigger PostgreSQL ne lève pas l'erreur attendue** : tests intégration explicites pour vérifier que `P0001` est bien remonté à SQLAlchemy → `IntegrityError` → 400 dans la réponse FastAPI.
- **Admin tente de publier 50 Funds en batch** : MVP = 1 par 1 via UI. Bulk import CSV/Excel = post-MVP.
- **Audit log entry `view_admin` doublon** : si admin recharge la page 5 fois → 5 entrées audit_log → spam. Mitigation MVP : 1 entrée par session admin par account_id par jour (dedup logique côté service).
- **Source devient outdated juste après publish d'un Fund** : le Fund reste publié (pas de cascade automatique vers `draft`). Warning admin sur la page du Fund. Admin doit manuellement remplacer la source ou accepter.
- **Layout admin charge sur mobile** : sidebar collapse en hamburger, dark mode preserved. Tests responsive.
- **Concurrent edit sur même entité catalogue** : 2 admins éditent même Fund → optimistic locking via `updated_at` ou version semver (last-write-wins documenté en MVP).
- **Trigger 4-yeux : super-admin tente verify sa propre source** : refus strict, aucun bypass. Documenter dans runbook : "Pour valider sa propre source, demander à un autre admin."
- **Migration 035 sur BDD avec entités catalogue déjà présentes** : la colonne `publication_status` est ajoutée avec DEFAULT='draft'. Toutes les entités existantes deviennent draft → invisible côté PME. Migration de données séparée nécessaire : UPDATE des entités validées par F01-F08 pour les passer à 'published'. Plan de rollout documenté.
- **Reset password : user a déjà 3 tokens actifs** : MVP autorise plusieurs tokens (le dernier prévaut, les autres restent valides jusqu'à expiration). Post-MVP : invalider les anciens tokens à chaque nouveau reset.
- **Page `/admin/metrics` lente avec 100k+ events** : ajouter index composite + matérialized view post-MVP. MVP : timeout query 5s.

## Requirements

### Functional Requirements

- **FR-001** : Une migration Alembic `035_admin_publication_status_workflow.py` (revision=`035_admin_publication_status_workflow`, down_revision=`033_create_skills`) MUST :
  - Ajouter la colonne `publication_status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK IN ('draft','published')` sur 10 tables : `funds`, `intermediaries`, `offers`, `referentials`, `indicators`, `criteria`, `templates`, `emission_factors`, `simulation_factors`, `skills`. Pour les tables où la colonne pourrait déjà exister (skills via F23), utiliser `ADD COLUMN IF NOT EXISTS`.
  - Créer la fonction PL/pgSQL `before_publish_check_sources_verified()` et 10 triggers BEFORE UPDATE associés (un par table).
  - Créer la fonction PL/pgSQL `before_verify_source_check_different_admin()` et 1 trigger BEFORE UPDATE sur `sources`.
  - Créer la table `password_reset_tokens(id UUID PK, user_id UUID FK users.id NOT NULL ON DELETE CASCADE, token_hash VARCHAR(128) UNIQUE NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())` avec index sur `(user_id, expires_at)` et index sur `token_hash`.

- **FR-002** : La fonction `before_publish_check_sources_verified()` MUST :
  - Si `OLD.publication_status='draft'` AND `NEW.publication_status='published'`, vérifier toutes les sources liées (via FK directes ou table `entity_sources`).
  - Si au moins une source a `verification_status != 'verified'`, lever `RAISE EXCEPTION SQLSTATE 'P0001' USING MESSAGE = 'cannot publish: source <id> has verification_status=<status>'`.
  - Sinon, autoriser le UPDATE.

- **FR-003** : La fonction `before_verify_source_check_different_admin()` MUST :
  - Si `OLD.verification_status='pending'` AND `NEW.verification_status='verified'`, vérifier `NEW.verified_by_user_id != OLD.captured_by_user_id`.
  - Si égal, lever `RAISE EXCEPTION SQLSTATE 'P0001' USING MESSAGE = '4-eyes principle violated: verifier must differ from creator'`.

- **FR-004** : Un router `app/modules/admin/funds_router.py` MUST exposer 6 endpoints REST protégés par `Depends(get_current_admin)` :
  - `GET /api/admin/funds?page=&limit=&fund_type=&status=&publication_status=&theme=&q=` (liste filtrée paginée)
  - `POST /api/admin/funds` (création, draft)
  - `GET /api/admin/funds/{id}` (détail avec sources liées + intermédiaires accrédités)
  - `PATCH /api/admin/funds/{id}` (édition, crée nouvelle version si published via VersioningMixin F04)
  - `POST /api/admin/funds/{id}/publish` (déclenche trigger gating)
  - `DELETE /api/admin/funds/{id}` (soft delete, valid_to=today() si pas de candidatures liées, sinon impact analysis)

- **FR-005** : Un router `app/modules/admin/intermediaries_router.py` MUST exposer la même structure CRUD que funds avec champs spécifiques (`required_documents`, `fees_structured`, `processing_time_days`, `success_rate`).

- **FR-006** : Un router `app/modules/admin/offers_router.py` MUST exposer CRUD couples Fund+Intermediary avec endpoint additionnel `POST /api/admin/offers/{id}/compute-effective` qui appelle le service F07 `compute_effective_offer(fund_id, intermediary_id)` et retourne les effective_* pré-calculés (sans persister).

- **FR-007** : Les routers `app/modules/admin/{referentials,indicators,criteria,templates,emission_factors,simulation_factors}_router.py` MUST exposer CRUD standard (GET list, POST create, GET detail, PATCH update, POST publish, DELETE) protégés par admin.

- **FR-008** : Un router `app/modules/admin/sources_router.py` MUST exposer :
  - `GET /api/admin/sources?status=&publisher=&q=&page=&limit=` (liste filtrée, statuses pending/verified/outdated/all)
  - `POST /api/admin/sources` (création, status=pending, captured_by_user_id=current_admin)
  - `GET /api/admin/sources/{id}` (détail)
  - `GET /api/admin/sources/{id}/dependents` (impact analysis : retourne `{indicators, criteria, formulas, emission_factors, simulation_factors, skills, total}`)
  - `PATCH /api/admin/sources/{id}` (édition + transitions verification_status soumises au trigger 4-yeux)
  - `DELETE /api/admin/sources/{id}` (soft delete avec impact analysis)

- **FR-009** : Un service `app/modules/admin/sources_service.py` MUST exposer :
  - `async def get_dependents(source_id: UUID, db) -> dict` : agrège tous les types d'entités catalogue référençant la source.
  - `async def can_delete_source(source_id, db) -> tuple[bool, list]` : retourne `(can_delete, blockers)`.
  - `async def soft_delete_with_cascade(source_id, db, force=False)` : si force=True, cascade `valid_to=today()` sur dépendants.

- **FR-010** : Un router `app/modules/admin/users_router.py` MUST exposer :
  - `GET /api/admin/users?role=&is_active=&q=&page=&limit=` (liste paginée)
  - `GET /api/admin/users/{id}` (détail user + account associé)
  - `POST /api/admin/users/{id}/reset-password` (génère token + email, audit log)
  - `POST /api/admin/users/{id}/toggle-active` (body `{reason: str}`, audit log)
  - Aucun endpoint de modification directe (pas de PATCH user pour MVP).

- **FR-011** : Un router `app/modules/admin/companies_router.py` (ou intégré dans users) MUST exposer :
  - `GET /api/admin/companies?account_status=&sector=&last_login_after=&page=&limit=` (liste PME)
  - `GET /api/admin/companies/{account_id}` : retourne profil + projets + candidatures + scores ESG/Carbon/Crédit + attestations + audit log de ce compte. **Crée automatiquement un audit_log F03 entry `view_admin`** avec dedup logique 1/jour/admin/account.

- **FR-012** : Un router `app/modules/admin/attestations_router.py` MUST exposer :
  - `GET /api/admin/attestations?status=&account_id=&page=&limit=` (liste)
  - `POST /api/admin/attestations/{id}/revoke` (body `{reason: str ≥ 10 chars}`, met à jour `revoked_at`, `revoked_by_user_id`, `revocation_reason`, audit log).

- **FR-013** : Un router `app/modules/admin/metrics_router.py` MUST exposer `GET /api/admin/metrics/overview` qui agrège (en une seule requête avec CTE) : sources counts + trend, accounts counts, candidatures placeholder, attestations counts, llm_costs placeholder. P95 < 500ms sur 1k+ entités.

- **FR-014** : Un service `app/modules/admin/metrics_service.py` MUST exposer `async def compute_overview(db) -> MetricsOverview` avec une seule transaction SQL utilisant CTE pour performance.

- **FR-015** : Un service `app/modules/admin/users_service.py` MUST exposer :
  - `async def initiate_password_reset(user_id, admin_id, db) -> str` : génère token (32 bytes URL-safe), hash sha256, insert password_reset_tokens, envoie email, audit log. Retourne `token_id` pour traçabilité.
  - `async def complete_password_reset(token: str, new_password: str, db)` : vérifie token (hash, expires_at, used_at), bcrypt hash le password, update users, marque used_at.
  - `async def toggle_user_active(user_id, admin_id, reason: str, db)` : toggle is_active, audit log avec metadata.

- **FR-016** : Un endpoint public `POST /api/auth/reset-password` (hors admin) MUST consommer le token créé par admin et permettre au user de définir son nouveau mot de passe. Validation : token valide (hash match), non utilisé (used_at IS NULL), non expiré (expires_at > now()), password ≥ 8 chars.

- **FR-017** : Tous les sous-routers admin MUST être montés dans `app/main.py` sous le préfixe `/api/admin/*`. Le router parent `app/modules/admin/router.py` (créé F02) include les sous-routers.

- **FR-018** : Le frontend MUST exposer un layout `layouts/admin.vue` avec sidebar gauche (sections Catalogue / Sources / Comptes / Métriques / Audit), header avec badge "Mode Admin" rouge, footer minimal. Dark mode complet avec palette accentuée admin (bordures rouge foncé). Aucun lien cross-vers les pages PME.

- **FR-019** : Le frontend MUST exposer ~17 pages admin organisées en :
  - `pages/admin/index.vue` (dashboard métriques)
  - 10 sections catalogue × 3 pages (index, new, [id]) = 30 pages CRUD (selon les besoins, certaines peuvent fusionner index+create)
  - `pages/admin/companies/index.vue`, `pages/admin/companies/[account_id].vue`
  - `pages/admin/sources/index.vue`, `new.vue`, `[id].vue`
  - `pages/admin/attestations/index.vue`
  - `pages/admin/audit/index.vue` (lien F03)
  - `pages/admin/metrics/index.vue`
  - `pages/admin/skills/{index,new,[id]}.vue` (lien F23)

- **FR-020** : Le frontend MUST exposer des composants partagés `components/admin/` :
  - `<EntityCRUDTable>` générique (props columns, dataLoader, actions, pagination, recherche, tri).
  - `<SourcePicker>` modal (filtre par publisher/title, prévisualisation URL, retourne source verified).
  - `<PublishButton>` (disabled si conditions non remplies, tooltip d'explication, clic appelle `POST /publish`).
  - Badges : `<DraftBadge>`, `<PublishedBadge>`, `<PendingBadge>`, `<VerifiedBadge>`, `<OutdatedBadge>`.
  - `<ImpactAnalysisModal>` (liste dépendants avec lien vers leur page).
  - `<MetricsCard>` (titre, valeur, sub-metrics, trend sparkline).

- **FR-021** : Le frontend MUST exposer composables `composables/useAdminCatalog.ts`, `useAdminSources.ts`, `useAdminMetrics.ts`, `useAdminUsers.ts`, `useAdminAttestations.ts`. Chaque composable expose les méthodes CRUD et gère le state via Pinia stores.

- **FR-022** : Le middleware Nuxt `middleware/admin.ts` (créé F02) MUST vérifier `useAuth().user.role === 'admin'`. Si non, redirect vers `/dashboard` avec query `?reason=admin_required`. Appliqué automatiquement à toutes les pages sous `pages/admin/*` via `definePageMeta({ middleware: ['admin'] })`.

- **FR-023** : Toute mutation admin (POST/PATCH/DELETE/publish/revoke/reset-password/toggle-active) MUST émettre un audit log F03 entry avec actor_id=admin.id, action explicite, entity_type, entity_id, metadata structuré (avant/après si applicable).

- **FR-024** : La consultation admin d'un compte PME (`GET /api/admin/companies/{id}`) MUST émettre un audit_log F03 entry `view_admin` avec actor_id=admin.id, entity_type="account", entity_id=account_id, dedup logique 1/jour/admin/account. Cette entry est visible côté PME via l'endpoint `GET /api/account/audit`.

- **FR-025** : Aucune référence à `admin_emails = {"admin@esg-mefali.com", "admin@mefali.org"}` ne MUST subsister dans le code (test conformity grep). F02 a déjà supprimé cet anti-pattern.

- **FR-026** : Tous les sous-routers admin MUST utiliser des schemas Pydantic stricts (`schemas.py` par sous-module) pour la validation entrée/sortie. Les réponses suivent le format consistent `{success, data, error, meta}` (pattern existant).

- **FR-027** : Service `app/core/email_service.py` (créé ou validé) MUST exposer `async def send_password_reset_email(user_email: str, reset_link: str)`. En dev (env `EMAIL_BACKEND=console`), log le lien dans la console au lieu d'envoyer un vrai email. En prod, utilise SMTP ou service externe (SendGrid/SES — assumption).

- **FR-028** : Tests de couverture ≥ 80 % sur les nouveaux modules `app/modules/admin/*` (services, routers, schemas) et triggers PostgreSQL via tests d'intégration (créer fixture, exécuter UPDATE, vérifier exception levée).

### Key Entities

- **`PublicationStatus` (colonne enum sur 10 tables)** : `draft | published`. Default `draft`. Le LLM ne consomme que `published`. Trigger gating `before_publish_check_sources_verified` empêche transition vers `published` si sources non verified.

- **`PasswordResetToken` (table `password_reset_tokens`)** : `id UUID PK`, `user_id UUID FK users.id`, `token_hash VARCHAR(128) UNIQUE` (sha256 du token plain), `expires_at TIMESTAMPTZ NOT NULL` (now + 1h), `used_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL`. Token plain envoyé par email, jamais stocké.

- **`Trigger before_publish_check_sources_verified`** : fonction PL/pgSQL + 10 triggers TABLE-spécifiques. Bloque transition `draft → published` si au moins une source liée est `pending` ou `outdated`. Lève `P0001` avec liste des sources bloquantes.

- **`Trigger before_verify_source_check_different_admin`** : fonction PL/pgSQL + 1 trigger sur `sources`. Bloque transition `pending → verified` si `verified_by_user_id = captured_by_user_id`. Lève `P0001`.

- **`AdminAuditLogEntry` (subset de F03 audit_log)** : action enum incluant `fund_created`, `fund_published`, `fund_deleted`, `intermediary_*`, `offer_*`, `source_created`, `source_verified`, `source_outdated`, `source_modified`, `view_admin`, `password_reset_initiated_by_admin`, `password_reset_completed`, `user_toggled_active`, `attestation_revoked`, `referential_*`, `indicator_*`, `criterion_*`, `template_*`, `emission_factor_*`, `simulation_factor_*`. Métadonnées structurées par action.

- **`MetricsOverview` (Pydantic)** : `{sources: {total, pending, verified, outdated, trend_30d}, accounts: {total_active, total_inactive, new_30d}, applications: {total, by_status} | placeholder, attestations: {total_emitted, total_revoked, total_active}, llm_costs: {total_tokens_in, total_tokens_out, total_cost_usd_estimated_30d} | placeholder, generated_at: datetime}`.

- **`DependentsReport` (Pydantic)** : `{source_id, indicators: list[{id, name, status}], criteria: [...], formulas: [...], emission_factors: [...], simulation_factors: [...], skills: [...], total: int}`. Utilisé par `<ImpactAnalysisModal>`.

## Success Criteria

### Measurable Outcomes

- **SC-001** : Migration `035_admin_publication_status_workflow.py` s'applique sur BDD existante sans erreur (test : `alembic upgrade head` puis `alembic downgrade -1` puis `alembic upgrade head`).
- **SC-002** : Test E2E 4-yeux source : Admin A crée Source → Admin A tente verify → 400 trigger violation → Admin B verify → 200, status verified. Couverture 100 %.
- **SC-003** : Test E2E publish gating : Admin crée Fund + Source pending → tente publish → 400 → Admin B verify Source → publish → 200. Couverture 100 %.
- **SC-004** : Test E2E isolation : User PME tente `/api/admin/funds` → 403. Tente `/admin/funds` (frontend) → middleware redirect. Couverture 100 %.
- **SC-005** : Test E2E reset password : Admin POST reset → token créé en BDD avec expires_at = now + 1h → email envoyé (console dev) → user POST reset-password avec token + new_pw → 200, token marqué used_at → user login avec new_pw → succès. Couverture 100 %.
- **SC-006** : Audit log F03 entry `view_admin` créée à chaque consultation admin d'un compte PME (dedup 1/jour). Visible côté PME via `/account/audit`.
- **SC-007** : 0 régression sur les tests backend existants (suite complète passe).
- **SC-008** : Couverture tests ≥ 80 % sur les nouveaux modules `app/modules/admin/*` (15 sous-routers, 5 services).
- **SC-009** : Aucune référence à `admin_emails = {...}` whitelist dans le code (test conformity grep `admin_emails` → 0 match dans `backend/app/`).
- **SC-010** : Endpoint `GET /api/admin/metrics/overview` retourne en P95 < 500ms sur fixtures (1000 sources, 5000 users, 100 attestations).
- **SC-011** : Page `/admin/funds` charge en < 2s sur 1000 fonds avec pagination 20/page.
- **SC-012** : Layout `layouts/admin.vue` a 100 % dark mode (audit visuel + tests Playwright dark mode toggle).
- **SC-013** : Tous les CRUD entités catalogue (10 entités × ~5 endpoints = ~50 endpoints) sont fonctionnels (test E2E par entité : create draft → publish blocked → fix sources → publish OK → edit → delete).
- **SC-014** : Trigger `before_publish_check_sources_verified` testé sur les 10 tables (1 test par table = 10 tests d'intégration).
- **SC-015** : Composant `<EntityCRUDTable>` réutilisable sur 10 sections catalogue (DRY validé : pas de duplication).

## Assumptions

- F01 (Sources) est mergé : table `sources` existe avec `verification_status`, `captured_by_user_id`, `verified_by_user_id`. F09 ajoute le workflow 4-yeux via trigger.
- F02 (Multi-tenant + roles) est mergé : `get_current_admin`, middleware `admin.ts`, layout admin squelette, suppression anti-pattern `admin_emails`.
- F03 (Audit log) est mergé : `audit_log_entry()` disponible. Page `pages/admin/audit/index.vue` créée (F09 valide les liens sidebar).
- F04 (Versioning) est mergé : `VersioningMixin` disponible pour édition entités catalogue (nouvelle version à chaque PATCH d'une entité published).
- F07 (Offer) est mergé : `compute_effective_offer(fund_id, intermediary_id)` disponible.
- F08 (Attestations) est mergé : modèle `attestations` avec `revoked_at`, `revoked_by_user_id`, `revocation_reason`. F09 expose endpoint admin de révocation.
- F23 (Skills) est mergé : router `app/modules/admin/skills_router.py` créé. F09 valide les liens sidebar et garantit cohérence du workflow draft→published (skills déjà conformes via F23).
- Service `app/core/email_service.py` existe ou est créé en F09. En dev, fallback console log (env var `EMAIL_BACKEND=console`).
- Le frontend a déjà une infrastructure de stores Pinia + composables (toutes les features précédentes l'ont utilisée).
- Aucune migration de données automatique : les entités catalogue existantes (seedées par F01-F08) deviennent `draft` après migration. Un script séparé `scripts/seed_publish_existing_catalog.py` doit être exécuté pour les passer à `published` après vérification manuelle des sources.
- Tests d'intégration utilisent une BDD PostgreSQL réelle (pas SQLite in-memory) car les triggers PL/pgSQL ne sont pas portables. Tests unitaires services peuvent utiliser SQLite mocked.
- Pagination MVP : default 20, max 100. Pas de cursor-based pagination (offset-based suffit pour < 10k entités).
- Recherche full-text : MVP utilise `ILIKE` SQL avec index trigram (extension `pg_trgm`). Post-MVP : Elasticsearch ou PostgreSQL FTS.
- Permissions intra-admin granulaires (`dpo`, `catalog_editor`, `support`) sont post-MVP. MVP utilise `role IN ('admin','user')` binaire.
- Bulk import CSV/Excel pour catalogue est post-MVP. MVP : création ligne par ligne via formulaires.
- Coûts LLM par PME : nécessite ajout `tokens_in/tokens_out/cost_usd` sur `tool_call_logs`. Post-MVP. MVP : placeholder dans MetricsOverview.
- Workflow `pending_review` intermédiaire entre draft et verified pour sources : post-MVP. MVP : draft → published direct (avec sources verified) ; pending → verified direct (4-yeux).
- Contributions communautaires consultants (marketplace) : post-MVP.
- Changelog public : post-MVP.
