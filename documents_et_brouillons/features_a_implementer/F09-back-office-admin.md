# F09 — Back-Office Admin Complet

**Module(s) source(s)** : Module 9 (Back-Office Admin), Module 0.1 (Source workflow), Module 0.5 (Versioning)
**Priorité** : P0 — bloquante "sans ce module, personne ne peut peupler le catalogue → plateforme inutile"
**Dépendances** : F01 (Source + Indicator + Référentiel), F02 (rôle Admin + RLS), F03 (audit log), F04 (versioning), F07 (Offer), F08 (révocation attestations), F23 (Skills)
**Estimation** : 3-4 sprints

## Contexte & motivation

Module 9 du brainstorming (citation textuelle) : « Sans ce module, **personne ne peut peupler le catalogue → plateforme inutile**. »

**État actuel** :
- Aucun routeur backend `/api/admin/*`
- Aucune page frontend `/admin/*`
- Aucun champ `role` sur User (F02 résout ça)
- Anti-pattern `admin_emails = {"admin@esg-mefali.com", "admin@mefali.org"}` codé en dur dans `backend/app/modules/financing/router.py:118` (à supprimer)
- Catalogue actuel peuplé via seed Python codé en dur (`modules/financing/seed.py`, `modules/esg/criteria.py`, `modules/carbon/emission_factors.py`) — toute modification = redéploiement

**Conséquences** :
- Pas de gestion produit (impossible d'ajouter un fonds, un intermédiaire, une source)
- Pas de validation 4-yeux des sources (Module 0.1 vide)
- Pas de support PME (incident, reset password, révocation attestation)
- Pas de métriques admin (combien de PME, sources pending, coûts LLM)
- Plateforme inopérable en production

## User stories

- **Admin Mefali** : « Je veux un layout admin distinct (sidebar rouge "Mode Admin") qui me donne accès aux écrans de gestion catalogue, sources, comptes PME, métriques. »
- **Admin** : « Je veux saisir une nouvelle Source (URL, titre, publisher, version, date, page), elle est en `pending`, un autre admin la valide → `verified`. Tant qu'elle n'est pas verified, le LLM ne peut pas l'utiliser. »
- **Admin** : « Je veux créer un nouveau Fonds, l'attacher à un ou plusieurs Intermédiaires (avec dates d'accréditation), définir ses critères (cliquer sur Indicateurs existants), uploader son logo, et passer en `published` quand toutes les sources liées sont `verified`. »
- **Admin** : « Je veux voir un compte PME en lecture seule (avec audit log de ma consultation visible côté PME), reset son mot de passe en cas de blocage, ou révoquer une attestation en cas d'incident. »
- **Admin** : « Je veux des métriques : nombre de sources pending/verified/outdated, nombre de PME actives, candidatures en cours, attestations émises, coûts LLM agrégés. »

## Périmètre fonctionnel

### Architecture du back-office

**Backend** : Module `app/modules/admin/` (squelette en F02, peuplé ici) avec sous-routers :
- `funds_router.py` (CRUD complet, déjà partiellement existant)
- `intermediaries_router.py` (CRUD complet)
- `offers_router.py` (CRUD via F07)
- `referentials_router.py` (CRUD)
- `indicators_router.py` (CRUD)
- `criteria_router.py` (CRUD)
- `templates_router.py` (CRUD templates dossier, lien avec F15)
- `sources_router.py` (CRUD + workflow validation)
- `emission_factors_router.py` (CRUD facteurs ADEME/IPCC, lien F17)
- `simulation_factors_router.py` (CRUD constantes simulateur, lien F16)
- `users_router.py` (lecture seule + reset password + toggle is_active)
- `attestations_router.py` (révocation)
- `metrics_router.py` (KPIs admin)
- `audit_router.py` (audit log global, déjà créé par F03)
- `skills_router.py` (CRUD skills, F23)

Tous protégés par `Depends(get_current_admin)` (F02).

**Frontend** : Layout `layouts/admin.vue` (squelette en F02, finalisé ici). Pages dans `pages/admin/*`.

### 9.1 Gestion du Catalogue

#### CRUD Fonds source

Pages :
- `pages/admin/funds/index.vue` : liste paginée avec filtres (`fund_type`, `status`, `publication_status`, `theme`)
- `pages/admin/funds/new.vue` : formulaire création
- `pages/admin/funds/[id].vue` : édition + onglets (Identité, Critères, Documents requis, Intermédiaires accrédités, Sources liées)

Workflow :
1. Saisie en `publication_status='draft'`
2. Lier au moins une Source (via picker `<SourcePicker>`) — la source doit déjà exister en `verified`
3. Définir tous les champs métier
4. Bouton "Publier" disabled tant que Sources non verified
5. Au clic "Publier" : passage `published`, visible côté PME

#### CRUD Intermédiaires

Idem fonds, page `pages/admin/intermediaries/*`. Champs spécifiques (`required_documents`, `fees_structured`, `processing_time_days`, `success_rate`).

#### CRUD Offres = couples

Page `pages/admin/offers/*` :
- Création via sélection d'un Fund + Intermediary (FK)
- Bouton "Calcul auto" qui pré-remplit `effective_*` depuis `compute_effective_offer` (F07)
- Édition des `effective_*` si l'admin veut ajuster
- Validation : Fund et Intermediary doivent être tous deux `published` ; toutes les sources des effective_* doivent être `verified`

#### CRUD Référentiels + Indicateurs + Critères

Pages :
- `pages/admin/referentials/*` : liste référentiels (ESG Mefali, GCF, IFC, BOAD, GRI, ODD, etc.) avec versioning visible
- `pages/admin/indicators/*` : liste indicateurs atomiques (ex : "% déchets recyclés", "tCO2e Scope 1", "Femmes en gouvernance")
- `pages/admin/criteria/*` : liste conditions logiques sur indicateurs

Édition d'un référentiel :
- Ajouter/retirer des indicateurs avec poids/seuil
- Versioning : éditer crée une nouvelle version (F04)

#### CRUD Documents requis

Page `pages/admin/required-documents/*` : catalogue mutualisé de documents (étude impact, business plan vert, etc.) avec template/format spec, chacun sourcé.

#### CRUD Templates de dossier

Page `pages/admin/templates/*` : templates par Offre (lien fort avec F15 et F23 Skills). Chaque template est associé à une Skill `skill_dossier_<offre>`.

#### CRUD Facteurs d'émission

Page `pages/admin/emission-factors/*` : table éditable (ADEME/IPCC/IEA) avec country, year, factor_value, source_id. Lien fort avec F17.

#### CRUD Simulation factors

Page `pages/admin/simulation-factors/*` : constantes du simulateur (ROI, carbon impact ratio) avec source obligatoire. Lien avec F16.

### 9.2 Gestion des Sources (CRITIQUE)

Pages :
- `pages/admin/sources/index.vue` : liste avec onglets "Toutes / Pending / Verified / Outdated"
- `pages/admin/sources/new.vue` : formulaire (URL, title, publisher, version, date_publi, page, section, captured_by=me)
- `pages/admin/sources/[id].vue` : détail
  - Bouton "Ouvrir le document officiel" (target="_blank")
  - Bouton "Marquer comme vérifiée" (visible **uniquement** si `current_user.id != source.captured_by_user_id` — workflow 4-yeux)
  - Bouton "Marquer comme obsolète" (avec champ raison)
  - Section "Entités dépendantes" (impact analysis : liste des indicators, criteria, formulas, etc. qui pointent vers cette source)

Workflow validation :
- Admin A saisit Source → status `pending`
- Admin B (≠ A) clique "Vérifier" → status `verified`, tracé dans audit log
- Source utilisable par le LLM uniquement quand `verified`

### 9.3 Support PME

Page `pages/admin/companies/index.vue` : liste paginée des comptes PME (filtrable par status, secteur, dernière connexion).

Page `pages/admin/companies/[account_id].vue` : vue lecture seule
- Profil entreprise
- Projets (F06)
- Candidatures (F07)
- Évaluations ESG/Carbon/Crédit (résumés)
- Attestations émises (avec bouton "Révoquer" — F08)
- Audit log de ce compte (F03)
- **Toute consultation par admin = audit_log entry visible côté PME** (F03 `view_admin`)

Actions :
- `POST /api/admin/users/{user_id}/reset-password` : génère token temporaire, envoie email "Cliquez ici pour définir un nouveau mot de passe" valide 1h
- `POST /api/admin/users/{user_id}/toggle-active` : bascule `is_active` (avec raison loggée)
- `POST /api/admin/attestations/{id}/revoke` (via F08) : raison obligatoire

### 9.4 Métriques Admin

Page `pages/admin/metrics/index.vue` : dashboard KPIs avec cards :
- **Sources** : total / pending / verified / outdated (avec trend 30j)
- **Comptes** : total PME actives / désactivées / nouveaux 30j
- **Candidatures** : par statut, taux de soumission, taux de succès (post-MVP)
- **Attestations** : émises / révoquées / actives
- **Coûts LLM** : par jour / par mois / par PME (post-MVP) / par tool / par modèle

Endpoint `GET /api/admin/metrics/overview` qui agrège.

### Audit log admin

Page `pages/admin/audit/index.vue` (créé par F03 mais finalisé ici) :
- Audit log global (toutes les actions plateforme)
- Filtres par account_id, user_id, entity_type, source_of_change, période
- Export CSV

### Workflow draft → published transversal

Pour toutes les entités catalogue (`funds`, `intermediaries`, `offers`, `referentials`, `indicators`, `criteria`, `templates`, `emission_factors`, `skills`) :
- Champ `publication_status: enum('draft', 'published')`
- Trigger PostgreSQL : passage `published` autorisé **uniquement** si toutes les `Source` liées (directement ou via `entity_sources`) sont en `verification_status='verified'`
- Le LLM ne consomme que les entités `published`

### Anti-pattern à supprimer

Dans `backend/app/modules/financing/router.py:118`, supprimer :
```python
admin_emails = {"admin@esg-mefali.com", "admin@mefali.org"}
if current_user.email not in admin_emails:
    raise HTTPException(403, ...)
```

Remplacer par :
```python
@router.post("/funds", dependencies=[Depends(get_current_admin)])
```

Mais idéalement, **migrer** les endpoints `/funds`, `/intermediaries` du router public vers le router admin (`/api/admin/funds`).

## Hors-scope (post-MVP)

- Bulk import CSV/Excel pour catalogue (lignes par ligne reste OK MVP)
- Workflow `pending_review` intermédiaire entre draft et verified pour les sources
- Contributions communautaires consultants (marketplace)
- Changelog public
- Permissions granulaires intra-admin (dpo / catalog_editor / support)
- Coûts LLM par PME (nécessite ajout `tokens_in/tokens_out/cost_usd` sur `tool_call_logs`)
- Analytics produit (cohort retention, funnel)

## Exigences techniques

### Backend

- Migration Alembic `026_add_publication_status_columns.py` :
  - Ajouter `publication_status` sur funds, intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills
  - Trigger PostgreSQL `before_publish_check_sources_verified`
  - Trigger PostgreSQL `before_verify_source_check_different_admin` (4-yeux)
- Module `app/modules/admin/` avec ~12 sous-routers
- Service `app/modules/admin/sources_service.py` (avec impact analysis : `get_dependents(source_id)`)
- Service `app/modules/admin/users_service.py` (reset password, toggle active)
- Service `app/modules/admin/metrics_service.py` (agrégations)
- Mise à jour `app/main.py` : monter `/api/admin/*`
- Tests :
  - Test 4-yeux : admin A saisit, admin A tente verify → 403 ; admin B verify → OK
  - Test publish gating : tenter publish d'un fund avec source non verified → 400
  - Test isolation : un user PME tente d'accéder à `/api/admin/*` → 403
  - Test admin view audit : consulter compte PME → audit_log entry visible côté PME
  - Test reset password : token email valide 1h, expiration cohérente
  - Test métriques : agrégation correcte sur fixtures

### Frontend

- Layout `layouts/admin.vue` (sidebar admin, header avec badge "Mode Admin", footer minimal)
- Pages :
  - `pages/admin/index.vue` (dashboard métriques)
  - `pages/admin/sources/*` (3 pages : index, new, [id])
  - `pages/admin/funds/*`
  - `pages/admin/intermediaries/*`
  - `pages/admin/offers/*`
  - `pages/admin/referentials/*`
  - `pages/admin/indicators/*`
  - `pages/admin/criteria/*`
  - `pages/admin/templates/*`
  - `pages/admin/emission-factors/*`
  - `pages/admin/simulation-factors/*`
  - `pages/admin/companies/*` (2 pages : index, [account_id])
  - `pages/admin/attestations/index.vue`
  - `pages/admin/audit/index.vue`
  - `pages/admin/metrics/index.vue`
  - `pages/admin/skills/*` (lien F23)
- Composants partagés `components/admin/` :
  - `<EntityCRUDTable>` générique pour list view
  - `<SourcePicker>` (modal pour sélectionner une source verified)
  - `<PublishButton>` (avec disabled state si conditions non remplies)
  - `<DraftBadge>`, `<PublishedBadge>`, `<PendingBadge>`, `<VerifiedBadge>`, `<OutdatedBadge>`
  - `<ImpactAnalysisModal>` (pour suppression / modification source/entité)
  - `<MetricsCard>`
- Composables `composables/useAdminCatalog.ts`, `useAdminSources.ts`, `useAdminMetrics.ts`
- Stores `stores/adminCatalog.ts`, `stores/adminSources.ts`, etc.
- Middleware `middleware/admin.ts` (créé F02)
- Dark mode (avec **palette accentuée admin** différente : par exemple bordures rouge foncé pour distinguer du PME)

### Base de données

- Colonnes `publication_status` ajoutées sur ~10 tables
- Triggers PostgreSQL spécifiés
- (post-MVP) : table `password_reset_tokens(token_hash, user_id, expires_at, used_at)` pour reset password sécurisé

## Critères d'acceptation

- [ ] Layout `admin.vue` fonctionnel avec sidebar rouge "Mode Admin"
- [ ] Tous les CRUD entités catalogue fonctionnels (funds, intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills)
- [ ] Workflow draft → published actif sur toutes les entités catalogue
- [ ] Workflow 4-yeux validation source actif (admin A ≠ admin B)
- [ ] Page `pages/admin/sources/[id]` affiche correctement les entités dépendantes (impact analysis)
- [ ] Page `pages/admin/companies/[account_id]` accessible en read-only avec audit log de la consultation
- [ ] Endpoint reset password fonctionnel avec token email valide 1h
- [ ] Endpoint toggle is_active fonctionnel
- [ ] Page `pages/admin/metrics` affiche les KPIs (sources, comptes, candidatures, attestations, coûts LLM)
- [ ] Anti-pattern email whitelist supprimé de `financing/router.py`
- [ ] Test E2E : admin A saisit Source → status pending → admin A tente verify → bloqué → admin B verify → status verified
- [ ] Test E2E : admin crée fonds avec source non verified → tente publish → bloqué ; admin verify la source → publish OK
- [ ] Test E2E : user PME tente `/admin/*` → 403 redirect
- [ ] Test E2E : admin reset password user PME → user reçoit email → clique → définit nouveau pw → login OK
- [ ] Couverture tests ≥ 80 %
- [ ] Documentation `docs/admin-runbook.md` : procédures (ajouter source, publier fonds, gérer incident, révoquer attestation)

## Risques & garde-fous

- **Risque** : un admin se trompe et publie un fonds avec mauvais critères. **Garde-fou** : versioning F04 → revenir à la version précédente. Audit log F03 → traçabilité.
- **Risque** : un admin malveillant (interne) tente d'accéder à des données PME sans trace. **Garde-fou** : audit log `view_admin` automatique, visible côté PME. Détection de patterns anormaux (post-MVP).
- **Risque** : la suppression d'une Source casse les entités qui en dépendent. **Garde-fou** : `<ImpactAnalysisModal>` avant suppression, refus si dépendants existent (force delete possible avec cascade `valid_to`).
- **Risque** : le seed initial des sources prend des semaines (capture manuelle de 30+ docs officiels). **Garde-fou** : prioriser les sources critiques (ADEME pour carbone, GCF Investment Framework, IFC PS, taxonomie UEMOA), accepter une phase pilote avec catalogue partiel.
- **Risque** : performance des pages admin avec catalogue de 1000+ entités. **Garde-fou** : pagination, recherche full-text, lazy loading.
- **Risque** : confusion visuelle entre interface PME et interface admin. **Garde-fou** : sidebar et header avec couleurs/styles distinctifs, badge "Mode Admin" persistant en haut, banner d'avertissement si admin se logue depuis une PME résiduelle.
