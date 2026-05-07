# Cross-Artifact Analysis: F09 — Back-Office Admin Complet (Module 9)

**Date** : 2026-05-07
**Auteur** : SpecKit Phase A (autonome, post `/speckit.tasks`)
**Status** : OK — pas de blocage critique identifié

## Vue d'ensemble

| Artefact | Taille | Conformité |
|----------|--------|------------|
| spec.md | 9 user stories, 28 FR, 15 SC, 22 assumptions, 14 edge cases | ✓ Format respecté |
| plan.md | 9 sections (summary, technical context, structure, phases, migration, phasage TDD, complexity tracking) | ✓ Format respecté |
| research.md | 9 décisions documentées (R1-R9) — généré par /speckit.plan | ✓ Couvre toutes les ambiguïtés clés |
| data-model.md | 7 entités (publication_status enum, password_reset_tokens table, 2 fonctions PL/pgSQL, MetricsOverview, DependentsReport, AuditLog admin entries types, audit view_admin dedup) | ✓ Schémas complets |
| quickstart.md | Procédures admin actionnables (4-yeux, publish, reset-pw, révocation, métriques) | ✓ Actionnable |
| contracts/ | 18 fichiers (publication_status_enum, 2 SQL triggers, password_reset_tokens, 14 admin endpoints, 1 auth public, 1 metrics schema) | ✓ Schémas + REST specs cohérents |
| checklists/quality.md | 4 sections + anti-régression admin | ✓ Format respecté |
| tasks.md | 113 tasks en 7 phases (4 sprints + setup + foundational + post-MVP), mapping US correct, estimation 3-4 sprints | ✓ Format respecté |

## Couverture FR → Tasks

| FR | Description courte | Coverage | Tasks |
|----|---|----|---|
| FR-001 | Migration 035 (publication_status × 10 tables + table password_reset_tokens + 2 triggers) | ✓ | T007 |
| FR-002 | Fonction `before_publish_check_sources_verified()` | ✓ | T007, T033 (test) |
| FR-003 | Fonction `before_verify_source_check_different_admin()` | ✓ | T007, T016 (test) |
| FR-004 | Router funds (6 endpoints CRUD) | ✓ | T034 (test), T038 |
| FR-005 | Router intermediaries | ✓ | T035 (test), T039 |
| FR-006 | Router offers + compute-effective | ✓ | T036 (test), T040 |
| FR-007 | Routers referentials/indicators/criteria/templates/emission_factors/simulation_factors | ✓ | T052-T057 (tests), T065-T066 |
| FR-008 | Router sources (6 endpoints + dependents) | ✓ | T017 (test), T020 |
| FR-009 | Service sources (get_dependents, can_delete, soft_delete_with_cascade) | ✓ | T019 |
| FR-010 | Router users (reset-password, toggle-active) | ✓ | T059 (test), T069 |
| FR-011 | Router companies (lecture + audit view_admin) | ✓ | T062 (test), T070 |
| FR-012 | Router attestations (révocation) | ✓ | T063 (test), T071 |
| FR-013 | Router metrics (overview) | ✓ | T088 (test), T090 |
| FR-014 | Service metrics (CTE aggregation) | ✓ | T087 (test), T089 |
| FR-015 | Service users (initiate/complete reset, toggle) | ✓ | T058 (test), T067 |
| FR-016 | Endpoint public POST /api/auth/reset-password | ✓ | T060 (test), T072 |
| FR-017 | Montage sous-routers dans main.py | ✓ | T021, T041, T073, T091 |
| FR-018 | Layout admin.vue avec palette accentuée | ✓ | T096 |
| FR-019 | ~17 pages frontend admin | ✓ | T028-T030, T046-T048, T078-T082, T094-T095 |
| FR-020 | Composants partagés (EntityCRUDTable, SourcePicker, PublishButton, badges, ImpactAnalysisModal, MetricsCard) | ✓ | T022-T026, T042, T076, T092 |
| FR-021 | Composables admin | ✓ | T027, T044, T045, T077, T093 |
| FR-022 | Middleware admin.ts (créé F02, validé F09) | ✓ | T084 (test E2E isolation) |
| FR-023 | Audit log F03 sur toutes mutations | ✓ | T014, T015 (test), T020, T038, T067, etc. |
| FR-024 | Audit log view_admin avec dedup 1/jour | ✓ | T014, T015 (test), T068, T070 |
| FR-025 | Aucune référence admin_emails (test conformity) | ✓ | T064, T103 |
| FR-026 | Schemas Pydantic stricts par sous-router | ✓ | T018 (partagés), couvert par chaque router |
| FR-027 | Service email avec console fallback | ✓ | T012, T013 (test) |
| FR-028 | Couverture tests ≥ 80 % | ✓ | T100 |

**Conclusion** : 28/28 FR couverts par au moins une tâche, avec test TDD avant implémentation. Exception : FR-022 (middleware admin.ts) est créé par F02, F09 ne fait que valider via T084 E2E.

## Couverture User Stories → Tasks

| US | Description | Tasks | Tests inclus | Indépendant ? |
|----|---|---|---|---|
| US1 | CRUD funds + workflow publish | T033-T036, T038-T044, T046-T051 | T034 (TDD), T049 (E2E) | ✓ Après Sprint 1 (sources verified) |
| US2 | 4-yeux validation sources | T016-T031, T032 | T016, T017 (TDD), T031 (E2E) | ✓ Après Phase 2 |
| US3 | Support PME (read-only + reset-pw + toggle + revoke) | T058-T063, T067-T072, T076-T077, T080-T086 | T058, T060, T061 (TDD), T085 (E2E) | ✓ Après Sprint 1+2 |
| US4 | Sources avec impact analysis | T017, T019, T025, T030 | T017 (TDD) | ✓ Couvert par US2 |
| US5 | Métriques admin dashboard | T087-T095 | T087, T088 (TDD) | ✓ Après tous les CRUDs |
| US6 | CRUD référentiels/indicators/criteria | T052-T054, T065, T074, T078 | T052-T054 (TDD) | ✓ Après Sprint 1 |
| US7 | CRUD offers + compute-effective | T036, T040, T048 | T036 (TDD) | ✓ Après US1 (funds + intermediaries publiés) |
| US8 | CRUD templates/emission_factors/simulation_factors | T055-T057, T066, T075, T079 | T055-T057 (TDD) | ✓ Après Sprint 1 |
| US9 | Isolation Admin/PME | T064, T083-T084 | T064 (conformity), T083 (E2E) | ✓ Indépendant après Phase 2 |

**Conclusion** : 9/9 US ont leur story indépendamment livrable + tests TDD avant implémentation. Ordre cohérent : Sprint 1 (sources + 4-yeux), Sprint 2 (funds/intermediaries/offers + publish gating), Sprint 3 (catalogue étendu + support PME + isolation), Sprint 4 (métriques + polish).

## Détection d'incohérences

### ✓ Cohérences vérifiées

1. **Migration Alembic** — `down_revision="033_create_skills"` cohérent avec dernière migration F23 mergée.
2. **Spec number 035** — disponible (specs/ contient jusqu'à 033 + 034 sera utilisé par une autre feature en parallèle, F09 utilise 035 par convention F23-déjà-mergé).
3. **Anti-pattern email whitelist** — la consigne précise que F02 a déjà supprimé `admin_emails` dans `financing/router.py:118`. F09 valide via test conformity T064.
4. **F02 squelette admin** — `app/modules/admin/router.py` et `middleware.py` existent (créés F02). F09 étend avec 13 sous-routers et raffine 2 (audit, skills déjà créés).
5. **F03 audit log** — `audit_log_entry()` disponible. Helper `log_view_admin_dedup()` (T014) utilise la fonction F03 avec dedup logique.
6. **F04 versioning** — `VersioningMixin` utilisé pour édition entités catalogue published (nouvelle version automatique).
7. **F07 compute_effective_offer** — service disponible, appelé par endpoint admin offers.
8. **F08 attestations** — modèle avec `revoked_at`, `revoked_by_user_id`, `revocation_reason` disponible. F09 expose endpoint admin de révocation.
9. **F23 skills** — `skills_router.py` créé. F09 valide les liens sidebar et garantit cohérence workflow draft→published.
10. **Triggers PL/pgSQL** — invariants imposés en BDD (impossible de bypass applicatif). Test SQLite skip car PL/pgSQL non portable. Test PostgreSQL réel obligatoire.
11. **Token reset password** — flow sécurisé (sha256 hash, expiration 1h, usage unique, never plain in DB).
12. **Audit view_admin dedup** — implémenté en service Python (1/jour/admin/account), pas en BDD UNIQUE constraint (trop rigide).

### ⚠ Points d'attention (non-bloquants)

1. **Table `entity_sources`** — la fonction trigger `before_publish_check_sources_verified()` suppose une table de jointure générique `entity_sources(entity_type, entity_id, source_id)` pour parcourir les sources liées. Si F01 utilise une approche différente (FK directe par table), la fonction trigger doit être adaptée. À résoudre en research.md (R1) avant migration.
2. **`bcrypt`, `secrets`, `Jinja2`, `aiosmtplib`** — T002 vérifie leur présence dans `requirements.txt`. Si absent, à ajouter en début de Phase 1.
3. **Email service en dev** — `EmailService` avec backend `console` requis pour les tests E2E (T085). Si F02/F08 a déjà initialisé un service email, F09 le réutilise (sinon création T012).
4. **Migration zero-downtime** — `ADD COLUMN ... DEFAULT 'draft'` est INSTANT depuis PG 11. Cependant, toutes les entités catalogue existantes deviennent draft après migration → invisible côté PME. Plan rollout : (1) migration, (2) script `seed_publish_existing_catalog.py` UPDATE existing en published manuel, (3) déployer code utilisant publication_status. À documenter dans T099 (admin-runbook.md).
5. **Trigger PL/pgSQL : performance** — overhead BEFORE UPDATE estimé < 5ms. Si bottleneck identifié à grande échelle, post-MVP : matérialized view `entity_publish_eligibility` pré-calculée.
6. **Pages frontend volume** — ~32 pages = volume important. Mitigation : `<EntityCRUDTable>` générique réduit drastiquement la duplication. Mesure DRY = T015 (composant utilisé sur 10 sections).
7. **Sécurité email** — log dans console en dev expose le reset link dans les logs. Acceptable en dev/staging, en prod utiliser SMTP TLS.
8. **Permissions intra-admin granulaires** — MVP utilise rôle binaire `admin`/`user`. Post-MVP : `dpo`, `catalog_editor`, `support`. Documenté dans assumptions.
9. **password_reset_tokens : invalidation des anciens tokens** — MVP autorise plusieurs tokens actifs simultanés. Post-MVP : invalider les anciens à chaque nouveau reset. Documenté dans edge cases.

### ✓ Risques mitigés

| Risque | Mitigation |
|--------|------------|
| Admin se trompe et publie un fonds avec mauvais critères | Versioning F04 → revenir version précédente. Audit log F03 → traçabilité. |
| Admin malveillant (interne) accède PME sans trace | Audit log `view_admin` automatique avec dedup 1/jour, visible côté PME. Détection patterns anormaux post-MVP. |
| Suppression d'une Source casse les entités dépendantes | `<ImpactAnalysisModal>` avant suppression, refus si dépendants existent (force delete possible avec cascade). |
| Seed initial des sources prend semaines | Prioriser sources critiques (ADEME, GCF Investment Framework, IFC PS, taxonomie UEMOA), accepter phase pilote partiel. |
| Performance pages admin avec 1000+ entités | Pagination obligatoire, recherche full-text avec index trigram (pg_trgm), lazy loading. |
| Confusion visuelle interface PME vs admin | Sidebar et header avec couleurs/styles distinctifs (palette rouge admin), badge "Mode Admin" persistant. |
| Trigger PL/pgSQL ne lève pas l'erreur attendue | Tests intégration explicites T016, T033 vérifient `IntegrityError` → 400 dans réponse FastAPI. |
| Token reset password expire pendant utilisation | Validation strict `expires_at > now()` à la complétion. Fenêtre 1h suffisante. |
| Admin malveillant force publish via SQL direct | Trigger BDD lève SQLSTATE P0001 même sur SQL direct (impossible de bypass). |
| Régression tests existants | T100 (couverture) + T101 (run pytest complet) attendu 0 régression sur 935+ tests. |
| Frontend dark mode oublié | T097 polish dark mode + T104 audit visuel + Playwright theme toggle test. |
| Race condition publication concurrente | Idempotence : 2e requête → no-op (publication_status déjà published, trigger ne re-fire pas). |
| Email service indisponible | Fallback console en dev, WARNING niveau ERROR si SMTP timeout en prod. |

## Couverture des Edge Cases (spec.md)

| Edge Case | Mitigation/Task |
|---|---|
| Suppression Source avec 100+ dépendants | `<ImpactAnalysisModal>` avec pagination interne (T025), force delete spinner (T030) |
| Race condition publish concurrent | Idempotence trigger (T038) |
| Token reset password expiré pendant utilisation | Validation strict `expires_at > now()` (T067, T072) |
| Email service indisponible | Fallback console (T012) |
| Trigger PL/pgSQL ne lève pas erreur attendue | Tests intégration explicites (T016, T033) |
| Admin tente publier 50 Funds en batch | MVP = 1 par 1, bulk import post-MVP (T106) |
| Audit log entry view_admin doublon | Dedup logique 1/jour (T014, T015) |
| Source devient outdated après publish | Pas de cascade automatique, warning admin sur page |
| Layout admin sur mobile | Sidebar collapse hamburger (T096) |
| Concurrent edit | Optimistic locking via updated_at, last-write-wins documenté |
| Super-admin tente verify sa propre source | Refus strict, aucun bypass (trigger) |
| Migration 035 sur BDD avec entités existantes | Plan rollout `seed_publish_existing_catalog.py` documenté (T099) |
| Reset password avec 3 tokens actifs | MVP autorise multiples, post-MVP invalide anciens (T106-T108) |
| Page metrics lente avec 100k+ events | Index composite + materialized view post-MVP, MVP timeout 5s (T089) |

**Conclusion** : 14/14 edge cases couverts par au moins une tâche.

## Couverture des Success Criteria

| SC | Description | Vérification |
|----|---|---|
| SC-001 | Migration 035 applique up/down sans erreur | T007 |
| SC-002 | E2E 4-yeux source 100 % | T031 |
| SC-003 | E2E publish gating 100 % | T049 |
| SC-004 | E2E isolation user PME 100 % | T083, T084 |
| SC-005 | E2E reset password 100 % | T085, T086 |
| SC-006 | Audit log view_admin créée + dedup | T014, T015 |
| SC-007 | 0 régression tests existants | T101 |
| SC-008 | Couverture tests ≥ 80 % | T100 |
| SC-009 | Aucune référence admin_emails | T064, T103 |
| SC-010 | GET /metrics/overview P95 < 500ms | T087 (benchmark), T089 |
| SC-011 | Page /admin/funds < 2s sur 1000 fonds | T101 + Playwright timing |
| SC-012 | Layout admin 100 % dark mode | T096, T097, T104 |
| SC-013 | Tous CRUD entités catalogue fonctionnels (10 entités) | T034-T036, T052-T057 |
| SC-014 | Trigger publish testé sur 10 tables | T033 (paramétré × 10) |
| SC-015 | EntityCRUDTable réutilisable sur 10 sections | T042 (générique) + T046-T048, T078-T079 (utilisation) |

**Conclusion** : 15/15 SC mesurés par tâches dédiées.

## Tasks ordering & dépendances critiques

```
Phase 1 [Setup]                       indépendant, parallèle
  ↓
Phase 2 [Foundational]                T007 (migration) → T008 (model) → T009 (test model)
                                      T010 (security helper) → T011 (test)
                                      T012 (email service) → T013 (test)
                                      T014 (audit helpers) → T015 (test)
  ↓
Phase 3 [Sprint 1 - Sources + 4-yeux] T016, T017 (tests) → T018-T020 (impl)
                                      T021 (mount router)
                                      T022-T026 (composants)
                                      T027-T030 (composables + pages)
                                      T031, T032 (E2E)
  ↓
Phase 4 [Sprint 2 - CRUD critiques]   T033-T036 (tests) → T037-T040 (impl)
                                      T041 (mount routers)
                                      T042-T044 (composants)
                                      T045-T048 (composables + pages)
                                      T049-T051 (E2E)
  ↓
Phase 5 [Sprint 3 - Étendu + Support] T052-T064 (tests, parallèle) → T065-T072 (impl)
                                      T073 (mount routers)
                                      T074-T077 (composants)
                                      T078-T082 (pages)
                                      T083-T086 (E2E)
  ↓
Phase 6 [Sprint 4 - Polish]           T087-T088 (tests) → T089-T091 (impl)
                                      T092-T095 (composants + pages)
                                      T096-T098 (layout + polish)
                                      T099 (doc)
                                      T100-T105 (validation finale)
```

**Tasks parallèles** (`[P]`) : 60+ sur 105 (~57 %), répartis sur les sprints pour permettre 2-3 dev en parallèle. Particulièrement dense sur Sprint 3 (35 tâches dont la plupart parallèles).

## Estimation et planning

| Sprint | Phases | Tasks | Estimation |
|---|---|---|---|
| Sprint 0 (préparation) | 1, 2 | T001-T015 | 2-3 jours dev |
| Sprint 1 | 3 | T016-T032 | 4-5 jours dev |
| Sprint 2 | 4 | T033-T051 | 4-5 jours dev |
| Sprint 3 | 5 | T052-T086 | 6-8 jours dev |
| Sprint 4 | 6 | T087-T105 | 4-5 jours dev |
| Total MVP | 1-6 | T001-T105 | 20-26 jours dev |

**Cohérence avec fiche F09** : 3-4 sprints × 5 jours = 15-20 jours dev. Avec couverture exhaustive backend + frontend + E2E, l'estimation 20-26 jours est plus réaliste. Si l'équipe est 2-3 dev en parallèle, ramené à 8-12 jours calendaires.

## Conclusion analyse

✓ **Spec.md** : 9 US, 28 FR, 15 SC, 14 edge cases, tous mappés à au moins une tâche TDD.
✓ **Plan.md** : structure projet alignée, 5 zones de modification clairement identifiées, migration Alembic 035 spécifiée avec triggers PL/pgSQL.
✓ **Tasks.md** : 105 tâches MVP en 6 phases avec dépendances claires, TDD strict, parallélisation [P] documentée. 8 tâches post-MVP optionnelles.
✓ **Contracts** : 18 schémas/specs cohérents avec data-model.md.
✓ **Quickstart** : actionnable pour Admin et Dev (runbook).
✓ **Checklist quality** : 4 sections + anti-régression post-merge.

**Aucun blocage identifié**. Prêt pour `/speckit.implement` dans une session ultérieure.

## Recommandations pré-implémentation

1. **Vérifier dépendances** (Phase 1) : `bcrypt`, `secrets` (stdlib), `Jinja2`, `aiosmtplib` dans `backend/requirements.txt`.
2. **Vérifier table `entity_sources`** : la fonction trigger `before_publish_check_sources_verified()` suppose cette table générique. Si F01 utilise des FK directes par table, adapter la fonction (research.md R1).
3. **Coordonner avec F02** : valider que `app/modules/admin/router.py` (parent) existe et est mountable dans `main.py`. Si pas encore, F09 doit le créer en Phase 2.
4. **Vérifier `EmailService`** : si F02/F08 a déjà initialisé un service email, F09 le réutilise. Sinon T012 le crée.
5. **Plan rollout migration** : préparer `scripts/seed_publish_existing_catalog.py` avant déploiement prod. Documenter dans `docs/admin-runbook.md` (T099).
6. **Coordination équipe** : Sprint 1 (sources + 4-yeux) doit être complété avant Sprint 2 (publish gating dépend des sources verified). Sprint 3 et 4 peuvent partiellement chevaucher.
7. **Tests PostgreSQL** : configurer un service PostgreSQL dans CI (GitHub Actions) pour les tests d'intégration triggers (T016, T033). SQLite ne suffit pas.
8. **Frontend layout** : valider avec design la palette accentuée admin (rouge foncé) — différenciation visuelle stricte avec PME requise.
9. **Audit log volume** : avec dedup 1/jour, ~10 admins × 100 PME consultations/jour = 1000 entries audit_log/jour. À monitorer (table audit_log croissance).
10. **Documentation runbook** : T099 est une tâche critique pour l'opérabilité en production. Inclure scénarios incident PME, rotation admin, audit forensic.
