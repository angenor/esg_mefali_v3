# Tasks — F20 Bibliothèque Ressources + Fiches par Intermédiaire

**Spec**: [spec.md](./spec.md) — **Plan**: [plan.md](./plan.md) — **Clarify**: [clarify.md](./clarify.md)
**Total**: 64 tâches ordonnées (dépendances explicites)

Légende :
- `[BE]` Backend Python / FastAPI / SQLAlchemy
- `[FE]` Frontend Nuxt 4 / Vue / TS
- `[DB]` Migration Alembic / PostgreSQL
- `[T]` Tests (backend pytest / frontend Vitest / E2E Playwright)
- `[OPS]` Seed / scripts / docs / config
- `[GUARD]` Garde-fous de conformité

---

## Phase 1 — Fondation BDD + modèle (T01–T08)

- **T01** `[DB]` Créer migration `backend/alembic/versions/038_create_resources.py` avec `down_revision='037_alternative_credit_data'`. CREATE TABLE `resources` complet (toutes colonnes + CHECK + FK). `downgrade()` = DROP TABLE.
- **T02** `[DB]` Ajouter indexes : `idx_resources_lookup` (type, publication_status, valid_to), UNIQUE `idx_resources_slug`, `idx_resources_intermediary` partiel WHERE type='intermediary_guide', `idx_resources_views` partiel WHERE published.
- **T03** `[DB]` Ajouter index trigram GIN sur `(title || ' ' || description)` (PostgreSQL only via `if op.get_bind().dialect.name == 'postgresql'`).
- **T04** `[BE]` Créer `backend/app/models/resource.py` : classe `Resource(Base, UUIDMixin, TimestampMixin)` avec relations `source`, `intermediary`, `creator`, `verifier`, `supersedes_target`.
- **T05** `[BE]` Ajouter `Resource` à `EXEMPT_MODELS` dans `backend/app/core/audit_models.py` (catalogue admin-only, pas d'`account_id`, pas de mixin Auditable).
- **T06** `[T]` Tests `backend/tests/test_models/test_resource.py` (8 cas : mixins, defaults, FK relations, repr).
- **T07** `[T]` Tests migration `backend/tests/migrations/test_alembic_038.py` (5 cas : round-trip, indexes présents, CHECK actifs, FK présentes, ENUMs).
- **T08** `[T]` Exécuter `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` sur PostgreSQL — round-trip validé.

## Phase 2 — Schemas Pydantic v2 (T09–T12)

- **T09** `[BE]` Créer `backend/app/modules/resources/__init__.py` + `schemas.py` avec enums (`ResourceTypeEnum`, `LanguageEnum`, `PublicationStatusEnum`, `TargetAudienceEnum`).
- **T10** `[BE]` Schemas : `ResourceBase`, `ResourceCreateAdmin`, `ResourceUpdateAdmin`, `ResourceReadPublic`, `ResourceReadAdmin`, `ResourceListItem`, `ResourceListResponse`, `ResourceSearchQuery`, `RecommendationContext`, `RecommendedResourceItem`.
- **T11** `[BE]` Validators : slug regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`, video_url whitelist (YouTube/Vimeo/local), content_md ≤ 50 000 chars, cohérence type ↔ champs (intermediary_id, file_url, video_url), `model_validator` cross-field.
- **T12** `[T]` Tests `backend/tests/test_schemas/test_resource_schemas.py` (12 cas couvrant tous les validators).

## Phase 3 — Service backend (T13–T22)

- **T13** `[BE]` Créer `backend/app/modules/resources/service.py` avec `list_published(filters)`.
- **T14** `[BE]` Implémenter `get_by_slug(slug)` avec filtre `publication_status='published'` AND `superseded_by IS NULL`.
- **T15** `[BE]` Implémenter `get_intermediary_guide(intermediary_id)` (404-friendly).
- **T16** `[BE]` Implémenter `increment_view_count(slug)` — UPDATE SQL atomique `view_count = view_count + 1`, retourne nouvelle valeur.
- **T17** `[BE]` Implémenter `search_resources(query, type_, category, limit=10)` — full-text simple PostgreSQL trigram + fallback ILIKE pour SQLite tests.
- **T18** `[BE]` Implémenter `get_related(resource, limit=3)` — mêmes catégories, hors lui-même, publiées.
- **T19** `[BE]` Implémenter `get_recommendations(user, scores, active_module, limit=5)` — scoring déterministe (catégorie ×3 + audience ×2 + view_count normalisé).
- **T20** `[BE]` Implémenter `create_resource(data, created_by)` — validation cross-field, vérification source verified, génération slug.
- **T21** `[BE]` Implémenter `update_resource(id, data, editor)` — in-place si `draft`, sinon création nouvelle version draft `<patch+1>`.
- **T22** `[BE]` Implémenter `publish_resource(id, verifier)` (4-yeux verifier ≠ created_by, source verified, unicité par intermediary_id, set valid_from=today, supersede ancienne version) + `archive_resource` + `delete_resource` (drafts only).

## Phase 4 — Routers publics + admin (T23–T30)

- **T23** `[BE]` Créer `backend/app/modules/resources/router.py` avec `GET /api/resources`, `GET /api/resources/{slug}`, `POST /api/resources/{slug}/view` (anonyme), `GET /api/intermediaries/{id}/guide`.
- **T24** `[BE]` Créer `backend/app/modules/admin/resources_router.py` avec `Depends(get_current_admin)` global. CRUD complet + endpoints `publish`, `archive`, `upload`.
- **T25** `[BE]` Helper upload fichier (`POST /api/admin/resources/{id}/upload`) : validation MIME (`.pdf`, `.docx`, `.xlsx`, `.png`, `.jpg`, `.mp4`), taille 10 Mo, chemin `/uploads/resources/<resource_id>/<filename>`.
- **T26** `[BE]` Enregistrer les deux routers dans `backend/app/main.py` (préfixes `/api/resources`, `/api/admin/resources`, `/api/intermediaries`).
- **T27** `[T]` Tests `backend/tests/test_routers/test_resources_router.py` (9 cas : 200, 404 slug, filtres, pagination, view_count, intermediary_guide).
- **T28** `[T]` Tests `backend/tests/test_routers/test_admin_resources_router.py` (11 cas : 403 PME, CRUD admin, 4-yeux refusé, source non-verified refusée, publish unicité par intermediary).
- **T29** `[T]` Test `backend/tests/test_routers/test_view_count_atomic.py` — 100 requêtes simultanées via `asyncio.gather`, vérifier exactement 100 incréments.
- **T30** `[T]` Tests service `backend/tests/test_services/test_resources_service.py` (18 cas couvrant toutes les méthodes).

## Phase 5 — Tools LangChain + garde-fous (T31–T35)

- **T31** `[BE]` Créer `backend/app/graph/tools/resource_tools.py` avec 3 tools (`search_resources`, `get_resource_content`, `recommend_resources_for_user`) — Pydantic args, lecture seule.
- **T32** `[BE]` Injecter `RESOURCE_TOOLS` dans `GLOBAL_WHITELIST` (`backend/app/graph/tool_selector_config.py`). Vérifier `MAX_TOOLS_PER_TURN` suffisant.
- **T33** `[BE]` Injecter `RESOURCE_TOOLS` dans les 7 ToolNode (chat, esg_scoring, carbon, financing, application, credit, action_plan) via `bind_tools` LLM dans chaque nœud.
- **T34** `[GUARD]` Créer test conformité `backend/tests/graph/tools/test_no_resource_mutation_tool.py` qui scanne tools enregistrés et fail si pattern `^(create|update|delete|publish|unpublish|archive)_resource`.
- **T35** `[T]` Tests `backend/tests/graph/tools/test_resource_tools.py` (6 cas : args validation, sérialisation JSON, fallback erreur).

## Phase 6 — Seed initial (T36–T39)

- **T36** `[OPS]` Créer `backend/app/modules/resources/seed.py` avec liste `SEED_RESOURCES` : 5 guides ESG, 5 fiches intermédiaires (BOAD/PNUD/BAD/FEM/GCF avec 6 sections), 3 templates `.docx/.xlsx`, 2 FAQ. Chaque ressource avec `source_id` F01 vérifiée existante.
- **T37** `[OPS]` Rédiger fichiers réels `/uploads/resources/templates/{politique-anti-corruption.docx, charte-ess.docx, registre-risques.xlsx}` (ou fichiers placeholder si rédaction trop longue, à compléter post-PR).
- **T38** `[OPS]` Créer script CLI `backend/scripts/seed_resources.py` invocable via `python -m app.scripts.seed_resources` — idempotent (SELECT before INSERT par slug).
- **T39** `[T]` Tests `backend/tests/test_seed/test_seed_resources.py` (4 cas : count ≥ 15, idempotence, source_id verified, slug unique).

## Phase 7 — Frontend types + composables + store (T40–T43)

- **T40** `[FE]` Créer `frontend/app/types/resource.ts` : types miroir (Resource, ResourceType, Language, PublicationStatus, TargetAudience, ResourceListItem, ResourceFilters, IntermediaryGuide).
- **T41** `[FE]` Créer `frontend/app/composables/useResources.ts` (`listResources`, `getResource`, `getIntermediaryGuide`, `incrementView`, `searchResources`).
- **T42** `[FE]` Créer `frontend/app/composables/useAdminResources.ts` (CRUD complet + upload).
- **T43** `[FE]` Créer `frontend/app/stores/resources.ts` (Pinia : items, total, currentResource, filters, loading, error + getters byType/byCategory).

## Phase 8 — Frontend composants publics (T44–T49)

- **T44** `[FE]` Composant `frontend/app/components/resources/ResourceCard.vue` (props, dark mode, click handler).
- **T45** `[FE]` Composant `frontend/app/components/resources/ResourceTypeBadge.vue` (5 couleurs par type).
- **T46** `[FE]` Composant `frontend/app/components/resources/ResourceMarkdownRenderer.vue` — parse markdown + DOMPurify + résolution `[texte](#source:<id>)` en `<SourceLink>` cliquable.
- **T47** `[FE]` Composants `ResourceFilters.vue`, `RelatedResources.vue`, `ResourceVideoPlayer.vue` (iframe sandboxée), `ResourceTemplateDownload.vue` (déclenche increment-view).
- **T48** `[FE]` Composant `frontend/app/components/resources/IntermediaryGuideView.vue` — 6 sections (process steps, contacts cards, delays, conseils, attention, FAQ accordion).
- **T49** `[T]` Tests Vitest composants publics (`ResourceCard`, `ResourceMarkdownRenderer`, `ResourceFilters`, `IntermediaryGuideView`) — ~22 tests.

## Phase 9 — Frontend pages publiques (T50–T53)

- **T50** `[FE]` Page `frontend/app/pages/resources/index.vue` — grille paginée + filtres URL-synchronisés + barre de recherche + dark mode.
- **T51** `[FE]` Page `frontend/app/pages/resources/[slug].vue` — header, rendu markdown, bouton télécharger/lecteur vidéo selon type, ressources liées.
- **T52** `[FE]` Page `frontend/app/pages/financing/intermediaries/[id]/guide.vue` (wrapper IntermediaryGuideView + lien retour fonds F07).
- **T53** `[FE]` Ajouter lien sidebar « Bibliothèque » dans `AppSidebar.vue` (icône livre, route `/resources`).

## Phase 10 — Frontend admin (T54–T58)

- **T54** `[FE]` Installer `toast-ui/editor` côté frontend (`npm install @toast-ui/editor`).
- **T55** `[FE]` Composant `frontend/app/components/admin/resources/ResourceForm.vue` — onglets (Général, Contenu markdown via toast-ui, Médias, Sourçage, Audience, Métadonnées) + dark mode.
- **T56** `[FE]` Composants admin `ResourceList.vue`, `ResourcePublishButton.vue` (4-yeux), `SourcePicker.vue` (réutilise composant F01 si existant).
- **T57** `[FE]` Pages `frontend/app/pages/admin/resources/{index.vue, new.vue, [id].vue}` + lien sidebar admin.
- **T58** `[T]` Tests Vitest composants admin (`ResourceForm`, `ResourcePublishButton`, `useAdminResources`, `stores/resources`) — ~25 tests.

## Phase 11 — E2E + finalisation (T59–T64)

- **T59** `[T]` Spec Playwright `frontend/tests/e2e/F20-bibliotheque-ressources.spec.ts` — 4 scénarios (consulter guide, fiche BOAD, télécharger template, admin publish 4-yeux).
- **T60** `[OPS]` Documentation `docs/resources-library.md` : cycle de vie, sourçage F01 obligatoire, garde-fou anti-mutation LLM, versioning F04, workflow 4-yeux, dépannage.
- **T61** `[T]` Vérifier couverture backend ≥ 80 % sur les modules F20 (`pytest --cov=app/modules/resources --cov=app/graph/tools/resource_tools --cov=app/models/resource --cov-report=term-missing`).
- **T62** `[T]` Vérifier couverture frontend Vitest ≥ 80 % sur les composants/composables F20.
- **T63** `[T]` Vérifier zéro régression : `pytest backend/tests` (tous les tests baseline + F20 verts) et `npm run test` (tous les Vitest verts).
- **T64** `[OPS]` Commit final avec message conventionnel `feat(F20): bibliothèque ressources + fiches par intermédiaire` (NE PAS push selon instructions caller).

---

## Dépendances clés

```
T01–T03 (DB) → T04–T05 (model) → T06–T08 (tests model)
                                     ↓
T09–T12 (schemas) → T13–T22 (service) → T23–T30 (routers + tests)
                                     ↓
T31–T35 (tools + guard) → T36–T39 (seed)
                                     ↓
T40–T43 (FE types/composables/store) → T44–T49 (composants publics)
                                     ↓
T50–T53 (pages publiques) → T54–T58 (admin) → T59–T64 (E2E + final)
```

**Parallélisable** : T44–T48 (composants publics indépendants), T54–T56 (composants admin indépendants), T36–T37 (rédaction seed pendant que T31–T35 avance).

---

## Critères d'acceptation par phase

- **Phase 1 (T01–T08)** : `alembic upgrade head/downgrade -1/upgrade head` passe sur PostgreSQL ; tests model + migration verts.
- **Phase 2 (T09–T12)** : tests schemas Pydantic verts (12/12) ; couverture ≥ 95 %.
- **Phase 3 (T13–T22)** : tests service verts (18/18) ; couverture ≥ 85 %.
- **Phase 4 (T23–T30)** : tests routers verts (20/20) ; test atomicité passé ; couverture ≥ 90 %.
- **Phase 5 (T31–T35)** : test conformité `no_resource_mutation_tool` PASS ; tests tools verts (6/6).
- **Phase 6 (T36–T39)** : seed idempotent vérifié ; ≥ 15 ressources en base après run.
- **Phase 7–10 (T40–T58)** : tests Vitest verts (~47) ; dark mode complet (manuel) ; pages accessibles.
- **Phase 11 (T59–T64)** : E2E Playwright verts (4/4) ; couverture globale ≥ 80 % ; zéro régression.

---

## Notes opérationnelles

- **Time-boxing** : ~8 jours-développeur (1.5 sprints conformément à la spec source).
- **Risque rédaction seed** : si la rédaction des 15 ressources prend plus d'une journée, prioriser fiches intermédiaires (BOAD/PNUD/GCF) et conserver les autres en `draft` avec issue de suivi post-MVP.
- **Pas de push** : commit local uniquement (instruction caller).
