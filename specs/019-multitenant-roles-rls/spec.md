# Feature Specification: F02 — Multi-tenant + Rôle Admin + Row-Level Security

**Feature Branch**: `019-multitenant-roles-rls`
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "F02 — Introduire les entités `Account` et `RefreshToken`, ajouter `role` (PME/ADMIN) et `account_id` sur les utilisateurs, déployer la Row-Level Security PostgreSQL sur les 13+ tables métier pour isolation stricte multi-tenant, mettre en place une rotation de refresh token avec révocation, créer la dépendance `get_current_admin`, monter un routeur `/api/admin` protégé, autoriser le multi-utilisateurs PME via invitations d'équipe, livrer un middleware/layout admin frontend différencié, et supprimer la whitelist email anti-pattern existante."

## Clarifications

### Session 2026-05-06

Mode autonomie totale (utilisateur absent) — décisions prises selon les invariants ESG Mefali, la stack imposée, et le critère « plus simple et testable ». Le détail rationnel est enregistré ci-dessous.

- Q : Quelle TTL pour les tokens d'invitation d'équipe PME ? → A : 7 jours (industry standard, équilibre sécurité/expérience ; configurable via une variable de configuration `INVITE_TOKEN_TTL_DAYS`).
- Q : Comment livrer les emails d'invitation en MVP (sans service SMTP réel) ? → A : Stratégie « stub + persistance ». Le contenu de l'email (sujet + corps + lien) est journalisé sur stdout en INFO et l'invitation est inscrite en BDD dans `account_invitations`. Aucun branchement SMTP/SendGrid/SES en F02. Une interface `EmailDeliveryService` est introduite avec une seule implémentation `LoggingEmailDelivery` pour permettre le swap futur sans modification d'appelants.
- Q : Quel rôle PostgreSQL utiliser pour appliquer les policies RLS ? → A : Pas de rôle PostgreSQL séparé en MVP. Le `database_url` existant continue à se connecter avec son rôle courant. Pour garantir que les policies s'appliquent même au propriétaire des tables, chaque table activera `ENABLE ROW LEVEL SECURITY` ET `FORCE ROW LEVEL SECURITY` (fail-closed). Les variables de session `app.current_account_id` et `app.current_role` sont positionnées sur la connexion à chaque requête authentifiée via `SET LOCAL` dans une transaction.
- Q : Quelle relation entre `Account` et `company_profiles` après l'introduction du multi-tenant ? → A : 1:1 avec `Account` (un seul `company_profile` par `Account`, contrainte d'unicité sur `company_profiles.account_id`). La colonne `user_id` est conservée comme attribut historique « auteur » mais n'est plus la clé d'unicité métier. Lors du backfill, si plusieurs utilisateurs partageaient un même `company_name` mais avaient chacun leur `company_profile`, seul le profil le plus récent est conservé pour l'`Account`, les autres sont soft-archivés (déplacés dans `_legacy_company_profiles_archive` ou marqués `archived = true`) avec journalisation.
- Q : Quel est l'effet de la désactivation d'un `Account` (`is_active = false`) sur ses données ? → A : Désactivation logicielle uniquement (« soft deactivation »). Toutes les sessions des membres sont invalidées (refresh tokens révoqués), les futures tentatives de connexion sont rejetées (HTTP 403 avec message explicite), mais les données restent intactes en base. Aucun `CASCADE DELETE` n'est appliqué. La réactivation est possible à tout moment par un Admin et restaure l'accès sans perte. L'archivage RGPD complet (anonymisation) est repoussé en F05.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Isolation stricte des données entre comptes PME (Priority: P1)

Une PME A et une PME B utilisent la plateforme en parallèle. Aucune erreur applicative (oubli de filtre `WHERE`, fuite via une requête SQL directe, bug dans un service) ne doit jamais permettre à un utilisateur de la PME A d'accéder aux données de la PME B (profil, candidatures, scores ESG, plan d'action, conversations, documents).

**Why this priority** : C'est l'invariant de sécurité fondamental de la plateforme. Sans cette garantie, la conformité multi-tenant est impossible et toute fuite de données détruit la confiance et expose à un risque RGPD. Cette user story est BLOQUANTE pour toutes les autres features qui manipulent des données métier.

**Independent Test** : Créer deux comptes PME (A et B) dans la même base de données, puis exécuter, en tant qu'utilisateur de la PME A, une requête métier (par exemple `GET /api/conversations`, `GET /api/applications`, ou même une requête SQL directe `SELECT * FROM conversations` interceptée dans la transaction applicative) ; vérifier qu'aucune ligne appartenant à la PME B n'est retournée, même quand un service applicatif est volontairement modifié pour omettre le filtre par `account_id`.

**Acceptance Scenarios** :

1. **Given** une PME A et une PME B avec chacune 3 conversations, 2 documents et 1 plan d'action, **When** l'utilisateur de la PME A appelle n'importe quel endpoint métier (`/api/conversations`, `/api/documents`, `/api/dashboard`, `/api/action-plan`), **Then** seules les ressources de la PME A sont retournées (3 conversations, 2 documents, 1 plan d'action) et aucune référence (id ou contenu) aux ressources de la PME B n'apparaît.
2. **Given** un service backend dont la requête est volontairement modifiée pour omettre `WHERE account_id = ...`, **When** la requête est exécutée dans le cadre d'une session authentifiée d'un utilisateur PME A, **Then** la base de données filtre automatiquement les résultats grâce à la Row-Level Security et ne retourne que les lignes appartenant à la PME A.
3. **Given** qu'aucune variable de session `app.current_account_id` n'est définie sur la connexion (cas d'erreur applicative), **When** une requête est tentée sur une table métier protégée par RLS, **Then** la requête échoue (ou retourne 0 ligne) plutôt que de fuiter des données — comportement « secure by default ».

---

### User Story 2 - Accès du back-office Admin réservé à l'équipe Mefali (Priority: P1)

L'équipe ESG Mefali (rôle `ADMIN`) doit pouvoir accéder à un espace back-office (`/admin/*`) distinct du tableau de bord PME, tandis qu'un utilisateur PME standard est rejeté avec un 403 ou redirigé vers son `/dashboard`. L'identité visuelle de l'espace admin (couleur d'accent rouge/orange, badge persistant « Mode Admin ») évite toute confusion entre les deux contextes.

**Why this priority** : Le back-office est la condition nécessaire pour que F09 (Back-Office Admin), F20 (Bibliothèque ressources) et toutes les fonctionnalités de gestion catalogue/sources puissent exister. Sans rôle Admin réel, la plateforme repose aujourd'hui sur une whitelist d'emails en dur (`backend/app/modules/financing/router.py:118`), un anti-pattern à supprimer.

**Independent Test** : Créer un utilisateur Admin via seed/migration, se connecter en tant qu'Admin et accéder à `/admin/health` (200) et `/api/admin/health` (200) ; se connecter ensuite en tant qu'utilisateur PME et vérifier que l'accès à `/admin/*` redirige vers `/dashboard` et que l'API `/api/admin/*` retourne 403.

**Acceptance Scenarios** :

1. **Given** un utilisateur dont `role = 'ADMIN'`, **When** il accède au frontend `/admin/health`, **Then** la page se charge avec le layout admin (sidebar admin, badge « Mode Admin », accent rouge/orange) et l'API `GET /api/admin/health` retourne 200.
2. **Given** un utilisateur dont `role = 'PME'`, **When** il accède au frontend `/admin/*`, **Then** il est redirigé vers `/dashboard` (ou voit une page 403) et l'API `GET /api/admin/health` retourne 403 Forbidden.
3. **Given** un appel à `POST /api/financing/funds` (création d'un fonds), **When** l'utilisateur authentifié n'a pas le rôle `ADMIN`, **Then** la requête retourne 403, et la whitelist email statique a été supprimée du code.

---

### User Story 3 - Multi-utilisateurs PME via invitations d'équipe (Priority: P2)

Une PME doit pouvoir inviter un collaborateur (un autre utilisateur) à rejoindre son `Account`. Le collaborateur reçoit un lien d'invitation, s'inscrit, puis accède exactement aux mêmes données (profil, candidatures, scores ESG, plan d'action) que l'invitant. Aucune granularité hiérarchique en MVP : tous les membres d'un même `Account` ont des droits équivalents.

**Why this priority** : Permet à une PME de déléguer la gestion de la conformité ESG à plusieurs personnes (dirigeant + responsable QHSE par exemple), prérequis du Module 7.3 (Tableau de bord multi-utilisateurs). Importance secondaire en P1 mais fonctionnellement structurante.

**Independent Test** : Se connecter avec un utilisateur PME existant, créer une invitation via `POST /api/account/invite` pour `nouveau@example.com`, ouvrir le lien d'invitation `/register?invite=<token>` dans un autre navigateur, finaliser l'inscription, puis vérifier que le nouvel utilisateur voit l'intégralité des données de l'`Account` parent (mêmes conversations, mêmes scores, mêmes documents).

**Acceptance Scenarios** :

1. **Given** un utilisateur PME A authentifié, **When** il appelle `POST /api/account/invite` avec un email cible, **Then** une invitation est créée (avec un token unique et une expiration), un email d'invitation est envoyé (ou l'envoi est journalisé en mode dev), et l'invitation apparaît dans `GET /api/account/users` avec le statut `pending`.
2. **Given** une invitation valide reçue par email avec un lien `/register?invite=<token>`, **When** le destinataire ouvre ce lien et soumet le formulaire d'inscription, **Then** un nouvel utilisateur est créé avec `account_id` égal à celui de l'invitant et `role = 'PME'`, et l'invitation est marquée `accepted`.
3. **Given** deux utilisateurs PME (Alice invitante, Bob invité acceptant) appartenant au même `Account`, **When** Alice crée une candidature de fonds, **Then** Bob voit cette même candidature dans son interface et peut la modifier ou la consulter avec les mêmes droits qu'Alice.
4. **Given** un utilisateur PME A authentifié, **When** il appelle `DELETE /api/account/users/{id}` pour retirer un collaborateur, **Then** le collaborateur perd l'accès aux données de l'`Account` (sa session est invalidée, ses futurs appels retournent 401 ou 403 selon le contexte).

---

### User Story 4 - Sessions sécurisées avec refresh token rotatif et logout (Priority: P2)

Chaque rafraîchissement de session doit invalider l'ancien refresh token (rotation) pour limiter l'impact d'une fuite de token, et un endpoint de logout doit révoquer toutes les sessions actives d'un utilisateur. Une fenêtre de grâce de 5 secondes tolère l'usage simultané de l'ancien et du nouveau refresh token (cas multi-onglets) sans casser l'expérience utilisateur.

**Why this priority** : Renforce la posture de sécurité de l'authentification existante (déjà en JWT) sans la remplacer. Nécessaire pour respecter les bonnes pratiques OWASP et préparer une éventuelle conformité plus stricte (SOC 2, ISO 27001).

**Independent Test** : Se connecter, capturer le refresh token initial (RT1), appeler `POST /auth/refresh` pour obtenir RT2, puis tenter à nouveau d'utiliser RT1 ; vérifier qu'il est rejeté (sauf dans la fenêtre de grâce de 5 secondes où il est accepté avec une alerte journalisée). Appeler ensuite `POST /auth/logout` et vérifier qu'aucun refresh token (RT2 inclus) n'est plus utilisable.

**Acceptance Scenarios** :

1. **Given** un utilisateur connecté avec un refresh token RT1, **When** il appelle `POST /auth/refresh` avec RT1, **Then** un nouveau refresh token RT2 est émis, RT1 est marqué `revoked_at` dans la table `refresh_tokens` et son champ `replaced_by_jti` pointe vers le JTI de RT2.
2. **Given** RT1 a été révoqué il y a moins de 5 secondes au profit de RT2, **When** un appel `POST /auth/refresh` est fait avec RT1 (cas multi-onglets), **Then** RT2 est retourné une seconde fois et un événement d'alerte est journalisé (`grace_window_reuse`).
3. **Given** RT1 a été révoqué il y a plus de 5 secondes, **When** un appel `POST /auth/refresh` est fait avec RT1, **Then** la requête retourne 401 et un événement `refresh_token_replay` est journalisé.
4. **Given** un utilisateur connecté avec plusieurs refresh tokens valides (multi-appareils), **When** il appelle `POST /auth/logout`, **Then** tous ses refresh tokens sont marqués `revoked_at = now()` et toute tentative ultérieure de refresh retourne 401.
5. **Given** la configuration de durée d'access token, **When** un utilisateur se connecte, **Then** son access token expire après 1440 minutes (24 heures) et non plus après 480 minutes (8 heures).

---

### Edge Cases

- **Migration des utilisateurs existants sans `company_name`** : si la colonne `users.company_name` est NULL ou vide pour un utilisateur historique, la migration crée un `Account` nommé `default` (ou `Account legacy <user_id>`), associe l'utilisateur, et journalise une anomalie pour audit ultérieur.
- **Backfill `account_id` sur tables métier dont les lignes orphelines** : si une ligne métier référence un `user_id` qui n'existe plus (FK obsolète), la migration journalise l'anomalie et soit (a) supprime la ligne orpheline si elle est en pratique inutile (à valider table par table), soit (b) l'attache à un `Account` `default-orphan` puis émet un avertissement.
- **Variable de session non SET** : si `app.current_account_id` n'est pas définie au moment d'une requête métier (bug applicatif), les policies RLS retournent 0 ligne (comportement « fail-closed »). Aucune fuite ne peut survenir.
- **Admin sans `account_id`** : un Admin (`role = 'ADMIN'`) a `account_id = NULL` et bénéficie de la policy `admin_full_access` qui filtre uniquement sur `current_setting('app.current_role') = 'ADMIN'` ; ses requêtes voient toutes les lignes (en lecture/écriture) selon les routes auxquelles il accède.
- **Invitation expirée ou déjà acceptée** : le formulaire `/register?invite=<token>` détecte l'expiration (TTL 7 jours dépassée) ou la double-utilisation et refuse l'inscription avec un message clair.
- **Account désactivé** : si un `Account` a `is_active = false`, toutes les sessions actives de ses membres sont invalidées (révocation de l'intégralité de leurs refresh tokens), les futures tentatives de connexion retournent HTTP 403 avec un message explicite (« Ce compte est temporairement désactivé »), mais aucune donnée métier n'est supprimée. La réactivation par un Admin restaure l'accès sans perte.
- **Suppression du dernier utilisateur d'un `Account`** : si un PME utilise `DELETE /api/account/users/{id}` pour retirer le dernier membre actif de son compte (typiquement lui-même par erreur), l'opération est refusée (un `Account` doit toujours avoir au moins 1 utilisateur actif).
- **Backfill `company_profiles` avec doublons** : si plusieurs utilisateurs partageaient un même `company_name` et avaient chacun leur propre `company_profile`, le backfill conserve un seul profil (le plus récent) pour l'`Account` correspondant et marque les autres `archived = true` avec journalisation pour audit ; ces archives ne sont pas exposées par l'API.
- **Tentative de promotion auto-élevation** : aucun endpoint API ne permet à un utilisateur PME de devenir Admin (la promotion est uniquement possible via seed/migration). Toute tentative directe sur une mutation `users.role` via API publique est refusée.
- **Nouvelle table métier sans `account_id` introduite par un développeur** : un test CI scanne `backend/app/models/*.py` après chaque PR et lève une alerte si une table considérée « métier » n'a pas `account_id` + RLS policy associée.

## Requirements *(mandatory)*

### Functional Requirements

#### Modèles et données

- **FR-001** : Le système DOIT introduire une entité `Account` représentant un compte PME (collectivité d'utilisateurs sous une même entreprise) avec au minimum les attributs : identifiant unique, nom de l'entreprise, statut actif/inactif, date de création.
- **FR-002** : Le système DOIT étendre l'entité `User` avec un champ `role` à valeurs `PME` ou `ADMIN` (défaut `PME`) et un champ `account_id` qui référence l'`Account` parent.
- **FR-003** : Le système DOIT garantir l'invariant suivant via une contrainte de cohérence : un utilisateur de rôle `PME` a obligatoirement un `account_id` non nul, un utilisateur de rôle `ADMIN` a obligatoirement un `account_id` nul.
- **FR-004** : Le système DOIT introduire une entité `RefreshToken` qui historise les refresh tokens émis (identifiant JTI, utilisateur, dates d'émission/expiration/révocation, lien `replaced_by_jti` vers un éventuel successeur) pour permettre la rotation et l'audit.
- **FR-005** : Le système DOIT ajouter une colonne `account_id` non nulle sur les 14 tables métier suivantes : `company_profiles`, `documents`, `esg_assessments`, `carbon_assessments`, `credit_scores`, `fund_matches`, `fund_applications`, `action_plans`, `action_items`, `reminders`, `conversations`, `messages`, `interactive_questions`, `tool_call_logs`, `reports`. La colonne `user_id` existante DOIT être conservée (qui-a-fait-quoi) en plus de `account_id` (à-qui-cela-appartient).
- **FR-006** : Le système DOIT migrer les données existantes en créant un `Account` par valeur distincte de `users.company_name` puis en liant chaque utilisateur historique à l'`Account` correspondant ; les utilisateurs sans `company_name` sont rattachés à un `Account` `default` et l'anomalie est journalisée.
- **FR-007** : Le système DOIT permettre la création de comptes Admin (rôle `ADMIN`, `account_id` nul) via un mécanisme de seed exécuté en migration ou en script d'amorçage, et NON via un endpoint public.
- **FR-007a** : Le système DOIT garantir une relation 1:1 entre `Account` et `company_profiles` via une contrainte d'unicité sur `company_profiles.account_id`. Les profils dupliqués détectés au backfill sont archivés (`archived = true` ou table d'archive) avec journalisation, le profil le plus récent étant retenu pour l'`Account`.
- **FR-007b** : Le système DOIT supporter la désactivation logicielle d'un `Account` (`is_active = false`). Cette désactivation invalide toutes les sessions actives des membres (révocation des refresh tokens), refuse les futures tentatives de connexion (HTTP 403 avec message explicite), mais ne supprime aucune donnée métier ; la réactivation est possible par un Admin et restaure l'accès intégral sans perte.

#### Isolation et sécurité multi-tenant

- **FR-008** : Le système DOIT activer la Row-Level Security PostgreSQL (`ENABLE ROW LEVEL SECURITY` ET `FORCE ROW LEVEL SECURITY` pour appliquer aux propriétaires de tables aussi) sur chacune des 14 tables métier listées en FR-005, avec deux policies au minimum : (a) une policy d'accès PME limitant les opérations aux lignes dont `account_id` correspond à une variable de session courante, (b) une policy d'accès Admin autorisant toutes les lignes lorsqu'une variable de session indique le rôle Admin. En MVP, les policies sont appliquées via le rôle PostgreSQL existant utilisé par le `database_url` applicatif (pas de rôle séparé `application_user` introduit en F02).
- **FR-009** : Le système DOIT, à chaque requête authentifiée, positionner sur la connexion de base de données les variables de session qui identifient l'utilisateur courant (compte d'appartenance et rôle), de sorte que les policies RLS s'appliquent automatiquement à toutes les requêtes ORM ou SQL exécutées dans la transaction.
- **FR-010** : Le système DOIT garantir que, en l'absence des variables de session attendues (cas d'erreur applicative), les policies RLS bloquent l'accès aux données plutôt que de retourner des lignes (« fail-closed »).
- **FR-011** : Le système DOIT être robuste face à un service applicatif qui omet un filtre `WHERE account_id = ...` : la base de données seule garantit l'isolation et aucune fuite ne peut survenir même en cas de bug logique au niveau service.

#### Authentification et sessions

- **FR-012** : Le système DOIT prolonger la durée de vie de l'access token JWT à 24 heures (1440 minutes) au lieu de la valeur actuelle de 8 heures (480 minutes).
- **FR-013** : Le système DOIT, à chaque appel `POST /auth/refresh`, révoquer le refresh token utilisé en lui assignant une date `revoked_at` et un `replaced_by_jti` pointant vers le nouveau refresh token émis (rotation).
- **FR-014** : Le système DOIT tolérer la réutilisation d'un refresh token déjà révoqué pendant une fenêtre de grâce de 5 secondes (multi-onglets), retourner alors le refresh token successeur déjà émis (et non un nouveau) et journaliser un événement d'alerte `grace_window_reuse`.
- **FR-015** : Le système DOIT rejeter (HTTP 401) toute réutilisation d'un refresh token révoqué au-delà de la fenêtre de grâce et journaliser un événement `refresh_token_replay`.
- **FR-016** : Le système DOIT exposer un endpoint `POST /auth/logout` qui révoque l'intégralité des refresh tokens valides de l'utilisateur courant.

#### Routes et permissions

- **FR-017** : Le système DOIT exposer un routeur applicatif `/api/admin/*` dont l'accès est strictement réservé aux utilisateurs `role = 'ADMIN'` ; toute requête d'un utilisateur PME retourne HTTP 403.
- **FR-018** : Le système DOIT, en F02, fournir un endpoint minimal `GET /api/admin/health` qui retourne 200 si l'appelant est Admin et 403 sinon (squelette préparant F09).
- **FR-019** : Le système DOIT supprimer la whitelist d'emails statique présente dans `backend/app/modules/financing/router.py:118` et remplacer la protection par la dépendance `get_current_admin` réutilisable.
- **FR-020** : Le système DOIT exposer une dépendance `get_current_admin` réutilisable à monter sur tout endpoint réservé à l'équipe Mefali.

#### Multi-utilisateurs PME et invitations

- **FR-021** : Le système DOIT permettre à un utilisateur PME d'inviter un collaborateur via un endpoint d'invitation, qui génère un token d'invitation à durée de vie limitée (par défaut 7 jours, configurable) et déclenche la livraison via une interface `EmailDeliveryService` ; en MVP F02, l'unique implémentation est `LoggingEmailDelivery` (sujet, corps et lien `/register?invite=<token>` journalisés sur stdout en niveau INFO) tandis que l'invitation est inscrite en BDD dans `account_invitations`.
- **FR-022** : Le système DOIT permettre à un utilisateur invité d'accepter une invitation en s'inscrivant via le lien reçu, opération qui crée un nouvel utilisateur rattaché à l'`Account` de l'invitant avec `role = 'PME'`.
- **FR-023** : Le système DOIT exposer un endpoint pour lister les utilisateurs d'un `Account` (collaborateurs et invitations en cours) et un endpoint pour retirer un collaborateur de l'`Account`.
- **FR-024** : Le système DOIT garantir que tous les membres d'un même `Account` ont des droits équivalents (pas de hiérarchie Owner/Member/Viewer en MVP).
- **FR-025** : Le système DOIT empêcher la suppression du dernier utilisateur actif d'un `Account` (un `Account` doit toujours conserver au moins un membre actif).

#### Frontend et expérience utilisateur

- **FR-026** : Le système DOIT exposer côté frontend un indicateur `isAdmin` calculé à partir du rôle de l'utilisateur courant, utilisable dans les composants pour afficher/masquer des éléments d'interface.
- **FR-027** : Le système DOIT fournir un middleware Nuxt `admin` (non global) qui, sur les pages `/admin/*`, redirige les utilisateurs non-Admin vers `/dashboard` ou affiche une page 403.
- **FR-028** : Le système DOIT fournir un layout dédié `admin` avec une sidebar admin (entrées catalogue, sources, comptes PME, métriques, audit log à terme), un header avec un badge persistant « Mode Admin », et une couleur d'accent rouge/orange différente du thème PME pour éviter toute confusion contextuelle.
- **FR-029** : Le système DOIT fournir un composant frontend `RoleBadge` réutilisable pour afficher le rôle d'un utilisateur de manière cohérente.
- **FR-030** : Le système DOIT enrichir les pages `login` et `register` pour gérer le flux d'invitation : si un paramètre `invite=<token>` est présent dans l'URL, l'inscription est associée à cet `Account` et n'autorise pas la création d'un nouvel `Account`.
- **FR-031** : Le système DOIT fournir une page de gestion d'équipe accessible par les utilisateurs PME, permettant d'inviter, lister et retirer des collaborateurs.
- **FR-032** : Le système DOIT respecter le mode sombre obligatoire (variantes `dark:` Tailwind) sur tous les nouveaux composants et pages introduits par F02.

#### Documentation et garde-fous

- **FR-033** : Le système DOIT fournir une documentation `docs/auth-and-multitenant.md` couvrant le modèle de menaces, la stratégie RLS, la rotation des refresh tokens, et les conventions à suivre pour ajouter une nouvelle table métier.
- **FR-034** : Le système DOIT inclure un test d'intégration continue qui inspecte la déclaration des tables métier et alerte si une nouvelle table métier est introduite sans colonne `account_id` ni policy RLS.

### Key Entities

- **Account** : compte PME représentant une entreprise cliente. Attributs principaux : identifiant unique, nom de l'entreprise, statut actif/inactif (désactivation logicielle), date de création. Relations : un `Account` peut contenir N `User` (rôle PME) et possède exactement 0 ou 1 `CompanyProfile` (relation 1:1 avec contrainte d'unicité sur `company_profiles.account_id`). Un `Account` est référencé par toutes les lignes des 14 tables métier listées en FR-005 via la colonne `account_id`.
- **User (étendu)** : utilisateur de la plateforme. Attributs ajoutés : `role` (PME ou ADMIN), `account_id` (référence à un `Account` ou nul si Admin). Conserve les attributs existants (email, mot de passe haché, nom complet, nom de l'entreprise legacy, statut actif).
- **RefreshToken** : enregistrement audit-friendly d'un refresh token JWT émis. Attributs principaux : identifiant JTI unique, utilisateur émetteur, date d'émission, date d'expiration, date de révocation éventuelle, identifiant `replaced_by_jti` du successeur en cas de rotation. Relations : un `User` peut avoir N `RefreshToken` (multi-appareils, historique de rotations).
- **AccountInvitation** : invitation envoyée par un PME à un futur collaborateur. Attributs principaux : identifiant, `Account` cible, email destinataire, token unique (haché en BDD), date d'expiration (par défaut +7 jours par rapport à la création, configurable), statut (`pending`, `accepted`, `expired`, `revoked`), date d'acceptation éventuelle, identifiant du `User` invitant. Relations : référence un `Account` et, après acceptation, le `User` créé. Tous les tokens expirés sont automatiquement basculés au statut `expired` par un job de nettoyage périodique (scope F02) ou à la première tentative d'utilisation après TTL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Aucune requête métier n'est en mesure de retourner une ligne appartenant à un autre `Account` que celui de l'utilisateur courant, même si un service applicatif omet volontairement un filtre par compte (vérifié par tests d'isolation automatisés exécutés dans la CI).
- **SC-002** : 100 % des 14 tables métier listées disposent d'une colonne `account_id` non nulle et de policies RLS actives, vérifié par un test CI qui scanne les modèles applicatifs et l'introspection de la base.
- **SC-003** : Un utilisateur PME tentant d'accéder à `/api/admin/*` reçoit une réponse 403 dans 100 % des cas, et un utilisateur Admin reçoit 200 dans 100 % des cas (vérifié par tests E2E).
- **SC-004** : La whitelist d'emails statique est totalement supprimée du code source (vérifié par recherche `grep "admin@esg-mefali.com\|admin@mefali.org"` qui doit retourner 0 occurrence en zone applicative).
- **SC-005** : 100 % des refresh tokens utilisés sont révoqués automatiquement après usage dans le délai d'une seconde (vérifié par test d'intégration qui mesure l'état `revoked_at` après un appel refresh).
- **SC-006** : Le délai d'expiration de l'access token est exactement 1440 minutes (24 heures), confirmé par décodage du JWT émis lors de la connexion.
- **SC-007** : 100 % des invitations acceptées rattachent le nouvel utilisateur à l'`Account` de l'invitant et lui donnent un accès partagé identique aux données existantes (vérifié par test E2E du flux complet invite → register → access partagé).
- **SC-008** : La couverture de tests sur le périmètre F02 (modèles `Account`/`RefreshToken`, dépendances `get_current_user`/`get_current_admin`, flux invitation, isolation RLS, rotation refresh token) atteint au minimum 80 %.
- **SC-009** : Aucune dégradation de performance supérieure à 20 % n'est constatée sur les 5 endpoints les plus chauds (chat, dashboard, applications/list, conversations/list, documents/list) avant/après l'activation du RLS, mesurée par benchmark automatique en CI.
- **SC-010** : 100 % des nouveaux composants/pages frontend introduits par F02 incluent les variantes dark mode Tailwind (vérifié par revue manuelle de la PR).
- **SC-011** : La documentation `docs/auth-and-multitenant.md` est livrée et couvre les sections obligatoires : modèle de menaces, mécanisme RLS, rotation refresh token, ajout d'une nouvelle table métier (procédure pas-à-pas).
- **SC-012** : Un test E2E Playwright vérifie de bout en bout que deux PME créées en parallèle ne voient jamais les données l'une de l'autre, et qu'un utilisateur Admin créé manuellement accède aux pages `/admin/*` tandis qu'un utilisateur PME en est redirigé.
- **SC-013** : 100 % des tokens d'invitation expirent automatiquement après 7 jours et l'expiration est testée par un test d'intégration qui simule l'écoulement du temps.
- **SC-014** : 100 % des envois d'email d'invitation produisent une trace identifiable dans les logs serveur en niveau INFO (vérifié par capture des logs en test) tant que le service réel n'est pas branché.
- **SC-015** : La désactivation d'un `Account` invalide en moins de 1 seconde toutes les sessions actives de ses membres (vérifié par test d'intégration : `is_active = false` puis tentative de refresh → HTTP 401).

## Assumptions

- **A1** : L'authentification existante repose sur JWT (access token + refresh token) avec FastAPI ; F02 étend ce mécanisme et ne le remplace pas. La stack JWT déjà en place reste la base.
- **A2** : Les refresh tokens révoqués sont stockés dans la base de données PostgreSQL existante (table `refresh_tokens`), pas dans Redis ou un autre cache externe (cohérent avec la décision MVP « Redis post-MVP » dans le projet).
- **A3** : Le backfill de l'`account_id` sur les tables métier suit la règle « un `Account` par valeur distincte de `users.company_name` » ; les utilisateurs sans `company_name` sont rattachés à un `Account` `default` créé pour la circonstance et l'anomalie est journalisée pour traitement ultérieur.
- **A4** : En MVP, tous les membres d'un même `Account` ont des droits équivalents (pas de hiérarchie Owner/Member/Viewer). La granularité est repoussée en post-MVP.
- **A5** : La couleur d'accent du back-office Admin (rouge/orange) sera ajoutée à la configuration Tailwind dans `frontend/app/assets/css/main.css` (ou équivalent), en prolongeant le thème dark/light existant.
- **A6** : L'envoi des emails d'invitation est, en MVP F02, simulé via une journalisation côté serveur (implémentation `LoggingEmailDelivery` derrière l'interface `EmailDeliveryService`). Le branchement sur un service d'emailing réel (SendGrid, AWS SES, ou autre) est hors scope F02 et se fera par swap d'implémentation sans modification d'appelants. La TTL des tokens d'invitation est fixée par défaut à 7 jours, configurable via une variable de configuration `INVITE_TOKEN_TTL_DAYS`.
- **A7** : Aucun framework Redis ou message broker n'est introduit par F02 ; toutes les opérations restent synchrones via PostgreSQL et FastAPI.
- **A8** : F02 introduit la migration Alembic numérotée `019_multitenant_and_roles.py` (la séquence locale fait passer de `018` à `019` ; en cas de conflit avec une autre feature en flight, la migration sera renumérotée par l'orchestrateur).
- **A9** : Toute mutation `users.role` est effectuée via migration ou script de seed, pas via une route publique ; aucune logique d'auto-promotion par utilisateur n'est introduite.
- **A10** : Les tests E2E sont écrits en Playwright (`frontend/tests/e2e/F02-multitenant-roles-rls.spec.ts`) conformément à l'invariant projet « tests E2E Playwright exécutables ».
- **A11** : F02 est PRÉREQUIS pour F03 (audit log), F04 (versioning + Money typed), F05 (RGPD consents), F06 (entité projet vert), F09 (back-office admin) — donc la solidité de l'isolation et la qualité du modèle priment sur la rapidité de livraison.

## Dependencies

- **Aucune dépendance fonctionnelle bloquante** : F02 est une feature de fondation. Néanmoins, les éléments de stack ci-dessous sont prérequis matériels :
  - PostgreSQL 16 avec capacité d'activer `ROW LEVEL SECURITY` sur les tables (toutes les versions ≥ 9.5 supportent).
  - Possibilité d'exécuter `SET LOCAL` sur les variables de session (`app.current_account_id`, `app.current_role`) — natif PostgreSQL.
  - Alembic configuré (déjà présent : 18 migrations existantes dans `backend/alembic/versions/`).
  - Mécanisme JWT existant (`backend/app/core/security.py`, `backend/app/api/auth.py`).

- **Features dépendantes en aval** : F03, F04, F05, F06, F09, F19, F20, F23, F24 (selon `.cc-deps.json`).
