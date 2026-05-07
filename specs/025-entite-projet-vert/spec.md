# Feature Specification: F06 — Entité Projet Vert (Module 1.3)

**Feature Branch**: `feat/F06-entite-projet-vert` (alias SpecKit `025-entite-projet-vert`)
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F06 — Modélisation de l'entité Projet Vert pour matérialiser le triangle conceptuel `Entreprise 1—N Projets 1—N Candidatures vers Offres = (Fonds × Intermédiaire)`. Aujourd'hui, `FundApplication` est rattaché directement à `user_id + fund_id + intermediary_id` ; aucune entité `Project` n'existe et la PME ne peut pas déclarer plusieurs projets verts distincts ni candidater au même projet sur plusieurs offres en parallèle. F06 introduit le modèle `Project` (account_id F02, Auditable F03, Money typed F04 sur `target_amount`), la table de jointure `project_documents`, ajoute `project_id` à `fund_applications` (NULL transitoire puis NOT NULL après backfill), 7 tools LangChain (`list_projects`, `get_project`, `create_project`, `update_project`, `delete_project`, `duplicate_project`, `link_document_to_project`), refactor des pages profil (`/profile/company` + `/profile/projects/[index|new|[id]|[id]/duplicate]`), 8 composants Vue (`ProjectCard`, `ProjectForm`, `ProjectList`, `ProjectImpactBadges`, `ProjectStatusSelector`, `ProjectMap`, `DuplicateProjectModal`), composable `useProjects.ts`, store `projects.ts`. Le LLM peut proposer la création de projets pré-remplis depuis le chat (avec confirmation `ask_yes_no` via F10 — fallback `ask_interactive_question` F18 disponible aujourd'hui)."

## Clarifications

### Session 2026-05-07

- Q: Multi-valeurs de `objective_env` (mitigation, adaptation, biodiversity, etc.) — colonne `ARRAY` PostgreSQL ou table satellite `project_objectives` ? → A: **Colonne JSONB `objective_env` typée comme tableau de strings** (ex. `["renewable_energy", "mitigation"]`), avec un CHECK contrainte applicatif sur les valeurs autorisées dans `app/models/project.py` (validateur Pydantic strict côté API). Rationale : pas de jointure supplémentaire pour un attribut consulté à chaque affichage de carte projet, JSONB indexable via GIN si besoin post-MVP, dégradation gracieuse SQLite tests via `JSON`.
- Q: Stratégie de backfill pour les `FundApplication` orphelines existantes lors de la migration `025_create_projects` ? → A: **Backfill par génération automatique d'un `Project` minimal par application** avec `name = "Projet hérité — <fund.name> (<created_at YYYY-MM>)"` (tronqué à 200 chars), `description = application.sections.summary` si présent sinon `"Projet créé automatiquement lors de la migration F06."`, `status = mapping_app_status_to_project_status(app.status)` (cf. data-model § 3.4), `objective_env = []`, `auto_generated = true`, `account_id = app.account_id`. Aucune `FundApplication` ne reste sans `project_id` ; la migration applique ensuite `NOT NULL` en deuxième temps. Une PME peut renommer/affiner ces projets a posteriori.
- Q: Garde-fou suppression d'un `Project` avec candidatures actives — refus dur ou paramètre `force=True` ? → A: **Refus par défaut + paramètre `force=true` côté API/tool LangChain** quand l'utilisateur (ou le LLM avec confirmation `ask_yes_no` / `ask_interactive_question`) confirme explicitement. Le tool `delete_project` retourne `{ok: false, blocked_by: [{application_id, fund_name, status}], hint: "force=true pour confirmer"}` quand `force=False` et applications `status NOT IN (rejected, accepted, cancelled)`. Avec `force=True` : `Project.status = 'cancelled'` (soft-delete logique conservé pour traçabilité audit log F03), suppression réelle en base de données différée à un job post-MVP. Cette stratégie évite les pertes de candidatures actives liées à un projet supprimé par mégarde.
- Q: Statut autorisé pour la duplication d'un `Project` — duplique-t-on le `status` source ou force-t-on `draft` ? → A: **Force `status = 'draft'`** sur la copie ; tous les autres champs du modèle Project sont copiés (description, objective_env, maturity, target_amount Money, duration_months, financing_structure, expected_impact_*) ; le `name` reçoit le suffixe `" (copie)"` (ou `new_name` fourni par l'appelant), `auto_generated = false`, les `project_documents` ne sont PAS copiés (l'utilisateur peut les re-lier explicitement). Rationale : éviter la confusion d'avoir 2 projets simultanément dans le statut `seeking_funding` ou `funded` après duplication.
- Q: Coordonnées géographiques `location_coordinates` — PostGIS POINT obligatoire dès F06 ou différé ? → A: **Différé post-MVP via story de F11 (`show_map`)**. F06 ajoute uniquement `location_country: Char(2)` (ISO 3166-1 alpha-2, validation Pydantic) et `location_region: String(100)` (ville/région libre, défaut NULL). La colonne `location_coordinates` n'est PAS créée en F06 ; elle sera ajoutée par une migration ultérieure (F11) avec extension `postgis` activée à ce moment-là. Cette stratégie évite d'imposer l'extension PostGIS dans la stack PostgreSQL de F06.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Modéliser plusieurs projets verts distincts pour une même entreprise (Priority: P1)

Une PME ivoirienne (déjà profilée via Module 1.2) déclare avoir trois projets verts distincts en cours : (1) installer 50 kWc de panneaux solaires sur l'usine principale, (2) remplacer 200 lampes halogènes par des LED basse consommation, (3) mettre en place un compostage des déchets organiques. Elle accède à la page `/profile/projects/new` depuis la sidebar « Mes Projets » et crée trois projets séparés, chacun avec son propre nom, description, objectif environnemental (`renewable_energy`, `circular_economy`), maturité (`pilot`, `pre_feasibility`), montant cible Money (XOF), impacts attendus (tCO2e évités, emplois créés). La page `/profile/projects` affiche les 3 cartes avec badges visuels et statuts.

**Why this priority** : Sans projet distinct, le matching reste « PME ↔ Fonds » au lieu de « Projet ↔ Offre ». Une PME ne peut pas distinguer ses ambitions, ce qui rend le matching sectoriel imprécis et bloque l'invariant clé du brainstorming (`Entreprise 1—N Projets`). Cette user story est P1 car elle débloque toutes les fonctionnalités aval (matching, candidature, plan d'action multi-projets).

**Independent Test** : Se connecter en tant que PME, accéder à `/profile/projects/new`, créer un projet « Panneaux solaires usine » avec `objective_env=['renewable_energy']`, `target_amount={amount:'50000000', currency:'XOF'}`, `expected_impact_tco2e=120`, vérifier en base que la ligne `projects` existe avec `account_id` correct et que l'audit log F03 contient une entrée `create` avec `source_of_change='manual'`. Répéter pour 2 autres projets et vérifier que `/profile/projects` affiche les 3 cartes triées par `created_at DESC`.

**Acceptance Scenarios** :

1. **Given** une PME authentifiée avec un profil entreprise existant, **When** elle accède à `/profile/projects/new` et soumet un formulaire `ProjectForm` valide (name, description, objective_env multi-select, maturity, target_amount Money, expected_impact_tco2e), **Then** le projet est créé avec `account_id = current_account_id`, `status = 'draft'`, `auto_generated = false`, l'audit log F03 contient une ligne `action='create' source_of_change='manual' entity_type='projects'` et l'utilisateur est redirigé vers `/profile/projects/[id]`.
2. **Given** une PME ayant déjà 3 projets enregistrés, **When** elle accède à `/profile/projects`, **Then** la page affiche 3 `ProjectCard` triées par `created_at DESC`, chaque card affiche le nom, le badge de statut, le badge de maturité, le montant cible via `<MoneyDisplay>` (F04), les badges d'objectif via `<ProjectImpactBadges>`, le compteur de candidatures rattachées (vide à ce stade) et un bouton « Voir candidatures » désactivé (vu qu'il n'y en a pas).
3. **Given** une PME éditant un projet existant via `/profile/projects/[id]` (formulaire `ProjectForm` en mode `mode='edit'`), **When** elle modifie `expected_jobs_created` de 5 à 8 et soumet, **Then** la ligne projet est mise à jour, l'audit log F03 contient une ligne `action='update' field='expected_jobs_created' old_value=5 new_value=8 source_of_change='manual'`.
4. **Given** une PME PME-A et une PME PME-B sur deux comptes distincts, **When** PME-A appelle `GET /api/projects`, **Then** elle ne voit que ses propres projets (RLS PostgreSQL F02 filtre via `app.current_account_id`) ; PME-B voit ses propres projets uniquement ; aucune fuite cross-tenant.

---

### User Story 2 — Candidater à plusieurs offres en parallèle pour le même projet (Priority: P1)

Une PME possède un projet « Panneaux solaires usine » (déjà créé via US1). Elle souhaite candidater simultanément à 2 fonds verts différents pour ce même projet : GCF via l'intermédiaire BOAD, et SUNREF via l'intermédiaire Ecobank. Aujourd'hui, `FundApplication` est rattaché à `user_id + fund_id + intermediary_id` mais pas à un projet — elle ne peut pas distinguer plusieurs candidatures pour le même projet ni voir les candidatures rattachées au projet sur sa page `/profile/projects/[id]`.

**Why this priority** : C'est le cas d'usage central du brainstorming Module 3 (« plusieurs candidatures parallèles pour le même projet »). Sans `FundApplication.project_id`, le système est incapable de regrouper les candidatures par projet et donc de présenter la vue « pipeline projet → offres ». Cette user story dépend strictement de US1 et conditionne F09 (matching projet-offre).

**Independent Test** : Créer un projet « Panneaux solaires » via US1, depuis `/financing` lancer 2 candidatures vers 2 fonds différents en sélectionnant systématiquement le projet (via dropdown ou tool `create_fund_application(fund_id, project_id, ...)`), vérifier en base que les 2 lignes `fund_applications` partagent le même `project_id` et que `/profile/projects/[id]/applications` (ou `/applications?project_id=X`) liste les 2 candidatures.

**Acceptance Scenarios** :

1. **Given** une PME avec un `Project` `prj-A` existant, **When** elle déclenche la création d'une `FundApplication` (via UI `/financing/[fund_id]` → bouton « Candidater » ou via tool LLM `create_fund_application(fund_id, project_id=prj-A, target_type='intermediary_bank', intermediary_id=...)`), **Then** la ligne `fund_applications` est créée avec `project_id=prj-A` non null, `account_id = current_account_id`, et l'audit log F03 contient une entrée `create` sur `fund_applications` avec le diff incluant `project_id`.
2. **Given** une PME avec 2 `FundApplication` rattachées au même `Project` `prj-A`, **When** elle accède à `GET /api/projects/{prj-A}/applications`, **Then** la réponse contient les 2 applications triées par `created_at DESC`, avec leurs statuts respectifs et les noms de fonds.
3. **Given** une `FundApplication` créée pré-F06 sans `project_id`, **When** la migration `025_create_projects` est appliquée, **Then** un `Project` minimal est créé pour cette application (`auto_generated=true`, `name='Projet hérité — <fund.name> (<created_at YYYY-MM>)'`, `status` mappé selon `application.status`), l'application est liée à ce projet (`project_id` non null), et la migration applique ensuite `NOT NULL` sur `fund_applications.project_id`.
4. **Given** une PME ayant un projet `auto_generated=true` issu de la migration backfill, **When** elle accède à la liste `/profile/projects`, **Then** la card affiche un badge « Projet généré automatiquement — à compléter » et un bouton « Modifier maintenant » qui ouvre `/profile/projects/[id]` ; aucune candidature n'est perdue ni dupliquée.

---

### User Story 3 — Le LLM propose la création d'un projet vert pré-rempli depuis le chat (Priority: P2)

Une PME mentionne dans le chat : « J'ai un atelier où on utilise des générateurs diesel pour pallier les coupures électriques. » L'assistant identifie un projet vert potentiel (« remplacement par énergie solaire ») et propose à l'utilisateur de le créer pré-rempli (name, description, objective_env=`['renewable_energy', 'mitigation']`, maturity=`ideation`, target_amount estimé sourcé via `cite_source`). L'utilisateur valide via le widget interactif F18 (`ask_interactive_question` avec QCU `oui / non / je veux ajuster`) et le projet est créé. L'audit log F03 contient `source_of_change='llm'` (pas `manual`).

**Why this priority** : Cas d'usage différencié pour la « conversation-driven UX » (principe constitutionnel III) : le LLM agit comme co-pilote proactif. C'est P2 car les US1 et US2 couvrent déjà la création manuelle ; cette story enrichit l'expérience mais n'est pas bloquante pour le MVP.

**Independent Test** : Lancer une conversation avec « J'ai un atelier où on utilise des générateurs diesel… », observer que le LLM appelle `ask_interactive_question` (F18) avec une QCU « voulez-vous créer un projet pré-rempli ? », répondre `oui`, observer ensuite l'appel à `create_project(name='Remplacement générateurs diesel par énergie solaire', objective_env=['renewable_energy','mitigation'], maturity='ideation', ...)`, vérifier que la ligne `projects` est créée avec l'audit log F03 montrant `source_of_change='llm'` et que le widget retourne un `<SourceLink>` vers la source ADEME / IEA citée pour le potentiel d'économies CO2e.

**Acceptance Scenarios** :

1. **Given** un utilisateur en conversation libre (`/chat` ou `chat_global`), **When** il déclare une activité non encore modélisée comme projet (générateurs diesel, lampes halogènes, atelier de tri non modernisé, etc.), **Then** l'assistant détecte le potentiel projet vert et appelle `ask_interactive_question` (F18) avec une QCU `["Oui, crée le projet pré-rempli", "Je veux ajuster d'abord", "Non, pas maintenant"]`.
2. **Given** la PME répond « Oui, crée le projet pré-rempli », **When** le LLM appelle `create_project(...)` avec les valeurs déduites du contexte conversation + profil, **Then** la ligne `projects` est créée, l'audit log F03 contient `action='create' source_of_change='llm' entity_type='projects' new_value` complet ; chaque chiffre cité par le LLM (target_amount estimé, expected_impact_tco2e estimé) est lié à une `Source` `verified` via `cite_source` (F01) ou marqué `unsourced` via `flag_unsourced`.
3. **Given** la PME répond « Je veux ajuster d'abord », **When** le widget se résout, **Then** le LLM répond en texte avec un brouillon du projet et invite la PME à ouvrir `/profile/projects/new` avec un brouillon pré-rempli côté frontend (params `?prefill=...` lus par `ProjectForm`).
4. **Given** un projet créé via le LLM (`source_of_change='llm'`), **When** la PME accède à `/profile/projects`, **Then** la card du projet affiche un badge `Créé par l'IA` (couleur indigo/violet, dark mode complet) cliquable qui ouvre l'historique audit log filtré sur cette entité (lien vers `/historique?entity_type=projects&entity_id=...`).

---

### User Story 4 — Dupliquer un projet existant pour préparer un projet similaire sur un autre site (Priority: P2)

Une PME possède un projet « Panneaux solaires Site A » (`status='funded'`, financement obtenu). Elle veut préparer un projet similaire sur le Site B et gagner du temps en dupliquant le projet existant pour ensuite ajuster `name`, `location_region`, `target_amount`. Elle accède à `/profile/projects/[id]/duplicate`, le formulaire pré-rempli s'affiche, elle modifie le nom en « Panneaux solaires Site B », ajuste `location_region='Bouaké'` et `target_amount` à 30 M XOF, soumet ; le nouveau projet est créé en `status='draft'` avec tous les autres champs copiés.

**Why this priority** : Productivité utilisateur. Ce cas d'usage est P2 car non bloquant pour le MVP mais fortement attendu dans l'expérience produit (économie de saisie pour PME multi-sites).

**Independent Test** : Créer un projet via US1, accéder à la page de duplication, soumettre avec un nouveau nom, vérifier que la ligne dupliquée existe en base avec un nouvel `id`, le `name` modifié, le `status='draft'`, et tous les autres champs identiques au projet source ; vérifier que les `project_documents` du projet source NE SONT PAS dupliqués (table de jointure non copiée).

**Acceptance Scenarios** :

1. **Given** un projet source `prj-A` complet (avec `target_amount`, `expected_impact_*`, `objective_env`, etc.), **When** la PME appelle `POST /api/projects/{prj-A}/duplicate` avec `new_name='Projet B'`, **Then** un nouveau projet `prj-B` est créé avec un nouvel `id`, `name='Projet B'`, `status='draft'`, `auto_generated=false`, tous les champs métier copiés (description, objective_env, maturity, target_amount Money, etc.), audit log F03 contient une ligne `create` avec `actor_metadata={'duplicated_from': 'prj-A'}`.
2. **Given** un projet `prj-A` avec 2 entrées dans `project_documents`, **When** `prj-A` est dupliqué en `prj-B`, **Then** `project_documents` ne contient PAS d'entrée pour `prj-B` (à charge de la PME de re-lier les documents pertinents) ; un message UI indique « Les documents associés ne sont pas copiés. Liez-les manuellement si pertinent. ».
3. **Given** un projet `prj-A` avec `status='funded'`, **When** la PME le duplique sans préciser `new_name`, **Then** le nouveau projet reçoit `name='<prj-A.name> (copie)'` (suffixe automatique tronqué à 200 chars si dépassement) et `status='draft'` (force `draft` quel que soit le statut source).
4. **Given** un appel via le tool LangChain `duplicate_project(project_id='prj-A', new_name='Projet B')`, **When** le tool s'exécute, **Then** le comportement est identique à l'appel API REST (même contrat) ; l'audit log F03 trace `source_of_change='llm'`.

---

### Edge Cases

- **Suppression d'un projet avec applications actives** : tentative `DELETE /api/projects/{id}` (ou tool `delete_project(project_id, confirm=False)`) avec `FundApplication.status NOT IN (rejected, accepted, cancelled)` → réponse `409 Conflict` avec liste des applications bloquantes ; nécessite `force=true` (soft-delete : `status='cancelled'` côté projet, audit log F03).
- **Création d'un projet sans pays renseigné** : `location_country=NULL` autorisé (PME pas encore profilée géographiquement) ; le LLM peut suggérer de compléter ; aucune erreur.
- **`target_amount` partiel (amount sans currency ou inverse)** : Pydantic strict refuse ; l'un des deux NULL implique l'autre NULL (validateur croisé `target_amount_pair_consistency_chk`).
- **`objective_env` vide ou invalide** : un tableau vide est autorisé (projet en cours de définition) ; un libellé non répertorié dans la whitelist `['mitigation','adaptation','biodiversity','circular_economy','water','renewable_energy','sustainable_agriculture','mixed']` est rejeté côté Pydantic et CHECK applicatif.
- **Concurrence sur `duplicate_project`** : si 2 utilisateurs (même compte multi-utilisateur F02) dupliquent simultanément le même projet source, les 2 lignes sont créées indépendamment (UUID PK distincts) ; pas de verrou applicatif, pas d'unicité sur `name` (on autorise les doublons de nom).
- **Migration backfill avec une `FundApplication` orpheline `account_id=NULL`** : la migration F02 (`019_multitenant_and_roles`) a déjà rétroactivement renseigné `account_id` ; aucune `FundApplication` ne peut survivre sans `account_id` post-F02 ; la migration F06 utilise donc `app.account_id` direct sans nouvelle hypothèse.
- **Duplication d'un projet `auto_generated=true`** : autorisée ; le nouveau projet hérite de `auto_generated=false` (la PME prend la main).
- **Tool LLM `create_project` sans `target_amount`** : autorisé (champ NULL) ; le LLM est explicitement instruit de ne JAMAIS inventer un montant si la PME ne l'a pas mentionné ; flag_unsourced en cas de ratio générique.
- **Soft-delete via `force=true`** : ne supprime pas la ligne en BDD ; passe `status='cancelled'` ; les `FundApplication` rattachées conservent leur `project_id` (traçabilité) ; `/profile/projects` filtre les statuts `cancelled` par défaut, un onglet « Archivés » expose les projets soft-deleted.
- **Validateur source obligatoire post-tool LLM** : si `create_project` fournit `target_amount` ou `expected_impact_tco2e` non null sans `cite_source` accompagnant, le validator `source_required.py` (F01) déclenche un retry, puis substitue par fallback texte « [montant à confirmer par la PME] » et passe les champs à NULL si la PME ne les valide pas.

## Requirements *(mandatory)*

### Functional Requirements

#### Modèle de données

- **FR-001** : Le système DOIT créer la table `projects` avec les colonnes : `id` (UUID PK), `account_id` (UUID FK accounts.id NOT NULL, multi-tenant F02), `name` (String(200) NOT NULL), `description` (Text), `objective_env` (JSONB ou JSON ; tableau de strings parmi la whitelist), `maturity` (String(32) parmi `ideation/pre_feasibility/pilot/scale/replication`), `status` (String(32) parmi `draft/seeking_funding/funded/in_execution/closed/cancelled`), `target_amount_amount` (Numeric(20,2) NULL, Money typed F04), `target_amount_currency` (Char(3) NULL parmi `XOF/EUR/USD/GBP/JPY`), `duration_months` (Integer NULL), `financing_structure` (String(32) parmi `subvention/pret_concessionnel/equity/blending/mixte` NULL), `expected_impact_tco2e` (Numeric(20,4) NULL), `expected_jobs_created` (Integer NULL ≥ 0), `expected_beneficiaries` (Integer NULL ≥ 0), `expected_hectares_restored` (Numeric(10,2) NULL ≥ 0), `expected_other_impacts` (JSONB NULL), `location_country` (Char(2) NULL ISO 3166-1 alpha-2), `location_region` (String(100) NULL), `auto_generated` (Boolean NOT NULL default `false`), `created_at` (TimestampTZ default `now()`), `updated_at` (TimestampTZ on update).
- **FR-002** : Le système DOIT créer la table `project_documents` avec : `id` (UUID PK), `project_id` (UUID FK projects.id ON DELETE CASCADE), `document_id` (UUID FK documents.id ON DELETE CASCADE), `doc_type` (String(32) parmi `feasibility_study/business_plan/impact_assessment/support_letter/other`), `created_at` (TimestampTZ default `now()`), avec UNIQUE constraint `(project_id, document_id)`.
- **FR-003** : Le système DOIT ajouter la colonne `project_id` (UUID FK projects.id) sur la table `fund_applications` ; la colonne EST INITIALEMENT `NULL`, peuplée par backfill (cf. FR-008), puis passée à `NOT NULL` dans la même migration en deuxième temps.
- **FR-004** : La table `projects` DOIT avoir 2 indexes composites `idx_projects_account_status (account_id, status)` et `idx_projects_account_maturity (account_id, maturity)` pour optimiser les listes filtrées.
- **FR-005** : La table `project_documents` DOIT avoir un index `idx_project_documents_project_id (project_id)` et un index `idx_project_documents_document_id (document_id)`.
- **FR-006** : Le modèle SQLAlchemy `Project` DOIT hériter de `Auditable` (F03), `UUIDMixin`, `TimestampMixin`, `Base` ; les mutations CRUD DOIVENT être tracées dans `audit_log` automatiquement via le listener `before_flush` F03.
- **FR-007** : `Project` DOIT être ajouté à la frozenset `AUDITABLE_MODELS` dans `app/core/auditable.py` ; `ProjectDocument` DOIT être ajouté à `EXEMPT_MODELS` (table de jointure pure, pas une entité métier — la traçabilité est sur Project).

#### Migration et backfill

- **FR-008** : La migration Alembic `025_create_projects` (down_revision=`024_carbone_mix_uemoa`) DOIT exécuter dans l'ordre : (1) CREATE TABLE `projects` + indexes, (2) CREATE TABLE `project_documents` + indexes + UNIQUE, (3) ALTER TABLE `fund_applications` ADD COLUMN `project_id` UUID NULL FK projects.id, (4) backfill : pour chaque `fund_applications` avec `project_id IS NULL`, INSERT INTO `projects` un projet auto-généré (cf. clarification Q2), UPDATE `fund_applications` SET `project_id` = nouveau projet, (5) ALTER TABLE `fund_applications` ALTER COLUMN `project_id` SET NOT NULL ; le downgrade est symétrique (DROP CONSTRAINT NOT NULL → DROP COLUMN project_id → DROP TABLE project_documents → DROP TABLE projects). Tous les triggers F02 RLS sont conservés et appliqués sur les nouvelles tables `projects` et `project_documents` (RLS ENABLE+FORCE + 2 policies `pme_access_own_account` + `admin_full_access`).
- **FR-009** : Le backfill DOIT être idempotent (réexécutable sans dommage : utilisation de `WHERE fund_applications.project_id IS NULL`) et logger par stdout le nombre de projets auto-générés.
- **FR-010** : Les projets auto-générés (`auto_generated=true`) DOIVENT pouvoir être listés via un filtre dédié dans l'API REST (`GET /api/projects?auto_generated=true`) afin que la PME les revue après migration.

#### API REST

- **FR-011** : Le système DOIT exposer `GET /api/projects` qui retourne la liste paginée (default `page=1, limit=25`) des projets de l'utilisateur (filtré par RLS via `account_id`), avec filtres `status`, `maturity`, `objective_env`, `auto_generated`, tri par défaut `created_at DESC`.
- **FR-012** : Le système DOIT exposer `GET /api/projects/{id}` qui retourne le projet complet incluant la liste des `project_documents` associés (`documents` joints) et le compteur de `fund_applications` actives rattachées.
- **FR-013** : Le système DOIT exposer `POST /api/projects` qui accepte un `ProjectCreate` Pydantic v2 strict, vérifie que `account_id = current_account_id` (via `get_current_user`), crée la ligne et retourne `ProjectRead`.
- **FR-014** : Le système DOIT exposer `PATCH /api/projects/{id}` qui accepte un `ProjectUpdate` partiel, vérifie que le projet appartient au compte (RLS), et met à jour les champs fournis non null ; aucun champ `id`, `account_id`, `auto_generated`, `created_at` n'est modifiable.
- **FR-015** : Le système DOIT exposer `DELETE /api/projects/{id}?force=false` ; sans `force=true` et avec `FundApplication.status NOT IN ('rejected','accepted','cancelled')` rattachée, retourne `409 Conflict` avec la liste des applications bloquantes ; avec `force=true`, le projet passe en `status='cancelled'` (soft-delete) et l'audit log F03 trace l'opération.
- **FR-016** : Le système DOIT exposer `POST /api/projects/{id}/duplicate` qui accepte `{new_name?: str}`, copie les champs métier (sauf `id`, `created_at`, `updated_at`, `auto_generated`, `project_documents`), force `status='draft'`, applique le suffixe `' (copie)'` si `new_name` absent, et retourne le nouveau `ProjectRead`.
- **FR-017** : Le système DOIT exposer `GET /api/projects/{id}/applications` qui retourne la liste des `fund_applications` rattachées au projet, avec leurs statuts et noms de fonds.

#### Tools LangChain

- **FR-018** : Le module `app/graph/tools/project_tools.py` DOIT exposer 7 tools LangChain Pydantic-validated :
  - `list_projects() -> list[ProjectSummary]`
  - `get_project(project_id: UUID) -> ProjectDetail`
  - `create_project(name: str, description: str, objective_env: list[str], maturity: str, target_amount: Money | None, ..., status: str = 'draft') -> ProjectDetail`
  - `update_project(project_id: UUID, fields: dict) -> ProjectDetail`
  - `delete_project(project_id: UUID, force: bool = False) -> DeleteResult`
  - `duplicate_project(project_id: UUID, new_name: str | None = None) -> ProjectDetail`
  - `link_document_to_project(project_id: UUID, document_id: UUID, doc_type: str) -> ProjectDocumentRead`
- **FR-019** : Les 7 tools DOIVENT être ajoutés à `MODULE_TOOL_MAPPING['chat']` et `PAGE_TOOL_MAPPING['profile']` + nouvelle entrée `PAGE_TOOL_MAPPING['profile_projects']` dans `tool_selector_config.py` (avec respect de la borne `MAX_TOOLS_PER_TURN = 14` ; 5/10 max par page sélectionnés selon contexte).
- **FR-020** : Le tool `delete_project` AVEC `force=False` DOIT vérifier l'existence d'applications actives ; en cas d'applications bloquantes, il DOIT retourner un payload exploitable par le LLM pour appeler `ask_interactive_question` (F18 — fallback de F10 `ask_yes_no`) afin de demander confirmation à la PME.
- **FR-021** : Le tool `create_project` DOIT respecter l'invariant F01 sourçage : si `target_amount` ou `expected_impact_tco2e` non null sont fournis, le LLM DOIT accompagner la création d'un appel `cite_source(source_id)` ou `flag_unsourced(reason)` ; le validator `source_required.py` (F01) post-tour vérifie cette discipline.

#### Frontend

- **FR-022** : Le frontend DOIT créer la page `pages/profile.vue` en page index avec navigation onglets vers `/profile/company` (existant, contenu déplacé) et `/profile/projects` (nouvel onglet) ; chaque onglet conserve son URL canonique pour le routage profond.
- **FR-023** : Le frontend DOIT créer 4 sous-pages : `pages/profile/projects/index.vue` (liste cards + filtres + pagination), `pages/profile/projects/new.vue` (création), `pages/profile/projects/[id].vue` (édition), `pages/profile/projects/[id]/duplicate.vue` (duplication avec formulaire pré-rempli).
- **FR-024** : Le frontend DOIT créer 7 composants Vue dans `components/projects/` (sans préfixe de dossier en autoimport conformément à `pathPrefix: false`) : `ProjectCard.vue`, `ProjectForm.vue` (création + édition mutualisés via prop `mode`), `ProjectList.vue`, `ProjectImpactBadges.vue`, `ProjectStatusSelector.vue`, `DuplicateProjectModal.vue`, `ProjectFilters.vue`. La spec Module 1.3 mentionne `ProjectMap.vue` (Leaflet) — ce composant est DIFFÉRÉ POST-MVP via F11 (`show_map`).
- **FR-025** : Tous les composants Vue créés DOIVENT être compatibles dark mode (`dark:` Tailwind sur fonds, textes, bordures, hover) conformément au CLAUDE.md.
- **FR-026** : Le frontend DOIT créer le composable `composables/useProjects.ts` exposant `listProjects(filters)`, `getProject(id)`, `createProject(payload)`, `updateProject(id, fields)`, `deleteProject(id, force)`, `duplicateProject(id, newName)`, `linkDocument(projectId, documentId, docType)`, `getProjectApplications(id)` ; chaque méthode appelle l'API REST via `useFetchAuth` et gère erreurs/loading.
- **FR-027** : Le frontend DOIT créer le store Pinia `stores/projects.ts` avec état `{projects: ProjectSummary[], currentProject: ProjectDetail | null, filters: ProjectFilters, loading: boolean, error: string | null}`, mutations dérivées du composable, et getters `activeProjects`, `archivedProjects`, `byStatus`.
- **FR-028** : La sidebar de navigation DOIT inclure un lien « Mes Projets » vers `/profile/projects` (icône arbre/feuille verte) ; le badge compte les projets actifs (statut ≠ `cancelled`/`closed`).

#### Intégration LLM

- **FR-029** : Le module `backend/app/api/chat.py` DOIT renommer `_load_profile_for_state` en `_load_full_context_for_state` (ou ajouter une fonction sœur `_load_projects_for_state`) qui charge le profil entreprise ET la liste des projets actifs (statut `seeking_funding`, `funded`, `in_execution`) ; le résultat est injecté dans le state LangGraph pour que le LLM ait conscience des projets existants à chaque tour.
- **FR-030** : Les prompts `app/prompts/application.py` et `app/prompts/financing.py` DOIVENT être mis à jour pour mentionner explicitement la sélection d'un projet avant la candidature : « Avant de créer un dossier de candidature, identifiez le projet de la PME concerné par cette candidature (via `list_projects`). Si aucun projet n'existe, proposez de le créer via `ask_interactive_question` puis `create_project` avant tout autre chose. »
- **FR-031** : Le prompt système (cantonné à `app/prompts/system.py`) NE DOIT PAS être modifié dans cette feature (zone interdite en parallèle) ; le contexte projets est injecté dans le state via FR-029, pas dans le prompt système global.
- **FR-032** : Le `chat_node` DOIT recevoir la liste des projets via le state (et non via injection prompt), et le tool `list_projects` est exposé dans `MODULE_TOOL_MAPPING['chat']` afin que le LLM puisse interroger la base à tout moment.

#### Sécurité, audit log et sourçage

- **FR-033** : Toutes les routes API REST DOIVENT être protégées par `Depends(get_current_user)` et appliquer la RLS PostgreSQL F02 (variable de session `app.current_account_id`) ; aucun bypass cross-tenant possible.
- **FR-034** : Toutes les mutations passant par les tools LangChain DOIVENT s'exécuter dans le scope `source_of_change_scope('llm')` (déjà géré par les nœuds LangGraph décorés `@_with_llm_source` F03) ; le diff field-level est tracé automatiquement dans `audit_log`.
- **FR-035** : Le tool `create_project` DOIT injecter dans `actor_metadata` du `audit_log` le champ `tool_name='create_project'` et `conversation_id` quand disponible (cohérent avec le pattern F03).
- **FR-036** : Le tool `delete_project` AVEC `force=true` DOIT logger un événement structuré INFO `project_force_deleted` avec `{project_id, account_id, blocked_by_count, user_id}` pour observabilité post-MVP.

### Key Entities *(include if feature involves data)*

- **Project** : entité principale représentant un projet vert d'une PME. Multi-tenant (account_id F02), Auditable (F03), Money typed (F04). Champs : nom, description, objectif environnemental (multi), maturité, statut, montant cible Money, durée, structure financement, impacts attendus (tCO2e, emplois, bénéficiaires, hectares, autres JSONB), localisation (pays + région), flag `auto_generated` pour différencier les projets issus de la migration backfill.
- **ProjectDocument** : table de jointure entre `projects` et `documents`. Spécifie le `doc_type` (feasibility_study, business_plan, impact_assessment, support_letter, other). UNIQUE (project_id, document_id). Pas Auditable (table technique).
- **FundApplication (refactor)** : ajout du champ `project_id` (UUID FK projects.id NOT NULL après backfill). Permet de regrouper les candidatures par projet et de matérialiser le triangle conceptuel.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des `FundApplication` existantes au moment de la migration `025_create_projects` ont un `project_id` non null après backfill (vérifiable par `SELECT COUNT(*) FROM fund_applications WHERE project_id IS NULL` qui retourne 0).
- **SC-002** : Une PME peut créer 5 projets distincts via UI en moins de 60 secondes, chaque projet immédiatement listé dans `/profile/projects`.
- **SC-003** : Le LLM peut créer un projet via le tool `create_project` en 1 tour de conversation après confirmation `ask_interactive_question` ; le résultat est immédiatement visible dans le state LangGraph (FR-029).
- **SC-004** : Le RLS PostgreSQL F02 isole correctement les projets : un test cross-tenant `pytest tests/integration/test_project_rls.py` couvre 5 cas (PME-A liste / récupère / modifie / supprime / duplique → toutes les opérations sur PME-B échouent en 0 résultat ou 404).
- **SC-005** : L'audit log F03 capture 100 % des mutations Project (create, update, delete) avec le bon `source_of_change` (manual UI / llm / admin) ; vérifié par `pytest tests/integration/test_project_audit.py` (3 cas : UI manual, tool LLM, admin).
- **SC-006** : Aucune régression sur les modules existants : les 1674 tests backend baseline F17 restent verts ; les 0 régression ; couverture du nouveau module `app/modules/projects/` ≥ 80 %.
- **SC-007** : Test E2E Playwright `frontend/tests/e2e/F06-entite-projet-vert.spec.ts` exécute 4 scénarios indépendants (création UI + audit log, création LLM tool + audit log llm, duplication champ par champ, refus delete avec applications actives) et tous passent en CI.
- **SC-008** : Les composants Vue créés sont conformes dark mode (audit visuel sur 3 thèmes : light, dark, mixed) et accessibilité (audit aXe : 0 violation `serious` ou `critical`).
- **SC-009** : Round-trip Alembic `up/down/up` validé sur PostgreSQL local via `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` sans perte de données métier (les `fund_applications` retrouvent leur état initial après down + up).
- **SC-010** : Le tool `delete_project` retourne un payload exploitable (`{ok, blocked_by, hint}`) que le LLM peut utiliser pour invoquer `ask_interactive_question` ; vérifié par test unitaire `test_delete_project_blocked_by_applications.py`.
