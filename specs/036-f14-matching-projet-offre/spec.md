# Feature Specification: F14 — Matching Projet ↔ Offre + Comparateur Multi-Intermédiaires

**Feature Branch**: `feat/F14-matching-projet-offre`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "F14 — Matching Projet ↔ Offre + Comparateur Multi-Intermédiaires : refactor du modèle `FundMatch` (User↔Fund) en `OfferMatch` (Project↔Offer) avec score décomposé fund_score + intermediary_score, identification du goulot d'étranglement (bottleneck), service `compute_offer_match`, comparateur multi-intermédiaires pour un même fonds, alertes nouvelles offres compatibles, tools LangChain (`list_matches_for_project`, `compare_offers_for_fund`), pages Vue (section sur `/profile/projects/[id]`, page `/financing/compare/[fund_id]`), composants `<MatchCard>` (F11) et `<ComparisonTableBlock>` (F11)."

## Clarifications

### Session 2026-05-08

- **Stratégie de migration `FundMatch` → `OfferMatch`** : créer une nouvelle table `offer_matches` en parallèle (aucun renommage de `fund_matches`). La table `fund_matches` est conservée 2 sprints (legacy `_deprecated`, lecture seule, plus aucune écriture après migration). Backfill best-effort : pour chaque `FundMatch` actif (status `suggested|interested`), tenter de générer un `OfferMatch` par paire `(project_id_inferé, offer_id_inferé)` — `project_id` inféré via SELECT du dernier projet actif de `account_id`, `offer_id` inféré via SELECT de l'offre `(fund_id, intermediary_id=DIRECT singleton, version la plus récente publiée)`. Si l'inférence échoue (pas de project, pas d'offer DIRECT, fund non publié), le fund_match est ignoré (logué WARN `f14_backfill_skipped`). La page `/financing` continue de lire `fund_matches` jusqu'au feature flag `USE_OFFER_MATCH_VIEW=true` (défaut `false` MVP, `true` post-MVP).
- **Modèle `OfferMatch`** :
  - `id: UUID PK`
  - `account_id: UUID FK accounts.id ondelete=RESTRICT NOT NULL` (F02 multi-tenant + RLS)
  - `project_id: UUID FK projects.id ondelete=CASCADE NOT NULL` (F06)
  - `offer_id: UUID FK offers.id ondelete=RESTRICT NOT NULL` (F07)
  - `global_score: int NOT NULL CHECK 0..100`
  - `fund_score: int NOT NULL CHECK 0..100`
  - `intermediary_score: int NOT NULL CHECK 0..100`
  - `score_breakdown: jsonb NOT NULL DEFAULT '{}'` (sous-arbres `fund` et `intermediary` avec `sector_match`, `esg_match`, `size_match`, `location_match`, `documents_match`, `missing_criteria[]`)
  - `bottleneck: VARCHAR(20) NOT NULL CHECK IN ('fund','intermediary','balanced')`
  - `recommended_actions: jsonb NOT NULL DEFAULT '[]'`
  - `status: VARCHAR(20) NOT NULL DEFAULT 'suggested' CHECK IN ('suggested','viewed','dismissed','converted')`
  - `computed_at: timestamptz NOT NULL DEFAULT now()`
  - `expires_at: timestamptz NOT NULL` (computed_at + 30 jours par défaut)
  - `last_notified_at: timestamptz NULL` (idempotence des alertes — voir alertes ci-dessous)
  - **Mixin `Auditable` F03 + RLS PostgreSQL ENABLE+FORCE** (table contient `account_id`, donc multi-tenant strict)
  - Contrainte unique : `(project_id, offer_id)` (un seul match courant par paire — recompute = UPDATE in-place)
- **Calcul du `bottleneck`** : règle déterministe sans seuil flottant.
  - `bottleneck='fund'` si `fund_score < intermediary_score - 10`
  - `bottleneck='intermediary'` si `intermediary_score < fund_score - 10`
  - `bottleneck='balanced'` sinon (écart ≤ 10 pts)
  - `global_score = min(fund_score, intermediary_score)` (éligibilité réelle = chemin le plus contraint)
- **Service `compute_offer_match`** (`backend/app/modules/financing/matching_service.py`) :
  - Lit `Project` (F06) + `Offer` (F07, avec `fund` et `intermediary` chargés en `selectin`)
  - Lit la dernière `ESGAssessment` finalisée du compte (`status='completed'`, ordre `finalized_at DESC`) — si aucune, score ESG = 50 (neutre) avec flag `assessment_missing=true` dans `score_breakdown`
  - Délègue le calcul fund/intermediary à `compute_referential_score_for_offer` (F13, déjà implémenté dans `app.modules.esg.multi_referential_service`) qui retourne `BottleneckInfo(fund_score, intermediary_score, missing_criteria[], top_3_blockers[])`
  - Calcule en parallèle 5 sub-scores **non-ESG** déterministes (sector_match, size_match, location_match, documents_match, instrument_match) basés sur `Project` vs `Offer.effective_*` :
    - `sector_match` : 100 si `project.sector ∈ offer.fund.target_sectors`, 0 sinon (sectors hardcodés référencés F01)
    - `size_match` : 100 si `project.target_amount ∈ [offer.fund.min_amount_money, max_amount_money]` (Money typed F04, conversion via `currency_service` si devises différentes), graduel sinon (linéaire vers 0 à ±50%)
    - `location_match` : 100 si `project.location_country ∈ offer.fund.eligible_countries`, 0 sinon
    - `documents_match` : ratio `len(project_documents) / len(offer.effective_required_documents)` borné à 100
    - `instrument_match` : 100 si `project.financing_structure ∈ offer.fund.instruments`, 0 sinon
  - **Pondération MVP figée (côté code, sourcée via constante `MATCHING_WEIGHTS`)** : `sector=0.25, esg=0.30, size=0.15, location=0.10, documents=0.10, instrument=0.10` → total 100. Pondération admin-modifiable post-MVP via table `matching_weights` (hors-scope F14).
  - `fund_score` = somme pondérée des 5 sub-scores + esg_fund_score (F13)
  - `intermediary_score` = somme pondérée des 5 sub-scores (mêmes valeurs base) + esg_intermediary_score (F13) — la différence réside dans la couche ESG/référentiel intermédiaire qui peut être plus stricte
  - `recommended_actions` : top 3 critères manquants formatés en actions FR (« Renseignez le critère X (référentiel Y) — voir source Z »)
- **Cache et recalcul** :
  - Persistance via UPDATE in-place sur `(project_id, offer_id)` (UNIQUE constraint), `expires_at = computed_at + INTERVAL '30 days'`
  - Cache in-memory FastAPI **non utilisé** pour les matches (BDD persiste, c'est l'autorité). Le cache in-memory est utilisé uniquement pour les **listes triées** (`list_matches_for_project` peut être cachée 5 min via `lru_cache(ttl_seconds=300)`).
  - Recalcul incrémental :
    - **Trigger 1 — projet modifié** : event listener SQLAlchemy `after_update` sur `Project` qui invalide les matches (`expires_at = now()`) et schedule un recalcul async via `BackgroundTasks` (limité à 50 offres / projet, log si > 50).
    - **Trigger 2 — offer modifiée ou nouveau call_for_proposals** : event listener `after_update` sur `Offer` (champs `is_active`, `publication_status`, `effective_*`) qui invalide tous les matches référençant cet `offer_id`. Hook secondaire sur `Fund` pour l'apparition d'un nouveau fund publié (`publication_status: draft → published`).
    - **Trigger 3 — cron quotidien (F19)** : `scripts/recompute_stale_matches.py` (idempotent, picks WHERE `expires_at < now()`, batch 100/run, audit log F03 source `import`).
- **Endpoints API** :
  - `GET /api/projects/{project_id}/matches` — Liste tous les `OfferMatch` actifs (`expires_at > now()`) pour un projet, triée par `global_score DESC`. Filtres query : `min_score: int=0`, `bottleneck: 'fund'|'intermediary'|'balanced'|None`, `fund_id: UUID|None`. Pagination `page/limit` (limit max 50). RLS PG via `current_setting('app.current_account_id')`.
  - `POST /api/projects/{project_id}/recompute-matches` — Déclenche un recalcul async pour toutes les offres publiées (`publication_status='published'`, `is_active=true`). Retourne `202 Accepted` + `{recompute_request_id: UUID, total_offers_to_compute: int}`. BackgroundTasks. Cap dur 50 offres/run (politique anti-DoS).
  - `GET /api/projects/{project_id}/compare?fund_id=X` — Comparateur. Retourne toutes les offres pour `fund_id` (donc N intermédiaires) avec scoring complet par offre. Format `ComparisonResult` réutilisable par tool F11. RLS PG.
  - `GET /api/projects/{project_id}/match-details/{offer_id}` — Détail complet d'un match : tous les critères couverts/manquants avec `source_id` (F01) cliquable. RLS PG.
  - **Aucun endpoint admin dédié** (les matches sont calculés côté PME, l'admin lit via `/api/admin/companies/{account_id}` post-MVP — hors-scope F14).
- **Alertes nouvelles offres compatibles** :
  - Table `match_alerts_subscriptions` (déjà mentionnée dans la spec brouillon) :
    - `id: UUID PK`
    - `account_id: UUID FK accounts.id ondelete=CASCADE NOT NULL` (F02)
    - `project_id: UUID FK projects.id ondelete=CASCADE NOT NULL` (F06)
    - `min_global_score: int NOT NULL DEFAULT 60 CHECK 0..100`
    - `is_active: bool NOT NULL DEFAULT true`
    - `created_at: timestamptz NOT NULL DEFAULT now()`
    - Contrainte unique `(project_id)` (une souscription par projet, mise à jour in-place)
    - **Pas de `notification_channels`** en MVP (transport unique = Reminder F19 via SSE in-app et badge dashboard, email post-MVP)
  - Souscription **automatique à la création d'un projet** (F06 hook event `after_insert` sur `Project` → INSERT idempotent dans `match_alerts_subscriptions`). PME peut désactiver via toggle dans `/profile/projects/[id]` (`PATCH /api/projects/{id}/match-alerts {is_active: false}`).
  - Cron `scripts/notify_new_offer_matches.py` (idempotent, lié F19) :
    - Pour chaque souscription active, recalcul des matches (réutilise `compute_offer_match`)
    - Si nouveau match (= jamais notifié → `OfferMatch.last_notified_at IS NULL`) ET `global_score >= subscription.min_global_score` → crée un Reminder F19 `kind='new_offer_alert'` avec payload `{project_id, offer_id, fund_name, intermediary_name, global_score, bottleneck}`
    - Met à jour `OfferMatch.last_notified_at = now()` (idempotence — un match déjà notifié ne re-déclenche pas)
- **Tools LangChain** (4 tools dans `app/graph/tools/matching_tools.py`) :
  - `list_matches_for_project(project_id, min_score=60, limit=10)` — retourne JSON compact, lecture seule
  - `compare_offers_for_fund(project_id, fund_id)` — émet un `<ComparisonTableBlock>` (F11) via marker SSE `__sse_visualization_block__`. Lecture seule.
  - `recompute_matches_for_project(project_id)` — déclenche async, retourne `recompute_request_id` (mutation, scope `source_of_change='llm'`)
  - `get_match_details(project_id, offer_id)` — détail d'un match avec critères manquants (lecture seule)
  - Tools injectés dans 3 nœuds : `chat`, `financing`, `application`. Whitelist via `MODULE_TOOL_MAPPING`. Tools de lecture aussi disponibles sur la page `/profile/projects/{id}` via `PAGE_TOOL_MAPPING['profile_projects']`.
  - `compare_offers_for_fund` est **déjà déclaré en F07 mais non implémenté côté F14** — on remplace son implémentation actuelle (stub) par la version F14 qui appelle vraiment le calcul de matching. Ajout d'un test conformity vérifiant qu'il émet un block visualisation typé.
- **Frontend** :
  - **Page `/profile/projects/[id]` (F06)** — extension d'une section `<OffersCompatibleSection>` placée après les sections existantes. Affiche jusqu'à 5 `<MatchCard>` (F11) avec score décomposé visible (badges fund/intermediary), bouton « Voir tous les matches (N) » → navigue vers `/profile/projects/[id]/matches`, et bouton « Comparer N intermédiaires pour [Fund] » par groupe de fund (visible si ≥ 2 offres pour un même fund) → navigue vers `/financing/compare/[fund_id]?project_id=X`. Toggle « Recevoir des alertes » (`PATCH /api/projects/{id}/match-alerts`).
  - **Page `/profile/projects/[id]/matches`** (nouvelle) — liste paginée de tous les matches du projet, filtres URL-synchronisés (`min_score`, `bottleneck`, `fund_id`). Empty state explicite si aucun match.
  - **Page `/financing/compare/[fund_id]`** (nouvelle, query `?project_id=X` obligatoire — redirige vers `/profile/projects` si manquant) — comparateur multi-intermédiaires :
    - Header : « Comparer les voies d'accès au [Fund.name] pour le projet [Project.name] »
    - `<ComparisonTableBlock>` (F11) avec lignes : Score global, Score fonds (commun), Score intermédiaire, Frais cumulés (Money typed F04), Délais cumulés (jours min/max), Documents requis (badges), Track record / success_rate, Bottleneck. Highlight gagnant par ligne.
    - Bouton CTA « Démarrer ma candidature via [Intermediary] » par colonne → navigue vers `/financing/offers/[offer_id]` (F07).
  - **Page `/financing/offers/[offer_id]` (F07)** — extension d'une section « Mon score pour ce projet » avec sélecteur de projet (Pinia store `projects.activeProjects`), affichage décomposé fund/intermediary, critères manquants cliquables vers `<SourceModal>` (F01).
  - **Composants** :
    - Réutilisation `<MatchCard>` (F11) — pas de nouveau composant card.
    - Réutilisation `<ComparisonTableBlock>` (F11).
    - Nouveau `<MatchScoreBreakdown>` : graphe radar 5 axes (sector/esg/size/location/documents) en SVG natif (pas de dépendance externe). Dark mode complet.
    - Nouveau `<BottleneckBadge>` : pastille colorée (rouge fund / amber intermediary / vert balanced) + tooltip ARIA `aria-describedby`.
    - Nouveau `<MissingCriteriaList>` : extrait simplifié de F13 avec lien `<SourceLink>` (F01) par critère manquant.
    - Nouveau `<MatchAlertToggle>` : switch ARIA `role=switch` + persiste via API.
  - **Composable** `composables/useMatching.ts` (8 méthodes : `listMatches`, `recomputeMatches`, `compareOffersForFund`, `getMatchDetails`, `subscribeToAlerts`, `unsubscribeFromAlerts`, `pollMatchesAfterRecompute`, `getMatchById`)
  - **Store Pinia** `stores/matches.ts` (state : `matchesByProject: Record<projectId, OfferMatch[]>`, `comparisonsByFund: Record<fundId, ComparisonResult>`, `subscriptionsByProject: Record<projectId, Subscription>`, getters `getActiveMatches(projectId)`, `getBottleneck(matchId)`, `getTopMatch(projectId)`)
  - **Types TypeScript** `types/matching.ts` (8 types : `OfferMatch`, `MatchScoreBreakdown`, `MatchSubBreakdown`, `MissingCriterion`, `MatchBottleneck`, `MatchSubscription`, `RecomputeMatchesResponse`, `ComparisonResult`)
  - **Dark mode complet** : tous nouveaux composants utilisent `dark:bg-dark-card`, `dark:border-dark-border`, `dark:text-surface-dark-text`, `dark:hover:bg-dark-hover`. Aucune couleur hardcodée sans variante dark.
  - **ARIA** : `<MatchScoreBreakdown>` (`role="img" aria-label="Détail du score"`), `<BottleneckBadge>` (`aria-describedby` pour tooltip), `<MatchAlertToggle>` (`role="switch" aria-checked`).
- **Migration Alembic** : revision `036_offer_matches_and_alerts`. **`down_revision = la dernière migration sur main au moment du Phase B`** (à confirmer en Phase B — au moment de Phase A la dernière est `035_admin_publication_status_workflow` mais F19 PR #20 pourrait introduire une migration intermédiaire avant le merge de F14). Crée :
  1. Table `offer_matches` (16 colonnes, 4 CHECK, 5 indexes : `(project_id, computed_at DESC)`, `(account_id, expires_at)`, `(offer_id)`, `(account_id, global_score DESC)`, UNIQUE `(project_id, offer_id)`)
  2. Table `match_alerts_subscriptions` (7 colonnes, 1 UNIQUE `(project_id)`)
  3. RLS PostgreSQL ENABLE+FORCE sur les 2 tables avec policies `pme_access_own_account` et `admin_full_access` (cohérent F02)
  4. Backfill best-effort `fund_matches` → `offer_matches` (ON CONFLICT DO NOTHING)
  5. **Aucune modification de `fund_matches`** (table conservée 2 sprints, drop dans migration ultérieure hors-scope F14)
  - Round-trip `up/down/up` validé sur PostgreSQL.
- **Audit F03** : `OfferMatch` ajouté à `AUDITABLE_MODELS`. `MatchAlertSubscription` aussi (les changements de `min_global_score` ou `is_active` doivent être tracés). Source of change : `manual` côté PME (toggle), `llm` côté tool, `import` côté cron.
- **Money typed F04** : pas de nouveau champ Money dans les modèles F14 (les frais effectifs sont dans `Offer.effective_fees` JSONB qui contient déjà du Money typed via F04). Le service de matching consomme et affiche du Money typed sans le persister.
- **Sourçage F01** : chaque critère dans `score_breakdown.missing_criteria[].source_id` pointe vers une `Source` verified. Le rapport « Mon match » utilise `<SourceLink>` (F01) sur chaque critère manquant.
- **Multi-tenant F02 + RLS** : `account_id` NOT NULL sur les 2 tables, RLS ENABLE+FORCE + 2 policies. PME ne peut lire/écrire que ses propres matches. Admin a accès complet via `admin_full_access` policy.
- **Cap LLM** : tools de matching ajoutés à la borne `MAX_TOOLS_PER_TURN` qui passe de 14 à 18 (4 nouveaux tools). Aucun tool muté ne dépasse le timeout 60s (cron pour batch lourds).
- **Tests E2E Playwright** : `frontend/tests/e2e/F14-matching-projet-offre.spec.ts` (4 scénarios) :
  1. **US1** : créer projet → page projet → section « Offres compatibles » affiche au moins 1 `<MatchCard>` avec score décomposé
  2. **US2** : naviguer `/financing/compare/[fund_id]?project_id=X` → table comparative ≥ 2 colonnes intermédiaires + highlight gagnant
  3. **US3** : cliquer sur critère manquant → `<SourceModal>` (F01) s'ouvre avec source verified
  4. **US4** : toggle « Recevoir des alertes » sur `/profile/projects/[id]` → confirmation visuelle + état persisté après refresh
  - Mocks backend complets via helpers `frontend/tests/e2e/F14-helpers.ts` (matching API + comparator + projects + offers + sources)
- **Tests backend pytest** :
  - Unit : `test_models_offer_match.py`, `test_schemas_matching.py`, `test_matching_service.py` (compute_offer_match avec ESG present/absent, bottleneck rules, scoring sectorMatch/sizeMatch/locationMatch, documents_match, instrument_match), `test_matching_tools.py` (4 tools, args validation, sérialisation JSON), `test_matching_invalidation.py` (event listeners SQLAlchemy après_update Project/Offer)
  - Integration : `test_matching_router.py` (4 endpoints, RLS, pagination, filters), `test_recompute_async.py` (BackgroundTasks + 202), `test_compare_offers_endpoint.py` (multi-intermédiaires), `test_alerts_subscription.py` (auto-souscription création projet, toggle, cron notify)
  - Migration : `test_alembic_036.py` (round-trip up/down/up, structure table, indexes, RLS policies, backfill idempotent)
  - Conformity : `test_no_fund_match_writes.py` (vérifie qu'aucun nouveau code n'écrit dans `fund_matches` après F14 — grep AST)
  - Couverture cible ≥ 80 % sur les modules F14 (`app.modules.financing.matching_service`, `app.models.offer_match`, `app.models.match_alert_subscription`, `app.modules.financing.alerts_service`, `app.graph.tools.matching_tools`, `app.modules.financing.matching_router`)
- **Tests frontend Vitest** :
  - `useMatching.test.ts` (8 méthodes)
  - `stores/matches.test.ts` (state + getters)
  - `MatchScoreBreakdown.test.ts`, `BottleneckBadge.test.ts`, `MissingCriteriaList.test.ts`, `MatchAlertToggle.test.ts`
  - Couverture cible ≥ 80 %
- **Documentation** : `docs/matching-offers.md` (modèle conceptuel projet↔offre, règles bottleneck, formule pondération, cycle de vie d'un match, troubleshooting, RLS, ajout d'un nouveau sub-score).

---

## User Scenarios & Testing

### User Story 1 — Voir mes offres compatibles pour un projet (Priority: P1)

En tant que PME ayant créé un projet « Panneaux solaires 5M FCFA », je veux voir une liste d'offres compatibles (pas de fonds nus) avec un score décomposé fund + intermediary, pour comprendre quel chemin d'accès au financement est le plus réaliste.

**Why this priority**: Cœur du différenciateur F14 vs le matching naïf actuel (User↔Fund). Sans cette US, le module F14 n'a aucune valeur visible pour la PME.

**Independent Test**: Créer un projet test → vérifier que la section « Offres compatibles » affiche au moins 1 MatchCard avec scores décomposés visibles → cliquer sur la card → page détail avec critères couverts/manquants.

**Acceptance Scenarios**:
1. **Given** un projet actif avec au moins 1 offre publiée compatible (sector match), **When** la PME ouvre `/profile/projects/[id]`, **Then** la section « Offres compatibles » affiche les MatchCards triées par global_score DESC avec fund_score et intermediary_score visibles.
2. **Given** un projet sans offre compatible, **When** la PME ouvre la page, **Then** un empty state explicite est affiché avec CTA « Modifier mes critères de projet ».

### User Story 2 — Comparer plusieurs intermédiaires pour un même fonds (Priority: P1)

En tant que PME intéressée par le GCF, je veux comparer 3 voies d'accès (BOAD, UNDP, AFD) côte-à-côte sur frais, vitesse, taux de succès et score décomposé, pour choisir l'intermédiaire optimal.

**Why this priority**: Différenciateur clé absent du produit actuel. Module 3.2 du brainstorming.

**Independent Test**: Sur un projet avec ≥ 2 offres pour un même fund, naviguer `/financing/compare/[fund_id]?project_id=X` → table comparative ≥ 2 colonnes avec highlight gagnant par ligne.

**Acceptance Scenarios**:
1. **Given** un projet avec 3 offres pour le fund GCF (BOAD, UNDP, AFD), **When** la PME clique « Comparer 3 intermédiaires pour GCF » sur la page projet, **Then** la page comparateur affiche un ComparisonTableBlock avec score global / score fonds / score intermédiaire / frais / délais / documents / track record / bottleneck.
2. **Given** la PME consulte la table, **When** elle scanne une ligne, **Then** la cellule du gagnant est mise en évidence (highlight, badge « Meilleur »).

### User Story 3 — Comprendre les critères manquants via les sources F01 (Priority: P2)

En tant que PME, je veux qu'un critère manquant soit cliquable vers la source officielle qui le définit, pour comprendre les exigences précises (ex : « vous n'atteignez pas le seuil ESS BOAD »).

**Why this priority**: Renforce la pédagogie ESG et matérialise le sourçage F01 dans le parcours PME.

**Independent Test**: Sur la page `/financing/offers/[offer_id]?project_id=X`, cliquer un critère manquant → SourceModal s'ouvre avec extrait + URL.

**Acceptance Scenarios**:
1. **Given** un match avec critères manquants, **When** la PME clique sur un critère, **Then** un SourceModal F01 s'ouvre avec le titre, l'extrait de la source, l'URL et le badge « verified ».

### User Story 4 — Recevoir des alertes nouvelles offres compatibles (Priority: P3)

En tant que PME, je veux recevoir des alertes quand un nouveau call_for_proposals s'ouvre pour un fonds compatible avec mes projets, pour ne pas manquer une opportunité.

**Why this priority**: Capacité différenciante (proactivité produit) mais infra (cron F19) et UX (badge dashboard) sont relativement simples.

**Independent Test**: Activer l'alerte sur un projet → simuler un nouveau match via cron `notify_new_offer_matches.py` → vérifier qu'un Reminder F19 `kind='new_offer_alert'` apparaît sur le dashboard.

**Acceptance Scenarios**:
1. **Given** un projet avec souscription d'alertes active, **When** une nouvelle offre publiée matche avec global_score ≥ 60, **Then** un Reminder F19 est créé et la PME voit un badge sur son dashboard.
2. **Given** un match déjà notifié, **When** le cron tourne à nouveau, **Then** aucun nouveau Reminder n'est créé (idempotence via `last_notified_at`).

---

## Functional Requirements

- **FR-001** : Le système DOIT créer une table `offer_matches` avec FK vers `projects` (F06), `offers` (F07) et `accounts` (F02).
- **FR-002** : Le système DOIT calculer un `fund_score` et un `intermediary_score` séparés sur 0..100.
- **FR-003** : Le système DOIT calculer `global_score = min(fund_score, intermediary_score)`.
- **FR-004** : Le système DOIT identifier le `bottleneck` selon la règle déterministe : `fund` si `fund_score < intermediary_score - 10`, `intermediary` si l'inverse, `balanced` sinon.
- **FR-005** : Le système DOIT persister `score_breakdown` JSONB avec sub-scores et critères manquants par référentiel.
- **FR-006** : Le système DOIT exposer 4 endpoints REST (`/matches`, `/recompute-matches`, `/compare`, `/match-details`) sous `/api/projects/{project_id}/*`.
- **FR-007** : Le système DOIT appliquer RLS PostgreSQL (ENABLE+FORCE) sur les 2 tables F14 avec policies cohérentes F02.
- **FR-008** : Le système DOIT recalculer les matches incrémentalement quand un projet ou une offre est modifiée (event listeners SQLAlchemy).
- **FR-009** : Le système DOIT permettre à une PME de désactiver les alertes d'un projet via `PATCH /api/projects/{id}/match-alerts {is_active: false}`.
- **FR-010** : Le système DOIT créer un Reminder F19 pour chaque nouveau match notifiable et marquer `last_notified_at` pour idempotence.
- **FR-011** : Le système DOIT exposer 4 tools LangChain (`list_matches_for_project`, `compare_offers_for_fund`, `recompute_matches_for_project`, `get_match_details`).
- **FR-012** : Le tool `compare_offers_for_fund` DOIT émettre un block visualisation typé `<ComparisonTableBlock>` (F11).
- **FR-013** : Le système DOIT afficher la section « Offres compatibles » sur `/profile/projects/[id]` avec MatchCards et bouton comparateur.
- **FR-014** : Le système DOIT afficher la page `/financing/compare/[fund_id]?project_id=X` avec table comparative.
- **FR-015** : Le système DOIT afficher la section « Mon score pour ce projet » sur `/financing/offers/[offer_id]` avec critères manquants cliquables vers SourceModal F01.
- **FR-016** : Le système DOIT auditer (F03) toutes les mutations sur `offer_matches` et `match_alerts_subscriptions` avec `source_of_change` correct (manual / llm / import).
- **FR-017** : Le système DOIT respecter la cap `MAX_TOOLS_PER_TURN` portée à 18 après ajout des 4 tools F14.
- **FR-018** : Le système DOIT supporter le dark mode complet sur tous les nouveaux composants Vue.
- **FR-019** : Le système DOIT respecter les exigences ARIA (role/aria-label/aria-checked/aria-describedby) sur les composants interactifs.
- **FR-020** : Le système DOIT atteindre une couverture de tests ≥ 80 % sur les modules F14 (backend + frontend).

---

## Success Criteria

- **SC-001** : 100 % des matches affichent fund_score, intermediary_score et bottleneck.
- **SC-002** : La page comparateur s'affiche en < 2s pour un projet avec 5 offres pour un même fund.
- **SC-003** : Le cron `notify_new_offer_matches.py` est idempotent : double exécution ne crée pas de Reminder dupliqué (vérifié par test).
- **SC-004** : 0 régression sur les 2693 tests backend baseline (post-F23) et tests frontend baseline.
- **SC-005** : Round-trip Alembic up/down/up validé sur PostgreSQL.
- **SC-006** : Aucun nouveau code n'écrit dans `fund_matches` (vérifié par test conformity grep).
- **SC-007** : Tous les composants Vue F14 ont leur variante `dark:` Tailwind.
- **SC-008** : Le tool `compare_offers_for_fund` émet bien un block visualisation typé conforme F11.

---

## Hors-scope (post-MVP)

- ML scoring (apprentissage sur historique soumissions/acceptations)
- Recommandations narratives IA « Voici comment combler le score IFC : 1)… »
- Score prédictif « probabilité d'acceptation »
- Email digest hebdo des nouvelles offres
- Filtres avancés (instruments, durée, devise) sur la liste de matches
- Pondération admin-modifiable via table `matching_weights`
- Drop de `fund_matches` (reporté ≥ 2 sprints)
