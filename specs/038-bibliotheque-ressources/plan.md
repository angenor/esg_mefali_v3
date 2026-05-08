# Implementation Plan — F20 Bibliothèque Ressources + Fiches par Intermédiaire

**Spec**: [spec.md](./spec.md)
**Clarify**: [clarify.md](./clarify.md)
**Spec Number**: 038
**Migration**: `038_create_resources` (down_revision=`037_alternative_credit_data`)
**Branche**: `feat/F20-bibliotheque-ressources`
**Date**: 2026-05-08

---

## 1. Architecture cible

### 1.1 Vue d'ensemble

```
┌────────────────────────────────────────────────────────────┐
│                      FRONTEND (Nuxt 4)                     │
│  pages/resources/index.vue            (liste publique)     │
│  pages/resources/[slug].vue           (détail ressource)   │
│  pages/financing/intermediaries/      (fiche pratique)     │
│         [id]/guide.vue                                     │
│  pages/admin/resources/index.vue      (CRUD admin)         │
│  pages/admin/resources/new.vue                             │
│  pages/admin/resources/[id].vue                            │
│                                                            │
│  components/resources/                                     │
│    ResourceCard.vue                                        │
│    ResourceMarkdownRenderer.vue                            │
│    ResourceTypeBadge.vue                                   │
│    ResourceFilters.vue                                     │
│    IntermediaryGuideView.vue                               │
│    ResourceVideoPlayer.vue                                 │
│    ResourceTemplateDownload.vue                            │
│    RelatedResources.vue                                    │
│  components/admin/resources/                               │
│    ResourceForm.vue           (toast-ui/editor markdown)   │
│    ResourceList.vue                                        │
│    ResourcePublishButton.vue  (4-yeux)                     │
│                                                            │
│  composables/useResources.ts                               │
│  composables/useAdminResources.ts                          │
│  stores/resources.ts          (Pinia)                      │
│  types/resource.ts                                         │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                         │
│  app/models/resource.py                                    │
│  app/modules/resources/                                    │
│    schemas.py        (Pydantic v2 strict)                  │
│    service.py        (CRUD + recherche + recommandation)   │
│    router.py         (lecture publique)                    │
│    seed.py           (15+ ressources idempotent)           │
│  app/modules/admin/resources_router.py                     │
│                                                            │
│  app/graph/tools/resource_tools.py                         │
│    search_resources                                        │
│    get_resource_content                                    │
│    recommend_resources_for_user                            │
│  + injection GLOBAL_WHITELIST (transverse 7 nœuds)         │
│  + test conformité no_resource_mutation_tool               │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                  POSTGRESQL 16 + pgvector                  │
│  Migration 038_create_resources                            │
│    Table `resources` (~25 colonnes)                        │
│    Indexes :                                               │
│      - btree(type, publication_status, valid_to)           │
│      - btree(slug) UNIQUE                                  │
│      - btree(intermediary_id) WHERE type='intermediary_guide' │
│      - GIN trigram sur (title || ' ' || description)       │
│      - btree(view_count DESC)                              │
│    CHECK constraints (type, language, publication_status,  │
│      4-yeux created_by != verified_by)                     │
│    FK: source_id → sources (RESTRICT)                      │
│    FK: intermediary_id → intermediaries (RESTRICT)         │
│    FK: created_by → users (RESTRICT)                       │
│    FK: verified_by → users (RESTRICT, nullable)            │
│    FK: superseded_by → resources (SET NULL, self)          │
│  /uploads/resources/<filename>  (FS local)                 │
└────────────────────────────────────────────────────────────┘
```

### 1.2 Conventions

- Type Python `Resource` ajouté à `EXEMPT_MODELS` (catalogue admin-only, pas de `account_id`, pas de mixin `Auditable` — audit via middleware admin existant F03/F09).
- Toutes les mutations admin passent par middleware `AdminAuditContextMiddleware` (déjà en place) → `source_of_change=admin`.
- Toutes les mutations LLM seraient `source_of_change=llm` mais aucune n'est autorisée — garde-fou de conformité (test bloquant comme F23).
- Slug : généré côté admin via `slugify(title)` + suffixe numérique si collision. Immuable après publication.
- Markdown : assaini DOMPurify côté frontend, tag `<script>`/`<iframe>` (hors providers whitelist) refusés à la création/édition.

---

## 2. Modèle de données

### 2.1 Table `resources`

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `id` | UUID | PK, default uuid_generate_v4() | |
| `type` | VARCHAR(30) | NOT NULL, CHECK enum | guide, template_doc, video, faq, intermediary_guide |
| `title` | VARCHAR(200) | NOT NULL | |
| `slug` | VARCHAR(200) | NOT NULL, UNIQUE | immuable après publication |
| `description` | VARCHAR(500) | NOT NULL | |
| `content_md` | TEXT | NULL pour video pure | ≤ 50 000 chars (CHECK applicatif) |
| `file_url` | VARCHAR(500) | NULL | obligatoire si type=template_doc |
| `video_url` | VARCHAR(500) | NULL | obligatoire si type=video, whitelist |
| `duration_seconds` | INTEGER | NULL, CHECK ≥ 0 | facultatif |
| `category` | JSONB | NOT NULL, default '[]' | array de tags |
| `target_audience` | JSONB | NOT NULL, default '[]' | array (pme_micro, pme_small, pme_medium) |
| `language` | VARCHAR(2) | NOT NULL, CHECK IN ('fr','en') | default 'fr' |
| `source_id` | UUID | NOT NULL, FK sources(id) RESTRICT | F01 |
| `intermediary_id` | UUID | NULL, FK intermediaries(id) RESTRICT | NOT NULL ssi type=intermediary_guide (CHECK applicatif) |
| `version` | VARCHAR(50) | NOT NULL default '1.0.0' | F04 |
| `valid_from` | DATE | NULL | F04, default today à publish |
| `valid_to` | DATE | NULL | F04 |
| `superseded_by` | UUID | NULL, FK resources(id) SET NULL | F04, self |
| `publication_status` | VARCHAR(20) | NOT NULL default 'draft', CHECK | draft, published, archived |
| `view_count` | INTEGER | NOT NULL default 0, CHECK ≥ 0 | atomique |
| `created_by` | UUID | NOT NULL, FK users(id) RESTRICT | F09 4-yeux |
| `verified_by` | UUID | NULL, FK users(id) RESTRICT | F09 4-yeux |
| `created_at` | TIMESTAMPTZ | NOT NULL default now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL default now() | trigger update |

### 2.2 Contraintes

- `CHECK (type IN ('guide','template_doc','video','faq','intermediary_guide'))`
- `CHECK (language IN ('fr','en'))`
- `CHECK (publication_status IN ('draft','published','archived'))`
- `CHECK (verified_by IS NULL OR verified_by <> created_by)` — 4-yeux
- `CHECK (view_count >= 0)`
- `CHECK (duration_seconds IS NULL OR duration_seconds >= 0)`
- Contraintes applicatives (service-level, validées par tests) :
  - si `type='intermediary_guide'` → `intermediary_id IS NOT NULL`
  - sinon → `intermediary_id IS NULL`
  - si `type='template_doc'` → `file_url IS NOT NULL`
  - si `type='video'` → `video_url IS NOT NULL` et matching whitelist
  - une seule fiche `published` par `intermediary_id` à instant T (vérif au publish)
  - un slug `published` ne peut être réédité in-place — création nouvelle version

### 2.3 Indexes

- `idx_resources_lookup` btree(type, publication_status, valid_to)
- `idx_resources_slug` btree UNIQUE(slug)
- `idx_resources_intermediary` btree(intermediary_id) WHERE type='intermediary_guide'
- `idx_resources_search` GIN trigram (`pg_trgm`) sur `(title || ' ' || description)` (PostgreSQL only, skip SQLite tests)
- `idx_resources_views` btree(view_count DESC) WHERE publication_status='published'

### 2.4 Migration `038_create_resources.py`

- `down_revision='037_alternative_credit_data'`
- `op.create_table('resources', ...)` avec toutes colonnes et CHECK
- Création des indexes (sauf trigram GIN si SQLite)
- Pas de RLS PostgreSQL (catalogue exempt) — accès admin via `app.current_role=admin` (cohérent F01)
- `downgrade()` : `op.drop_table('resources')`
- Round-trip `up/down/up` testé sur PostgreSQL

---

## 3. Backend

### 3.1 Modèle SQLAlchemy `app/models/resource.py`

```
class Resource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "resources"
    type, title, slug, description, content_md, file_url, video_url
    duration_seconds, category (JSONB), target_audience (JSONB), language
    source_id, intermediary_id
    version, valid_from, valid_to, superseded_by
    publication_status, view_count
    created_by, verified_by
    # relationships : source, intermediary, supersedes_target, creator, verifier
```

Ajout à `EXEMPT_MODELS` (catalogue admin-only).
Pas de mixin `Auditable` — la traçabilité passe par le middleware admin F03.

### 3.2 Schemas Pydantic v2 `app/modules/resources/schemas.py`

- `ResourceTypeEnum`, `LanguageEnum`, `PublicationStatusEnum`, `TargetAudienceEnum`
- `ResourceBase` (champs communs)
- `ResourceCreateAdmin` (input admin)
- `ResourceUpdateAdmin` (input partial)
- `ResourceReadPublic` (output public, exclut `created_by/verified_by`)
- `ResourceReadAdmin` (output admin complet)
- `ResourceListItem` (light, pour les listings)
- `ResourceListResponse` (`items`, `total`, `page`, `limit`)
- `ResourceSearchQuery` (filtres `type`, `category`, `language`, `intermediary_id`, `q`, `page`, `limit`)
- `RecommendationContext` (entrée tool : `account_id`, `scores`, `active_module`)
- `RecommendedResourceItem` (output tool : `slug`, `title`, `type`, `score`, `why`)
- Validators :
  - `slug` regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`
  - `video_url` whitelist (YouTube/Vimeo/local)
  - `content_md` ≤ 50 000 chars
  - cohérence type ↔ champs dépendants

### 3.3 Service `app/modules/resources/service.py`

Méthodes principales (toutes async) :

- `list_published(filters: ResourceSearchQuery) -> ResourceListResponse`
- `get_by_slug(slug: str) -> ResourceReadPublic | None`
- `get_intermediary_guide(intermediary_id: UUID) -> ResourceReadPublic | None`
- `increment_view_count(slug: str) -> int` (UPDATE atomique, retourne nouveau count)
- `search_resources(query: str, type_: str | None, category: str | None, limit: int=10) -> list[ResourceListItem]`
- `get_recommendations(user, scores: dict, active_module: str | None, limit: int=5) -> list[RecommendedResourceItem]`
- `get_related(resource: Resource, limit: int=3) -> list[ResourceListItem]` (mêmes catégories, hors lui-même, publiées)
- (admin) `create_resource(data: ResourceCreateAdmin, created_by: UUID) -> Resource`
- (admin) `update_resource(id: UUID, data: ResourceUpdateAdmin, editor: UUID) -> Resource` (in-place si draft, sinon nouvelle version draft patch+1)
- (admin) `publish_resource(id: UUID, verifier: UUID) -> Resource` (vérif 4-yeux, vérif source verified, vérif unicité publish par intermediary_id, set valid_from=today, supersede ancienne version)
- (admin) `archive_resource(id: UUID, editor: UUID) -> Resource` (soft-delete : valid_to=today, publication_status=archived)
- (admin) `delete_resource(id: UUID) -> None` (hard delete drafts uniquement)

Algorithme `get_recommendations` :

1. Filtrer ressources `published` (non superseded), language matching profil utilisateur (default `fr`).
2. Pour chaque ressource, calculer score :
   - +3 par catégorie qui matche `active_module` ou `low_score_pillar` extrait des scores.
   - +2 par tag `target_audience` qui matche la taille de l'entreprise.
   - +1 × `view_count_normalized` (max-min normalization).
3. Trier desc, retourner top 5.
4. Fallback si rien : retourner top 3 par `view_count desc`.

### 3.4 Routers

#### `app/modules/resources/router.py` (public)

- `GET /api/resources` → `list_published`
- `GET /api/resources/{slug}` → `get_by_slug` (404 si introuvable ou non-publié)
- `POST /api/resources/{slug}/view` → `increment_view_count` (anonyme, 200 + nouveau count)
- `GET /api/intermediaries/{id}/guide` → `get_intermediary_guide`

Auth : aucune requise pour les GET/POST/view publics. Le `/uploads/resources/...` est servi par StaticFiles FastAPI déjà en place.

#### `app/modules/admin/resources_router.py`

- `Depends(get_current_admin)` sur tous les endpoints
- `GET /api/admin/resources` → liste paginée toutes statuts/langues/types
- `GET /api/admin/resources/{id}` → détail admin complet
- `POST /api/admin/resources` → `create_resource`
- `PATCH /api/admin/resources/{id}` → `update_resource`
- `DELETE /api/admin/resources/{id}` → `delete_resource` (drafts only)
- `POST /api/admin/resources/{id}/publish` → `publish_resource` (4-yeux)
- `POST /api/admin/resources/{id}/archive` → `archive_resource`
- (helper) `POST /api/admin/resources/{id}/upload` → upload fichier `template_doc` ou vidéo locale (gère MIME, taille 10 Mo)

### 3.5 Tools LangChain `app/graph/tools/resource_tools.py`

- `search_resources(query: str, type: str | None, category: str | None) -> list[dict]`
  - Pydantic args : `SearchResourcesArgs`
  - Délègue à `service.search_resources`
  - Lecture seule
- `get_resource_content(slug: str) -> dict`
  - Pydantic args : `GetResourceContentArgs`
  - Retourne `{title, type, content_md, source: {...}, related: [...]}`
- `recommend_resources_for_user() -> list[dict]`
  - Pydantic args : `RecommendResourcesArgs` (vide ou avec `limit`)
  - Inject context depuis state LangGraph (user_id, scores, active_module)
  - Délègue à `service.get_recommendations`

Injection : `RESOURCE_TOOLS` ajouté à `GLOBAL_WHITELIST` (transverse 7 nœuds : chat, esg_scoring, carbon, financing, application, credit, action_plan). Borne `MAX_TOOLS_PER_TURN` à étendre si besoin (probablement déjà 14+).

### 3.6 Garde-fou conformité

Test `tests/graph/tools/test_no_resource_mutation_tool.py` qui scanne tous les `tool` enregistrés et `RAISE` si un nom matche `^(create|update|delete|publish|unpublish|archive)_resource`. Pattern exact F23.

### 3.7 Seed `app/modules/resources/seed.py`

15+ ressources idempotentes :

- 5 guides ESG : « Comprendre la taxonomie verte UEMOA », « Politique anti-corruption pour PME africaine », « Mesurer son empreinte carbone : guide pratique », « Critères ESS : ce que les bailleurs attendent », « Préparer un dossier de financement vert ».
- 5 fiches intermédiaires : BOAD, PNUD, BAD, FEM/GEF, GCF (toutes avec process, contacts, délais, conseils, points d'attention, FAQ).
- 3 templates : politique anti-corruption (.docx), charte ESS (.docx), registre des risques (.xlsx).
- 2 FAQ : « Questions fréquentes sur le scoring ESG », « Questions fréquentes sur les fonds verts ».

Chaque ressource pointe vers une `source_id` F01 vérifiée existante (sourcing déjà fait par F01). Idempotence via vérification `slug` (SELECT before INSERT).

Script CLI `scripts/seed_resources.py` invocable.

### 3.8 Configuration

- Pas de variable d'env supplémentaire en MVP.
- `EXEMPT_MODELS` : ajouter `Resource`.
- `GLOBAL_WHITELIST` (graph) : ajouter `RESOURCE_TOOLS`.
- Limite upload fichier : 10 Mo (validation MIME : .pdf, .docx, .xlsx, .png, .jpg pour vignettes vidéo).

---

## 4. Frontend

### 4.1 Pages publiques

- `pages/resources/index.vue` : grille de cartes paginée, barre de recherche, filtres latéraux (type, catégorie, langue, audience), URL-synchronisés (query string).
- `pages/resources/[slug].vue` : header (titre, type, langue, dernière maj), rendu markdown sourcé, bouton télécharger si `template_doc`, lecteur vidéo si `video`, section ressources liées.
- `pages/financing/intermediaries/[id]/guide.vue` : wrapper qui charge `IntermediaryGuideView` avec sections structurées + lien retour vers la fiche fonds (F07).

### 4.2 Pages admin

- `pages/admin/resources/index.vue` : liste paginée, filtres statut/type/langue, actions Publier/Archiver/Supprimer, badges 4-yeux.
- `pages/admin/resources/new.vue` : formulaire avec éditeur markdown WYSIWYG (`toast-ui/editor`), upload fichier, association source F01 (modal de sélection), choix intermédiaire (si type=intermediary_guide).
- `pages/admin/resources/[id].vue` : édition + bouton Publier (vérifie second validateur côté serveur).

### 4.3 Composants

- `ResourceCard.vue` : props `resource`, dark mode, cliquable, badge type, miniature pour video, picto pour template_doc.
- `ResourceMarkdownRenderer.vue` : parse markdown + DOMPurify + résolution liens `#source:<id>` en `<SourceLink>` cliquables.
- `ResourceTypeBadge.vue` : badge couleur selon type (5 couleurs).
- `ResourceFilters.vue` : checkboxes types/categories/audience + select langue.
- `IntermediaryGuideView.vue` : 6 sections (process en steps numérotées, contacts cards, delays badge, conseils liste, attention warnings, FAQ accordion).
- `ResourceVideoPlayer.vue` : iframe sandboxée pour YouTube/Vimeo, video native pour `/uploads/`.
- `ResourceTemplateDownload.vue` : bouton + checksum + déclenche `POST .../view` au clic.
- `RelatedResources.vue` : 3 cards en bas de page.
- `admin/ResourceForm.vue` : formulaire complet avec onglets (Général, Contenu markdown, Médias, Sourçage, Audience, Métadonnées).
- `admin/ResourceList.vue` : table admin avec actions inline.
- `admin/ResourcePublishButton.vue` : checkbox confirmation + appel POST publish.

Tous les composants : dark mode complet (`dark:bg-dark-card`, `dark:border-dark-border`, etc.), ARIA roles, FR avec accents.

### 4.4 Composables

- `composables/useResources.ts` : `listResources`, `getResource`, `getIntermediaryGuide`, `incrementView` (utilise `useFetchAuth` ou `$fetch` public selon).
- `composables/useAdminResources.ts` : `adminList`, `adminGet`, `adminCreate`, `adminUpdate`, `adminPublish`, `adminArchive`, `adminDelete`, `adminUploadFile`.

### 4.5 Store Pinia `stores/resources.ts`

État : `items`, `total`, `currentResource`, `relatedResources`, `intermediaryGuide`, `filters`, `loading`, `error`. Getters : `byType`, `byCategory`. Mutations : reset, addItem, updateItem.

### 4.6 Types `types/resource.ts`

Types miroir des schemas Pydantic : `Resource`, `ResourceType`, `Language`, `PublicationStatus`, `TargetAudience`, `ResourceListItem`, `ResourceFilters`, `IntermediaryGuide`.

### 4.7 Lien sidebar

- Ajouter « Bibliothèque » dans `AppSidebar.vue` avec icône livre, route `/resources`.
- Ajouter « Ressources » dans la sidebar admin avec route `/admin/resources`.

---

## 5. Tests

### 5.1 Backend (pytest)

| Module | Tests cibles | Couverture |
|---|---|---|
| `models/resource` | 8 (mixins, FK, defaults) | 100 % |
| `modules/resources/schemas` | 12 (validators, enum, slug, video URL whitelist, content_md size) | ≥ 95 % |
| `modules/resources/service` | 18 (list/get/search/recommend/create/update/publish/archive/delete/4-yeux/source-verified/view-count atomique) | ≥ 85 % |
| `modules/resources/router` | 9 (404, 403, pagination, filtres, increment view) | ≥ 90 % |
| `modules/admin/resources_router` | 11 (CRUD admin, 403 PME, 4-yeux, publish refusé sans source) | ≥ 90 % |
| `graph/tools/resource_tools` | 6 (chaque tool, args validation, error fallback) | ≥ 90 % |
| `graph/tools/test_no_resource_mutation_tool` | 1 (conformity) | n/a |
| `modules/resources/seed` | 4 (idempotence, count ≥ 15, source_id verified, slug unique) | ≥ 90 % |
| `migrations/test_alembic_038` | 5 (round-trip, indexes, CHECK, FK) | n/a |
| `integration/test_view_count_atomic` | 1 (100 requêtes simultanées asyncio.gather) | n/a |

Total : ~75 nouveaux tests. Couverture cible ≥ 80 % sur le périmètre F20.

### 5.2 Frontend (Vitest)

| Composant / Composable | Tests | Couverture |
|---|---|---|
| `useResources.ts` | 6 | ≥ 90 % |
| `useAdminResources.ts` | 7 | ≥ 90 % |
| `stores/resources.ts` | 5 | ≥ 90 % |
| `ResourceCard.vue` | 5 (rendu, types, dark mode, click) | ≥ 85 % |
| `ResourceMarkdownRenderer.vue` | 6 (XSS, source links, sanitization) | ≥ 85 % |
| `ResourceFilters.vue` | 4 | ≥ 85 % |
| `IntermediaryGuideView.vue` | 5 (6 sections, état vide, dark mode) | ≥ 85 % |
| `admin/ResourceForm.vue` | 6 (validation, upload, soumission) | ≥ 85 % |
| `admin/ResourcePublishButton.vue` | 3 | ≥ 85 % |

Total : ~47 nouveaux tests Vitest.

### 5.3 E2E Playwright

`frontend/tests/e2e/F20-bibliotheque-ressources.spec.ts` (4 scénarios) :

1. PME navigue `/resources` → filtre catégorie « gouvernance » → ouvre un guide → clique sur source F01.
2. PME ouvre `/financing/intermediaries/<boad_id>/guide` → vérifie 6 sections → copie email contact.
3. PME ouvre `/resources/<template_slug>` → clique « Télécharger » → vérifie download + view_count incrémenté.
4. Admin se connecte → crée une ressource draft → un second admin la publie → elle apparaît côté public.

---

## 6. Phasage et ordre d'implémentation

### Phase 1 — Fondation BDD + modèle (jour 1)

1. Migration Alembic `038_create_resources` (up/down/up testé).
2. Modèle SQLAlchemy `Resource` + ajout `EXEMPT_MODELS`.
3. Schemas Pydantic v2 + validators.
4. Tests model + schemas + migration.

### Phase 2 — Backend service + routers publics (jour 2)

5. Service `list_published`, `get_by_slug`, `increment_view_count`, `get_intermediary_guide`, `search_resources`, `get_related`, `get_recommendations`.
6. Router public + tests router.
7. Test atomicité `view_count`.

### Phase 3 — Backend admin (jour 3)

8. Service admin (`create`, `update`, `publish`, `archive`, `delete`).
9. Router admin + tests router admin (403, 4-yeux, source verified).
10. Helper upload fichier `/uploads/resources/...`.

### Phase 4 — Tools LangChain + garde-fous (jour 4)

11. Tools `search_resources`, `get_resource_content`, `recommend_resources_for_user`.
12. Injection `GLOBAL_WHITELIST`.
13. Test conformité `no_resource_mutation_tool`.

### Phase 5 — Seed (jour 4-5)

14. 15+ ressources rédigées en français avec sources F01.
15. Script CLI `scripts/seed_resources.py` idempotent.
16. Tests seed.

### Phase 6 — Frontend public (jour 5-6)

17. Types TS + composable `useResources` + store Pinia.
18. Composants `ResourceCard`, `ResourceMarkdownRenderer`, `ResourceTypeBadge`, `ResourceFilters`, `RelatedResources`.
19. Pages `/resources/index.vue` et `/resources/[slug].vue`.
20. Composant `IntermediaryGuideView` + page `/financing/intermediaries/[id]/guide.vue`.
21. Composant `ResourceVideoPlayer`, `ResourceTemplateDownload`.
22. Tests Vitest composants publics.

### Phase 7 — Frontend admin (jour 6-7)

23. Composable `useAdminResources`.
24. Composants admin : `ResourceForm` (toast-ui/editor), `ResourceList`, `ResourcePublishButton`.
25. Pages `/admin/resources/index.vue`, `/new.vue`, `/[id].vue`.
26. Lien sidebar admin.
27. Tests Vitest composants admin.

### Phase 8 — E2E + finalisation (jour 7-8)

28. Spec Playwright E2E (4 scénarios).
29. Documentation `docs/resources-library.md` (cycle de vie, sourçage, garde-fous).
30. Vérification couverture ≥ 80 % et zéro régression.

---

## 7. Risques et garde-fous

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Rédaction des 15 ressources chronophage | Moyenne | Élevé | Prioriser fiches BOAD/PNUD/GCF d'abord ; accepter des draft pour MVP avec finalisation J+30 |
| XSS via markdown utilisateur | Faible | Critique | Double sanitization (backend + frontend DOMPurify), CSP stricte, pas de balise `<script>` |
| Mutation accidentelle via tool LLM | Faible | Élevé | Test de conformité bloquant + revue des tools dans GLOBAL_WHITELIST |
| Slug en collision sur création concurrente | Faible | Moyen | `UNIQUE` index + retry avec suffixe numérique côté service |
| Fichier `template_doc` corrompu / absent | Faible | Moyen | Validation MIME + checksum à l'upload, log structuré au 404 |
| `view_count` race condition | Faible | Faible | UPDATE SQL atomique testé avec asyncio.gather |
| Source pointée devient `outdated` | Moyenne | Moyen | Audit cron F11 (existant) alerte admins, blocage du publish si `source.status != verified` |
| Volume de markdown > 50k chars | Faible | Moyen | CHECK applicatif, message d'erreur 422 explicite |
| Versioning : édition crée des forks divergents | Faible | Moyen | Service garantit un seul `published` par slug + `superseded_by` chain stricte |

---

## 8. Compatibilité ascendante

- Aucun module existant à refactoriser.
- Aucune migration de données préexistantes nécessaire.
- Pas de breaking change sur les API existantes.
- Conservation legacy : non applicable.

---

## 9. Définition de fini (DoD)

- [x] Migration `038_create_resources` réversible (`up/down/up`)
- [x] 15+ ressources seedées (5 guides, 5 fiches intermédiaires, 3 templates, 2 FAQ)
- [x] CRUD admin fonctionnel avec 4-yeux F09
- [x] Pages publiques `/resources`, `/resources/[slug]`, `/financing/intermediaries/[id]/guide` opérationnelles
- [x] 3 tools LangChain en lecture seule + garde-fou conformité
- [x] Tests backend ≥ 80 % couverture sur le périmètre F20
- [x] Tests frontend Vitest ≥ 80 % couverture sur les composants/composables F20
- [x] Spec Playwright E2E (4 scénarios) verts
- [x] Dark mode complet sur toutes les pages
- [x] Documentation `docs/resources-library.md` rédigée
- [x] Zéro régression sur les tests existants
