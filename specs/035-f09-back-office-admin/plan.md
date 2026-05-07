# Implementation Plan: F09 — Back-Office Admin Complet (Module 9)

**Branch**: `feat/F09-back-office-admin` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/035-f09-back-office-admin/spec.md`

## Summary

F09 finalise le back-office Admin Mefali, le module qui permet à l'équipe interne de **peupler le catalogue qui alimente toute la plateforme**. Sans F09, le système est inopérable en production : aucun fonds, aucun intermédiaire, aucune source ne peut être ajouté ou validé.

3 capacités principales :

1. **CRUD complet du catalogue (~10 entités)** : 15 sous-routers `app/modules/admin/*` (funds, intermediaries, offers, referentials, indicators, criteria, templates, sources, emission_factors, simulation_factors, users, attestations, metrics, audit, skills) protégés par `Depends(get_current_admin)`. Workflow `draft → published` transversal sur 10 entités catalogue.
2. **Workflow 4-yeux validation source + Publish gating** : 2 triggers PostgreSQL (`before_publish_check_sources_verified` sur 10 tables, `before_verify_source_check_different_admin` sur sources) qui imposent les invariants au niveau BDD (impossible de bypass au niveau applicatif).
3. **Frontend admin** : layout `layouts/admin.vue` avec palette accentuée rouge admin, ~17 pages CRUD, composants partagés (`<EntityCRUDTable>`, `<SourcePicker>`, `<PublishButton>`, badges, `<ImpactAnalysisModal>`, `<MetricsCard>`), middleware `admin.ts`. Support PME : reset password + toggle active + révocation attestation + métriques admin.

Inclut aussi : table `password_reset_tokens` pour reset password sécurisé (token hashé, expiration 1h, usage unique), endpoint public `POST /api/auth/reset-password`, audit log `view_admin` automatique sur consultation admin d'un compte PME (visible côté PME), service email avec fallback console dev.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** : FastAPI, SQLAlchemy async, Alembic, Pydantic v2, bcrypt (password hash), secrets (token génération), psycopg/asyncpg (driver PG pour triggers), Jinja2 (email templates) ; côté frontend Nuxt 4, Vue Composition API, Pinia, TailwindCSS, vue-chartjs (sparkline metrics)
**Storage** : PostgreSQL 16 — 1 nouvelle table (`password_reset_tokens`), 10 tables catalogue avec colonne `publication_status` ajoutée, 2 fonctions PL/pgSQL + 11 triggers BEFORE UPDATE, 1 index supplémentaire sur `password_reset_tokens.token_hash`
**Testing** : pytest + pytest-asyncio (markers `unit`, `integration`, `e2e`) ; Playwright pour E2E frontend ; tests d'intégration triggers nécessitent PostgreSQL réel (les triggers PL/pgSQL ne sont pas portables vers SQLite)
**Target Platform** : Linux server (uvicorn) / GitHub Actions CI (Ubuntu 22.04)
**Project Type** : web-service (mono-repo backend/ + frontend/)
**Performance Goals** :
- `GET /api/admin/funds?page=1&limit=20` : < 200ms P95 sur 1000 entités
- `GET /api/admin/metrics/overview` : < 500ms P95 sur 1000 sources, 5000 users, 100 attestations (CTE agrégat)
- `GET /api/admin/sources/{id}/dependents` : < 300ms P95 (joins multiples mais bornés)
- `POST /api/admin/users/{id}/reset-password` : < 300ms P95 (génération token + email async)
- Page `/admin/funds` : First Contentful Paint < 2s, Time to Interactive < 3s
- Triggers PL/pgSQL : < 5ms overhead par UPDATE
**Constraints** :
- Aucune régression sur les ~935 tests backend existants
- Triggers PostgreSQL implémentés en BDD (pas applicatif) pour garantir les invariants même en cas de bug code
- Audit log F03 sur **toutes** les mutations + sur consultation admin (dedup 1/jour)
- Token reset password jamais en clair en BDD (sha256 hash uniquement)
- Migration zero-downtime : `ADD COLUMN ... DEFAULT 'draft'` sur 10 tables (seuls les nouveaux entrants seront draft, pas les existants en prod après update manuel)
**Scale/Scope** :
- 1 nouvelle table BDD (`password_reset_tokens`) avec 6 colonnes + 2 indexes
- 1 colonne `publication_status` ajoutée sur 10 tables existantes
- 1 nouvelle migration Alembic 035
- 2 fonctions PL/pgSQL + 11 triggers
- 13 nouveaux sous-routers admin (2 existants raffinés : audit, skills)
- 5 nouveaux services admin (`sources_service`, `users_service`, `metrics_service`, `companies_service`, `attestations_service` raffinement)
- 1 endpoint public `POST /api/auth/reset-password`
- ~17 pages frontend admin (~32 fichiers Vue avec sous-routes)
- 8+ composants partagés admin (`EntityCRUDTable`, `SourcePicker`, `PublishButton`, 5 badges, `ImpactAnalysisModal`, `MetricsCard`)
- 5 nouveaux composables (`useAdminCatalog`, `useAdminSources`, `useAdminMetrics`, `useAdminUsers`, `useAdminAttestations`)
- ~30 nouveaux fichiers backend, ~50 nouveaux fichiers frontend, ~10 fichiers modifiés
- Estimation : 3-4 sprints (consigne F09)

## Constitution Check

Pas de fichier constitution dans ce projet (vérification : `.specify/memory/` n'a pas de constitution active). Gates standards appliqués :

- **Test coverage** : ≥ 80 % minimum sur `app/modules/admin/*` (15 sous-routers, 5 services). Tests d'intégration triggers PG (10 tables × publish + 1 source × 4-yeux = 11 tests). Tests E2E (4 obligatoires).
- **Sécurité** : tous les routers admin protégés par `Depends(get_current_admin)`. Token reset password sha256-hashé. Endpoint public `/api/auth/reset-password` validé strict (hash match + expires_at + used_at). Audit log F03 systématique sur mutations + view_admin.
- **Performance** : index composite sur tables catalogue (publication_status, valid_to). CTE pour métriques. Pagination obligatoire sur listes.
- **Immutabilité** : édition entité catalogue `published` crée nouvelle version via VersioningMixin (F04). Pas de mutation in-place. Soft delete uniquement (`valid_to=today()`).
- **Pas de bypass admin** : triggers PostgreSQL imposent les invariants (impossible de patcher la logique applicative pour contourner). 4-yeux strict (même un super-admin ne peut pas valider sa propre source).
- **Anti-pattern email whitelist** : déjà supprimé par F02. F09 ajoute test conformity grep `admin_emails` → 0 match.
- **Audit log F03** : toute mutation et consultation admin tracées. Dedup `view_admin` 1/jour/admin/account.

## Project Structure

### Documentation (this feature)

```text
specs/035-f09-back-office-admin/
├── spec.md                  # Spec finalisée avec clarifications
├── plan.md                  # Ce fichier
├── research.md              # Phase 0 — patterns triggers PG, password reset secure flow, CRUD admin patterns
├── data-model.md            # Phase 1 — schéma password_reset_tokens + publication_status enum + audit log entries types
├── quickstart.md            # Phase 1 — runbook admin (créer fonds, valider source 4-yeux, reset password user, révoquer attestation)
├── contracts/
│   ├── publication_status_enum.md          # Enum draft|published, transitions autorisées
│   ├── trigger_publish_gating.sql          # Fonction PL/pgSQL + 10 triggers
│   ├── trigger_4_eyes_source.sql           # Fonction PL/pgSQL + 1 trigger
│   ├── password_reset_tokens_schema.md     # Schéma table + sécurité token
│   ├── admin_funds_endpoints.md            # Spec REST funds (6 endpoints)
│   ├── admin_intermediaries_endpoints.md
│   ├── admin_offers_endpoints.md
│   ├── admin_referentials_endpoints.md
│   ├── admin_indicators_endpoints.md
│   ├── admin_criteria_endpoints.md
│   ├── admin_templates_endpoints.md
│   ├── admin_sources_endpoints.md          # Inclut /dependents
│   ├── admin_emission_factors_endpoints.md
│   ├── admin_simulation_factors_endpoints.md
│   ├── admin_users_endpoints.md            # /reset-password, /toggle-active
│   ├── admin_companies_endpoints.md        # GET avec audit view_admin
│   ├── admin_attestations_endpoints.md     # /revoke
│   ├── admin_metrics_endpoints.md          # /overview avec MetricsOverview schema
│   ├── auth_reset_password_endpoint.md     # Endpoint public
│   └── metrics_overview_schema.json        # JSON Schema MetricsOverview
├── checklists/
│   └── quality.md           # Checklist qualité spec
└── tasks.md                 # Phase 2 — output /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   ├── email_service.py                    # NOUVEAU OU VALIDÉ — send_password_reset_email() + console fallback
│   │   └── security.py                         # MODIFIÉ — generate_reset_token, hash_token, verify_token
│   ├── models/
│   │   └── password_reset_token.py             # NOUVEAU — PasswordResetToken SQLAlchemy
│   ├── modules/
│   │   ├── admin/                              # ÉTENDU
│   │   │   ├── __init__.py
│   │   │   ├── router.py                       # MODIFIÉ — include 13 sous-routers
│   │   │   ├── schemas.py                      # NOUVEAU — schemas partagés (MetricsOverview, DependentsReport, etc.)
│   │   │   ├── funds_router.py                 # NOUVEAU — 6 endpoints CRUD
│   │   │   ├── intermediaries_router.py        # NOUVEAU
│   │   │   ├── offers_router.py                # NOUVEAU — inclut compute-effective F07
│   │   │   ├── referentials_router.py          # NOUVEAU
│   │   │   ├── indicators_router.py            # NOUVEAU
│   │   │   ├── criteria_router.py              # NOUVEAU
│   │   │   ├── templates_router.py             # NOUVEAU
│   │   │   ├── sources_router.py               # NOUVEAU — inclut /dependents impact analysis
│   │   │   ├── emission_factors_router.py      # NOUVEAU
│   │   │   ├── simulation_factors_router.py    # NOUVEAU
│   │   │   ├── users_router.py                 # NOUVEAU — reset-password, toggle-active
│   │   │   ├── companies_router.py             # NOUVEAU — read-only + audit view_admin
│   │   │   ├── attestations_router.py          # NOUVEAU OU RAFFINÉ — /revoke
│   │   │   ├── metrics_router.py               # NOUVEAU — /overview
│   │   │   ├── audit_router.py                 # CONSERVÉ (F03)
│   │   │   ├── skills_router.py                # CONSERVÉ (F23)
│   │   │   ├── catalog_publish_helper.py       # NOUVEAU — service partagé : publish entity, audit log
│   │   │   ├── sources_service.py              # NOUVEAU — get_dependents, can_delete, soft_delete_with_cascade
│   │   │   ├── users_service.py                # NOUVEAU — initiate_password_reset, complete_password_reset, toggle_user_active
│   │   │   ├── companies_service.py            # NOUVEAU — get_company_overview avec audit view_admin
│   │   │   └── metrics_service.py              # NOUVEAU — compute_overview avec CTE
│   │   ├── auth/
│   │   │   └── router.py                       # MODIFIÉ — ajout POST /api/auth/reset-password endpoint public
│   │   └── financing/
│   │       └── router.py                       # CONSERVÉ — F02 a déjà retiré l'anti-pattern email whitelist
│   └── main.py                                 # MODIFIÉ — monter sous-routers admin (déjà partiel via F02)
├── alembic/
│   └── versions/
│       └── 035_admin_publication_status_workflow.py  # NOUVEAU — colonne + triggers + table
└── tests/
    ├── unit/
    │   ├── core/
    │   │   ├── test_email_service.py           # NOUVEAU — console fallback
    │   │   └── test_security_token.py          # NOUVEAU — generate, hash, verify
    │   ├── models/
    │   │   └── test_password_reset_token_model.py  # NOUVEAU
    │   └── modules/
    │       └── admin/
    │           ├── test_sources_service.py     # get_dependents, can_delete, cascade
    │           ├── test_users_service.py       # reset password flow, toggle active
    │           ├── test_companies_service.py   # get_company_overview + audit view_admin dedup
    │           └── test_metrics_service.py     # CTE aggregation correctness
    ├── integration/
    │   ├── admin/
    │   │   ├── test_admin_funds_router.py      # NOUVEAU — 6 endpoints + auth
    │   │   ├── test_admin_intermediaries_router.py
    │   │   ├── test_admin_offers_router.py
    │   │   ├── test_admin_referentials_router.py
    │   │   ├── test_admin_indicators_router.py
    │   │   ├── test_admin_criteria_router.py
    │   │   ├── test_admin_templates_router.py
    │   │   ├── test_admin_sources_router.py    # CRUD + 4-yeux + impact
    │   │   ├── test_admin_emission_factors_router.py
    │   │   ├── test_admin_simulation_factors_router.py
    │   │   ├── test_admin_users_router.py      # reset-password + toggle-active
    │   │   ├── test_admin_companies_router.py  # GET + audit view_admin
    │   │   ├── test_admin_attestations_router.py  # /revoke
    │   │   └── test_admin_metrics_router.py    # /overview
    │   ├── triggers/
    │   │   ├── test_trigger_publish_gating.py  # 10 tables × publish blocked si source pending
    │   │   └── test_trigger_4_eyes_source.py   # admin A != admin B
    │   ├── auth/
    │   │   └── test_reset_password_endpoint.py # endpoint public
    │   └── conformity/
    │       └── test_no_admin_emails_whitelist.py  # grep test
    └── e2e/
        ├── test_admin_4_eyes_source_flow.py    # E2E complet
        ├── test_admin_publish_gating_flow.py   # E2E complet
        ├── test_admin_isolation_pme.py         # E2E user PME → 403
        └── test_admin_reset_password_flow.py   # E2E reset → email → reset

frontend/
├── app/
│   ├── layouts/
│   │   └── admin.vue                           # MODIFIÉ — finalisation sidebar + dark mode + palette rouge
│   ├── middleware/
│   │   └── admin.ts                            # CONSERVÉ (F02)
│   ├── pages/
│   │   ├── admin/
│   │   │   ├── index.vue                       # NOUVEAU — dashboard métriques
│   │   │   ├── funds/
│   │   │   │   ├── index.vue                   # NOUVEAU — liste + filtres
│   │   │   │   ├── new.vue                     # NOUVEAU — formulaire création
│   │   │   │   └── [id].vue                    # NOUVEAU — édition + onglets
│   │   │   ├── intermediaries/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── offers/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue                    # avec bouton "Calcul auto"
│   │   │   ├── referentials/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── indicators/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── criteria/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── templates/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── emission-factors/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── simulation-factors/
│   │   │   │   ├── index.vue
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue
│   │   │   ├── sources/
│   │   │   │   ├── index.vue                   # tabs Pending/Verified/Outdated
│   │   │   │   ├── new.vue
│   │   │   │   └── [id].vue                    # détail + impact analysis
│   │   │   ├── companies/
│   │   │   │   ├── index.vue                   # liste PME
│   │   │   │   └── [account_id].vue            # read-only + actions
│   │   │   ├── attestations/
│   │   │   │   └── index.vue                   # liste + révocation
│   │   │   ├── audit/
│   │   │   │   └── index.vue                   # CONSERVÉ (F03), valider liens
│   │   │   ├── metrics/
│   │   │   │   └── index.vue                   # KPIs détaillés
│   │   │   └── skills/
│   │   │       ├── index.vue                   # CONSERVÉ (F23)
│   │   │       ├── new.vue                     # CONSERVÉ (F23)
│   │   │       └── [id].vue                    # CONSERVÉ (F23)
│   │   └── auth/
│   │       └── reset.vue                       # NOUVEAU — page publique reset password (consomme token)
│   ├── components/
│   │   └── admin/
│   │       ├── EntityCRUDTable.vue             # NOUVEAU — table générique (slots, pagination, recherche)
│   │       ├── SourcePicker.vue                # NOUVEAU — modal sélection source verified
│   │       ├── PublishButton.vue               # NOUVEAU — bouton avec disabled state + tooltip
│   │       ├── ImpactAnalysisModal.vue         # NOUVEAU — liste dépendants + cancel/force
│   │       ├── MetricsCard.vue                 # NOUVEAU — carte KPI avec sparkline
│   │       ├── badges/
│   │       │   ├── DraftBadge.vue              # gris
│   │       │   ├── PublishedBadge.vue          # vert
│   │       │   ├── PendingBadge.vue            # jaune
│   │       │   ├── VerifiedBadge.vue           # bleu
│   │       │   └── OutdatedBadge.vue           # rouge
│   │       ├── forms/
│   │       │   ├── FundForm.vue                # NOUVEAU — formulaire fund (réutilisable new/edit)
│   │       │   ├── IntermediaryForm.vue
│   │       │   ├── OfferForm.vue               # avec bouton "Calcul auto"
│   │       │   ├── ReferentialForm.vue
│   │       │   ├── IndicatorForm.vue
│   │       │   ├── CriterionForm.vue
│   │       │   ├── TemplateForm.vue
│   │       │   ├── EmissionFactorForm.vue
│   │       │   ├── SimulationFactorForm.vue
│   │       │   └── SourceForm.vue
│   │       └── companies/
│   │           ├── CompanyOverview.vue         # read-only profile + projets + scores
│   │           └── CompanyActions.vue          # boutons reset password, toggle active, révoquer
│   ├── composables/
│   │   ├── useAdminCatalog.ts                  # NOUVEAU — CRUD générique pour 10 entités
│   │   ├── useAdminSources.ts                  # NOUVEAU — sources + dependents
│   │   ├── useAdminUsers.ts                    # NOUVEAU — reset password + toggle active
│   │   ├── useAdminCompanies.ts                # NOUVEAU — get_company_overview
│   │   ├── useAdminAttestations.ts             # NOUVEAU — list + revoke
│   │   ├── useAdminMetrics.ts                  # NOUVEAU — overview
│   │   └── useAdminPublication.ts              # NOUVEAU — publish entity, gestion 400 errors
│   └── stores/
│       ├── adminCatalog.ts                     # NOUVEAU — state catalogue par type
│       ├── adminSources.ts                     # NOUVEAU
│       └── adminMetrics.ts                     # NOUVEAU
└── tests/
    └── e2e/
        └── admin/
            ├── catalog-funds.spec.ts           # NOUVEAU — Playwright CRUD funds
            ├── source-4-eyes.spec.ts           # NOUVEAU
            ├── publish-gating.spec.ts          # NOUVEAU
            ├── isolation-pme.spec.ts           # NOUVEAU
            └── reset-password.spec.ts          # NOUVEAU

docs/
└── admin-runbook.md                            # NOUVEAU — procédures admin (créer fonds, valider source, gérer incident, révoquer attestation, reset pw)
```

**Structure Decision** : architecture modulaire conforme aux conventions du projet. F09 est ~50 % backend (15 sous-routers + 5 services + migration + triggers) + ~50 % frontend (~32 pages + 8+ composants partagés + 7 composables). La majorité des modifications portent sur 5 zones :

1. `app/modules/admin/*` (étension du module avec 13 sous-routers et 5 services)
2. `app/models/password_reset_token.py` + `app/core/security.py` + `app/core/email_service.py` (sécurité reset password)
3. `alembic/versions/035_admin_publication_status_workflow.py` (migration colonne + triggers)
4. `frontend/app/pages/admin/*` (~32 pages CRUD)
5. `frontend/app/components/admin/*` (composants partagés réutilisables)

Plus tests d'intégration triggers PG (11 tests), tests E2E (4 tests obligatoires + ~5 tests par catalogue), runbook admin documenté.

## Phases

### Phase 0 — Research

Sortie : `research.md`. Sujets :

- **Patterns triggers PostgreSQL pour invariants métier** : approches comparées (BEFORE INSERT vs BEFORE UPDATE, RAISE EXCEPTION SQLSTATE custom). Choix : SQLSTATE `P0001` avec MESSAGE structuré, catché par SQLAlchemy → `IntegrityError` → 400 dans FastAPI.
- **Sécurité reset password (token flow)** : revue OWASP Authentication Cheat Sheet. Token 32 bytes URL-safe (secrets.token_urlsafe), sha256 hash en BDD, expiration courte (1h MVP, 15min recommandé post-MVP), usage unique. Comparaison avec JWT short-lived (rejeté car nécessite rotation).
- **Pattern CRUD admin scalable** : DRY via composant `<EntityCRUDTable>` générique + `useAdminCatalog<T>` typed composable. Comparaison avec patterns Strapi / Forest / Retool.
- **Audit log dedup** : stratégies pour éviter spam audit_log sur recharges page admin. Choix : dedup logique en service (1/jour/admin/account), pas de dedup en BDD (UNIQUE constraint trop rigide).
- **Migration zero-downtime** : ADD COLUMN avec DEFAULT — depuis PostgreSQL 11, INSTANT donc safe. Le risque est uniquement les entités existantes en prod qui passent toutes draft → invisible côté PME. Plan rollout : (1) déployer migration, (2) script seed_publish_existing_catalog.py UPDATE existing en published, (3) déployer code utilisant publication_status.
- **Email service en dev/prod** : abstraction `EmailService` avec backends `console` (dev), `smtp` (staging), `sendgrid|ses` (prod). Choix MVP : console + smtp basique, post-MVP service externe.
- **Composable Pinia pour CRUD générique** : pattern factory `createAdminCatalogStore<T>()` qui produit un store typed. Réutilisé sur 10 entités catalogue.
- **Performance metrics aggregation** : CTE PostgreSQL avec sous-requêtes parallèles vs requêtes successives. Choix : 1 CTE multi-section pour P95 < 500ms.
- **Impact analysis service** : graph traversal vs requêtes SQL séparées par table. Choix : requêtes SQL séparées avec `Promise.all` côté service Python (asyncio.gather), plus simple à maintenir.

### Phase 1 — Design

Sortie : `data-model.md` + `contracts/`.

**`data-model.md`** documente :

- Colonne `publication_status` ajoutée sur 10 tables (CHECK IN ('draft','published'), DEFAULT 'draft', NOT NULL)
- Table `password_reset_tokens` (6 colonnes + 2 indexes)
- Fonction PL/pgSQL `before_publish_check_sources_verified()` (logique : iter sources liées, if any.verification_status != 'verified' THEN RAISE)
- Fonction PL/pgSQL `before_verify_source_check_different_admin()` (logique : if NEW.verified_by_user_id = OLD.captured_by_user_id THEN RAISE)
- 11 triggers BEFORE UPDATE (10 publish + 1 verify)
- Schéma `MetricsOverview` (Pydantic)
- Schéma `DependentsReport` (Pydantic)
- Audit log entries types (subset F03)

**`contracts/`** :

- `publication_status_enum.md` : enum + transitions autorisées (draft → published OK, published → draft via unpublish optionnel post-MVP)
- `trigger_publish_gating.sql` : code SQL des fonctions et triggers
- `trigger_4_eyes_source.sql` : code SQL
- `password_reset_tokens_schema.md` : schéma table + sécurité (hash sha256, expiration, usage unique)
- `admin_*_endpoints.md` : 14 specs REST par sous-router (params, body, response, codes statut, exemples)
- `auth_reset_password_endpoint.md` : endpoint public
- `metrics_overview_schema.json` : JSON Schema strict

**`quickstart.md`** :

- Procédure admin : ajouter une source officielle (saisie + 4-yeux)
- Procédure admin : créer un fonds avec sources liées (draft → publish)
- Procédure admin : gérer un incident PME (consultation + reset password + révocation attestation)
- Procédure admin : interpréter les métriques admin (sources pending pile haute = action requise)
- Procédure dev : exécuter la migration 035 sur DB existante (avec seed_publish_existing_catalog.py)

### Phase 2 — Tasks (NOT created by /speckit.plan)

Voir `tasks.md` (généré par `/speckit.tasks`).

## Migration Alembic 035

```python
"""F09 — Admin publication status workflow + 4-eyes triggers + password reset tokens

Revision ID: 035_admin_publication_status_workflow
Revises: 033_create_skills
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "035_admin_publication_status_workflow"
down_revision = "033_create_skills"
branch_labels = None
depends_on = None


CATALOG_TABLES_FOR_PUBLISH = [
    "funds",
    "intermediaries",
    "offers",
    "referentials",
    "indicators",
    "criteria",
    "templates",
    "emission_factors",
    "simulation_factors",
    "skills",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Ajout colonne publication_status sur 10 tables
    for table in CATALOG_TABLES_FOR_PUBLISH:
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS publication_status VARCHAR(20)
            NOT NULL DEFAULT 'draft'
            CHECK (publication_status IN ('draft', 'published'))
            """
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_publication_status "
            f"ON {table} (publication_status)"
        )

    # 2. Table password_reset_tokens
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_password_reset_tokens_user_expires",
        "password_reset_tokens",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
    )

    if not is_postgres:
        # SQLite : pas de triggers PL/pgSQL (tests d'intégration triggers nécessitent PG réel)
        return

    # 3. Trigger publish gating (PostgreSQL only)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION before_publish_check_sources_verified()
        RETURNS TRIGGER AS $$
        DECLARE
            unverified_count INTEGER;
            offending_source_id UUID;
            offending_status VARCHAR;
            entity_type VARCHAR;
        BEGIN
            -- Only fire on draft -> published
            IF NOT (OLD.publication_status = 'draft' AND NEW.publication_status = 'published') THEN
                RETURN NEW;
            END IF;

            entity_type := TG_TABLE_NAME;

            -- Lookup sources via entity_sources OR direct FK depending on table
            -- (This pseudo-implementation: iterate via entity_sources standard table)
            SELECT s.id, s.verification_status
                INTO offending_source_id, offending_status
            FROM sources s
            JOIN entity_sources es ON es.source_id = s.id
            WHERE es.entity_type = entity_type
              AND es.entity_id = NEW.id
              AND s.verification_status != 'verified'
            LIMIT 1;

            IF offending_source_id IS NOT NULL THEN
                RAISE EXCEPTION
                    'cannot publish: source % has verification_status=%',
                    offending_source_id, offending_status
                    USING ERRCODE = 'P0001';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table in CATALOG_TABLES_FOR_PUBLISH:
        op.execute(
            f"""
            DROP TRIGGER IF EXISTS trg_{table}_before_publish ON {table};
            CREATE TRIGGER trg_{table}_before_publish
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION before_publish_check_sources_verified();
            """
        )

    # 4. Trigger 4-yeux validation source
    op.execute(
        """
        CREATE OR REPLACE FUNCTION before_verify_source_check_different_admin()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Only fire on pending -> verified
            IF NOT (OLD.verification_status = 'pending' AND NEW.verification_status = 'verified') THEN
                RETURN NEW;
            END IF;

            IF NEW.verified_by_user_id IS NULL THEN
                RAISE EXCEPTION
                    '4-eyes principle: verified_by_user_id required'
                    USING ERRCODE = 'P0001';
            END IF;

            IF NEW.verified_by_user_id = OLD.captured_by_user_id THEN
                RAISE EXCEPTION
                    '4-eyes principle violated: verifier (%) must differ from creator (%)',
                    NEW.verified_by_user_id, OLD.captured_by_user_id
                    USING ERRCODE = 'P0001';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_sources_before_verify ON sources;
        CREATE TRIGGER trg_sources_before_verify
            BEFORE UPDATE ON sources
            FOR EACH ROW
            EXECUTE FUNCTION before_verify_source_check_different_admin();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # Drop triggers + functions
        op.execute("DROP TRIGGER IF EXISTS trg_sources_before_verify ON sources")
        op.execute("DROP FUNCTION IF EXISTS before_verify_source_check_different_admin()")
        for table in CATALOG_TABLES_FOR_PUBLISH:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_before_publish ON {table}")
        op.execute("DROP FUNCTION IF EXISTS before_publish_check_sources_verified()")

    # Drop password_reset_tokens
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_expires", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    # Drop publication_status sur 10 tables
    for table in CATALOG_TABLES_FOR_PUBLISH:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_publication_status")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS publication_status")
```

> **Note** : la table `entity_sources` est supposée exister via F01 (table de jointure générique entity_type/entity_id ↔ source_id). Si F01 utilise une approche différente (FK directe par table), la fonction trigger doit être adaptée par table. Le research.md décide de l'approche définitive.

## Phasage TDD (3-4 sprints)

### Sprint 1 — Migration + Triggers + Sources Workflow (P1)

- Migration 035 (colonne + triggers + table password_reset_tokens)
- Tests d'intégration triggers (publish gating × 10 tables, 4-yeux × 1 table sources)
- `app/modules/admin/sources_router.py` + `sources_service.py` (CRUD + 4-yeux + dependents)
- `app/modules/admin/catalog_publish_helper.py` (service partagé publish)
- Frontend : `<SourcePicker>`, `<PublishButton>`, badges, `<ImpactAnalysisModal>`
- Frontend : pages `pages/admin/sources/{index,new,[id]}.vue`
- Composable `useAdminSources.ts`
- E2E `test_admin_4_eyes_source_flow.py` (P1)

### Sprint 2 — CRUD Catalogue Funds + Intermediaries + Offers (P1)

- `funds_router.py`, `intermediaries_router.py`, `offers_router.py` (3 sous-routers + tests)
- Frontend : `<EntityCRUDTable>` générique
- Frontend : pages funds/, intermediaries/, offers/
- Composable `useAdminCatalog.ts`
- E2E `test_admin_publish_gating_flow.py` (P1)

### Sprint 3 — Catalogue Etendu + Support PME (P1-P2)

- Routers : referentials, indicators, criteria, templates, emission_factors, simulation_factors (6 sous-routers + tests)
- Pages frontend correspondantes
- `users_router.py` + `users_service.py` (reset-password + toggle-active)
- `companies_router.py` + `companies_service.py` (read-only + audit view_admin)
- `attestations_router.py` (révocation)
- Endpoint public `/api/auth/reset-password`
- Page publique `pages/auth/reset.vue`
- Composables `useAdminUsers`, `useAdminCompanies`, `useAdminAttestations`
- E2E `test_admin_isolation_pme.py` (P1)
- E2E `test_admin_reset_password_flow.py` (P1)

### Sprint 4 — Métriques + Layout + Documentation (P2-P3)

- `metrics_router.py` + `metrics_service.py` (CTE aggregation)
- Page `pages/admin/metrics/index.vue` + `<MetricsCard>` + sparkline
- Layout `layouts/admin.vue` finalisé (sidebar complète, palette accentuée admin, dark mode)
- Page `pages/admin/index.vue` (dashboard agrégé)
- Pages restantes : `pages/admin/attestations/index.vue`, audit/skills validation
- Documentation `docs/admin-runbook.md`
- Tests conformity grep `admin_emails`
- Polish dark mode toutes pages
- Couverture tests ≥ 80 %

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 2 triggers PostgreSQL en PL/pgSQL | Invariants métier critiques (4-yeux, publish gating) doivent être imposés en BDD pour empêcher tout bypass applicatif | La logique applicative seule peut être contournée par bug, par script direct SQL, ou par un endpoint oublié. Les triggers donnent une garantie ferme. |
| 15 sous-routers dans `app/modules/admin/` | Couvrir 10 entités catalogue + 5 entités support (sources, users, companies, attestations, metrics) avec endpoints distincts | Un router admin monolithique de ~3000 lignes serait illisible et impossible à reviewer. Découpage par entité = SRP. |
| ~32 pages frontend admin | Couvrir 10 sections catalogue × 3 pages CRUD + 7 sections support | Un dashboard SPA avec routing client serait possible mais perdrait les bénéfices Nuxt (lazy loading par route, SSR, dark mode par page). |
| 8+ composants partagés admin | DRY sur les 10 sections catalogue (sinon ~32 pages × code redondant = ~5000 LOC dupliqué) | Sans `<EntityCRUDTable>` réutilisable, chaque CRUD section dupliquerait pagination, recherche, tri, slots actions. Composant générique = -80 % LOC. |
| 4 tests E2E obligatoires | 4-yeux source, publish gating, isolation PME, reset password = chemins critiques sécurité | Sans E2E, ces chemins ne sont testés qu'en intégration, ne couvrent pas le full stack (frontend + backend + BDD + email). |
| Estimation 3-4 sprints | Volume : 15 sous-routers + ~32 pages + composants + 5 services + migration + tests | Le découpage par sprints suit la priorité P1 (sources + CRUD critique catalogue), puis P1-P2 (catalogue étendu + support PME), puis P2-P3 (métriques + polish). |
