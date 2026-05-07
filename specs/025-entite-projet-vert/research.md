# Phase 0 — Research: F06 Entité Projet Vert

**Feature** : F06 — Entité Projet Vert (Module 1.3)
**Date** : 2026-05-07
**Branch** : `feat/F06-entite-projet-vert`

## 1. Choix de stockage `objective_env` (multi-valeurs)

### Contexte
La spec mentionne que `objective_env` peut prendre plusieurs valeurs simultanées (ex. un projet peut être à la fois `renewable_energy` et `mitigation`). Trois options de stockage en PostgreSQL :
1. Colonne ARRAY native PostgreSQL (`text[]`)
2. Colonne JSONB typée comme tableau (`["a", "b"]`)
3. Table satellite `project_objectives` (`project_id`, `objective`)

### Décision
**Option 2 — JSONB typée comme tableau de strings**, avec validateur Pydantic strict côté API et CHECK applicatif (whitelist de 8 valeurs autorisées).

### Rationale
- **Simplicité de requête** : un seul SELECT pour récupérer un projet et ses objectifs (pas de jointure).
- **Affichage carte projet** : les objectifs sont systématiquement affichés sur chaque card (`<ProjectImpactBadges>`), une jointure systématique pèserait inutilement.
- **Volumétrie réduite** : ≤ 8 valeurs par projet (la whitelist en compte 8).
- **Indexable** : si besoin de filtrer par objectif (ex. `?objective_env=mitigation`), un index GIN sur la colonne JSONB peut être ajouté post-MVP sans refactor.
- **Compatibilité tests SQLite** : SQLAlchemy bascule automatiquement sur `JSON` pour SQLite (pattern `JSONType = JSONB().with_variant(JSON(), "sqlite")` réutilisé depuis `app/models/source.py`).
- **Versionnement** : non concerné — les valeurs autorisées sont gouvernées par la whitelist applicative, pas par un référentiel sourcé.

### Alternatives écartées
- **Table satellite** : surdimensionnée pour 8 valeurs max, complique les requêtes simples, jointure systématique sur la liste.
- **Colonne ARRAY PostgreSQL** : non portable SQLite (les tests cassent), pas de variant SQLAlchemy clair.

## 2. Stratégie backfill `FundApplication.project_id`

### Contexte
Au moment de la migration F06, des `FundApplication` existent déjà sans `project_id` (notamment celles seedées par F08 et F09). Trois options :
1. Laisser `project_id` NULL post-migration et bloquer la PME jusqu'à création manuelle d'un projet.
2. Créer automatiquement un Project minimal pour chaque FundApplication orpheline (avec flag `auto_generated=true`).
3. Demander à la PME via UI bloquante de fusionner ses applications dans des projets.

### Décision
**Option 2 — Génération automatique de projets minimaux** avec `auto_generated=true`, name `"Projet hérité — <fund.name> (<created_at YYYY-MM>)"` (tronqué à 200 chars), description `application.sections.summary` si présent sinon `"Projet créé automatiquement lors de la migration F06."`, status mappé selon `application.status` (cf. data-model § 3.4), `objective_env=[]`, `account_id` repris de l'application.

### Rationale
- **Migration non bloquante** : aucune PME ne perd l'accès à ses applications.
- **Réversibilité** : le downgrade Alembic supprime la colonne `project_id` de `fund_applications`, puis les tables `project_documents` et `projects`.
- **Traçabilité** : le flag `auto_generated=true` permet à la PME de filtrer ces projets dans l'UI (`/profile/projects?auto_generated=true`) et de les revoir/affiner.
- **Idempotence** : la migration utilise `WHERE fund_applications.project_id IS NULL` ; réexécution n'a aucun effet.

### Mapping statut application → statut projet (FR-008, data-model § 3.4)

| Application status | Project status auto-généré |
|---|---|
| `draft`, `preparing_documents`, `in_progress`, `review` | `seeking_funding` |
| `ready_for_intermediary`, `ready_for_fund`, `submitted_to_intermediary`, `submitted_to_fund`, `under_review` | `seeking_funding` |
| `accepted` | `funded` |
| `rejected` | `seeking_funding` (la PME peut retenter avec un autre fonds pour le même projet) |

### Alternatives écartées
- **Option 1 (NULL post-migration)** : bloque l'utilisateur sur `/applications`, viole l'invariant projet n°1 du brainstorming.
- **Option 3 (UI bloquante)** : friction utilisateur élevée, déploiement compliqué.

## 3. Garde-fou suppression Project avec applications actives

### Contexte
Quand une PME tente de supprimer un projet ayant des applications actives (`status NOT IN ('rejected', 'accepted', 'cancelled')`), trois options :
1. Refus dur (HTTP 409, aucun contournement).
2. Refus par défaut + paramètre `force=true` côté API/tool LangChain pour confirmer.
3. ON DELETE CASCADE qui supprime aussi les applications.

### Décision
**Option 2 — Refus par défaut + paramètre `force=true` + soft-delete logique** (`status='cancelled'` côté projet, traçabilité audit log F03 conservée). La suppression réelle de la ligne est différée à un job admin post-MVP.

### Rationale
- **Préservation des données** : aucune `FundApplication` n'est supprimée silencieusement (perte irrémédiable de candidatures).
- **Traçabilité audit log F03** : la mutation `status='cancelled'` est tracée comme un `update`, pas un `delete` (le diff field-level est conservé).
- **Confirmabilité côté LLM** : le tool `delete_project(force=False)` retourne `{ok: false, blocked_by: [{application_id, fund_name, status}], hint: "force=true pour confirmer"}` que le LLM exploite via `ask_interactive_question` (F18) pour demander confirmation à l'utilisateur.
- **Récupération possible** : `/profile/projects?status=cancelled` (onglet « Archivés ») permet à l'utilisateur de réactiver un projet annulé par mégarde.

### Alternatives écartées
- **Option 1 (refus dur)** : bloque le workflow LLM (« je veux annuler ce projet ») ; oblige à utiliser un endpoint admin.
- **Option 3 (CASCADE)** : viole le principe de préservation des données ; perte de candidatures historiques.

## 4. Statut sur duplication

### Contexte
Quand une PME duplique un projet, faut-il copier le `status` source ou forcer un statut neutre ?

### Décision
**Force `status='draft'`** sur la copie ; tous les autres champs métier sont copiés.

### Rationale
- **Évite la confusion** : avoir 2 projets simultanément en `funded` ou `seeking_funding` est ambigu (« lequel finance quoi ? »).
- **Sémantique cohérente** : la duplication est un acte de préparation, pas de promotion. Le projet copié est par essence en cours de définition.
- **Suffixe `(copie)` automatique** : aide à distinguer visuellement les doublons.
- **Simplicité** : pas de logique de mapping conditionnelle.

### Champs NON copiés à la duplication
- `id` (nouveau UUID)
- `created_at`, `updated_at` (réinitialisés)
- `auto_generated` (false par défaut, jamais hérité)
- `project_documents` (table de jointure non copiée — l'utilisateur re-lie manuellement les documents pertinents)

### Alternatives écartées
- **Copier statut source** : risque de doubler les engagements financiers.
- **Force `seeking_funding`** : suppose que la PME duplique pour candidater immédiatement, ce qui n'est pas toujours vrai.

## 5. Coordonnées géographiques `location_coordinates`

### Contexte
La spec source mentionne `location_coordinates: geography(POINT, 4326)` pour `show_map`. PostGIS est une extension PostgreSQL non triviale (CREATE EXTENSION postgis ; nécessite installation côté infra).

### Décision
**Différer post-MVP via la feature F11 (`show_map`)**. F06 ajoute uniquement :
- `location_country: Char(2) NULL` (ISO 3166-1 alpha-2, validation Pydantic)
- `location_region: String(100) NULL` (ville/région libre)

### Rationale
- **Évite l'introduction de PostGIS** dans cette feature (changements infra non triviaux : Docker image, config, droits).
- **F11 dédiée** : la story `show_map` (F11) pilotera l'introduction de PostGIS, l'ajout de la colonne `location_coordinates` et le composant `ProjectMap.vue` (Leaflet).
- **MVP fonctionnel** : `location_country + location_region` suffisent pour l'affichage textuel et la majorité des cas de matching projet-offre (la géolocalisation précise est secondaire au MVP).

### Alternatives écartées
- **PostGIS dès F06** : alourdit la migration, retarde la livraison de l'entité Project.
- **Stocker en JSON `{lat, lng}`** : pas de support requête géographique ; pas d'avantage vs colonnes typées plus tard.

## 6. Pattern enum portable PG/SQLite

### Contexte
Les champs `maturity`, `status`, `financing_structure` sont des enums conceptuels avec valeurs limitées. Deux patterns coexistent dans le projet :
1. ENUM PG natif (cf. `audit_action`, `audit_source`, `application_status_enum`)
2. VARCHAR + CHECK applicatif Pydantic (cf. `VALID_CATEGORIES` de carbone, F17)

### Décision
**VARCHAR + CHECK applicatif Pydantic** pour les 3 champs Project enum.

### Rationale
- **Cohérence avec F17** : F17 a documenté que VARCHAR + CHECK applicatif est plus testable (SQLite ne supporte pas les ENUMs PG portables).
- **Évolutivité** : ajouter une nouvelle valeur (ex. `repurposing` à `maturity`) ne requiert pas une migration ALTER TYPE complexe ; il suffit de mettre à jour la whitelist Pydantic.
- **Tests unitaires SQLite** : 100 % des tests unitaires fonctionnent en SQLite in-memory (cf. F17 conftest.py).
- **Réservé aux infrastructure ENUMs** : le pattern ENUM PG natif est conservé pour les enums « techniques » (audit_action, audit_source, target_type_app_enum, application_status_enum) ; les enums « métier » de Project basculent en VARCHAR.

### Whitelists applicatives

```python
PROJECT_OBJECTIVE_ENV_VALUES = frozenset({
    "mitigation", "adaptation", "biodiversity", "circular_economy",
    "water", "renewable_energy", "sustainable_agriculture", "mixed",
})
PROJECT_MATURITY_VALUES = frozenset({
    "ideation", "pre_feasibility", "pilot", "scale", "replication",
})
PROJECT_STATUS_VALUES = frozenset({
    "draft", "seeking_funding", "funded", "in_execution", "closed", "cancelled",
})
PROJECT_FINANCING_STRUCTURE_VALUES = frozenset({
    "subvention", "pret_concessionnel", "equity", "blending", "mixte",
})
PROJECT_DOC_TYPE_VALUES = frozenset({
    "feasibility_study", "business_plan", "impact_assessment",
    "support_letter", "other",
})
```

### Alternatives écartées
- **ENUM PG natif** : friction tests SQLite, migrations ALTER TYPE complexes.

## 7. Réutilisation composants F01 / F04 / F18

### Composants réutilisés
- **`<MoneyDisplay>`** (F04) — affichage `target_amount` Money typé avec mode `displayCurrencyMode` (native/pme/both)
- **`<SourceLink>`** (F01) — lien cliquable vers la source quand le LLM cite un montant ou un impact
- **`<RoleBadge>`** (F02) — badge couleur (PME/ADMIN) si pertinent dans `/profile`
- **`useFocusTrap`** (F18 héritage) — utilisé dans `DuplicateProjectModal`
- **Store `ui.displayCurrencyMode`** (F04) — lecture pour `<MoneyDisplay>`

### Composants créés (réutilisables)
- **`ProjectStatusSelector`** : paramétrable via prop `:statuses` (whitelist passée en prop) — utilisable hors module Projects.
- **`ProjectImpactBadges`** : paramétrable via prop `:impacts` (tableau d'objets `{label, value, unit, source_id}`) — réutilisable pour afficher des impacts ailleurs.
- **`ProjectFilters`** : composable autonome avec `useUrlSync` pour persister les filtres en query params.

### Pattern « Audit log entity link »
Le badge `Créé par l'IA` sur `ProjectCard` (FR-029 acceptance scenario 4) est un nouveau pattern réutilisable. Il s'inspire de la page `/historique` (F03). Implémentation :
```vue
<RouterLink
  v-if="project.source_of_change === 'llm'"
  :to="`/historique?entity_type=projects&entity_id=${project.id}`"
  class="badge badge-llm"
>
  Créé par l'IA
</RouterLink>
```

## 8. Stratégie validator `source_required.py` pour `create_project`

### Contexte
Si le LLM appelle `create_project(target_amount=Money(amount=50000000, currency='XOF'), expected_impact_tco2e=120, ...)`, ces chiffres doivent être sourcés (cf. invariant n°1 F01).

### Décision
- Le validator `source_required.py` (F01) parcourt le payload de retour du tool `create_project`. S'il détecte une grappe « chiffre + unité » dans `target_amount` ou `expected_impact_*` ET que la conversation ne contient aucun `cite_source` invoqué pendant le tour, il déclenche un retry max 1 puis substitue par fallback texte « [montant à confirmer par la PME] ».
- Le tool `create_project` lui-même accepte les chiffres null ; le LLM est donc libre de créer un projet sans target_amount si la PME ne l'a pas mentionné explicitement.
- En cas de fallback, les champs concernés sont passés à NULL côté projet (la PME pourra les ajuster manuellement).

### Tests
- `test_create_project_with_source.py` : LLM appelle `cite_source(source_id_X)` puis `create_project(target_amount=...)` → projet créé avec montants.
- `test_create_project_without_source.py` : LLM appelle `create_project(target_amount=...)` sans `cite_source` → validator retry 1x ; échec retry → fallback texte ; projet créé avec target_amount=NULL.
- `test_create_project_user_provided_amount.py` : la PME énonce explicitement « 50 millions FCFA » → LLM extrait le chiffre comme citation utilisateur (`flag_unsourced(reason='user_input')`) → projet créé avec montant.

## 9. Performance et indexation

### Indexes prévus

```sql
-- Liste paginée par account + status (FR-011, FR-004)
CREATE INDEX idx_projects_account_status ON projects(account_id, status);

-- Liste paginée par account + maturity (FR-004)
CREATE INDEX idx_projects_account_maturity ON projects(account_id, maturity);

-- FK lookups
CREATE INDEX idx_project_documents_project_id ON project_documents(project_id);
CREATE INDEX idx_project_documents_document_id ON project_documents(document_id);

-- Unique constraint pour éviter doublons document-projet (FR-005)
CREATE UNIQUE INDEX idx_project_documents_unique ON project_documents(project_id, document_id);

-- Lookup par fund_application.project_id (déjà couvert par FK index implicite Postgres)
-- mais on ajoute explicitement pour la requête `/api/projects/{id}/applications`
CREATE INDEX idx_fund_applications_project_id ON fund_applications(project_id);
```

### Performance cible
- `GET /api/projects` (25 résultats, filtre `status`) : index `idx_projects_account_status` couvre exactement la requête → < 80 ms p95.
- `POST /api/projects` : 1 INSERT + 1 INSERT audit_log (via listener before_flush F03) → < 100 ms p95.
- `POST /api/projects/{id}/duplicate` : 1 SELECT + 1 INSERT + 1 INSERT audit_log → < 150 ms p95.
- Migration `up/down/up` sur ~1000 fund_applications historiques : < 30 s sur base dev (CTE Postgres + INSERT...SELECT).

## 10. RLS PostgreSQL F02

### Pattern hérité F02
Les nouvelles tables `projects` et `project_documents` héritent du pattern F02 :

```sql
-- Sur la table projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account ON projects
  FOR ALL
  USING (
    current_setting('app.current_account_id', true)::uuid = account_id
    AND current_setting('app.current_role', true) = 'PME'
  );

CREATE POLICY admin_full_access ON projects
  FOR ALL
  USING (current_setting('app.current_role', true) = 'ADMIN');

-- Sur la table project_documents : pas de account_id direct, on filtre via la FK projects
CREATE POLICY pme_access_via_project ON project_documents
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_documents.project_id
        AND current_setting('app.current_account_id', true)::uuid = p.account_id
        AND current_setting('app.current_role', true) = 'PME'
    )
  );

CREATE POLICY admin_full_access_jt ON project_documents
  FOR ALL
  USING (current_setting('app.current_role', true) = 'ADMIN');
```

### Tests RLS
Le test `test_project_rls_cross_tenant.py` utilise 2 comptes (PME-A, PME-B) avec helper `set_rls_context(session, account_id, role, user_id)` (déjà disponible F02). Il vérifie que :
- `SELECT * FROM projects` (PME-A) ne retourne que les projets de PME-A.
- `INSERT INTO projects (account_id=PME-B...)` (en tant que PME-A) lève `RowLevelSecurityViolation`.
- `UPDATE projects SET name=... WHERE id=projet_de_PME-B` (en tant que PME-A) affecte 0 ligne.
- `DELETE FROM projects WHERE id=projet_de_PME-B` (en tant que PME-A) affecte 0 ligne.
- Idem pour `project_documents` via la jointure.

## 11. Tools LangChain — réutilisation patterns F01/F12

### Pattern d'appel async
Le module `app/graph/tools/project_tools.py` suit strictement le pattern de `memory_tools.py` (F12) et `sourcing_tools.py` (F01) :

```python
@tool("create_project", args_schema=ProjectCreateArgs)
async def create_project_tool(...) -> str:
    """Créer un nouveau projet vert pour l'entreprise..."""
    config = get_config_from_context()
    db = get_db_session(config)
    account_id = config["configurable"].get("account_id")
    user_id = config["configurable"].get("user_id")
    # ... appel service ...
    project = await service.create_project(db, account_id, user_id, payload)
    return json.dumps(project_summary, ensure_ascii=False)
```

### Injection dans les nœuds LangGraph
- Le tool `list_projects` est ajouté à `MODULE_TOOL_MAPPING['chat']` (le LLM peut interroger les projets depuis n'importe quel nœud).
- Les autres tools (create/update/delete/duplicate/link_document/get) sont ajoutés à `PAGE_TOOL_MAPPING['profile']` et nouvelle entrée `PAGE_TOOL_MAPPING['profile_projects']`.
- La borne `MAX_TOOLS_PER_TURN = 14` (héritée F12) est respectée : les 7 tools projet ne sont jamais tous présents simultanément ; le tool selector filtre selon `current_page`.

### Pas d'injection en GLOBAL_WHITELIST
Les tools projet sont contextuels (pas transverses comme `cite_source` ou `recall_history`) ; ils ne sont PAS ajoutés à la `GLOBAL_WHITELIST` (qui reste à 4 tools : `ask_interactive_question`, `trigger_guided_tour`, `cite_source`, `search_source`, `flag_unsourced`, `recall_history`).

## Synthèse des décisions Phase 0

| ID | Décision | Référence clarification |
|----|---------|-----|
| D1 | `objective_env` JSONB array + whitelist Pydantic | Q1 |
| D2 | Backfill par auto-génération avec `auto_generated=true` | Q2 |
| D3 | Soft-delete via `force=true` + `status='cancelled'` | Q3 |
| D4 | Force `status='draft'` sur duplication | Q4 |
| D5 | PostGIS différé F11 ; F06 ajoute `location_country` + `location_region` uniquement | Q5 |
| D6 | VARCHAR + CHECK applicatif Pydantic pour enums métier | (cohérence F17) |
| D7 | Réutilise `<MoneyDisplay>` F04, `<SourceLink>` F01, `useFocusTrap` F18 | (réutilisabilité CLAUDE.md) |
| D8 | Validator `source_required.py` F01 appliqué sur `create_project` payload | (invariant F01) |
| D9 | Indexes composites `(account_id, status)` + `(account_id, maturity)` | (perf p95 < 80 ms) |
| D10 | RLS héritée F02 + policy spécifique `project_documents` via jointure | (invariant F02) |
| D11 | Tools projet PAS dans GLOBAL_WHITELIST ; injectés par page selon tool_selector_config | (cohérence F12) |
