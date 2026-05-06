# Feature Specification: F03 — Audit Log Append-Only

**Feature Branch**: `feat/F03-audit-log` (folder `specs/021-audit-log/`)
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "F03 — Introduire une table `audit_log` strictement append-only (triggers PostgreSQL + permission DB stricte) qui trace toute mutation métier (CompanyProfile, FundApplication, ESGAssessment, ESGCriterionScore, CarbonAssessment, CarbonEmissionEntry, CreditScore, ActionPlan, ActionItem) avec qui-quoi-quand-ancienne/nouvelle valeur, distinguer la source de la mutation (manuel, LLM, import, admin) via une variable de contexte propagée par les nœuds LangGraph et les middlewares, capturer également l'événement `view_admin` quand un administrateur consulte un compte PME, exposer les endpoints PME (`GET /api/audit/me`, `GET /api/audit/me/export`) et admin (`GET /api/admin/audit/{account_id}`, `GET /api/admin/audit`), et livrer une page `/historique` (PME) ainsi qu'une page `/admin/audit` (admin) avec filtres, pagination et export CSV/JSON."

## Clarifications

### Session 2026-05-06

Mode autonomie totale (utilisateur absent) — décisions prises selon les invariants ESG Mefali, la stack imposée (Python 3.12 / FastAPI / SQLAlchemy async / Alembic / PostgreSQL 16 / Pydantic v2 / pytest / Nuxt 4 / Vue 3 / Pinia / TailwindCSS / Playwright / Vitest), et le critère « plus simple et testable ». Le détail rationnel est enregistré ci-dessous.

- Q : Comment garantir techniquement le caractère append-only de la table `audit_log` ? → A : Double défense en profondeur. (1) Triggers PostgreSQL `BEFORE UPDATE` et `BEFORE DELETE` sur `audit_log` qui exécutent `RAISE EXCEPTION` avec un message explicite (« audit_log is append-only ; UPDATE/DELETE are forbidden »). (2) Permission DB stricte : le rôle PostgreSQL applicatif (`application_user` ou rôle existant utilisé par le `database_url`) reçoit uniquement `INSERT, SELECT` sur `audit_log`, pas `UPDATE`, pas `DELETE`. Les deux mécanismes coexistent ; le premier protège contre une promotion accidentelle de privilèges, le second protège contre une migration future qui retirerait les triggers. Aucun rôle DPO formel en MVP — la suppression GDPR formelle (Art. 17) est documentée comme limitation et reportée post-MVP.
- Q : Comment instrumenter les modèles SQLAlchemy pour capturer automatiquement les mutations sans modifier chaque service ? → A : Mixin `Auditable` couplé à un listener global `event.listens_for(Session, 'before_flush')` (recommandé sur le Session asynchrone). Le listener parcourt `session.new` (insertions), `session.dirty` (mises à jour) et `session.deleted` (suppressions), filtre les instances dont la classe applique le mixin, calcule le diff `field-by-field` à partir de l'API `inspect(obj).attrs[<field>].history` (état avant/après), et enregistre une (ou plusieurs) ligne(s) `audit_log` dans la même session avant le flush. Les insertions d'`audit_log` sont elles-mêmes ignorées par le listener pour éviter la récursion. Cette approche garantit qu'aucune mutation ne peut contourner le log tant que l'instance passe par une `Session` (ce qui est l'invariant ORM du projet).
- Q : Quelle granularité du diff pour les champs JSON volumineux (`assessment_data`, `actor_metadata`, etc.) ? → A : Field-level diff borné à 10 KB par valeur. (1) Stocker uniquement les champs modifiés (pas l'objet entier) — par défaut, une mutation produit autant de lignes `audit_log` que de champs modifiés. (2) Si une valeur (sérialisée en JSON) dépasse 10 KB, elle est tronquée et un marqueur `{"_truncated": true, "_truncated_size": <bytes>, "_preview": "<premiers 8 KB>"}` est stocké à la place. Pas de diff structurel récursif sur les sous-clés JSON en MVP — la valeur entière est considérée comme « la valeur du champ ». Une option de regroupement par mutation (un seul row `audit_log` avec `field=NULL` et `new_value={"<f1>": ..., "<f2>": ...}`) est explicitement rejetée pour faciliter le requêtage par champ.
- Q : Comment positionner `source_of_change` selon le contexte d'invocation ? → A : ContextVar Python (`current_source_of_change: ContextVar[str]`) avec valeur par défaut `"manual"`. (a) Les nœuds LangGraph (chat, esg_scoring, carbon, financing, application, credit, action_plan, document, profiling) appellent `current_source_of_change.set("llm")` au début du nœud (token réinitialisé à la fin via `Token.reset`). (b) Les middlewares admin FastAPI (montés sur `/api/admin/*`) appellent `set("admin")`. (c) Les scripts d'import batch (CLI, future feature) appellent `set("import")`. (d) Les routeurs PME et endpoints REST classiques héritent de la valeur par défaut `"manual"`. Le mixin `Auditable` lit la ContextVar lors de l'insertion `audit_log`. Aucune introspection automatique « ai-je été appelé depuis un node LangGraph ? » — la décision est explicite et locale.
- Q : Comment l'événement `view_admin` est-il déclenché ? → A : Programmatiquement via un service `AuditService.record_admin_view(admin_user, target_account_id, context)`. Tout endpoint admin (déclaré dans `/api/admin/audit/{account_id}`, `/api/admin/users/{account_id}`, et plus généralement tout endpoint `/api/admin/*` qui consulte des données spécifiques à un compte PME) appelle ce helper avant ou après la lecture (avant pour préserver la trace même en cas d'erreur applicative, idempotent par requête grâce à un cache `request.state.audit_view_recorded`). L'enregistrement utilise `entity_type="account"`, `entity_id=<pme_account_id>`, `action="view_admin"`, `source_of_change="admin"`, `actor_metadata={"endpoint": "<path>", "request_id": "<uuid>"}`. La RLS standard de F02 n'empêche PAS l'audit_log `view_admin` d'apparaître côté PME : la policy PME existante autorise les lignes `audit_log` dont `account_id` correspond à `app.current_account_id`, et l'admin écrit explicitement `account_id = <pme>` même si lui-même a `current_account_id` nul.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reconstitution exhaustive de l'historique d'une candidature pour défense en cas de litige (Priority: P1)

Une PME a déposé une candidature au fonds GCF via l'intermédiaire BOAD. Trois mois plus tard, un fund officer la conteste : « le score ESG affiché dans le dossier final paraît incohérent avec votre profil — qui a modifié quoi et quand ? ». La PME doit pouvoir, dans la page `/historique` (ou en exportant en CSV pour son auditeur), reconstituer la chronologie complète : qui a saisi le score initial, quel critère ESG a été modifié, à quel moment, par l'humain ou par le LLM, et quel était l'état au moment de la soumission au fonds. Aucune mutation ne doit avoir échappé au log.

**Why this priority** : Module 0.4 du brainstorming qualifie cette traçabilité de « quasi-réglementaire en finance pour défense en cas de litige ». Sans cet historique, la plateforme ne peut pas se défendre face à un audit, un contentieux client, ou une réclamation d'un fund officer ; elle perd toute crédibilité auprès des acteurs financiers (BOAD, GCF, BAD) qui exigent une piste d'audit pour valider leurs décaissements.

**Independent Test** : Créer une PME, lui faire saisir un profil entreprise, créer une candidature à un fonds via l'agent LLM, puis modifier manuellement deux champs depuis `/profile` et un score ESG via une évaluation LLM. Ouvrir `/historique` et vérifier que la timeline contient au minimum 5 événements distincts (création profil + 2 mutations manuelles + création candidature LLM + mutation score ESG LLM), chacun avec acteur, horodatage, source_of_change, ancienne valeur et nouvelle valeur. Exporter en CSV et confirmer que les lignes correspondent strictement à ce que l'UI affiche.

**Acceptance Scenarios** :

1. **Given** une PME qui crée une candidature de fonds via une conversation LLM (l'agent appelle un tool `create_fund_application`), **When** la PME ouvre `/historique` immédiatement après, **Then** elle voit au moins une entrée d'audit `entity_type=fund_application, action=create, source_of_change=llm, actor_metadata.tool_name=create_fund_application` (et l'`actor_metadata` contient également le `conversation_id`) avec un horodatage à la seconde près.
2. **Given** une PME qui édite manuellement le champ `sector` de son profil entreprise depuis `/profile`, **When** elle consulte `/historique`, **Then** elle voit une entrée `entity_type=company_profile, action=update, field=sector, old_value="agriculture", new_value="energie", source_of_change=manual` avec son user_id en acteur.
3. **Given** la PME qui modifie 4 champs (`sector`, `legal_form`, `phone`, `address`) en un seul `PATCH /api/companies/me`, **When** elle consulte `/historique`, **Then** elle voit 4 entrées distinctes (une par champ) toutes horodatées à la même seconde, avec le même `user_id`, `source_of_change=manual`, et les paires (old_value, new_value) propres à chaque champ.
4. **Given** un score ESG dont une valeur dépasse 10 KB après sérialisation JSON (cas rare, ex. payload `assessment_data` dense), **When** la mutation est tracée, **Then** la valeur stockée dans `old_value`/`new_value` est tronquée à 10 KB avec un marqueur `{"_truncated": true, "_truncated_size": <bytes>, "_preview": "<premiers 8 KB>"}` et l'entrée audit reste interrogeable normalement.

---

### User Story 2 - Transparence sur l'accès admin au compte PME (Priority: P1)

Un administrateur ESG Mefali consulte un compte PME pour aider une équipe en difficulté ou pour modérer un signalement. La PME doit avoir une visibilité totale sur cet accès : quel admin, à quel moment, sur quel compte. Pas de surveillance masquée. Cette transparence est un engagement de confiance, et elle est elle-même auditée pour exclure tout doute.

**Why this priority** : Le multi-tenant introduit en F02 donne aux Admins un pouvoir de lecture sur les comptes PME (policy `admin_full_access`). Sans trace de cette consultation, l'asymétrie de pouvoir devient opaque et expose la plateforme à des reproches RGPD et à une perte de confiance utilisateur. La traçabilité de l'accès admin est, comme les triggers append-only, un mécanisme défensif essentiel.

**Independent Test** : Créer une PME et un Admin distincts. Connecté en Admin, ouvrir `/admin/audit/<pme_account_id>` (page de consultation du log d'un compte PME). Se reconnecter en PME et vérifier dans `/historique` qu'une entrée `action=view_admin, source_of_change=admin, entity_type=account` apparaît avec l'horodatage de la consultation et l'identifiant de l'admin.

**Acceptance Scenarios** :

1. **Given** un admin authentifié qui appelle `GET /api/admin/audit/{pme_account_id}`, **When** la requête est servie, **Then** une entrée `audit_log` est insérée avec `action=view_admin, source_of_change=admin, entity_type=account, entity_id=<pme_account_id>, account_id=<pme_account_id>, user_id=<admin_id>`, et la PME voit cette entrée dans son `/historique`.
2. **Given** un admin qui consulte le même compte PME 3 fois en 2 minutes via plusieurs sous-routes admin (`/api/admin/users/{account_id}`, `/api/admin/audit/{account_id}`, `/api/admin/financing/applications?account_id=<id>`), **When** chaque appel est servi, **Then** chaque appel produit son propre `audit_log` `view_admin` (une trace par requête), tous visibles côté PME — l'admin ne peut pas dissimuler une consultation par déduplication.
3. **Given** un appel admin qui échoue en milieu de traitement (par exemple 500 Internal Server Error sur la lecture des données), **When** la trace `view_admin` a été insérée *avant* la lecture (positionnement de l'audit en début de handler), **Then** l'audit reste persistant — la PME voit qu'un admin a tenté un accès, même si le résultat n'a pas été retourné.

---

### User Story 3 - Export CSV/JSON de l'historique pour archivage et auditeurs externes (Priority: P2)

Une PME doit pouvoir extraire l'intégralité de son historique au format CSV (tableur) ou JSON (intégration outil externe) pour archive locale ou partage avec un auditeur réglementaire. L'export respecte les filtres en cours (période, type d'entité, source) et inclut les mêmes champs que l'UI.

**Why this priority** : Les auditeurs externes (commissaire aux comptes, fund officer, autorité de régulation BCEAO) exigent souvent un export tabulaire indépendant de la plateforme. L'historique doit donc sortir de la base sans intermédiaire propriétaire ; cela renforce aussi la posture défensive de la PME en cas de litige (l'export horodaté peut être stocké hors plateforme).

**Independent Test** : Connecté en PME, après avoir produit au moins 50 événements d'audit (mutations diverses), appeler `GET /api/audit/me/export?format=csv` puis `GET /api/audit/me/export?format=json` ; vérifier que les deux fichiers contiennent exactement le même nombre d'événements, les mêmes valeurs, et que le CSV est lisible dans un tableur sans erreur d'encodage (UTF-8 BOM compatible Excel) ni de caractères français corrompus (é, è, ç doivent rester corrects).

**Acceptance Scenarios** :

1. **Given** une PME avec 120 événements d'audit, **When** elle appelle `GET /api/audit/me/export?format=csv`, **Then** elle reçoit un fichier CSV UTF-8 BOM avec exactement 120 lignes (plus l'en-tête), chaque ligne contenant les colonnes : `id, timestamp, user_email, user_id, account_id, entity_type, entity_id, action, field, old_value, new_value, source_of_change, actor_metadata` ; le `Content-Disposition` propose un nom de fichier de la forme `audit-log-<account_id>-<YYYYMMDD>.csv`.
2. **Given** une PME qui filtre `?since=2026-04-01&until=2026-05-01&source_of_change=llm`, **When** elle exporte au format JSON, **Then** elle reçoit un tableau JSON contenant uniquement les événements du mois d'avril 2026 dont la source est `llm`, dans le même ordre que celui de l'UI (timestamp DESC).
3. **Given** une PME qui appelle l'export avec un filtre qui retourne 0 événement, **When** la requête est servie, **Then** elle reçoit un fichier vide (CSV avec uniquement l'en-tête, ou JSON `[]`) avec un statut 200 — pas de 404.

---

### User Story 4 - Filtrage et pagination performants sur 100 000+ événements (Priority: P2)

À mesure que la plateforme grandit, le volume d'audit_log peut atteindre plusieurs milliers d'événements par PME. La page `/historique` doit rester réactive grâce à une pagination par défaut (50 entrées par page) et à un filtrage côté serveur sur `entity_type`, `entity_id`, `source_of_change`, `since`, `until`. Les requêtes doivent rester sous 500 ms même à 100 000 lignes par compte.

**Why this priority** : Performance utilisateur indispensable au quotidien. Sans pagination ni indexation, une PME active depuis 6 mois subirait un timeout sur sa propre page d'historique.

**Independent Test** : Charger 100 000 lignes `audit_log` pour une seule PME via un script de seed, puis ouvrir `/historique` et mesurer le temps de réponse de l'endpoint `GET /api/audit/me?page=1&limit=50` ; il doit rester sous 500 ms (P95 sur 50 requêtes successives). Activer un filtre `entity_type=fund_application&since=<date>` et vérifier que le temps de réponse reste sous 500 ms.

**Acceptance Scenarios** :

1. **Given** une PME avec 100 000 entrées `audit_log`, **When** elle appelle `GET /api/audit/me?page=1&limit=50`, **Then** la réponse est servie en moins de 500 ms (P95), avec exactement 50 entrées triées par timestamp DESC et un compteur total dans la réponse.
2. **Given** la même PME qui filtre par `entity_type=fund_application`, **When** elle paginate sur 5 pages, **Then** chaque page est servie sous 500 ms grâce à l'index composite `(account_id, entity_type, timestamp DESC)`.
3. **Given** une recherche full-text sur `actor_metadata.tool_name='create_fund_application'`, **When** la requête est exécutée, **Then** le filtre s'applique côté SQL via une condition JSONB sur `actor_metadata` (pas de scan en mémoire) et la réponse reste sous 1 seconde.

---

### User Story 5 - Garantie qu'aucune mutation n'échappe au log (Priority: P1)

Tout développeur qui ajoute une nouvelle entité métier ou un nouveau service doit constater qu'il est impossible de produire une mutation sans laisser de trace dans `audit_log`. Si un tool LangChain commet `db.commit()` direct (ancienne pratique) sans passer par un service `Auditable`, soit la CI échoue (test de garde-fou), soit le mixin global `before_flush` capte tout de même l'instance et écrit le log — le bypass devient impossible par construction.

**Why this priority** : Cette garantie protège la valeur du log en empêchant la dérive (« j'ai modifié vite-fait sans passer par le service, ça ira »). Sans cette discipline, le log devient incomplet et donc inutile en cas de litige. C'est un invariant projet au même titre que la RLS.

**Independent Test** : Écrire un test pytest qui (a) ouvre une session de base, (b) instancie directement un `CompanyProfile` (modèle marqué `Auditable`), (c) appelle `session.add()` puis `session.flush()` sans passer par aucun service applicatif, (d) vérifie qu'une ligne `audit_log` correspondante a été créée automatiquement. Ajouter ensuite un second test qui scanne via Python (`pytest --collect-only` + introspection AST ou whitelist) que tous les modèles dans la liste `AUDITABLE_MODELS` appliquent bien le mixin `Auditable` et que la liste reste synchronisée avec les modèles métier déclarés dans `app/models/`.

**Acceptance Scenarios** :

1. **Given** un nouveau service (ou un script ad-hoc) qui modifie un `CompanyProfile` sans appeler de service applicatif et fait `session.commit()` directement, **When** la transaction est commit, **Then** une (ou plusieurs) ligne(s) `audit_log` est insérée automatiquement par le listener `before_flush`, avec `source_of_change=manual` (la valeur par défaut de la ContextVar).
2. **Given** un développeur qui crée un nouveau modèle métier `MyNewEntity` sans appliquer le mixin `Auditable`, **When** la suite de tests CI s'exécute, **Then** un test dédié `test_auditable_models_whitelist_complete` échoue avec un message explicite : « `MyNewEntity` est déclarée comme métier dans `app/models/` mais n'applique pas le mixin `Auditable`. Ajoutez `class MyNewEntity(Auditable, Base):` ou exposez-la dans `EXEMPT_MODELS` avec une justification. »
3. **Given** un test qui exécute `UPDATE audit_log SET source_of_change='manual' WHERE id=<row_id>`, **When** la requête est exécutée par le rôle PostgreSQL applicatif, **Then** le trigger `BEFORE UPDATE` lève une `RAISE EXCEPTION 'audit_log is append-only ; UPDATE/DELETE are forbidden'` ET (en défense en profondeur) la permission DB stricte refuse également l'opération si le trigger est désactivé.

---

### Edge Cases

- **Mutation très volumineuse (champ JSON > 10 KB)** : le mixin tronque chaque valeur dépassant 10 KB et marque `_truncated: true` avec la taille originale ; le requêtage et l'export restent fonctionnels.
- **Mutation par migration Alembic** : les migrations DDL/DML produites par Alembic ne passent PAS par la session ORM et donc n'écrivent PAS de log — c'est le comportement attendu et documenté (les migrations sont versionnées par Alembic et toute évolution de schéma est elle-même journalisée par Git). Aucun test ne doit échouer sur ce point.
- **Insertion d'une ligne dans une table non auditable** : le listener `before_flush` filtre via `isinstance(obj, Auditable)` ; les modèles non `Auditable` (ex. `Source`, `EmissionFactor`, catalogue Admin) ne génèrent aucune ligne d'audit.
- **Mutation suivie d'un rollback** : si la transaction métier rollback, la ligne `audit_log` insérée dans la même session est elle aussi rollback — l'audit reste cohérent (« on ne logue pas une modification qui n'a jamais eu lieu »).
- **Source de changement inconnue** : si une nouvelle valeur de `source_of_change` apparaît (ex. typo dans un nœud LangGraph), elle est rejetée par la contrainte ENUM PostgreSQL — la transaction échoue et le développeur est forcé d'utiliser une valeur valide.
- **Tentative `DELETE FROM audit_log` par un attaquant** : double protection (trigger + permission DB) ; les deux barrières doivent être franchies pour réussir, et chacune est testée séparément.
- **Volume d'audit explose (100k+ lignes par jour)** : la pagination `limit=50` par défaut, les indexes ciblés et le tri `timestamp DESC` garantissent la performance ; un partitionnement par mois est documenté comme évolution post-MVP mais pas requis MVP.
- **RGPD vs append-only (Art. 17 droit à l'oubli)** : conflit reconnu et documenté ; en MVP, la suppression GDPR formelle n'est pas implémentée. Une documentation `docs/audit-log.md` explicite cette limite et ouvre la voie à un mécanisme DPO post-MVP (anonymisation + tombstone, hachage chaîné).
- **Admin sans `account_id`** : un admin a `users.account_id = NULL`. Lorsqu'il consulte un compte PME, l'audit_log écrit `account_id = <pme_account_id>` (donc la PME voit l'événement), `user_id = <admin_id>`. La policy RLS PME `pme_access_own_account` autorise la lecture car `account_id` correspond.
- **Visibilité des événements `view_admin` côté admin** : un admin doit pouvoir consulter les événements `view_admin` qu'il a lui-même générés (pour autocontrôle et audit interne) ; la policy `admin_full_access` lui donne cet accès via `/api/admin/audit`.
- **Tools LLM préexistants qui font `db.commit()` directement** : un audit du code (`grep "db.commit()" backend/app/graph/tools/`) identifie ces points ; F03 inclut leur migration vers les services métier `Auditable`. Les services concernés sont listés dans le plan d'implémentation.

## Requirements *(mandatory)*

### Functional Requirements

#### Modèles et données

- **FR-001** : Le système DOIT introduire une entité `audit_log` représentant un événement d'audit immuable, avec au minimum les attributs : identifiant unique, identifiant de l'acteur (user_id), identifiant du compte propriétaire (account_id), horodatage avec fuseau horaire, type d'entité affectée, identifiant d'entité, action (`create`, `update`, `delete`, `view_admin`), nom du champ muté (NULL pour `create`/`delete`/`view_admin`), valeur avant et après mutation (toutes deux JSON, NULL admises), source du changement (`manual`, `llm`, `import`, `admin`), et métadonnées d'acteur libres (JSON optionnel).
- **FR-002** : Le système DOIT contraindre l'horodatage `timestamp` à `timestamptz NOT NULL DEFAULT now()` et l'identifiant à un UUID auto-généré.
- **FR-003** : Le système DOIT exprimer `action` et `source_of_change` comme des ENUMs PostgreSQL contraints (toute valeur hors enum est rejetée).
- **FR-004** : Le système DOIT créer les indexes suivants sur `audit_log` : (a) `(account_id, timestamp DESC)` pour scrolling chronologique, (b) `(account_id, entity_type, entity_id)` pour reconstituer l'historique d'une entité, (c) `(user_id, timestamp DESC)` pour audit par acteur, (d) `(source_of_change, timestamp DESC)` pour métriques admin.
- **FR-005** : Le système DOIT borner chaque valeur (`old_value` et `new_value`) à 10 KB après sérialisation JSON ; au-delà, la valeur est tronquée et remplacée par un objet `{"_truncated": true, "_truncated_size": <bytes>, "_preview": "<premiers 8 KB de la valeur>"}`.

#### Append-only et permissions

- **FR-006** : Le système DOIT installer un trigger PostgreSQL `BEFORE UPDATE ON audit_log` qui exécute `RAISE EXCEPTION 'audit_log is append-only ; UPDATE is forbidden'` (texte exact).
- **FR-007** : Le système DOIT installer un trigger PostgreSQL `BEFORE DELETE ON audit_log` qui exécute `RAISE EXCEPTION 'audit_log is append-only ; DELETE is forbidden'` (texte exact).
- **FR-008** : Le système DOIT, en MVP F03 et tant que l'environnement de production le permet (cf. limites MVP), retirer les permissions `UPDATE` et `DELETE` sur la table `audit_log` au rôle PostgreSQL applicatif (rôle utilisé par `database_url`) tout en lui laissant `INSERT, SELECT`. La migration Alembic exécute `REVOKE UPDATE, DELETE ON audit_log FROM <role>` après le `GRANT INSERT, SELECT`. Si le rôle applicatif est superuser ou owner du schéma, la migration journalise un avertissement (le trigger reste la défense effective).
- **FR-009** : Le système DOIT activer la Row-Level Security PostgreSQL (`ENABLE` + `FORCE`) sur la table `audit_log` avec deux policies cohérentes avec F02 : (a) `pme_access_own_account` autorise `SELECT` et `INSERT` aux lignes dont `account_id = current_setting('app.current_account_id')::uuid`, (b) `admin_full_access` autorise `SELECT` et `INSERT` quand `current_setting('app.current_role') = 'ADMIN'`. Aucun `UPDATE`/`DELETE` n'est exposé par les policies (cohérent avec FR-006/FR-007/FR-008).

#### Capture automatique des mutations

- **FR-010** : Le système DOIT introduire un mixin SQLAlchemy `Auditable` que les classes de modèles métier importent (ex. `class CompanyProfile(Auditable, Base): ...`).
- **FR-011** : Le système DOIT enregistrer un listener global `event.listens_for(Session, 'before_flush')` qui parcourt `session.new`, `session.dirty`, `session.deleted`, filtre les instances `Auditable`, calcule le diff `field-by-field` (en interrogeant `inspect(obj).attrs[<field>].history`), et insère dans la même session autant de lignes `audit_log` que de champs mutés.
- **FR-012** : Le système DOIT instrumenter les modèles suivants avec le mixin `Auditable` : `CompanyProfile`, `FundApplication`, `ESGAssessment`, `ESGCriterionScore`, `CarbonAssessment`, `CarbonEmissionEntry`, `CreditScore`, `ActionPlan`, `ActionItem`. La liste est publiée dans une constante `AUDITABLE_MODELS` du module `app/core/auditable.py` à des fins de test CI.
- **FR-013** : Le système DOIT, lors de l'insertion d'une ligne `audit_log`, lire la ContextVar `current_source_of_change` (défaut `"manual"`) et la stocker dans la colonne `source_of_change`.
- **FR-014** : Le système DOIT, lors de l'insertion d'une ligne `audit_log`, lire les ContextVars / variables de session disponibles pour récupérer le `user_id` courant (depuis `app.current_user_id` positionné par `set_rls_context`) et l'`account_id` propre à l'instance mutée (typiquement `obj.account_id` qui existe sur tous les modèles auditables grâce à F02).
- **FR-015** : Le système DOIT ignorer les insertions de la table `audit_log` elle-même dans le listener `before_flush` (anti-récursion).
- **FR-016** : Le système DOIT enregistrer une ligne `audit_log` `action="create"` avec `field=NULL`, `old_value=NULL`, `new_value=<snapshot des champs initiaux>` lors de l'insertion d'une instance auditable (création).
- **FR-017** : Le système DOIT enregistrer une ligne `audit_log` `action="delete"` avec `field=NULL`, `old_value=<snapshot des champs au moment du delete>`, `new_value=NULL` lors de la suppression d'une instance auditable.
- **FR-018** : Le système DOIT enregistrer une (ou plusieurs) ligne(s) `audit_log` `action="update"` avec `field=<nom>`, `old_value=<avant>`, `new_value=<après>` lors de la modification d'une instance auditable, une ligne par champ effectivement modifié (les champs inchangés ne génèrent rien).

#### Source du changement (ContextVar)

- **FR-019** : Le système DOIT introduire dans `app/core/audit_context.py` une `ContextVar[str]` nommée `current_source_of_change` avec la valeur par défaut `"manual"` et un helper `set_source_of_change(value: Literal['manual','llm','import','admin'])` qui retourne un `Token` pour reset après usage.
- **FR-020** : Le système DOIT, dans chacun des 9 nœuds LangGraph (`chat`, `esg_scoring`, `carbon`, `financing`, `application`, `credit`, `action_plan`, `document`, `profiling`), appeler `set_source_of_change("llm")` au début du nœud (puis `Token.reset()` à la fin via `try/finally` ou un context manager dédié).
- **FR-021** : Le système DOIT introduire un middleware FastAPI `AdminAuditContextMiddleware` monté sur le routeur `/api/admin/*` (cohérent avec F02 `get_current_admin`) qui appelle `set_source_of_change("admin")` au début du traitement de chaque requête admin.
- **FR-022** : Le système DOIT documenter dans `docs/audit-log.md` la procédure pour positionner `source_of_change="import"` dans les futurs scripts CLI/import (post-MVP : CLI batch). Aucun script d'import en MVP F03 — la valeur `"import"` est néanmoins ajoutée à l'ENUM pour anticipation.

#### Événement view_admin

- **FR-023** : Le système DOIT exposer un service `AuditService.record_admin_view(admin_user, target_account_id, request_context)` qui insère une ligne `audit_log` avec `action="view_admin"`, `source_of_change="admin"`, `entity_type="account"`, `entity_id=<target_account_id>`, `account_id=<target_account_id>`, `user_id=<admin_user.id>`, `actor_metadata={"endpoint": "<path>", "request_id": "<uuid>", "ip_address": "<x.x.x.x>", "user_agent": "<...>"}`.
- **FR-024** : Le système DOIT appeler `record_admin_view` automatiquement dans tous les endpoints admin qui consultent des données spécifiques à un compte PME : `GET /api/admin/audit/{account_id}`, `GET /api/admin/users/{account_id}` (s'il existe en F02), et chaque endpoint admin futur via une `Depends(audit_admin_view_dep)` réutilisable.
- **FR-025** : Le système DOIT garantir l'idempotence par requête : si plusieurs sous-handlers d'une même requête appellent `record_admin_view` pour le même `target_account_id`, une seule ligne `audit_log` est créée (cache `request.state.audit_view_recorded[target_account_id] = True`).

#### Endpoints PME

- **FR-026** : Le système DOIT exposer `GET /api/audit/me` qui retourne, pour l'utilisateur PME courant, les événements `audit_log` de son `account_id`, paginés (`page`, `limit`, défaut 50, max 200), filtrables par `entity_type`, `entity_id`, `action`, `source_of_change`, `since` (timestamp ISO 8601), `until` (timestamp ISO 8601). La réponse contient le tableau d'événements et un compteur total.
- **FR-027** : Le système DOIT exposer `GET /api/audit/me/export` qui retourne le même set filtré que FR-026 mais sans pagination (totalité du résultat), au format CSV (UTF-8 BOM) ou JSON selon `format=csv|json` (par défaut `csv`). Le `Content-Disposition` propose un nom de fichier `audit-log-<account_id>-<YYYYMMDD>.<ext>`.
- **FR-028** : Le système DOIT trier les événements par `timestamp DESC` (du plus récent au plus ancien) par défaut, avec une option `order=asc` pour inversion.

#### Endpoints Admin

- **FR-029** : Le système DOIT exposer `GET /api/admin/audit/{account_id}` qui retourne le log d'un compte PME spécifique, avec les mêmes filtres que FR-026, accessible UNIQUEMENT aux Admin (`get_current_admin`). L'appel déclenche un `record_admin_view`.
- **FR-030** : Le système DOIT exposer `GET /api/admin/audit` qui retourne le log global filtrable (par `account_id`, `user_id`, `entity_type`, `source_of_change`, `since`, `until`), accessible UNIQUEMENT aux Admin. Aucune trace `view_admin` n'est créée pour l'audit log global (pas de cible PME unique).
- **FR-031** : Le système DOIT, en cas d'accès PME à `/api/admin/audit/*`, retourner HTTP 403 (cohérent avec F02 `get_current_admin`).

#### Frontend PME

- **FR-032** : Le système DOIT fournir une page Nuxt `pages/historique.vue` (route `/historique`) avec layout `default` (layout PME standard) qui affiche les événements `audit_log` de la PME courante sous forme de timeline verticale, paginés par 50, avec filtres (entité, source, période) en sidebar.
- **FR-033** : Le système DOIT fournir un composant `<AuditLogEntry :event="..." />` qui rend chaque ligne lisible en français avec un pictogramme contextuel (sans emoji obligatoire si CLAUDE.md projet l'interdit ; à défaut, libellé textuel : « Création », « Modification », « Suppression », « Consultation Admin »), l'acteur (« Vous », « Un collaborateur », « L'assistant IA », « Un admin Mefali »), le résumé du diff (« sector : agriculture → energie »), et un horodatage relatif (« il y a 2 minutes »).
- **FR-034** : Le système DOIT fournir un composant `<AuditExportButton />` qui propose deux choix (CSV / JSON) et déclenche le téléchargement via `GET /api/audit/me/export`.
- **FR-035** : Le système DOIT fournir un composant `<AuditFilters />` qui expose les filtres (entité, source, période, recherche libre) et synchronise les query params avec l'URL (rafraîchissement F5 préservé).
- **FR-036** : Le système DOIT fournir un composable `composables/useAuditLog.ts` qui encapsule les appels HTTP et la pagination, et un store Pinia `stores/audit.ts` pour l'état local.
- **FR-037** : Le système DOIT respecter le mode sombre obligatoire (variantes `dark:` Tailwind) sur la page `/historique` et tous les composants liés.

#### Frontend Admin

- **FR-038** : Le système DOIT fournir une page Nuxt `pages/admin/audit/index.vue` (route `/admin/audit`) avec layout `admin` (layout admin de F02) qui affiche le log global filtrable par compte, utilisateur, entité, source, période.
- **FR-039** : Le système DOIT fournir une page Nuxt `pages/admin/audit/[accountId].vue` (route `/admin/audit/:accountId`) qui affiche le log d'un compte PME spécifique. L'ouverture de cette page (via `useAuditLog().fetchByAccount(id)` qui hit `GET /api/admin/audit/{account_id}`) déclenche côté backend l'enregistrement `view_admin`.
- **FR-040** : Le système DOIT respecter le mode sombre obligatoire et l'accent de couleur admin (rouge/orange F02) sur les pages admin/audit.

#### Garde-fous CI et documentation

- **FR-041** : Le système DOIT inclure un test CI `test_auditable_models_whitelist_complete` qui vérifie que tous les modèles déclarés métier dans `app/models/` (selon une whitelist `METIER_MODELS` partagée avec F02) appliquent le mixin `Auditable` ou figurent explicitement dans `EXEMPT_MODELS` avec une justification commentée. Si un nouveau modèle apparaît sans cette discipline, le test échoue.
- **FR-042** : Le système DOIT inclure un test pytest `test_audit_log_append_only_via_trigger` qui ouvre une session de base, exécute `UPDATE audit_log SET source_of_change='manual' WHERE id=...` puis `DELETE FROM audit_log WHERE id=...` et vérifie qu'une `ProgrammingError` ou équivalent est levée à chaque fois.
- **FR-043** : Le système DOIT inclure un test pytest `test_audit_log_isolation_via_rls` qui crée 2 PME, simule des mutations dans chacune, puis vérifie que la PME A n'accède jamais aux événements `audit_log` de la PME B (RLS).
- **FR-044** : Le système DOIT inclure un test pytest `test_source_of_change_propagation` qui vérifie : (a) une mutation via API REST PME (`PATCH /api/companies/me`) produit `source_of_change="manual"`, (b) une mutation via tool LangChain (`update_company_profile` invoqué dans un nœud) produit `source_of_change="llm"`, (c) un endpoint admin produit `source_of_change="admin"`.
- **FR-045** : Le système DOIT inclure un test pytest `test_view_admin_recorded` qui vérifie qu'un appel `GET /api/admin/audit/{account_id}` produit bien une ligne `audit_log` `action="view_admin"` côté PME.
- **FR-046** : Le système DOIT livrer une documentation `docs/audit-log.md` couvrant : modèle de menaces, schéma `audit_log`, requêtes SQL communes (« reconstituer l'historique d'une candidature »), format export CSV/JSON, limites MVP (RGPD vs append-only, pas de Merkle, pas de PDF signé), procédure pour rendre auditable un nouveau modèle.

### Key Entities

- **AuditLog** : événement d'audit immuable. Attributs principaux : identifiant unique (UUID), acteur (`user_id`), compte propriétaire (`account_id`), horodatage (`timestamp`), type d'entité (`entity_type`), identifiant d'entité (`entity_id`), action (`action` ENUM `create|update|delete|view_admin`), nom du champ muté (`field`, NULL pour `create`/`delete`/`view_admin`), valeur avant (`old_value` JSON, NULL admise), valeur après (`new_value` JSON, NULL admise), source du changement (`source_of_change` ENUM `manual|llm|import|admin`), métadonnées d'acteur (`actor_metadata` JSON optionnel : `tool_name`, `conversation_id`, `request_id`, `ip_address`, `user_agent`, `endpoint`). Relations : référence un `User` (acteur) et un `Account` (cible/propriétaire de la donnée). Aucun foreign key strict sur `entity_id` (l'entité référencée peut appartenir à n'importe laquelle des 9 tables `Auditable`).
- **Auditable (mixin)** : marqueur appliqué aux classes de modèles métier (CompanyProfile, FundApplication, ESGAssessment, ESGCriterionScore, CarbonAssessment, CarbonEmissionEntry, CreditScore, ActionPlan, ActionItem) qui active la capture automatique des mutations via le listener `before_flush`. N'introduit pas de colonne supplémentaire ; le mixin sert uniquement de marqueur typé pour l'introspection.
- **AuditContext (ContextVar)** : variable de contexte Python (`current_source_of_change: ContextVar[str] = ContextVar('current_source_of_change', default='manual')`) consultée par le mixin `Auditable` lors de l'écriture du log. Positionnée par les nœuds LangGraph (`set('llm')`), le middleware admin (`set('admin')`), les scripts d'import futurs (`set('import')`), et défaut `manual` partout ailleurs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des mutations sur les 9 modèles auditables produisent au moins une ligne `audit_log` correspondante (vérifié par tests d'intégration sur création/modification/suppression de chaque modèle).
- **SC-002** : 100 % des appels `UPDATE audit_log SET ...` et `DELETE FROM audit_log` exécutés par le rôle applicatif échouent (vérifié par test pytest dédié au trigger ET au permission DB).
- **SC-003** : 100 % des appels admin `GET /api/admin/audit/{account_id}` produisent une ligne `audit_log` `action="view_admin"` visible côté PME (vérifié par test E2E).
- **SC-004** : `source_of_change` correspond exactement au contexte d'invocation dans 100 % des cas (`manual` pour API REST PME, `llm` pour nœuds LangGraph, `admin` pour endpoints admin), vérifié par tests pytest paramétrés sur les 3 contextes.
- **SC-005** : 100 % des événements `audit_log` d'un compte sont invisibles depuis les autres comptes PME (RLS vérifiée par test d'isolation).
- **SC-006** : L'endpoint `GET /api/audit/me?page=1&limit=50` répond en moins de 500 ms P95 quand le compte contient 100 000 lignes `audit_log` (mesuré par benchmark CI dédié).
- **SC-007** : 100 % des exports `GET /api/audit/me/export?format=csv` produisent un fichier UTF-8 BOM lisible par Excel sans corruption des caractères français accentués (vérifié par test E2E qui décode le fichier).
- **SC-008** : 100 % des valeurs `old_value`/`new_value` dépassant 10 KB sont tronquées avec le marqueur `_truncated: true` et la valeur tronquée reste indexée et requêtable (vérifié par test unitaire de la fonction de troncature).
- **SC-009** : Couverture de tests sur le périmètre F03 (modèle `audit_log`, mixin `Auditable`, ContextVar, services PME et admin, endpoints, frontend) au minimum 85 % (mesuré par pytest-cov backend et vitest --coverage frontend).
- **SC-010** : Aucune régression de performance supérieure à 5 ms par mutation sur les 5 endpoints les plus chauds qui touchent un modèle auditable (chat, dashboard mutations, applications create, esg score update, profile update), mesurée par benchmark avant/après activation du mixin.
- **SC-011** : 100 % des pages frontend introduites par F03 (`/historique`, `/admin/audit`, `/admin/audit/:accountId`) incluent les variantes `dark:` Tailwind (vérifié par revue PR + scan automatisé du DOM en test E2E).
- **SC-012** : Le test E2E Playwright `frontend/tests/e2e/F03-audit-log.spec.ts` couvre 4 scénarios principaux : (a) édition manuelle du profil → audit `manual`, (b) création de candidature via LLM → audit `llm` avec diff complet, (c) consultation admin du compte PME → audit `view_admin` côté PME, (d) export CSV/JSON conforme.
- **SC-013** : 100 % des modèles métier déclarés dans `app/models/` (selon la whitelist `METIER_MODELS` héritée de F02) appliquent le mixin `Auditable` ou figurent dans `EXEMPT_MODELS` avec justification (vérifié par test CI `test_auditable_models_whitelist_complete`).
- **SC-014** : La documentation `docs/audit-log.md` est livrée et couvre les sections obligatoires : modèle de menaces, schéma `audit_log`, requêtes SQL communes, format export CSV/JSON, limites MVP, procédure pour rendre auditable un nouveau modèle.

## Assumptions

- **A1** : F03 hérite intégralement de F02 (multi-tenant + RLS + `get_current_admin` + `set_rls_context`). La policy `audit_log` réutilise les mêmes ContextVars de session PostgreSQL (`app.current_account_id`, `app.current_role`, `app.current_user_id`).
- **A2** : Le mixin `Auditable` repose sur les events SQLAlchemy `before_flush` au niveau de la `Session` (pas `Mapper`), ce qui est compatible avec l'usage `AsyncSession` du projet — les events sont déclenchés sur la session synchrone sous-jacente, et l'accès à `inspect(obj).attrs[...].history` est synchrone.
- **A3** : Les valeurs `old_value`/`new_value` sont sérialisées en JSON via `json.dumps(default=...)` qui gère `UUID`, `Decimal`, `datetime`, `date`, et fallback `str()` pour les autres types non-natifs.
- **A4** : La troncature à 10 KB est appliquée AVANT l'insertion (côté Python), pas via une contrainte SQL — cela évite les erreurs PostgreSQL côté insertion et permet de stocker un marqueur explicite.
- **A5** : Le `request_id` injecté dans `actor_metadata` provient de l'en-tête `X-Request-Id` ou est généré par un middleware FastAPI ; son existence est garantie par F02 ou F03 (à confirmer en plan).
- **A6** : Aucun rôle PostgreSQL `application_user` distinct n'est introduit en MVP F03 (cohérent avec la décision F02 « pas de rôle PostgreSQL séparé en MVP »). Les `REVOKE UPDATE, DELETE` s'appliquent au rôle existant utilisé par `database_url` ; si ce rôle est superuser/owner, la migration journalise un avertissement et le trigger reste la défense effective. La séparation de rôle est documentée comme évolution post-MVP.
- **A7** : Le format CSV utilise UTF-8 BOM (`﻿` en début) pour que Microsoft Excel reconnaisse l'encodage — lit correctement les accents français (é, è, ç, à, ù).
- **A8** : Les tools LangChain qui faisaient `db.commit()` direct sont migrés en F03 pour passer par les services métier (`CompanyService.update`, `FundApplicationService.create`, etc.) — ces services sont déjà en place ou créés à minima par F03 si nécessaires. La liste précise des tools à migrer est dans `plan.md`.
- **A9** : F03 introduit la migration Alembic `021_create_audit_log.py` avec `down_revision = '020_sources'` (cohérent avec la séquence `019_multitenant → 020_sources → 021_audit_log`).
- **A10** : Les tests E2E sont écrits en Playwright (`frontend/tests/e2e/F03-audit-log.spec.ts`) conformément à l'invariant projet « tests E2E Playwright exécutables ».
- **A11** : F03 est PRÉREQUIS pour F08 (PDF signé Ed25519 — l'audit log est référencé dans les rapports), F18 (logs et observabilité), et toute feature future qui touche aux entités auditées. La solidité du log et l'invariant d'intégrité priment sur la rapidité.
- **A12** : Aucun framework Redis/message broker n'est introduit ; tout reste synchrone via PostgreSQL (cohérent avec décision projet).
- **A13** : La page `/historique` n'inclut pas de diff visuel side-by-side en MVP — uniquement les valeurs textuelles avant/après. Le diff visuel est documenté comme évolution post-MVP.

## Dependencies

- **F02 (multi-tenant + RLS + roles + `get_current_admin`)** : DÉJÀ MERGÉ. F03 réutilise les ContextVars PostgreSQL (`app.current_account_id`, `app.current_role`, `app.current_user_id`) positionnées par `set_rls_context`, la dépendance FastAPI `get_current_admin`, le routeur `/api/admin/*`, le layout admin frontend.
- **F01 (sourçage + catalogue Source)** : DÉJÀ MERGÉ. Aucune dépendance fonctionnelle directe ; F03 ne mute pas le catalogue. Cohabite via la convention `# Aucun mixin Auditable sur les modèles catalogue (Source, EmissionFactor, ...)` documentée.

- **Stack matérielle prérequise** :
  - PostgreSQL 16 avec capacité d'exécuter des triggers et `RAISE EXCEPTION` (natif).
  - Possibilité de `REVOKE UPDATE, DELETE` sur le rôle applicatif (peut être no-op si superuser, journalisation prévue).
  - SQLAlchemy 2.x async avec events `before_flush` (utilisé dans le projet).
  - Alembic (déjà présent : 20 migrations existantes).

- **Features dépendantes en aval** : F08, F18, F20, F23, F24 (selon `.cc-deps.json`).
