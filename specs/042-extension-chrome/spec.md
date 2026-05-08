# Feature Specification: Extension Chrome MV3 — MVP P1 (F24)

**Feature Branch**: `feat/F24-extension-chrome`
**Created**: 2026-05-08
**Status**: Draft
**Input**: F24 — Extension Chrome MV3 (Module 8) — Scope strict MVP P1 : squelette MV3 + détection d'offres + popup auth + dashboard read-only candidatures.

## Clarifications

### Session 2026-05-08

- Q: Comment matérialiser le scope d'authentification dédié à l'extension côté backend ? → A: Ajouter une colonne `scope` (enum `web` | `extension`) sur la table `refresh_tokens` (F02), aucune nouvelle table.
- Q: Durée de vie du token long-lived dédié extension ? → A: 30 jours, rotatif au refresh, révocable côté serveur.
- Q: Borne du cache de détection côté extension ? → A: Cache LRU borné à 200 entrées, TTL 1 heure par URL exacte.
- Q: Seuil minimal de confiance pour afficher le bandeau ? → A: 0.8 (un pattern matché simple = 1.0, pas de matching probabiliste en MVP).
- Q: Forme de l'endpoint de détection ? → A: `POST /api/extension/v1/detect` avec body `{url: string}` retournant `{offer_id, offer_name, source_id?, confidence}` ou 204 si aucun match.
- Q: Contenu du profile-snapshot retourné à l'extension ? → A: secteur, pays, 3 derniers projets actifs (id, nom, statut).
- Q: Pagination de la liste des candidatures actives ? → A: Limite 50, tri par date de mise à jour décroissante, pas de pagination en MVP.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Authentification depuis l'extension (Priority: P1)

Une PME installe l'extension Chrome ESG Mefali, ouvre la popup, saisit son email/mot de passe (les mêmes que ceux de l'application web) et obtient une session active dans l'extension permettant aux fonctionnalités suivantes (détection, dashboard) de fonctionner.

**Why this priority** : sans authentification, aucune autre fonctionnalité de l'extension n'est utilisable. Brique de socle indispensable.

**Independent Test** : installer l'extension en mode développeur, ouvrir la popup, se connecter avec un compte de test ; vérifier que le statut « connecté » est affiché et persiste après fermeture/réouverture de la popup tant que la session navigateur est active.

**Acceptance Scenarios** :

1. **Given** un utilisateur PME possédant un compte sur l'application web et l'extension installée, **When** il ouvre la popup et saisit ses identifiants valides, **Then** il voit l'écran « connecté » avec son nom et son rôle (PME).
2. **Given** un utilisateur saisissant des identifiants invalides, **When** il valide le formulaire, **Then** il voit un message d'erreur en français sans fuite d'information sensible.
3. **Given** une session active, **When** l'utilisateur ferme et rouvre Chrome, **Then** il doit se reconnecter (token éphémère, session-scope).
4. **Given** un utilisateur non authentifié, **When** il ouvre la popup, **Then** il voit un écran « Connectez-vous d'abord » avec un lien vers l'application web et le formulaire de login intégré.

---

### User Story 2 — Détection automatique d'une offre sur un site externe (Priority: P1)

Une PME authentifiée navigue sur un site partenaire (ex. `sunref.boad.org`, `greenclimate.fund`) ; l'extension détecte que l'URL correspond à une offre cataloguée et affiche un bandeau discret « Offre détectée — voir le détail dans ESG Mefali » avec un lien profond vers la page `/financing/offers/[id]` de l'application principale.

**Why this priority** : c'est la valeur métier #1 de l'extension. Le scope MVP est read-only (pas de pré-remplissage, pas de création automatique de candidature) ; l'objectif est de prouver le matching URL→Offer et d'amener l'utilisateur dans l'application web pour la suite.

**Independent Test** : avec un compte connecté, naviguer sur les 5 URL prioritaires seedées (BOAD, GCF, SUNREF Ecobank, PNUD Africa, AFD) ; observer l'apparition du bandeau dans les 2 secondes suivant le chargement de la page.

**Acceptance Scenarios** :

1. **Given** un utilisateur connecté visitant une URL correspondant à un `url_pattern` d'une offre publiée, **When** la page se charge, **Then** un bandeau s'affiche en haut de la page avec le nom de l'offre et un bouton « Voir dans ESG Mefali » qui ouvre `/financing/offers/[id]` dans un nouvel onglet.
2. **Given** une offre détectée disposant d'une source de catalogage F01, **When** le bandeau est affiché, **Then** un libellé cliquable « Source : [publisher] » est visible et ouvre la fiche source dans l'application.
3. **Given** un utilisateur naviguant sur une URL non cataloguée, **When** la page se charge, **Then** aucun bandeau n'est affiché et aucune requête réseau de matching n'est déclenchée plus de 1 fois pour cette URL durant la session.
4. **Given** un utilisateur non authentifié, **When** il visite une URL d'une offre cataloguée, **Then** aucun bandeau n'est affiché (l'extension reste silencieuse).
5. **Given** un bandeau déjà affiché et fermé manuellement par l'utilisateur, **When** il rafraîchit la page, **Then** le bandeau ne réapparaît pas dans la même session de navigation.

---

### User Story 3 — Dashboard read-only des candidatures actives (Priority: P1)

Une PME authentifiée ouvre la popup et voit la liste de ses candidatures en cours (statut différent de `rejected`/`approved`/`disbursed`/`cancelled`) avec, pour chacune, le nom de l'offre, le statut, et un lien profond vers la fiche candidature dans l'application web.

**Why this priority** : permet à l'utilisateur de garder un œil sur ses dossiers sans ouvrir l'application web, et de revenir rapidement aux candidatures à compléter. Read-only en MVP — aucune action de modification depuis l'extension.

**Independent Test** : avec un compte ayant 2-3 candidatures à différents statuts, ouvrir la popup ; vérifier que la liste s'affiche, que les libellés français des statuts sont corrects, et que cliquer sur une ligne ouvre la fiche dans un nouvel onglet.

**Acceptance Scenarios** :

1. **Given** une PME connectée avec N candidatures actives, **When** elle ouvre la popup, **Then** elle voit la liste paginée (max 10 visibles) avec nom de l'offre, statut localisé en français, date de dernière mise à jour.
2. **Given** une PME sans candidature active, **When** elle ouvre la popup, **Then** elle voit un état vide « Aucune candidature en cours » avec un lien « Découvrir les financements » vers `/financing/offers`.
3. **Given** une candidature listée, **When** l'utilisateur clique dessus, **Then** un nouvel onglet s'ouvre sur la fiche candidature de l'application web.

---

### User Story 4 — Onboarding utilisateur non authentifié (Priority: P1)

Un utilisateur ouvre la popup pour la première fois sans être connecté ; il voit un écran clair lui expliquant le besoin de se connecter avec un compte ESG Mefali et un lien direct vers l'inscription dans l'application web.

**Why this priority** : empêche l'extension de paraître cassée pour un utilisateur sans compte ; sécurise toutes les autres fonctionnalités derrière l'authentification.

**Independent Test** : installer l'extension sur un profil Chrome neuf, ouvrir la popup ; vérifier l'écran d'onboarding et la présence du lien d'inscription.

**Acceptance Scenarios** :

1. **Given** un utilisateur sans token en stockage de session, **When** il ouvre la popup, **Then** il voit un message « Connectez-vous d'abord » et un formulaire de login intégré.
2. **Given** ce même écran, **When** il clique sur « Pas encore de compte ? », **Then** un onglet s'ouvre sur la page d'inscription de l'application web.

---

### Edge Cases

- L'application web est inaccessible (réseau coupé ou backend down) : la popup affiche « Service temporairement indisponible » et la détection d'offre est silencieusement désactivée (aucune erreur visible sur les sites externes).
- L'URL visitée correspond à plusieurs `url_patterns` (ex. un côté fonds et un autre côté intermédiaire) : l'extension affiche au plus un bandeau, en privilégiant l'offre directe (fonds + intermédiaire singleton DIRECT) ; sinon, première correspondance déterministe par identifiant croissant.
- Le token long-lived expire pendant la session : la prochaine requête API échoue ; l'extension efface le token, ferme tout bandeau actif, et l'utilisateur retrouve l'écran « Connectez-vous » à la prochaine ouverture de popup.
- L'utilisateur se déconnecte depuis l'application web : le token reste valide jusqu'à expiration côté backend ; l'extension respecte la révocation lors de la prochaine requête (401 → effacement local).
- Le site visité a une CSP très stricte qui empêche l'injection du bandeau : le contenu est silencieusement ignoré, aucune erreur n'est levée. Une trace console (debug) signale l'échec.
- L'utilisateur visite plus de 100 URLs distinctes en une session : le cache local de détection est borné (LRU max 200 entrées) pour éviter la fuite mémoire.

## Requirements *(mandatory)*

### Functional Requirements

**Authentification & session (US1, US4)**

- **FR-001** : L'extension DOIT proposer un formulaire de connexion (email + mot de passe) dans la popup pour les utilisateurs non authentifiés.
- **FR-002** : L'extension DOIT échanger les identifiants contre un token long-lived dédié extension (TTL 30 jours, scope `extension` distinct du scope `web`) via l'API backend, sans dupliquer la logique d'authentification existante.
- **FR-003** : Le token DOIT être stocké uniquement dans un emplacement éphémère lié à la session du navigateur (effacé à la fermeture de Chrome).
- **FR-004** : Une déconnexion explicite (bouton « Se déconnecter ») DOIT effacer le token local et révoquer côté serveur.
- **FR-005** : Toute requête API émise par l'extension DOIT inclure le token bearer en header `Authorization`.
- **FR-006** : En cas de réponse 401 d'une API, l'extension DOIT effacer le token local et basculer en état « non authentifié ».

**Détection d'offres (US2)**

- **FR-007** : L'extension DOIT, pour chaque URL visitée, interroger l'API backend afin de déterminer si l'URL correspond à une offre cataloguée (matching côté serveur via les `url_patterns` saisis sur Fund et Intermediary).
- **FR-008** : Le résultat de matching DOIT être mis en cache local (LRU borné à 200 entrées, par URL exacte, TTL 1 heure) pour éviter de réinterroger l'API à chaque rechargement de la même page.
- **FR-009** : L'extension NE DOIT injecter le bandeau QUE si l'utilisateur est authentifié, l'offre est publiée, et le matching renvoie un score de confiance ≥ 0.8.
- **FR-010** : Le bandeau DOIT afficher le nom de l'offre, un bouton « Voir dans ESG Mefali » avec lien profond, un bouton de fermeture, et — si la source F01 est disponible — un lien cliquable vers la fiche source.
- **FR-011** : Une fois fermé manuellement, le bandeau ne DOIT PAS réapparaître pour la même URL durant la session navigateur courante.
- **FR-012** : Aucune donnée du DOM des sites visités ne DOIT être collectée ou transmise à l'API en MVP (matching strictement basé sur l'URL).

**Dashboard candidatures (US3)**

- **FR-013** : La popup DOIT, lorsque l'utilisateur est authentifié, afficher la liste de ses candidatures actives (statuts hors `approved`, `rejected`, `disbursed`, `cancelled`), tri par date de mise à jour décroissante, limite 50 entrées, sans pagination MVP.
- **FR-014** : La liste DOIT être lue en read-only ; aucune action de modification (création, mise à jour, suppression) n'est exposée depuis l'extension en MVP.
- **FR-015** : Les libellés de statuts DOIVENT être affichés en français.
- **FR-016** : Cliquer sur une candidature DOIT ouvrir la fiche correspondante dans l'application web dans un nouvel onglet.

**Backend & API**

- **FR-017** : Le backend DOIT exposer un sous-routeur dédié `/api/extension/v1/*` regroupant 4 endpoints MVP : `auth/exchange`, `me/profile-snapshot`, `detect`, `applications/active`.
- **FR-018** : L'endpoint `POST /api/extension/v1/detect` DOIT accepter un body `{url: string}` et renvoyer `{offer_id, offer_name, source_id?, confidence}` en cas de match (HTTP 200), ou 204 (No Content) si aucun pattern ne matche.
- **FR-019** : Tous les endpoints `/api/extension/v1/*` (sauf `auth/exchange`) DOIVENT requérir un token bearer extension valide et appliquer l'isolation multi-tenant F02 (RLS PostgreSQL).
- **FR-020** : Le backend DOIT autoriser les origines `chrome-extension://*` dans sa configuration CORS.
- **FR-021** : Le matching d'URL DOIT être effectué exclusivement côté serveur (l'extension n'embarque aucune liste d'URLs sensibles).

**Catalogue & seed**

- **FR-022** : Les entités `Fund` et `Intermediary` DOIVENT pouvoir stocker une liste de patterns d'URL (chacun composé d'une expression régulière et d'un scope `homepage`/`submission_portal`).
- **FR-023** : Une migration de référence DOIT seeder au minimum 5 patterns prioritaires couvrant BOAD, GCF, SUNREF Ecobank, PNUD Africa et AFD.

**Observabilité & sécurité**

- **FR-024** : L'extension NE DOIT PAS exécuter de code distant (pas d'`eval`, pas de chargement de scripts depuis des URLs externes) — conformité Manifest V3 stricte.
- **FR-025** : Le bandeau injecté DOIT échapper toute donnée provenant de l'API avant insertion dans le DOM (anti-XSS).
- **FR-026** : Aucun secret (clé API, mot de passe) ne DOIT être embarqué dans le code de l'extension distribuée.
- **FR-027** : Toutes les requêtes API initiées par l'extension DOIVENT être journalisées côté serveur dans le journal d'audit F03 avec une source de modification distincte (`extension`).

**Internationalisation (MVP)**

- **FR-028** : L'interface utilisateur de l'extension (popup + bandeau) DOIT être disponible en français en MVP. La structure i18n DOIT être en place pour permettre l'ajout d'autres langues sans refactor majeur.

### Key Entities

- **Offer (existante, F07)** : couple Fonds × Intermédiaire avec score de matching ; consommée en lecture seule.
- **Fund (existante, F07)** : enrichie d'une nouvelle propriété `url_patterns` (liste de regex avec scope).
- **Intermediary (existante, F07)** : enrichie d'une propriété `url_patterns` similaire.
- **RefreshToken (existante, F02)** : enrichie d'une colonne `scope` (enum `web` | `extension`, défaut `web`) pour distinguer les sessions et appliquer des TTL différenciés (web : 30 j rotatif F02 ; extension : 30 j rotatif identique en MVP, scope distinct pour révocation ciblée future).
- **AuditLog (existante, F03)** : nouvelle valeur de champ `source_of_change` = `extension` pour tracer l'origine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Sur les 5 sites prioritaires seedés, le bandeau « Offre détectée » s'affiche dans 100 % des cas en moins de 2 secondes après le chargement complet de la page (cache chaud).
- **SC-002** : Le taux de faux positifs (bandeau affiché sur une URL non pertinente) est inférieur à 1 % sur un échantillon manuel de 50 URLs hors catalogue.
- **SC-003** : 95 % des connexions depuis la popup aboutissent en moins de 1,5 seconde sur connexion 4G typique.
- **SC-004** : 100 % des requêtes API émises par l'extension transitent par HTTPS avec un token bearer valide ; aucune fuite de credentials ne survient en cas d'inspection des outils développeur.
- **SC-005** : L'extension passe la validation manuelle des règles Chrome Web Store (Manifest V3, CSP, permissions justifiées) sans avertissement bloquant — vérifié via outil de pré-validation, soumission effective hors-scope MVP.
- **SC-006** : Aucune régression sur les tests automatisés existants du backend (≥ 2693 tests verts maintenus).
- **SC-007** : La couverture de tests unitaires sur la logique métier de l'extension (client API, matcher de détection, gestion du token) atteint ≥ 80 %.
- **SC-008** : La couverture de tests sur le module backend dédié à l'extension atteint ≥ 80 %.
- **SC-009** : Un développeur peut charger l'extension en mode développeur et reproduire les 4 user stories sans intervention manuelle hors-extension en moins de 10 minutes (suivant la documentation `docs/extension-chrome.md`).
- **SC-010** : La migration Alembic 042 effectue un round-trip `up/down/up` sans erreur sur PostgreSQL.

## Assumptions

- **A1** : Les utilisateurs cibles utilisent Chrome (ou un navigateur basé Chromium compatible Manifest V3) ; Firefox/Edge/Safari hors scope MVP.
- **A2** : L'authentification existante de l'application web (email/mot de passe + refresh tokens) est suffisamment stable pour être réutilisée sans modification fondamentale.
- **A3** : Les `url_patterns` saisis manuellement (par seed pour le MVP, par interface admin en post-MVP) couvrent les cas réels de navigation des PME bénéficiaires.
- **A4** : Le scoring de confiance de matching peut être calculé simplement (un pattern matché = score 1.0, plusieurs patterns = score le plus haut, fallback sur `null`).
- **A5** : Aucune information personnelle n'est extraite du DOM des sites visités en MVP — la valeur produit vient de la corrélation URL ↔ catalogue interne.
- **A6** : La langue d'interface utilisateur de l'extension est le français exclusivement en MVP ; l'anglais est différé.
- **A7** : L'utilisateur a accepté les CGU de l'application web et consent implicitement, en installant l'extension, à ce que le backend reçoive les URLs visitées matchant le catalogue (transparence affichée dans la popup).

## Dependencies

- F02 — Multi-tenant + auth bearer + refresh_tokens (livré)
- F06 — Project (livré, utilisé par profile-snapshot)
- F07 — Offer + Fund + Intermediary (livré, à enrichir avec `url_patterns`)
- F09 — Back-office admin (saisie des `url_patterns` post-MVP, MVP via SQL/seed)
- F01 — Sources et sourçage (utilisé pour SourceLink dans le bandeau)
- F03 — Audit log (extension comme nouvelle source de modification)

## Out of scope (P2/P3/P4 — Follow-up tickets séparés)

- Pré-remplissage automatique de formulaires sur les sites externes
- Panneau latéral de guidage pas-à-pas (Chrome `sidePanel`)
- Création automatique de candidatures depuis l'extension
- Notifications push J-30/J-7/J-1 via `chrome.alarms` + `chrome.notifications`
- Recommandations d'offres multi-référentiels (basées F13)
- Multilingue anglais
- Soumission Chrome Web Store (validation publique)
- Email parsing OAuth (Gmail/Outlook) pour mise à jour automatique de statut
- Mode offline avec sync différée (IndexedDB)
- Auto-soumission de formulaires sur les portails fonds
- Support Firefox / Edge / Safari
- Reconnaissance OCR de PDFs téléchargés
