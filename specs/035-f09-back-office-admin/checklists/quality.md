# Quality Checklist — F09 Back-Office Admin Complet

## Pre-implementation

- [ ] Spec.md relue, clarifications complètes (workflow draft→published, 4-yeux trigger, reset password sécurisé, audit view_admin dedup)
- [ ] Plan.md aligne sur architecture projet (FastAPI + SQLAlchemy + Nuxt 4 admin)
- [ ] Migration Alembic 035 numéro disponible (down_revision=`033_create_skills`)
- [ ] Branch `feat/F09-back-office-admin` créée à partir de main
- [ ] Aucun conflit avec features mergées (F01-F08, F10-F13, F17, F22, F23)
- [ ] Vérifier que `bcrypt`, `secrets` (stdlib), `Jinja2`, `aiosmtplib` sont dans `backend/requirements.txt`
- [ ] Vérifier que la table `entity_sources` (F01) existe et structure cohérente avec triggers
- [ ] Vérifier que `app/modules/admin/router.py` (F02) est mountable
- [ ] Vérifier que `EmailService` existe ou prévoir création (T012)
- [ ] PostgreSQL configuré dans CI pour tests d'intégration triggers

## During implementation

- [ ] TDD strict : tests écrits avant impl, doivent FAIL initialement
- [ ] Commit après chaque task ou groupe logique
- [ ] Run pytest local après chaque modification de modèle ou trigger
- [ ] Run Playwright local après chaque page admin
- [ ] Vérifier audit log F03 entries pour chaque mutation admin (CRUD + publish + delete + reset-pw + toggle + revoke)
- [ ] Vérifier audit view_admin dedup 1/jour fonctionnel
- [ ] Tests d'intégration triggers passent sur PostgreSQL réel (pas SQLite)
- [ ] Tests E2E (4 obligatoires) passent : 4-yeux source, publish gating, isolation PME, reset password
- [ ] Test conformity grep `admin_emails` → 0 match

## Post-implementation

- [ ] Run pytest complet — 0 régression sur ~935+ tests existants
- [ ] Run `pytest tests/integration/admin/` → tous verts (~14 sous-routers testés)
- [ ] Run `pytest tests/integration/triggers/` → tous verts (10 publish + 1 4-yeux)
- [ ] Run `pytest tests/e2e/` → 4 E2E backend verts
- [ ] Run Playwright `tests/e2e/admin/*.spec.ts` → tous verts
- [ ] Couverture `app/modules/admin/*` ≥ 80 %
- [ ] Couverture `app/core/email_service.py` ≥ 90 %
- [ ] Couverture `app/core/security.py` (token helpers) ≥ 95 % (sécurité)
- [ ] Endpoint `GET /api/admin/metrics/overview` mesurée P95 < 500ms sur fixtures
- [ ] Page `/admin/funds` charge < 2s sur fixtures 1000 entités
- [ ] Layout `layouts/admin.vue` 100 % dark mode (audit visuel + Playwright theme toggle)
- [ ] Toutes les pages admin ont dark mode complet
- [ ] Test conformity passe (aucune référence admin_emails whitelist)

## Pre-PR

- [ ] Documentation `docs/admin-runbook.md` complète (procédures admin)
- [ ] Script `scripts/seed_publish_existing_catalog.py` créé pour rollout migration 035
- [ ] CLAUDE.md mis à jour (Recent Changes section)
- [ ] Frontend admin pages `/admin/*` fonctionnelles, dark mode complet, palette accentuée admin
- [ ] Composants `<EntityCRUDTable>`, `<SourcePicker>`, `<PublishButton>`, `<ImpactAnalysisModal>`, `<MetricsCard>` testés unitairement (Vitest)
- [ ] Composables `useAdminCatalog`, `useAdminSources`, `useAdminUsers`, `useAdminCompanies`, `useAdminAttestations`, `useAdminMetrics`, `useAdminPublication` typés strict
- [ ] Branche rebasée sur main, sans conflit
- [ ] Migration 035 testée up/down sur PostgreSQL réel

## PR review

- [ ] Code review (code-reviewer agent)
- [ ] Security review (triggers PostgreSQL, reset password flow, isolation admin/PME, audit log)
- [ ] Tests E2E + intégration triggers verts en CI
- [ ] Pas de fichiers sensibles commités (.env, secrets, credentials)
- [ ] Gates CI tous verts (pytest backend, Vitest frontend, Playwright E2E, couverture, conformity)
- [ ] Revue 4-yeux : 2 reviewers minimum, dont 1 sécurité (impact sur isolation admin + reset password)

## Anti-régression admin (post-merge)

- [ ] Pas de réintroduction de l'anti-pattern `admin_emails` whitelist
- [ ] Triggers PL/pgSQL fonctionnels (test mensuel via script de check : tenter UPDATE direct → exception attendue)
- [ ] Audit view_admin dedup ne dégrade pas (mesurer count audit_log/jour, alerte si > 10x baseline)
- [ ] Volume audit_log surveillé (croissance estimée 100k/mois, alerte si > 1M/mois)
- [ ] Performance metrics overview < 500ms maintenue (alerte sur P95 > 1s)
- [ ] Tokens reset password expirés : nettoyés via job cron post-MVP (table `password_reset_tokens` ne grossit pas)
- [ ] Aucun bypass admin via SQL direct (test périodique : tenter publish entité avec source pending → exception attendue)

## Merge criteria

- [ ] Tous les tests CI verts
- [ ] Couverture ≥ 80 % sur nouveaux modules
- [ ] 4 E2E obligatoires passent
- [ ] Documentation runbook livrée
- [ ] Migration 035 testée up/down
- [ ] Approbation 2 reviewers (1 backend + 1 frontend ou 1 sécu)
- [ ] Pas de TODO/FIXME oublié dans le code livré
- [ ] CLAUDE.md mis à jour
