# Feature Specification: F05 — RGPD : Page « Mes Données » + Consentements + Export/Suppression

**Feature Branch**: `feat/F05-rgpd-mes-donnees-consents` (alias SpecKit `027-rgpd-mes-donnees-consents`)
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F05 — RGPD : Page « Mes Données » + Consentements + Export/Suppression. Cadre légal RGPD européen + loi ivoirienne 2013-450 + règlement UEMOA n°20/2010/CM/UEMOA. Permettre aux PME utilisatrices d'exercer les droits Art. 15 (accès), Art. 17 (effacement), Art. 20 (portabilité) et de donner/révoquer des consentements granulaires. Page `/mes-donnees` avec inventaire, export JSON, 7 consentements, suppression compte J+30. Politique publique `/legal/privacy`. Helper `require_consent` pour les services dépendants. Dépendances : F02 (multi-tenant) + F03 (audit log)."

## Clarifications

### Session 2026-05-07

- Q: Quel est le scope précis de l'enum `consent_type` (granularité finale des 7 valeurs) et leur stratégie d'évolution si une 8ᵉ valeur s'avérait nécessaire post-MVP ? → A: **Enum PostgreSQL natif `consent_type_enum` à 7 valeurs documentées** (`profile_analysis`, `document_analysis_ai`, `mobile_money_analysis`, `photos_ia_analysis`, `public_data_analysis`, `credit_certificate_generation`, `product_communications`) ; ajout d'une 8ᵉ valeur futur via migration Alembic dédiée `ALTER TYPE consent_type_enum ADD VALUE 'xxx'`. La table `consents` n'est jamais reconstruite ; le seed initial des consentements par défaut au moment de la création du compte est géré côté service (pas de trigger BDD).
- Q: Faut-il créer dès F05 une vraie table `data_export_jobs` pour les exports asynchrones, ou se contenter de tracer dans `audit_log` ? → A: **Tracer uniquement dans `audit_log` (F03)** pour le MVP ; un événement `data_export_requested` puis `data_export_ready` avec lien signé en `metadata.url` suffit. Une table dédiée `data_export_jobs` sera introduite **post-MVP** si F19 (cron dispatcher) ou un volume d'exports asynchrones le rend nécessaire (recommandation orchestrateur : différer toute table non strictement requise).
- Q: Stratégie d'anonymisation `audit_log` à la purge — UPDATE en place ou INSERT d'une copie anonymisée + DELETE de l'original ? → A: **UPDATE en place** : `UPDATE audit_log SET user_id = NULL, account_id = NULL WHERE account_id = X` lors de la purge effective. Pas de duplication. Conservation des champs `timestamp`, `entity_type`, `action`, `entity_id` (UUID non-PII), `payload` filtré (suppression des champs PII connus). Avantage : append-only respecté (pas de DELETE), moins coûteux en stockage.
- Q: La page `/legal/privacy` doit-elle être servie par un layout Nuxt « public » distinct (pas de sidebar/menu authentifié) ou par le layout `default` avec une condition ? → A: **Layout `public` distinct** créé dans cette feature s'il n'existe pas déjà (vérifier `frontend/app/layouts/`). Comportement : pas de sidebar, pas de menu authentifié, juste un header simple ESG Mefali + le contenu de la politique + le footer global. Cohérent avec une page « légale » consultable hors auth, sans risque de fuite de données utilisateur.
- Q: Vérification du mot de passe pour la modale de suppression : endpoint dédié ou réutilisation de l'endpoint de login interne ? → A: **Endpoint dédié `POST /api/me/account/verify-password`** (auth requise, body `{password}`, réponse 200/401) appelé en pré-flight depuis la modale, puis `POST /api/me/account/schedule-deletion` (auth requise, body `{password, confirmation_text='SUPPRIMER'}`) qui revérifie le mot de passe. Double validation côté backend pour éviter les attaques par session volée. Rationale : sépare clairement la vérification d'identité forte de l'action critique.
- Q: Gestion de l'export en mode asynchrone : queue dédiée ou tâche Background FastAPI ? → A: **Tâche `BackgroundTasks` FastAPI** pour le MVP (cohérent avec « Queue : Synchrone (Redis + Celery plus tard) » du `CLAUDE.md`). Migration vers Celery/RQ post-MVP en même temps que F19. La file `BackgroundTasks` est mémoire-process : suffisant pour le volume MVP, et le job repart simplement à la prochaine requête utilisateur si le process redémarre (l'`audit_log` capte l'état).
- Q: Test CI scanner `require_consent` — exhaustivité du scan (regex liste figée vs introspection dynamique) ? → A: **Regex sur les fonctions `analyze_*`, `fetch_*_external`, `generate_certificate_*` dans `backend/app/services/`, `backend/app/modules/*/service.py`, `backend/app/graph/tools/*_tools.py`** ; pour chaque fonction matched, le test échoue si le corps ne contient pas la chaîne `require_consent(`. Approche pragmatique, faux positifs traités via une liste d'exclusions explicite documentée dans `tests/security/test_require_consent_coverage.py`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Inventaire et export complet de mes données (Priority: P1)

Une PME utilisatrice se rend sur `/mes-donnees` depuis son menu utilisateur. Elle voit immédiatement un tableau de bord listant toutes les catégories de données stockées la concernant (profil entreprise, projets, candidatures, évaluations ESG, bilans carbone, scores crédit, documents, conversations, messages, attestations, consentements) avec, pour chacune, le nombre de lignes et la date de dernière modification. Elle clique sur « Exporter mes données » et reçoit un fichier ZIP contenant un JSON structuré exhaustif (toutes les tables `account_id`), des liens signés temporaires (24h) vers ses fichiers uploadés, et un `README.md` expliquant la structure.

**Why this priority** : Sans cette story, la plateforme viole immédiatement le droit d'accès (Art. 15 RGPD) et le droit à la portabilité (Art. 20 RGPD) dès la première PME inscrite. C'est la fonctionnalité minimum exigée par la loi pour qu'une PME puisse vérifier ce que la plateforme détient sur elle et récupérer ses données pour les transférer ailleurs. Sans elle, la mise en conformité de l'ensemble de la plateforme est bloquée.

**Independent Test** : Créer un compte PME, remplir le profil, lancer une évaluation ESG, créer un projet, télécharger un document, puis se rendre sur `/mes-donnees`. Vérifier que les compteurs reflètent les données saisies, cliquer sur « Exporter », attendre la génération, télécharger le ZIP et vérifier que le JSON contient bien le profil, le projet, l'évaluation, les métadonnées du document, les conversations, et que le README.md décrit la structure.

**Acceptance Scenarios** :

1. **Given** une PME authentifiée avec profil + 1 évaluation ESG + 1 projet + 1 document uploadé + 1 conversation chat, **When** elle ouvre `/mes-donnees`, **Then** la section Inventaire affiche les compteurs corrects pour chaque catégorie (profil : 1, projets : 1, évaluations : 1, documents : 1, conversations : ≥1, messages : ≥1), avec la date de dernière modification de chaque entité.
2. **Given** la même PME sur `/mes-donnees`, **When** elle clique sur « Exporter mes données en JSON », **Then** un export synchrone ≤ 100 MB est généré, l'utilisateur reçoit un fichier ZIP nommé `esg-mefali-export-{account_id}-{date}.zip` contenant `data.json`, un dossier `documents/` avec liens signés et `README.md`, et l'action est journalisée dans `audit_log` (`entity_type='account'`, `action='data_exported'`).
3. **Given** une PME avec un volume estimé > 100 MB, **When** elle déclenche l'export, **Then** la génération est asynchrone, l'UI affiche « Export en préparation, vous recevrez un email quand il sera prêt », un job arrière-plan génère le fichier, et la PME reçoit un email avec lien temporaire signé valide 7 jours pour télécharger.
4. **Given** une PME demande deux exports successifs en moins de 5 minutes, **When** le second est demandé, **Then** le système réutilise l'export précédent (ou refuse temporairement avec un message explicite « un export récent est encore disponible »), pour éviter la surcharge.

---

### User Story 2 — Consentements granulaires révocables (Priority: P1)

Avant que la plateforme analyse certains traitements sensibles (Mobile Money, photos d'exploitation, données publiques, attestations crédit), la PME doit donner un consentement explicite par usage. Sur `/mes-donnees → Consentements`, elle voit la liste de 7 consentements granulaires avec, pour chacun, son état actuel (accordé/non accordé), la date d'octroi, la version du texte présenté, et un toggle on/off à effet immédiat. Lorsqu'elle révoque un consentement Mobile Money, toute tentative ultérieure d'analyse de ses flux Mobile Money est rejetée avec un message d'erreur explicite et un lien vers la page Consentements.

**Why this priority** : Sans consentements granulaires révocables, la plateforme ne peut **légalement** pas démarrer l'analyse Mobile Money (F18), ni l'analyse photos IA (F18), ni générer d'attestation crédit transmissible (F08) — ce sont les piliers de la valeur métier. La capacité à donner/révoquer en granularité est une obligation RGPD (Art. 7) et le module 5 dépend de cette fondation.

**Independent Test** : Connecter une PME, ouvrir l'onglet Consentements, vérifier que les 7 types s'affichent avec leur valeur par défaut documentée (`profile_analysis=true`, `document_analysis_ai=true`, `mobile_money_analysis=false`, `photos_ia_analysis=false`, `public_data_analysis=false`, `credit_certificate_generation=true`, `product_communications=false`). Activer Mobile Money, vérifier que l'état passe à « Accordé », tenter une analyse Mobile Money via une API stub : l'appel passe. Désactiver Mobile Money, retenter : l'appel renvoie 403 avec un message identifiant le consentement manquant.

**Acceptance Scenarios** :

1. **Given** une PME nouvellement inscrite, **When** elle ouvre `/mes-donnees → Consentements`, **Then** les 7 consentements s'affichent avec les valeurs par défaut documentées, chaque ligne montrant le titre, la description en français, la base légale (`consent` pour les non-essentiels, `contract` pour les essentiels), la version du texte, et l'état du toggle.
2. **Given** un consentement `mobile_money_analysis = false`, **When** la PME active le toggle, **Then** une nouvelle ligne `consents` est insérée avec `granted=true`, `granted_at=now()`, `version='v1.0'`, `metadata={ip, user-agent}`, et un événement audit log `consent_granted` est créé.
3. **Given** un consentement `mobile_money_analysis = true`, **When** la PME désactive le toggle, **Then** la ligne courante est mise à jour avec `revoked_at=now()`, et un événement audit log `consent_revoked` est créé.
4. **Given** un service applicatif appelle `require_consent(account_id, 'mobile_money_analysis')` alors que le consentement est révoqué ou jamais accordé, **When** l'appel est effectué, **Then** le helper lève une `HTTPException(403, "Consentement Mobile Money requis pour cette analyse")` qui se propage au client, sans exécuter le traitement.
5. **Given** une PME avait accordé un consentement v1.0, **When** la plateforme publie une v2.0 du texte, **Then** l'UI affiche un bandeau « Nouvelle version de votre consentement disponible » et l'état passe en « Re-confirmation requise » pour ce type, sans révoquer l'historique précédent.

---

### User Story 3 — Suppression de compte avec délai de grâce 30 jours (Priority: P1)

Une PME décide de quitter la plateforme. Sur `/mes-donnees → Supprimer mon compte`, elle clique sur « Supprimer définitivement ». Une modale de triple confirmation apparaît : (a) liste des conséquences (candidatures annulées, attestations révoquées), (b) saisie du mot de passe, (c) saisie obligatoire du mot « SUPPRIMER » en majuscules. Après validation, le compte passe en état « suppression programmée à J+30 », un email de confirmation est envoyé avec un lien d'annulation, l'utilisateur peut continuer à utiliser le compte mais voit un bandeau de rappel. À J+30, un cron purge effectivement toutes les données du compte sauf l'audit log anonymisé.

**Why this priority** : Sans cette story, la PME ne peut pas exercer son droit à l'effacement (Art. 17 RGPD). Le délai de grâce protège contre les suppressions accidentelles ou par erreur d'authentification compromise. La purge effective différée permet aussi de respecter les obligations légales de conservation (audit log 6 ans, attestations en cours de validité).

**Independent Test** : Créer une PME, remplir des données, déclencher la suppression depuis `/mes-donnees → Supprimer mon compte`. Vérifier que la triple confirmation est exigée, que `accounts.deletion_scheduled_at` est positionnée à J+30, que l'email contient un lien d'annulation valide. Cliquer sur le lien d'annulation : vérifier que `deletion_scheduled_at` revient à NULL. Re-déclencher la suppression, simuler `now() = scheduled_at + 1 jour`, exécuter le cron `purge_scheduled_deletions.py`, vérifier que toutes les données `account_id` ont disparu, que les fichiers `/uploads/{account_id}/` sont supprimés, et que les rows audit_log existent encore mais avec `user_id=NULL`, `account_id=NULL`, autres champs intacts.

**Acceptance Scenarios** :

1. **Given** une PME authentifiée, **When** elle clique sur « Supprimer définitivement mon compte », **Then** une modale de triple confirmation s'affiche listant les conséquences, demandant le mot de passe et la saisie « SUPPRIMER » en majuscules.
2. **Given** la modale de confirmation est complétée correctement, **When** la PME valide, **Then** `accounts.deletion_scheduled_at = now() + 30 days`, un événement audit log `account_deletion_scheduled` est créé, l'utilisateur est redirigé vers `/mes-donnees` avec un bandeau persistant « Suppression programmée le {date}, annulable jusqu'à cette date », et un email de confirmation contenant un lien d'annulation est envoyé à l'adresse du compte.
3. **Given** une suppression programmée, **When** la PME clique sur le lien d'annulation reçu par email (ou utilise le bouton « Annuler la suppression » sur `/mes-donnees`), **Then** `deletion_scheduled_at` redevient NULL, un événement audit log `account_deletion_cancelled` est créé, et un email de confirmation d'annulation est envoyé.
4. **Given** une suppression programmée pour un `deletion_scheduled_at` antérieur à `now()`, **When** le cron `purge_scheduled_deletions.py` s'exécute, **Then** toutes les lignes liées à cet `account_id` sont supprimées en cascade (profil, projets, candidatures, scores, documents, conversations, messages, attestations, consentements), tous les fichiers sous `/uploads/{account_id}/` sont supprimés, les refresh tokens sont révoqués, `accounts.deleted_at = now()` est positionné, l'audit log est anonymisé (`user_id=NULL`, `account_id=NULL`, mais `timestamp`, `entity_type`, `action` conservés), et un email final de confirmation est envoyé.
5. **Given** une PME tente de programmer une suppression avec un mauvais mot de passe, **When** elle valide la modale, **Then** l'API renvoie 401 avec un message « Mot de passe incorrect », aucune mutation n'est faite, et un événement audit log `account_deletion_attempt_failed` est créé.

---

### User Story 4 — Politique de confidentialité publique et consentement à l'inscription (Priority: P2)

Le pied de page global de toute la plateforme expose un lien « Politique de confidentialité ». Cette page `/legal/privacy` est accessible **sans authentification** (layout public) et liste : identité du responsable de traitement, finalités et bases légales par usage, catégories de données, durée de conservation, sous-traitants (OpenRouter, exchangerate-api, hébergeur), transferts hors UE/UEMOA, droits utilisateurs, comment les exercer (lien vers `/mes-donnees` + email `privacy@esg-mefali.com`), date de dernière mise à jour, historique des versions. Sur la page `/register` (inscription), une case à cocher obligatoire « J'ai lu et j'accepte la politique de confidentialité v1.0 » bloque la soumission tant qu'elle n'est pas cochée ; cocher la case insère un événement audit log `privacy_policy_accepted` avec la version.

**Why this priority** : Cette story est P2 car les stories P1 sont prioritaires pour la conformité technique, mais publier une politique de confidentialité est une exigence d'opposabilité légale. Sans politique publiée, les consentements collectés sont fragiles juridiquement et la plateforme reste dans une zone grise réputationnelle. La case à cocher à l'inscription matérialise l'acceptation initiale.

**Independent Test** : Ouvrir un navigateur privé, naviguer sur `https://app/legal/privacy` : la page doit charger sans authentification, contenir les 10 sections requises, afficher la date de dernière mise à jour. Sur `/register`, tenter de s'inscrire sans cocher la case : la soumission est bloquée avec un message visible. Cocher la case et soumettre : l'inscription réussit, un événement `privacy_policy_accepted` est journalisé.

**Acceptance Scenarios** :

1. **Given** un visiteur non authentifié, **When** il navigue sur `/legal/privacy`, **Then** la page se charge sans redirection vers le login, toutes les sections obligatoires sont présentes (responsable, finalités, bases, données, durée, destinataires, transferts, droits, exercice, version), le pied de page de toutes les pages publiques contient un lien vers cette URL.
2. **Given** un utilisateur sur `/register` avec tous les champs remplis sauf la case « J'accepte », **When** il clique sur « S'inscrire », **Then** la soumission est bloquée côté frontend (message accessible via aria-live) et côté backend (validation 422 si l'API est appelée directement), aucun compte n'est créé.
3. **Given** un utilisateur coche la case et s'inscrit, **When** la création réussit, **Then** un événement audit log `privacy_policy_accepted` est inséré avec `metadata={'version': 'v1.0', 'ip', 'user_agent'}`.
4. **Given** la politique évolue de v1.0 à v2.0, **When** un utilisateur existant se connecte, **Then** un bandeau d'information lui indique la nouvelle version et lui propose de la consulter (sans bloquer l'usage), conformément aux usages standard du marché.

---

### User Story 5 — Garde-fou applicatif `require_consent` intégré aux services sensibles (Priority: P2)

Le helper `require_consent(account_id, type)` est exposé comme une dépendance partagée par tous les services backend qui réalisent un traitement non-essentiel. Au minimum, il est intégré comme stub dans les emplacements connus à ce jour : F18 (Mobile Money + photos IA + données publiques), F08 (génération attestation transmissible), et tout futur traitement sensible. Lorsqu'un de ces services est appelé sans consentement actif valide pour le type concerné, l'API retourne 403 avec un message en français identifiant le consentement manquant et un lien vers `/mes-donnees → Consentements`.

**Why this priority** : Sans ce helper applicatif systématique, les consentements stockés en base ne servent à rien : les services peuvent les ignorer. Le helper transforme la table `consents` en garde-fou opérationnel et matérialise l'invariant projet n°5 (« RGPD consentements ») de l'orchestrateur. C'est P2 car la story 2 (consentements granulaires) doit exister pour qu'il y ait quelque chose à vérifier.

**Independent Test** : Créer une PME, ne pas accorder le consentement `mobile_money_analysis`. Appeler un endpoint stub `/api/credit/mobile-money/preview` qui invoque `require_consent`. Vérifier que la réponse est 403 avec un body `{"detail": "Consentement Mobile Money requis", "consent_type": "mobile_money_analysis"}`. Accorder le consentement, retenter : l'endpoint répond 200 (ou 501 stub mais pas 403). Révoquer, retenter : 403 à nouveau.

**Acceptance Scenarios** :

1. **Given** un compte sans consentement `mobile_money_analysis`, **When** un service appelle `await require_consent(account_id, 'mobile_money_analysis')`, **Then** l'appel lève `HTTPException(403, ...)` avec un message en français mentionnant le type de consentement requis et incluant `consent_type` en métadonnée structurée.
2. **Given** un compte avec consentement `mobile_money_analysis` accordé puis révoqué, **When** le service rappelle `require_consent`, **Then** l'erreur 403 est levée car la dernière action est `revoke`, indépendamment de l'historique.
3. **Given** un compte avec consentement actif (granted=true, revoked_at=NULL), **When** le service appelle `require_consent`, **Then** la fonction retourne sans erreur et le service poursuit son exécution.
4. **Given** un nouveau service métier ajouté à l'avenir qui réalise un traitement non-essentiel, **When** un test d'intégration vérifie l'usage du helper, **Then** chaque fonction `analyze_*`, `fetch_*_external`, `generate_certificate_*` doit invoquer `require_consent` (vérifié par un test CI scannant les services).

---

### User Story 6 — Documentation hébergement et conformité (Priority: P3)

L'équipe ESG Mefali rédige et publie deux documents internes (`docs/rgpd-conformite.md` et `docs/hosting-and-data-residency.md`) qui décrivent l'état de conformité, les coordonnées DPO/privacy, le provider d'hébergement, la région de stockage (Europe ou Afrique de l'Ouest, **pas USA**), les mesures de chiffrement at-rest et la liste des sous-traitants avec leur DPA. Ces documents sont versionnés dans le repo, traduits si nécessaire, et tenus à jour à chaque évolution majeure.

**Why this priority** : C'est P3 car ces documents sont nécessaires pour la défense en cas d'audit et la transparence interne, mais leur absence n'empêche pas l'utilisation immédiate de la plateforme par les premières PME. Ils constituent la couche de documentation autour des garanties techniques mises en place par les autres stories.

**Independent Test** : Vérifier l'existence des fichiers `docs/rgpd-conformite.md` et `docs/hosting-and-data-residency.md`. Lire leur contenu et confirmer qu'ils couvrent l'ensemble des sections décrites dans le périmètre. Vérifier qu'ils citent les coordonnées `privacy@esg-mefali.com`, le provider, la région et le DPA.

**Acceptance Scenarios** :

1. **Given** le repo, **When** un développeur ouvre `docs/rgpd-conformite.md`, **Then** le document liste : checklist de conformité (au moins 15 items), processus d'exercice des droits, contacts (DPO post-MVP, `privacy@esg-mefali.com`), gabarits de réponse aux demandes RGPD.
2. **Given** le repo, **When** un développeur ouvre `docs/hosting-and-data-residency.md`, **Then** le document liste : provider (OVH / Scaleway / Africa Data Centres ou équivalent), région (UE ou Afrique Ouest, pas USA), chiffrement at-rest (AES-256 du provider), sous-traitants (OpenRouter, exchangerate-api, hébergeur) avec DPA.
3. **Given** une mise à jour de la politique ou un changement de sous-traitant, **When** la modification est faite, **Then** la date de mise à jour des documents est incrémentée dans une section « Historique » à la fin de chaque fichier.

---

### Edge Cases

- **Volume export > 100 MB** : la génération bascule automatiquement en asynchrone, l'utilisateur reçoit un email avec lien temporaire signé 7 jours quand l'export est prêt. Si la taille dépasse 1 GB, une alerte interne est levée et l'export est limité aux métadonnées (URLs signées des fichiers volumineux) pour éviter la saturation.
- **Demande d'export en double rapide** : si une PME demande un nouvel export alors que le précédent est encore en cours ou terminé depuis < 5 minutes, le système retourne le lien existant ou rejette avec un message explicite « Un export récent est disponible ».
- **Export avec partenaires externes** : les candidatures envoyées chez un intermédiaire (`fund_applications` post-soumission) restent dans l'export mais avec un libellé « Données soumises chez l'intermédiaire — votre suppression chez ESG Mefali ne supprime pas les copies que l'intermédiaire détient ».
- **Suppression cascade multi-utilisateur** : si un compte a plusieurs utilisateurs (rôles owner/collaborator/viewer via F02), seul l'utilisateur `owner` peut programmer la suppression du compte. Les collaborateurs ne peuvent supprimer que leur propre compte utilisateur (sans purger l'account).
- **Annulation hors délai** : si le lien d'annulation est cliqué après J+30 (mais avant que le cron ait tourné), le système accepte l'annulation tant que la purge n'a pas été exécutée. Après purge effective, le lien retourne « Compte déjà supprimé, annulation impossible ».
- **Cron purge interrompu en milieu d'exécution** : le job est idempotent (rejouable) ; si une exécution échoue après avoir supprimé une partie des données, la prochaine exécution reprend là où elle s'est arrêtée (utilisation d'un statut `purge_in_progress` sur l'account, suivi par `deleted_at` à la fin).
- **Révocation d'un consentement post-traitement déjà exécuté** : la révocation s'applique aux **futurs** traitements ; les outputs déjà générés (PDFs, dossiers, attestations) restent dans leur état. Si la PME veut effacer aussi les outputs, elle doit utiliser la suppression de compte ou une demande explicite via `privacy@esg-mefali.com`.
- **Politique de confidentialité v2.0** : si la politique évolue, l'utilisateur connecté voit un bandeau de re-acceptation, mais l'usage de la plateforme reste autorisé (les consentements existants restent valides jusqu'à révocation explicite ou nouvelle exigence légale).
- **Tentative de bypass `require_consent`** : un test CI scanne les services backend (`analyze_*`, `fetch_*_external`, `generate_certificate_*`) et échoue si un nouveau service est ajouté sans appeler `require_consent`.
- **Audit log volumineux post-purge** : les rows audit_log anonymisés (sans `user_id` ni `account_id`) restent en base 6 ans pour conformité comptable/légale ; ils ne contiennent plus aucune donnée personnelle (PII) après l'anonymisation.
- **Compte avec attestation crédit en cours de validité** : la suppression effective révoque l'attestation (`status='revoked'` avec raison `account_deleted`) avant la purge des données. L'identifiant public de l'attestation reste dans l'audit log anonymisé pour traçabilité.
- **Inscription refusant la politique** : la case à cocher « J'accepte » non cochée bloque le formulaire ; le backend rejette toute requête `POST /api/auth/register` ne contenant pas le flag `privacy_policy_accepted=true` avec une 422 et un message clair.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** : Le système DOIT exposer une page authentifiée `/mes-donnees` permettant à toute PME utilisatrice de visualiser un inventaire structuré de ses données stockées (compteurs par catégorie + date de dernière modification).
- **FR-002** : Le système DOIT permettre à toute PME authentifiée d'exporter en JSON l'ensemble de ses données (toutes les tables `account_id`) via un fichier ZIP contenant un fichier `data.json` exhaustif, un dossier `documents/` avec liens signés temporaires (24h) et un `README.md` explicatif.
- **FR-003** : Si la taille estimée de l'export dépasse 100 MB, le système DOIT basculer en mode asynchrone, notifier l'utilisateur par email avec un lien temporaire signé valide 7 jours, et logger l'action dans `audit_log`.
- **FR-004** : Le système DOIT stocker chaque consentement dans une table dédiée avec les champs : `id` UUID, `account_id`, `user_id`, `consent_type`, `granted` bool, `granted_at`, `revoked_at` nullable, `legal_basis` enum, `version` str, `metadata` jsonb (ip, user-agent).
- **FR-005** : Le système DOIT exposer 7 types de consentements granulaires : `profile_analysis` (default true), `document_analysis_ai` (default true), `mobile_money_analysis` (default false), `photos_ia_analysis` (default false), `public_data_analysis` (default false), `credit_certificate_generation` (default true), `product_communications` (default false).
- **FR-006** : Le système DOIT permettre à la PME d'activer/désactiver chaque consentement granulaire à tout moment via un toggle ; chaque action met à jour l'état stocké et est loggée dans `audit_log`.
- **FR-007** : Le système DOIT garantir au plus un consentement actif (granted=true, revoked_at=NULL) par couple (account_id, consent_type) à un instant donné.
- **FR-008** : Le système DOIT exposer un helper backend `require_consent(account_id, consent_type)` qui lève `HTTPException(403, ...)` en français avec une métadonnée `consent_type` lorsque le consentement n'est pas actif.
- **FR-009** : Le système DOIT intégrer `require_consent` dans tout service backend réalisant un traitement non-essentiel ; au minimum un stub de garde-fou DOIT être ajouté pour les emplacements F18 (Mobile Money, photos, données publiques) et F08 (attestation crédit).
- **FR-010** : Le système DOIT permettre à la PME de programmer la suppression de son compte via une modale de triple confirmation exigeant : (a) prise de connaissance des conséquences, (b) saisie du mot de passe valide, (c) saisie du mot « SUPPRIMER » en majuscules.
- **FR-011** : Le système DOIT positionner `accounts.deletion_scheduled_at = now() + 30 days` à la programmation, envoyer un email de confirmation contenant un lien d'annulation, et journaliser l'action dans `audit_log`.
- **FR-012** : Le système DOIT permettre à la PME d'annuler la suppression programmée à tout moment avant `deletion_scheduled_at` via un endpoint dédié (et lien email), repositionnant `deletion_scheduled_at = NULL`.
- **FR-013** : Le système DOIT fournir un job cron quotidien (`scripts/purge_scheduled_deletions.py`) qui purge les comptes dont `deletion_scheduled_at < now()` : suppression cascade des rows `account_id`, suppression des fichiers `/uploads/{account_id}/`, révocation des refresh tokens, mise à `deleted_at = now()` sur l'account, anonymisation des audit_log (`user_id=NULL`, `account_id=NULL`, autres champs intacts), envoi d'un email de confirmation final.
- **FR-014** : Le job cron DOIT être idempotent et reprendre proprement après interruption (statut `purge_in_progress` sur l'account, finalisation par `deleted_at`).
- **FR-015** : Le système DOIT publier une page publique `/legal/privacy` accessible **sans authentification** (layout public) couvrant : identité du responsable, finalités et bases légales, catégories de données, durée de conservation, sous-traitants, transferts hors UE/UEMOA, droits utilisateurs, exercice des droits (lien `/mes-donnees` + email `privacy@esg-mefali.com`), coordonnées DPO, date de mise à jour, historique des versions.
- **FR-016** : Le pied de page global de toutes les pages (publiques et privées) DOIT contenir un lien visible vers `/legal/privacy`.
- **FR-017** : La page `/register` DOIT contenir une case à cocher obligatoire « J'ai lu et j'accepte la politique de confidentialité v1.0 » bloquant la soumission tant qu'elle n'est pas cochée ; le backend rejette toute requête `POST /api/auth/register` sans flag `privacy_policy_accepted=true` avec une 422.
- **FR-018** : Le système DOIT exposer 7 endpoints REST authentifiés sur le module `/api/me` :
  - `GET /api/me/data/inventory` (compteurs par catégorie)
  - `GET /api/me/data/export?format=json` (export complet ou job asynchrone)
  - `GET /api/me/consents` (liste des consentements actifs)
  - `POST /api/me/consents/{type}/grant`
  - `POST /api/me/consents/{type}/revoke`
  - `POST /api/me/account/schedule-deletion` (avec password + confirmation_text)
  - `POST /api/me/account/cancel-deletion`
- **FR-019** : Toutes les routes du module `/api/me/*` DOIVENT s'appliquer strictement à `account_id` du JWT courant ; aucun cross-tenant ne DOIT être permis (invariant F02).
- **FR-020** : Toute mutation sur les tables `consents`, `accounts.deletion_scheduled_at`, `accounts.deleted_at` DOIT passer par un service décoré du mixin `Auditable` (invariant F03) ; pas de `db.commit()` direct.
- **FR-021** : Le système DOIT documenter dans `docs/rgpd-conformite.md` la checklist de conformité (au moins 15 items), le processus d'exercice des droits, et les contacts.
- **FR-022** : Le système DOIT documenter dans `docs/hosting-and-data-residency.md` le provider, la région d'hébergement (Europe ou Afrique Ouest, **pas USA**), le chiffrement at-rest, les sous-traitants (OpenRouter, exchangerate-api, hébergeur) avec DPA si applicable.
- **FR-023** : L'adresse `privacy@esg-mefali.com` DOIT être documentée dans la politique publique et dans `docs/rgpd-conformite.md` comme point de contact pour l'exercice des droits utilisateurs.
- **FR-024** : Tout export, consentement (grant/revoke), suppression programmée/annulée/effectuée, et acceptation de politique DOIT générer un événement audit_log avec un libellé explicite.
- **FR-025** : Lors de la purge effective, l'attestation crédit transmissible (F08) éventuellement active DOIT être marquée `revoked` avec raison `account_deleted` avant la suppression des données ; l'identifiant public de l'attestation reste dans l'audit log anonymisé pour traçabilité.

### Key Entities *(include if feature involves data)*

- **Consent** : représente un consentement utilisateur granulaire pour un traitement donné. Attributs principaux : `id` (UUID PK), `account_id` (FK accounts, NOT NULL — invariant F02), `user_id` (FK users, NOT NULL — qui a donné/révoqué), `consent_type` (enum à 7 valeurs documentées), `granted` (bool), `granted_at` (timestamptz), `revoked_at` (timestamptz nullable), `legal_basis` (enum : `consent`, `contract`, `legal_obligation`, `legitimate_interest`), `version` (str — version du texte de consentement présenté), `metadata` (jsonb : ip, user_agent au moment de l'action). Index : `(account_id, consent_type, revoked_at)` pour lookups rapides « consentement actif ».
- **Account (extended)** : extension du modèle existant `accounts` (introduit par F02) avec deux colonnes nouvelles : `deletion_scheduled_at` (timestamptz nullable — date à laquelle la purge effective doit avoir lieu, au plus tôt) et `deleted_at` (timestamptz nullable — date de purge effective). Index : `(deletion_scheduled_at) WHERE deletion_scheduled_at IS NOT NULL` pour le cron.
- **PrivacyPolicyAcceptance** (logique, non table) : événement audit_log `privacy_policy_accepted` capturant la version acceptée, l'ip et le user_agent au moment de l'inscription. Stocké dans `audit_log` (F03), pas de table dédiée.
- **DataExportJob** (logique, non table en MVP) : pour la story 1, l'export synchrone ne nécessite pas de table ; en mode asynchrone (>100 MB), un statut transitoire est journalisé dans `audit_log` avec `entity_type='data_export'`, `action='requested'` puis `action='ready'` ; l'URL signée est jointe en métadonnée. Une vraie table de jobs sera introduite si F19 (cron dispatcher) le rend nécessaire.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100% des PME peuvent accéder à `/mes-donnees` et y voir l'inventaire complet de leurs données stockées en moins de 3 secondes après chargement (compteurs corrects pour toutes les catégories `account_id`).
- **SC-002** : 100% des exports JSON synchrones (≤ 100 MB) sont délivrés à l'utilisateur en moins de 30 secondes après clic, et le fichier ZIP contient l'intégralité des données associées au compte (validable par comparaison ligne à ligne avec la BDD).
- **SC-003** : 100% des tentatives d'analyse Mobile Money / photos IA / données publiques / génération attestation sans consentement actif sont rejetées avec un code 403 et un message en français identifiant le consentement manquant ; aucune fuite de données ne se produit dans ce cas.
- **SC-004** : 100% des suppressions programmées peuvent être annulées par la PME avant `deletion_scheduled_at` en moins de 5 secondes via le lien email ou le bouton dédié.
- **SC-005** : 100% des suppressions effectives (au cron J+30) purgent toutes les lignes `account_id` et tous les fichiers `/uploads/{account_id}/`, et l'audit_log est anonymisé (vérifiable par un test : aucune donnée personnelle n'est récupérable d'un compte purgé).
- **SC-006** : La page publique `/legal/privacy` est accessible en moins de 1 seconde sans authentification et contient les 10 sections obligatoires décrites dans le périmètre.
- **SC-007** : 100% des inscriptions sur `/register` sont bloquées si la case « J'accepte la politique » n'est pas cochée (côté frontend ET côté backend, double validation).
- **SC-008** : La couverture de tests automatisés (unitaires + intégration + E2E) sur l'ensemble du périmètre F05 est ≥ 80%, validable via pytest-cov backend et vitest --coverage frontend.
- **SC-009** : Le délai entre la révocation d'un consentement et son effet (rejet effectif des futures analyses du même type) est inférieur à 1 seconde (effet immédiat dans la même requête).
- **SC-010** : 100% des évènements RGPD critiques (export, grant/revoke consent, suppression programmée/annulée/effectuée, acceptation politique) sont journalisés dans `audit_log` avec une horodate, l'action, l'entity_type et un payload JSON traçable.

## Assumptions

- **Stack** : la fonctionnalité réutilise la stack imposée par `.cc-orchestrator.md` (Python 3.12 + FastAPI + SQLAlchemy async + Alembic backend ; Nuxt 4 + Vue Composition API + Pinia + TailwindCSS frontend ; PostgreSQL 16 + pgvector ; Playwright pour les E2E).
- **Multi-tenant (F02)** : la table `accounts` existe déjà avec les colonnes `id` et les rôles owner/collaborator/viewer documentés ; toutes les tables métier comportent déjà `account_id`. La table `consents` créée ici applique cette même règle. Si F02 est mergé après le démarrage de cette feature, l'ordre de migration sera fixé en Phase B.
- **Audit log (F03)** : la table `audit_log` et le mixin `Auditable` existent déjà ; les évènements F05 réutilisent l'infrastructure sans créer de table satellite. Si F03 est mergé après, l'ordre de migration sera fixé en Phase B.
- **Authentification** : JWT en place (cohérence stack). Le mot de passe nécessaire à la modale de suppression réutilise l'endpoint de vérification existant (`POST /api/auth/verify-password` ou équivalent).
- **Email** : un service d'envoi d'email transactionnel est disponible (SMTP, SendGrid, Mailgun ou équivalent). Si le projet n'en dispose pas encore, F05 utilise un stub `app/core/mailer.py` qui logge les emails et les marque comme « envoyés » dans `audit_log`, à brancher en post-MVP.
- **Stockage fichiers** : les uploads sont en local sous `/uploads/{account_id}/...` (cohérent avec l'orchestrateur). La purge supprime les fichiers via `os.remove` / `shutil.rmtree`. Migration vers MinIO/S3 hors-scope.
- **Job cron** : le job `scripts/purge_scheduled_deletions.py` est exécutable manuellement (`python scripts/purge_scheduled_deletions.py`) et sera intégré au scheduler global F19 (cron dispatcher) une fois ce dernier mergé. Il est idempotent et peut tourner plusieurs fois par jour sans effet secondaire indésirable.
- **Volume export** : la limite 100 MB pour le mode synchrone est un seuil pragmatique cohérent avec les performances FastAPI ; elle peut être ajustée par variable d'environnement si nécessaire. La limite 1 GB pour l'alerte interne reste un garde-fou.
- **Horodate de purge** : le délai 30 jours est conforme à la pratique standard du marché (Google, Microsoft, etc.) et permet à l'utilisateur de revenir sur sa décision sans perte de données.
- **Politique de confidentialité v1.0** : la première version est rédigée par l'équipe ESG Mefali en français pendant cette feature ; les versions futures (v2.0, etc.) suivront un processus standard avec re-acceptation utilisateur.
- **Email `privacy@esg-mefali.com`** : la création de la boîte mail (DNS / forwarding) est hors-scope code mais documentée dans `docs/rgpd-conformite.md` comme dépendance opérationnelle ; un alias temporaire vers une adresse interne est acceptable pour le MVP.
- **DPO formalisé** : pas de DPO formalisé en MVP ; la documentation `docs/rgpd-conformite.md` indique « DPO post-MVP, contact temporaire `privacy@esg-mefali.com` ».
- **Re-acceptation politique v2** : la re-acceptation lors d'un changement majeur affiche un bandeau d'information, sans bloquer l'usage de la plateforme. Le blocage forcé n'est introduit que sur exigence légale future.
- **Cookies analytics tiers** : la plateforme n'en utilise pas en MVP (à confirmer avant le launch) ; aucun banner cookies n'est requis par cette feature.
- **Tests `require_consent`** : un test CI scanne les services backend (`analyze_*`, `fetch_*_external`, `generate_certificate_*`) et échoue si un nouveau service est ajouté sans appel au helper. Ce test est délivré dans cette feature et sert de garde-fou pour les features futures.
- **Sources et taxonomies** : F05 ne crée aucun chiffre ESG/carbone/financier ; aucune obligation de sourçage F01. Les seuls « chiffres » manipulés sont des compteurs (inventaire), des durées (30 jours, 24h, 7 jours), et des dates — non concernés par l'invariant n°1.
- **Devise et i18n** : pas d'impact monétaire ; tout le texte de la politique est en français avec accents corrects (cohérent avec la convention projet).
- **Langue** : tout le texte UI utilisateur est en français ; tous les libellés audit_log restent en anglais snake_case (cohérence avec F03).
