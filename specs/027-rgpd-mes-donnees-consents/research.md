# Phase 0 — Research : F05 RGPD Mes Données + Consentements + Export/Suppression

Date : 2026-05-07
Branche : `feat/F05-rgpd-mes-donnees-consents` (alias SpecKit `027-rgpd-mes-donnees-consents`)

## Décisions et alternatives

### Décision 1 — Stockage de `consent_type` (clarification Q1)

- **Décision** : Enum natif PostgreSQL `consent_type_enum` à 7 valeurs documentées (`profile_analysis`, `document_analysis_ai`, `mobile_money_analysis`, `photos_ia_analysis`, `public_data_analysis`, `credit_certificate_generation`, `product_communications`). Côté SQLAlchemy : `sa.Enum('profile_analysis', ..., name='consent_type_enum', create_type=True)`. Évolutions futures via migration Alembic dédiée `op.execute("ALTER TYPE consent_type_enum ADD VALUE 'xxx'")`.
- **Rationale** : Cohérent avec les patterns enums du projet (F02 `account_role`, F03 `audit_action`, F17 categories). Contrainte BDD native (rejette les valeurs inconnues). Pas de table de référence à maintenir. Migration future bien documentée par Alembic.
- **Alternatives considérées** :
  - *`String` libre + check application-level* : rejeté car perte de garantie BDD, validation distribuée en plusieurs endroits.
  - *Table `consent_types` de référence* : rejeté car sur-ingénierie pour 7 valeurs stables et documentées dans le code.
  - *Enum Python (StringEnum) sans CREATE TYPE* : rejeté car perdrait le check BDD ; mais Python `StrEnum` est utilisé en miroir côté backend pour la sérialisation Pydantic.

### Décision 2 — Pas de table `data_export_jobs` au MVP (clarification Q2)

- **Décision** : Au MVP, l'export est tracé exclusivement dans `audit_log` (F03). Mode synchrone : un événement `data_export_completed` avec `metadata.url` (signed) + `metadata.size_bytes`. Mode asynchrone : événement initial `data_export_requested` puis événement `data_export_ready` avec lien signé 7j.
- **Rationale** : Recommandation orchestrateur (« décision par défaut : différer toute table non strictement requise »). Le volume MVP (≤ 100 PME pilote, ≤ ~10 exports/jour estimés) ne justifie pas une table dédiée. Évite une migration supplémentaire sur le sprint F05.
- **Alternatives considérées** :
  - *Créer dès F05 une table `data_export_jobs(id, account_id, status, requested_at, ready_at, signed_url, size_bytes)`* : rejeté car prématuré ; sera créée post-MVP avec F19 (cron dispatcher) si volume justifie.
  - *Stocker dans une table générique `background_jobs`* : rejeté car non utilisée dans le projet pour le moment.

### Décision 3 — Anonymisation `audit_log` à la purge (clarification Q3)

- **Décision** : UPDATE en place : `UPDATE audit_log SET user_id = NULL, account_id = NULL, payload = anonymize_payload(payload) WHERE account_id = X`. La fonction `anonymize_payload(payload, account_id)` retire les champs whitelistés connus (`email`, `phone`, `ip`, `user_agent`, `name`, `address`, `mobile_number`, `bank_account`, etc.) du JSON et conserve les autres champs métier (entity_type, entity_id, action, status, etc.).
- **Rationale** : Préserve l'invariant append-only de F03 (pas de DELETE). Coût stockage minimal (UPDATE ne duplique pas). Une seule transaction SQL. Garantit qu'aucune PII (Personally Identifiable Information) ne reste dans audit_log post-purge, tout en conservant la valeur d'audit (action, timestamp, entity_type, entity_id non-PII).
- **Alternatives considérées** :
  - *INSERT d'une copie anonymisée + DELETE de l'original* : rejeté (viole l'append-only, double les writes).
  - *DELETE pur des rows account_id* : rejeté (perte totale de l'audit, violation conservation 6 ans légale).
  - *Filtrage applicatif uniquement (sans toucher BDD)* : rejeté (PII reste accessible via accès direct à la BDD ; non conforme RGPD).

### Décision 4 — Layout Nuxt `public.vue` distinct (clarification Q4)

- **Décision** : Création d'un layout Nuxt `public.vue` dans `frontend/app/layouts/` si absent. Ce layout présente : header simplifié (logo ESG Mefali + lien retour login), `<slot />` pour le contenu, footer global (lien `/legal/privacy` inclus). Pas de sidebar. Pas de menu utilisateur authentifié. Pas de fetch de données utilisateur.
- **Rationale** : Sépare clairement l'UX public de l'UX authentifié. Évite tout risque de fuite de données utilisateur via slot par défaut. Cohérent avec la pratique Nuxt standard (`definePageMeta({layout: 'public'})` sur la page).
- **Alternatives considérées** :
  - *Réutiliser `default.vue` avec condition `if (route.meta.public) hideSidebar()`* : rejeté (ajoute de la complexité conditionnelle, augmente le risque de fuite, viole le principe de simplicité).
  - *Pas de layout (page autonome `<NuxtPage />`)* : rejeté (perte de footer global avec lien `/legal/privacy`).

### Décision 5 — Endpoint dédié `verify-password` + revérification dans `schedule-deletion` (clarification Q5)

- **Décision** : Deux endpoints distincts. Frontend : `<DeletionConfirmModal>` appelle d'abord `POST /api/me/account/verify-password` (réponse 200/401) pour valider l'étape 2 (saisie du mot de passe), puis `POST /api/me/account/schedule-deletion` avec body `{password, confirmation_text='SUPPRIMER'}` qui revérifie le mot de passe côté backend.
- **Rationale** : Double validation côté backend = défense en profondeur. Un attaquant avec une session JWT volée ne peut pas programmer une suppression sans le mot de passe. Le `verify-password` séparé permet aussi un meilleur UX côté frontend (feedback immédiat sur le mot de passe avant la confirmation finale).
- **Alternatives considérées** :
  - *Réutiliser `POST /api/auth/login` interne* : rejeté car cet endpoint génère un nouveau JWT (effet secondaire indésirable).
  - *Endpoint unique `schedule-deletion` qui vérifie tout en une fois* : rejeté car perte de feedback utilisateur (le mot de passe n'est validé qu'à la fin).
  - *Vérification frontend uniquement* : rejeté (sécurité critique, ne jamais faire confiance au frontend).

### Décision 6 — `BackgroundTasks` FastAPI pour l'export asynchrone (clarification Q6)

- **Décision** : `BackgroundTasks` FastAPI (intégré, sans dépendance externe) pour les exports volumineux (> 100 MB). Le job est exécuté in-process post-réponse 202 ; à la fin, le job stocke le ZIP sur disque (`/uploads/exports/{account_id}/{export_id}.zip`), génère un lien signé 7j, et envoie un email à l'utilisateur.
- **Rationale** : Aligné avec `CLAUDE.md` (« Queue : Synchrone (Redis + Celery plus tard) »). Pas de nouvelle dépendance. Le risque de perte de job en cas de redémarrage process est acceptable au MVP : un événement `data_export_requested` reste dans audit_log, l'utilisateur peut relancer manuellement (et le frontend peut détecter via API d'inventaire que l'export précédent n'a jamais reçu son `data_export_ready`).
- **Alternatives considérées** :
  - *Celery + Redis* : rejeté car contrarie la directive `CLAUDE.md`. Sera introduit avec F19 (cron dispatcher).
  - *RQ (Redis Queue)* : même rationale.
  - *Crontab système qui scrute une table `pending_exports`* : rejeté (créerait la table `data_export_jobs` qu'on a justement décidé de différer en Décision 2).

### Décision 7 — Test CI scanner regex sur services sensibles (clarification Q7)

- **Décision** : Pytest dédié `backend/tests/security/test_require_consent_coverage.py`. Logique :
  1. Walk les fichiers `.py` dans `backend/app/services/`, `backend/app/modules/*/service.py`, `backend/app/graph/tools/*_tools.py`.
  2. Pour chaque fonction nommée `analyze_*`, `fetch_*_external`, `generate_certificate_*`, `process_*_sensitive`, vérifier que le corps contient la chaîne `require_consent(`.
  3. Liste d'exclusions explicite : si une fonction est légitimement non concernée (ex. `analyze_self_assessed_score` sur les données saisies par l'utilisateur eux-mêmes), elle peut être ajoutée à `EXCLUSIONS = {...}` documentée avec un commentaire.
  4. Le test fail avec une erreur claire listant les fonctions non conformes.
- **Rationale** : Pragmatique (aucune dépendance externe). Maintenable par tout développeur. Faux positifs gérés par la liste d'exclusions explicite (revue à chaque modification). Cohérent avec les patterns de test du projet (pytest existant).
- **Alternatives considérées** :
  - *Décorateur Python `@requires_consent('mobile_money_analysis')`* : envisagé puis combiné avec le scanner (les fonctions décorées passent automatiquement le test). Approche hybride : décorateur préféré dans le code, scanner garde-fou pour les implémentations directes.
  - *Linter ESLint-like personnalisé* : rejeté (sur-ingénierie, dépendance supplémentaire).
  - *Static analysis via `ast.parse`* : envisageable mais regex suffit au MVP.

### Décision 8 — Format URLs signées : `itsdangerous`

- **Décision** : Utiliser `itsdangerous.URLSafeTimedSerializer(SECRET_KEY)` pour signer les URLs de download d'export et les liens email d'annulation de suppression. Clé secrète dans `EXPORT_URL_SIGNING_KEY` (env var).
- **Rationale** : Bibliothèque standard FastAPI tutorials, déjà éprouvée, signature embarque tout le state nécessaire (no-stockage en BDD). Expiration native (24h pour les liens documents, 7j pour le lien email d'export, illimité pour le lien d'annulation de suppression mais expirera automatiquement à la purge).
- **Alternatives considérées** :
  - *JWT custom* : rejeté (overkill pour des URLs courte durée, dépendance plus lourde).
  - *Token UUID v4 stocké en BDD avec expiration* : rejeté (nécessite une table supplémentaire ; viole le principe de simplicité).
  - *HMAC SHA256 manuel* : rejeté (réinvente la roue, plus risqué).

### Décision 9 — Email transactionnel : stub si pas de SMTP

- **Décision** : `app/core/mailer.py::send_email(to, subject, body_html, body_text)` : si `SMTP_HOST` non configuré dans env, le mailer logge le payload dans `audit_log` (`entity_type='email'`, `action='sent_stub'`, `metadata={to, subject, body_text}`) et retourne succès. Si `SMTP_HOST` configuré, envoi SMTP réel via `aiosmtplib` (asynchrone).
- **Rationale** : Permet aux tests E2E de vérifier l'envoi sans dépendance SMTP réelle (mock = lookup audit_log). Production : déploiement SMTP géré au niveau infra. Cohérent avec la pratique des stubs en tests.
- **Alternatives considérées** :
  - *Bloquer l'application si SMTP non configuré* : rejeté (empêche le développement local).
  - *Mock complet via fixture pytest* : utilisé en parallèle pour les tests unit/integration ; le stub `audit_log` sert pour les E2E.

### Décision 10 — Cron job : flag `purge_in_progress` pour idempotence

- **Décision** : `accounts.purge_in_progress: boolean NOT NULL DEFAULT false`. Le cron : `SELECT * FROM accounts WHERE deletion_scheduled_at < now() AND deleted_at IS NULL`. Pour chaque account : `UPDATE accounts SET purge_in_progress=true` AVANT la cascade ; à la fin, `UPDATE accounts SET deleted_at=now(), purge_in_progress=false`. Si redémarrage en milieu de purge : la prochaine exécution du cron voit `purge_in_progress=true` ET `deleted_at IS NULL` ET `deletion_scheduled_at < now()`, et reprend la cascade là où elle s'est arrêtée.
- **Rationale** : Idempotence simple, sans table d'état séparée. La cascade est elle-même partiellement idempotente (DELETE de rows déjà supprimés est no-op).
- **Alternatives considérées** :
  - *Table `purge_jobs(account_id, status, started_at, completed_at)`* : rejeté (sur-ingénierie pour le volume MVP).
  - *Lock pessimiste sur l'account* : rejeté (compliqué, le cron est mono-thread au MVP).

### Décision 11 — Triple confirmation modale : 3 étapes incrémentales

- **Décision** : `<DeletionConfirmModal>` Vue présente 3 étapes successives (UI :
  1. **Étape 1 — Conséquences** : liste des effets (« vos candidatures seront annulées », « votre attestation crédit sera révoquée », etc.) + checkbox « Je comprends ces conséquences ».
  2. **Étape 2 — Mot de passe** : input password + appel asynchrone `/api/me/account/verify-password` au blur. Feedback immédiat (vert/rouge).
  3. **Étape 3 — Confirmation textuelle** : input text + validation côté frontend que `value === 'SUPPRIMER'` (case-sensitive).
- Le bouton « Confirmer la suppression » est désactivé tant que les 3 étapes ne sont pas validées.
- À la confirmation, appel `POST /api/me/account/schedule-deletion` avec `{password, confirmation_text}` — le backend revérifie tout.
- **Rationale** : UX standard pour les actions critiques (Google Workspace, GitHub, etc.). Validation incrémentale améliore l'UX (feedback immédiat sur le mot de passe). Double validation backend.
- **Alternatives considérées** :
  - *Une seule étape avec tous les champs en même temps* : rejeté (UX moins claire, l'utilisateur ne réalise pas la portée).
  - *Confirmation par email avant `schedule-deletion`* : rejeté (UX trop frictionnelle, et la confirmation par email arrive après).

### Décision 12 — Structure du fichier export ZIP

- **Décision** :
  ```
  esg-mefali-export-{account_id}-{YYYYMMDD-HHmmss}.zip
  ├── README.md                  # Description structure + URLs signées 24h documentées
  ├── data.json                  # Toutes les tables account_id (profil, projets, candidatures, esg_assessments, carbon_assessments, credit_scores, conversations, messages, attestations, consents, audit_log_personnel)
  └── documents/
      └── manifest.json          # Liste {filename, signed_url, expires_at, original_path, mimetype, size}
  ```
- Les fichiers binaires (PDF documents) NE SONT PAS inclus dans le ZIP. Seuls les liens signés 24h sont fournis dans `manifest.json`.
- **Rationale** : ZIP léger (< 1 MB pour la plupart des comptes). L'utilisateur clique sur le lien signé pour récupérer chaque document. Permet de gérer les très gros comptes sans saturation. Contrepartie : si l'utilisateur veut tout archiver, il doit lancer un script de download. Acceptable au MVP, documenté dans `README.md`.
- **Alternatives considérées** :
  - *Inclure tous les fichiers dans le ZIP* : rejeté (peut dépasser 1 GB facilement, saturation).
  - *Deux ZIPs séparés (data + documents)* : rejeté (UX confuse).
  - *Format JSON streamé sans ZIP* : rejeté (perte de la structure documents/ + README).

### Décision 13 — Helper `require_consent` async + dépendance FastAPI

- **Décision** : `async def require_consent(db: AsyncSession, account_id: UUID, consent_type: ConsentType) -> None`. Utilisable directement dans un service ou via FastAPI Depends comme `RequireConsentDep = Depends(get_consent_dependency('mobile_money_analysis'))`. Le helper async est cohérent avec la stack `asyncpg` du projet.
- **Rationale** : Async pour cohérence stack. Forme `Depends` permet une utilisation déclarative dans les routers (ex: `@router.post("/credit/mobile-money/preview", dependencies=[Depends(require_consent_mobile_money)])`). Forme directe utilisable dans les services / tools LangChain.
- **Alternatives considérées** :
  - *Sync only* : rejeté (incompatible avec asyncpg).
  - *Decorator Python pur (`@requires_consent('mobile_money_analysis')`)* : envisagé mais nécessite de pouvoir extraire `account_id` du contexte ; ajouté en complément (helper async + decorator combinable avec `request.state.user`).

## Risques et garde-fous

| Risque | Probabilité | Impact | Garde-fou |
|--------|-------------|--------|-----------|
| Une feature future ajoute un service `analyze_*` sans `require_consent` | Moyen | Critique RGPD | Test CI security `test_require_consent_coverage.py` (Décision 7) |
| Le cron purge échoue en milieu d'exécution et laisse un compte demi-supprimé | Faible | Élevé | Flag `purge_in_progress` + idempotence cascade (Décision 10) |
| Un export volumineux > 1 GB sature le serveur | Faible | Moyen | Limite alerte 1 GB documentée + bascule async > 100 MB |
| Un attaquant avec session volée tente de programmer la suppression | Moyen | Critique | Double vérification mot de passe (Décision 5) |
| L'enum `consent_type_enum` doit évoluer après mise en production | Élevé (probable) | Faible | Migration Alembic dédiée `ALTER TYPE ... ADD VALUE` documentée |
| Le SMTP n'est pas configuré en prod et les emails ne partent pas | Moyen | Élevé | Stub mailer + alerte logs si `SMTP_HOST` absent en prod (variable env requise documentée dans `docs/hosting-and-data-residency.md`) |
| Une PME perd son lien d'annulation par email et ne peut pas annuler | Faible | Moyen | Bouton « Annuler » également disponible sur `/mes-donnees` (auth) tant que le compte n'est pas purgé |
| Anonymisation `audit_log` ne couvre pas un nouveau champ PII ajouté plus tard | Moyen | Critique | `anonymize_payload` whitelist auditée à chaque ajout de champ ; test unitaire qui vérifie qu'aucun champ PII connu ne survit |

## Ordre des migrations Alembic

Au démarrage de F05 (état HEAD = `9b2800e`, soit `024_carbone_mix_uemoa.py` mergé), les migrations existantes sont 001…024. Le `down_revision` exact de la migration F05 sera **fixé en Phase B** selon l'ordre de merge effectif :

- Si F06 (`entite-projet-vert`) est mergé avant F05 : `down_revision = '025_xxx'`
- Si F08 (`attestation-verifiable-ed25519`) est mergé avant : `down_revision = '026_xxx'` (ou plus récent)
- Sinon : `down_revision = '024_carbone_mix_uemoa'`

Le numéro pressenti est `027` mais peut être ajusté en Phase B en consultation avec l'orchestrateur. La migration sera nommée `0XX_consents_and_account_deletion.py`.

## Sources / références

- RGPD 2016/679, articles 7 (consentement), 15 (droit d'accès), 17 (droit à l'effacement), 20 (droit à la portabilité).
- Loi ivoirienne n°2013-450 du 19 juin 2013 relative à la protection des données à caractère personnel.
- Règlement UEMOA n°20/2010/CM/UEMOA portant lutte contre les pratiques anticoncurrentielles, partie protection des données.
- FastAPI Background Tasks : https://fastapi.tiangolo.com/tutorial/background-tasks/
- itsdangerous URLSafeTimedSerializer : https://itsdangerous.palletsprojects.com/
- Pratiques RGPD :
  - Délai de grâce 30 jours : standard chez Google, Microsoft, Atlassian.
  - Anonymisation audit_log : recommandation CNIL « pseudonymisation et minimisation ».
- Pattern enum natif PostgreSQL : Alembic cookbook https://alembic.sqlalchemy.org/
