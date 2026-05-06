# F06 — Entité Projet Vert (Module 1.3)

**Module(s) source(s)** : Module 1.3 (Profilage des Projets Verts), Module 1.2 (mapping UI Profil)
**Priorité** : P0 — bloquante pour le matching Projet ↔ Offre (F14) et la cohérence du modèle conceptuel
**Dépendances** : F01 (sources), F02 (multi-tenant), F03 (audit log)
**Estimation** : 2 sprints

## Contexte & motivation

Le brainstorming pose comme **modèle conceptuel structurant** : `Entreprise 1—N Projets 1—N Candidatures vers Offres = (Fonds × Intermédiaire)`.

**État actuel** :
- Aucune entité `Project` au modèle BDD : `ls backend/app/models/` ne contient pas `project.py`. `ls backend/app/modules/` ne contient pas `projects/`.
- `FundApplication` (= candidature) est lié directement à `user_id + fund_id + intermediary_id` — pas à un `project_id`.
- Page `/profile` (`frontend/app/pages/profile.vue`) ne contient que la vue Entreprise.
- Aucun composant `ProjectForm`, `ProjectCard`, `ProjectList`.
- Aucun store/composable Projets.
- Aucun tool LangChain `create_project`, `update_project`, `delete_project`.

**Conséquences** :
- Une PME ne peut pas modéliser plusieurs projets verts distincts (ex : "panneaux solaires + irrigation goutte-à-goutte" = 2 projets différents)
- Une candidature n'est pas liée à un projet → impossible de soumettre 2 candidatures différentes pour le même projet (multi-fonds en parallèle, point clé du brainstorming)
- Le matching reste "PME ↔ Fonds", pas "Projet ↔ Offre" (le projet est l'objet réel de la candidature)

## User stories

- **PME** : « Mon entreprise a 3 projets verts en cours : 1) installer 50 kWc panneaux solaires sur l'usine ; 2) remplacer 200 lampes halogènes par LED ; 3) mettre en place un compostage des déchets organiques. Je veux les modéliser séparément avec leurs propres montants, impacts attendus, statuts. »
- **PME** : « Pour mon projet "panneaux solaires", je veux candidater à 2 offres en parallèle : GCF via BOAD et SUNREF via Ecobank. Je dois pouvoir voir les 2 candidatures rattachées au même projet. »
- **PME** : « Le LLM a détecté que je parlais de "rénovation énergétique du siège" et m'a proposé de créer un projet vert pré-rempli. Je veux pouvoir valider, ajuster et l'enregistrer. »
- **PME** : « Je veux dupliquer un projet existant (ex : panneaux solaires Site A) pour préparer un projet similaire sur le Site B. »

## Périmètre fonctionnel

### Modèle `Project`

Table `projects` :
- `id: UUID PK`
- `account_id: UUID FK accounts.id NOT NULL` (multi-tenant F02)
- `name: str(200) NOT NULL`
- `description: text` (objectif environnemental détaillé)
- `objective_env: enum('mitigation', 'adaptation', 'biodiversity', 'circular_economy', 'water', 'renewable_energy', 'sustainable_agriculture', 'mixed')` (multi-valeurs autorisées via `objective_env: ARRAY` ou table satellite)
- `maturity: enum('ideation', 'pre_feasibility', 'pilot', 'scale', 'replication')`
- `status: enum('draft', 'seeking_funding', 'funded', 'in_execution', 'closed', 'cancelled')`
- `target_amount_amount: Numeric(20, 2) | null` (Money typed F04)
- `target_amount_currency: Char(3) | null`
- `duration_months: int | null`
- `financing_structure: enum('subvention', 'pret_concessionnel', 'equity', 'blending', 'mixte') | null`
- `expected_impact_tco2e: Numeric(20, 4) | null` (impact carbone attendu)
- `expected_jobs_created: int | null`
- `expected_beneficiaries: int | null`
- `expected_hectares_restored: Numeric(10, 2) | null`
- `expected_other_impacts: jsonb | null` (extensible)
- `location_country: str(2) | null` (ISO 3166-1 alpha-2)
- `location_region: str(100) | null`
- `location_coordinates: geography(POINT, 4326) | null` (pour `show_map`)
- `created_at: datetime`
- `updated_at: datetime`
- (versioning F04 : pas nécessaire ici, project = donnée user qui évolue)

Table `project_documents` (jointure) :
- `project_id: UUID`
- `document_id: UUID` (FK vers `documents` existant)
- Type : `feasibility_study`, `business_plan`, `impact_assessment`, `support_letter`, `other`

### Refactor `FundApplication` (candidature)

Ajouter à la table `fund_applications` :
- `project_id: UUID FK projects.id NULL` (NULL transitoirement durant la migration, NOT NULL après)
- (en F07, sera complété par `offer_id` qui remplacera `(fund_id, intermediary_id)`)

Migration : pour chaque `FundApplication` existante, créer un `Project` minimal (depuis le titre/description de l'application) si l'utilisateur n'en a pas, puis lier.

### Comportements proactifs LLM

Quand une activité est mentionnée dans le chat (Module 1.2 profilage entreprise), le LLM peut :
- **Identifier les projets verts potentiels** : « Vous avez parlé d'utiliser des générateurs diesel — un projet de remplacement par énergie solaire serait éligible. Je peux le créer ? » → tool `ask_yes_no` (F10) → `create_project`
- **Reformuler une activité existante** : transformer "j'ai un atelier de tri" en projet "Modernisation chaîne de tri" finançable
- **Découper un grand projet en sous-projets** adaptés à différentes offres (ex : projet à 5 M€ découpé en 3 sous-projets de 1.5 M€ chacun pour différents fonds)

### Vue Profil → Projets

Refactor `pages/profile.vue` en deux sous-onglets ou deux sous-routes :
- `pages/profile/company.vue` — édition Entreprise (existant)
- `pages/profile/projects/index.vue` — liste des projets (cards avec preview, filtres par statut/maturité)
- `pages/profile/projects/new.vue` — création
- `pages/profile/projects/[id].vue` — édition
- `pages/profile/projects/[id]/duplicate.vue` — duplication

Chaque card affiche :
- Nom, statut (badge), maturité, montant cible (`<MoneyDisplay>` F04)
- Type d'impact (badges visuels)
- Nb de candidatures rattachées (badge "3 candidatures actives")
- Bouton "Voir candidatures" → `/applications?project_id=X`

### Tools LangChain

Créer `backend/app/graph/tools/project_tools.py` :
- `list_projects() → list[ProjectSummary]`
- `get_project(project_id) → Project`
- `create_project(name, description, objective_env, maturity, target_amount_amount, target_amount_currency, ..., status='draft') → Project`
- `update_project(project_id, fields) → Project`
- `delete_project(project_id, confirm: bool) → DeleteResult` (avec garde-fou : si candidatures actives, demander confirmation `ask_yes_no`)
- `duplicate_project(project_id, new_name) → Project`
- `link_document_to_project(project_id, document_id, doc_type)`

Inclure les tools dans `tool_selector_config.py` :
- Visibles sur pages `/profile`, `/profile/projects/*`, `/applications`, `/applications/*`, `chat_global`
- 5/10 max par page

### Intégration avec audit log et sourçage

- Toutes les mutations Project passent par `Auditable` (F03)
- Si le LLM affirme un montant ou un impact carbone attendu, doit invoquer `cite_source` (F01) ou `flag_unsourced` (acceptable car estimation user)

### API REST

Module `backend/app/modules/projects/` :
- `GET /api/projects` (liste, filtres `status`, `maturity`, `objective_env`, paginée)
- `GET /api/projects/{id}`
- `POST /api/projects`
- `PATCH /api/projects/{id}`
- `DELETE /api/projects/{id}` (refuse si applications actives, sauf force=true)
- `POST /api/projects/{id}/duplicate`
- `GET /api/projects/{id}/applications` (candidatures liées)

## Hors-scope (post-MVP)

- Phasage projet (sous-tâches dans un projet)
- Dépendances inter-projets
- Versioning des projets (snapshot lors de la soumission de candidature, géré par F04 sur application)
- Workflow d'approbation interne du projet
- Partage de projet avec un consultant externe en read-only
- Export projet en PDF "fiche projet"
- Intégration avec un référentiel ODD pour mapping automatique objectifs → ODD

## Exigences techniques

### Backend

- Migration Alembic `023_create_projects.py` :
  - Table `projects` (avec `account_id`, RLS via F02)
  - Table `project_documents`
  - Ajouter `project_id` (NULL initialement) sur `fund_applications`
  - Backfill : créer un Project minimal pour chaque FundApplication orpheline, lier
  - NOT NULL sur `fund_applications.project_id` après backfill
- Modèle `app/models/project.py`, `app/models/project_document.py`
- Module `app/modules/projects/` : service, router, schemas
- Tools `app/graph/tools/project_tools.py` (7 tools)
- Mise à jour `tool_selector_config.py`
- Mise à jour `app/prompts/system.py` : injecter résumé projets actifs dans le contexte LLM (en plus du profil entreprise)
- Mise à jour `app/api/chat.py` : `_load_profile_for_state` doit aussi charger `projects` actifs et les injecter dans le state
- Mise à jour des prompts `application.py`, `financing.py` pour mentionner explicitement la sélection d'un projet avant la candidature
- Tests :
  - Test CRUD : create/read/update/delete projet
  - Test duplicate : champs dupliqués correctement, `name` modifié
  - Test guard delete : project avec FundApplication active → refus sauf force
  - Test multi-tenant : project visible uniquement par account
  - Test audit log : mutation crée un audit_log entry

### Frontend

- Pages `pages/profile/company.vue` et `pages/profile/projects/*`
- Refactor `pages/profile.vue` → page index avec navigation onglets vers ces deux sections
- Composants `components/projects/` :
  - `ProjectCard.vue`
  - `ProjectForm.vue` (création + édition)
  - `ProjectList.vue` (filtres + grid)
  - `ProjectImpactBadges.vue` (badges objectif_env, maturité)
  - `ProjectStatusSelector.vue`
  - `ProjectMap.vue` (avec Leaflet, voir F11)
  - `DuplicateProjectModal.vue`
- Composable `composables/useProjects.ts`
- Store `stores/projects.ts`
- Mise à jour navigation : ajouter lien "Mes Projets" dans sidebar
- Dark mode complet
- Accessibilité

### Base de données

- Tables : `projects`, `project_documents`
- Colonne ajoutée : `fund_applications.project_id`
- Indexes : `projects(account_id, status)`, `projects(account_id, maturity)`, `project_documents(project_id, document_id) UNIQUE`
- RLS via F02 sur les nouvelles tables
- (post-MVP : `projects.location_coordinates` requiert l'extension PostGIS)

## Critères d'acceptation

- [ ] Modèle `Project` créé avec tous les champs spécifiés
- [ ] Modèle `ProjectDocument` créé
- [ ] Migration backfill OK : toutes les `FundApplication` sont liées à un `Project` parent
- [ ] CRUD API REST fonctionnel
- [ ] 7 tools LangChain implémentés et exposés
- [ ] Pages `/profile/company` et `/profile/projects/*` créées et fonctionnelles
- [ ] Composants Projects implémentés avec dark mode
- [ ] Multi-tenant : un user ne voit jamais les projets d'un autre account
- [ ] Audit log capture les mutations
- [ ] Test E2E : créer projet via UI → vérifier en BDD + audit log
- [ ] Test E2E : créer projet via LLM (`create_project` tool) → vérifier en BDD + audit log avec source_of_change=llm
- [ ] Test E2E : duplication projet → nouveau row avec champs identiques sauf id et name
- [ ] Test E2E : tenter delete projet avec applications actives → refus
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : la migration backfill crée des projets "orphelins" mal nommés ("Project from application X") qui pollue la base. **Garde-fou** : import script avec heuristique de nommage à partir de la description de l'application + flag `auto_generated: true` à éliminer après revue user.
- **Risque** : le user crée 50 projets brouillon et l'UI devient lente. **Garde-fou** : pagination obligatoire (25 par page), filtres rapides, action bulk "supprimer drafts > 90j".
- **Risque** : le découpage automatique d'un grand projet par le LLM crée des sous-projets incohérents. **Garde-fou** : confirmation explicite via `ask_yes_no` avant chaque création, summary card preview, possibilité d'annuler.
- **Risque** : suppression projet sans candidatures actives mais avec données ESG/carbone calculées qui le référencent. **Garde-fou** : à terme, autres entités (impacts mesurés post-financement) référencent `project_id` → ajouter le check dans le guard delete.
- **Risque** : l'utilisateur ne sait pas s'il doit créer un projet ou modifier l'entreprise. **Garde-fou** : onboarding driver.js avec tooltip "Entreprise = identité, Projets = ce que vous voulez financer". LLM proactif qui suggère "voulez-vous créer un projet ?" quand approprié.
