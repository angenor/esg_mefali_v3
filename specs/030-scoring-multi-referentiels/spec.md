# Feature Specification: F13 — Scoring ESG Multi-Référentiels (GCF, IFC, BOAD, SUNREF, GRI, ODD)

**Feature Branch**: `feat/F13-scoring-multi-referentiels` (alias SpecKit `030-scoring-multi-referentiels`)
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F13 — Scoring ESG Multi-Référentiels. Implémenter un scoring ESG multi-référentiels qui complète le score « ESG Mefali » actuel avec des scores détaillés par référentiel (GCF, IFC PS, BOAD ESS, SUNREF, GRI 2021, ODD), tous calculés à partir du même catalogue d'indicateurs (F01). Une seule saisie d'indicateur PME alimente N scores sans duplication. Quand un projet (F06) cible une Offre (F07 — Fonds × Intermédiaire), afficher 2 scores côte-à-côte (référentiel fonds source + référentiel intermédiaire) avec identification du goulot d'étranglement. Création table `referential_scores`, services `compute_all_referential_scores` et `compute_referential_score_for_offer`, refactor `esg_scoring_node`, 3 tools LangChain (`finalize_esg_assessment`, `recompute_score`, `compare_referentials`), endpoint `POST /api/reports/esg/{id}/generate` avec body `referentials`, page `/esg/results` avec sélecteur, page `/financing/offers/[id]` avec dual view, composants `<ReferentialSelector>`, `<ReferentialScoreCard>`, `<DualReferentialView>`, `<MissingCriteriaList>`. Versioning F04 actif. Annexe Sources F01 dans le PDF. Dépendances : F01, F04, F07."

## Clarifications

### Session 2026-05-07

- Q: Quand une PME modifie un indicateur après calcul (saisie « 60 % déchets recyclés » puis correction « 70 % »), le système doit-il recalculer immédiatement les N scores (synchrone) ou en différé (background task / cron) ? → A: **Recalcul asynchrone via background task** : la mutation `PATCH /api/esg/assessments/{id}/indicator-values` enqueue un job (FastAPI `BackgroundTasks`, in-memory MVP, Redis post-MVP) qui calcule N scores en parallèle (1 par référentiel actif). Le client reçoit `202 Accepted` immédiatement avec un `recompute_request_id`. Côté UI, les scores existants restent affichés avec un badge « Mise à jour en cours » jusqu'à la complétion (polling 2 s sur `GET /api/esg/assessments/{id}/referential-scores`). **Rationale** : recalcul synchrone bloque l'utilisateur 5-15 s pour 5-7 référentiels et chaîne d'appels LLM ; la latence saisie → score est plus tolérable que la latence saisie → réponse HTTP. Garde-fou : si le job échoue (timeout LLM, exception), l'ancien score est conservé et un événement `audit_log` est créé (`action='referential_score_recompute_failed'`). En MVP sans Redis, les jobs vivent dans le process FastAPI ; redéploiement = perte des jobs en cours, l'utilisateur doit refresh.
- Q: Le score Mefali historique (déjà calculé via `compute_overall_score` mono-référentiel) doit-il être migré dans la table `referential_scores` (avec referential_id pointant sur ESG Mefali) ou rester dans la colonne legacy `esg_assessments.overall_score` ? → A: **Backfill complet vers `referential_scores`** : la migration `030_create_referential_scores` exécute, pour chaque `esg_assessment` existant, un `INSERT INTO referential_scores (assessment_id, referential_id=<ESG_Mefali_uuid>, overall_score, pillar_scores, computed_at, computed_by='auto', referential_version='1.0.0', covered_criteria=[], missing_criteria=[], gap_to_threshold=overall_score-50)`. Les colonnes legacy `esg_assessments.overall_score` et `esg_assessments.environment_score|social_score|governance_score` sont **conservées 2 sprints** en deprecated (cohérence dashboard F11) puis supprimées dans une migration ultérieure (post-F13). **Rationale** : un seul lieu d'autorité (`referential_scores`) évite les divergences ; le backfill garantit zéro perte de données ; conserver les colonnes legacy temporairement protège les pages `/dashboard` et `/action-plan` qui les lisent encore. Garde-fou : pendant les 2 sprints de transition, le service `compute_all_referential_scores` met à jour les deux endroits (referential_scores + colonnes legacy) pour cohérence ; un test d'intégration vérifie l'égalité.
- Q: Quand un référentiel (ex : IFC PS) ne couvre que partiellement les indicateurs renseignés (coverage_rate < 50 %), le `overall_score` calculé doit-il être affiché « 32/100 (couverture 30 %) » avec badge alerte, ou le système doit-il refuser le calcul en retournant `null` avec un message explicite ? → A: **Calcul toujours effectué + affichage avec badge alerte coverage** : le service `compute_score_for_referential` calcule toujours un score (pondération qui ignore les indicateurs non renseignés, pas zéro par défaut) et stocke `overall_score` + `coverage_rate` séparément dans `referential_scores`. Si `coverage_rate < 0.5`, l'UI affiche l'overall_score avec un badge orange « Couverture indicateurs : X % — score indicatif » et désactive le bouton « Inclure dans rapport PDF » (l'admin peut forcer via override Admin F09). **Rationale** : cacher un score parce qu'il manque 30 indicateurs sur 50 punit la PME et casse le parcours pédagogique (« voici ce qu'il vous reste à renseigner pour viser X référentiel ») ; la transparence (afficher le score + le coverage) est plus actionnable. Garde-fou : seuils `coverage_rate` configurables admin (default 50 %) ; alerte UI explicite ; PDF marqué « Rapport préliminaire » si une section référentiel a coverage < 50 %.
- Q: Le `referential_version` snapshot dans `referential_scores` capture-t-il une chaîne sémantique (ex : `"1.2.0"`) gérée manuellement par l'admin, ou est-il calculé automatiquement à partir du hash des indicateurs et pondérations actifs au moment du calcul ? → A: **Chaîne sémantique gérée par admin (`major.minor.patch`)** alignée sur la table `referentials.version` (F01/F04). Lors du calcul, `referential_scores.referential_version = referentials.version` snapshot. L'admin incrémente la version manuellement quand il modifie la liste d'indicateurs ou les pondérations d'un référentiel via le back-office F09 (workflow 4-yeux F01). **Rationale** : les hashes auto sont opaques pour les non-techs et empêchent la communication claire avec les PME (« votre score IFC PS v1.2 reste valide »). Une chaîne sémantique gérée + traçable = standard de l'industrie (Semver). Garde-fou : la migration de la version d'un référentiel ne déclenche PAS un recalcul automatique des scores existants (le PME garde son score historique sourcé v1.1) ; un cron mensuel propose un recalcul opt-in via notification dashboard (« la grille IFC PS a évolué v1.1 → v1.2, voulez-vous recalculer ? »).
- Q: Pour la page `/financing/offers/[id]`, quand une offre ne référence pas explicitement de référentiel (cas où `fund.referential_id IS NULL` ou `intermediary.referential_id IS NULL` parce que F01 n'a pas encore lié toutes les sources), faut-il afficher un seul score (Mefali fallback) ou bloquer l'affichage de la section dual view ? → A: **Fallback explicite ESG Mefali avec note pédagogique** : si `fund.referential_id IS NULL`, le système affiche le score Mefali de la PME avec une note « Le référentiel spécifique de ce fonds n'est pas encore catalogué. Score affiché selon ESG Mefali (vue synthétique). » Idem pour l'intermédiaire. Si les deux sont NULL, l'UI affiche un seul score Mefali (pas la dual view). Si un seul est NULL, l'UI affiche un score réel (le côté connu) + le Mefali (le côté NULL) avec différenciation visuelle (couleur estompée, badge « Référentiel Mefali — fallback »). **Rationale** : ne pas bloquer le parcours PME parce que le catalogue F01 est incomplet ; une transparence pédagogique est préférable à un message d'erreur ; à mesure que F09 enrichit le catalogue, les fallbacks disparaissent naturellement. Garde-fou : la note explicite indique à la PME pourquoi le score est synthétique ; un événement audit_log est créé pour les admins (`action='dual_view_fallback_used'`).
- Q: Le pattern d'historisation des versions de scores (`referential_version='1.1.0'` puis `'1.2.0'` après recalcul opt-in) doit-il utiliser une table d'historique séparée `referential_score_versions`, le pattern F04 `superseded_by` (UUID FK pointant vers la version précédente), ou un champ `is_current bool` sur la table principale avec relâchement de l'index unique ? → A: **Pattern F04 `superseded_by` (UUID FK self-référente nullable)** : la contrainte unique `(assessment_id, referential_id)` est remplacée par un index unique partiel `(assessment_id, referential_id) WHERE superseded_by IS NULL` (un seul score « courant » par paire). Quand un recalcul opt-in produit une nouvelle version, on insère une nouvelle ligne (`superseded_by=NULL`) puis on UPDATE l'ancienne pour mettre `superseded_by=<new_id>`. L'historique est requêté via `WHERE superseded_by IS NOT NULL ORDER BY computed_at DESC`. **Rationale** : (1) cohérence avec F04 (pattern déjà en place pour Fund/Intermediary versioning, on évite un nouveau pattern parallèle), (2) pas de table satellite supplémentaire (mantenance reduite), (3) l'index unique partiel PostgreSQL garantit qu'un seul score courant existe par couple, ce qui simplifie les requêtes côté API (`WHERE superseded_by IS NULL`). Garde-fou : un test d'intégration vérifie qu'une seule ligne `superseded_by IS NULL` existe par couple `(assessment_id, referential_id)` après chaque recalcul.
- Q: Le terme « ESG Mefali » est-il modélisé comme un référentiel à part entière (ligne dans `referentials` avec `code='mefali'`) ou comme un agrégat virtuel calculé à la volée à partir des scores des autres référentiels ? → A: **Référentiel à part entière dans `referentials`** : seed migration crée `referentials(code='mefali', name='ESG Mefali', version='1.0.0', is_active=true, threshold=50, ...)` avec sa propre liste d'indicateurs (les 30 critères E/S/G actuels de F05) liés via `referential_indicators`. Le score Mefali est donc calculé exactement comme les autres référentiels (par `compute_score_for_referential(mefali_referential, indicator_values)`), mais sa visibilité UI est « par défaut » (sélecteur initial), et les colonnes legacy `esg_assessments.overall_score` continuent à le miroir pendant 2 sprints. **Rationale** : (1) homogénéité du modèle de calcul (un seul code path `compute_score_for_referential`), (2) versioning F04 applicable nativement (l'admin peut faire évoluer le référentiel Mefali v1.0 → v1.1), (3) compatibilité avec le pattern « 1 saisie = N scores » (Mefali = un score parmi N), (4) ouvre la voie à des évolutions futures où Mefali pourrait être désactivé/archivé sans casser le code. Garde-fou : `referentials.code='mefali'` est protégé contre la suppression (soft delete uniquement) ; les UUIDs Mefali sont stables et seedés dans la migration `030_create_referential_scores` (idempotent, ON CONFLICT DO NOTHING).
- Q: Le cron mensuel qui propose le recalcul opt-in après évolution de version d'un référentiel (« la grille IFC PS a évolué v1.1 → v1.2 ») doit-il créer une notification persistée par PME concernée (table `notifications` ou champ `dashboard_alerts`), ou émettre un événement éphémère consommé au prochain login PME ? → A: **Notification persistée dans la table existante des rappels (F11 reuse)** : le cron crée une entrée dans la table existante `reminders` (F11) avec `kind='referential_version_evolved'`, `metadata={referential_id, old_version, new_version, delta_summary}`, `account_id=PME owner`. Le frontend (composable `useReminders.ts` F11 déjà en place) affiche la notification dans la cloche dashboard avec un bouton « Voir le delta » (modale détaillant les nouveaux indicateurs/pondérations) et un bouton « Recalculer maintenant » (déclenche `recompute_score(assessment_id, referentiel_id)`). La notification est marquée `read` quand la PME clique sur « Recalculer » ou « Plus tard ». **Rationale** : (1) éviter de créer une nouvelle table `notifications` pour un seul use case, (2) F11 reminders supporte déjà multi-tenant (account_id + RLS), polling 60s, dark mode, badge UI, (3) cohérence UX : la PME voit ses rappels et ses notifications référentiels au même endroit. Garde-fou : le cron est idempotent (un seul reminder par couple `(assessment_id, referential_id, new_version)` via une contrainte d'unicité dans `reminders.metadata` ou un check `WHERE NOT EXISTS`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — PME bascule entre référentiels et découvre les écarts (Priority: P1)

Aïssa est dirigeante d'une PME agroalimentaire au Sénégal qui transforme des céréales locales. Sur la page `/esg/results`, elle a déjà renseigné 35 indicateurs et son score « ESG Mefali » affiche `78/100`. À côté du titre du score, un sélecteur déroulant propose les options « ESG Mefali ▼ ». Elle clique : ESG Mefali, GCF, IFC PS, BOAD ESS, GRI 2021, ODD. Elle sélectionne « IFC PS » : la page se rafraîchit instantanément (sans rechargement complet) et affiche `52/100` avec un nouveau radar par pilier (`Performance Standards 1-8`), une liste des critères couverts (12 / 25), et une liste des critères manquants (13 critères, chacun cliquable vers la source officielle IFC). Un badge orange « Couverture indicateurs : 48 % — score indicatif » est affiché. Elle clique sur le critère manquant « PS6 — Conservation de la biodiversité » et une page modale s'ouvre avec la définition IFC, le lien vers la source officielle (PDF IFC Performance Standards 2012, p.42), et la suggestion : « Renseignez votre indicateur Mefali "Politique biodiversité" pour couvrir ce critère IFC PS6. »

**Why this priority** : C'est la promesse différenciante du brainstorming Module 2.3 (« scoring ESG multi-référentiels avec activation contextuelle »). Sans cette story, la PME ne sait pas qu'elle est éligible à un fonds (78/100 Mefali) mais bloquée à un autre (52/100 IFC) — l'information n'est pas actionnable. Cette story justifie la création de la table `referential_scores` et du sélecteur UI ; toutes les autres stories en dépendent.

**Independent Test** : Créer une `EsgAssessment` avec 35 `IndicatorValues` saisis, calculer les 5 référentiels MVP via `compute_all_referential_scores`, ouvrir `/esg/results` en tant que PME propriétaire, vérifier que le sélecteur affiche les 5 référentiels, basculer entre 2 référentiels et vérifier que le score, le radar, les critères couverts/manquants changent sans rechargement complet de la page (SPA Vue).

**Acceptance Scenarios** :

1. **Given** une `EsgAssessment` finalisée pour une PME avec 35 indicateurs renseignés et 5 référentiels actifs (Mefali, GCF, IFC PS, BOAD ESS, GRI 2021), **When** le service `compute_all_referential_scores(assessment_id)` est appelé, **Then** la table `referential_scores` contient 5 lignes (une par référentiel) avec `overall_score`, `pillar_scores`, `covered_criteria`, `missing_criteria`, `coverage_rate`, `gap_to_threshold`, `eligibility`, et chaque ligne référence sa `Source` F01 via les `covered_criteria.*.source_id`.
2. **Given** la PME ouvre `/esg/results` avec les 5 scores calculés, **When** elle clique sur le sélecteur « ESG Mefali » et choisit « IFC PS », **Then** le composant `<ReferentialScoreCard>` affiche le score IFC (`52/100`), le radar par pilier IFC, et les listes critères couverts / manquants — le tout sans recharger la page entière (changement local Vue).
3. **Given** la PME visualise IFC PS avec coverage 48 %, **When** la page se rafraîchit, **Then** un badge orange « Couverture indicateurs : 48 % — score indicatif » est affiché et le bouton « Inclure dans rapport PDF » est désactivé avec tooltip « Couverture insuffisante (< 50 %). Renseignez plus d'indicateurs. »
4. **Given** la PME clique sur le critère manquant « PS6 — Biodiversité » dans la `<MissingCriteriaList>`, **When** la modale s'ouvre, **Then** elle voit la définition IFC, un lien `<SourceLink>` cliquable vers la source officielle F01 (URL + page + date d'extraction), et la suggestion d'indicateur Mefali à renseigner pour couvrir ce critère.

---

### User Story 2 — PME consulte une Offre et voit son éligibilité réelle avec goulot d'étranglement (Priority: P1)

Aïssa décide de candidater au GCF via la BOAD pour son projet d'agroforesterie. Sur la page `/financing/offers/{offer_id}` (l'offre « GCF via BOAD — Mitigation Afrique Ouest »), une section « Mon éligibilité pour cette offre » affiche **deux scores côte-à-côte** :

- **Côté gauche** : « Selon GCF (fonds source) » avec score `45/100`, un radar par pilier GCF, une liste des critères manquants GCF (8 critères).
- **Côté droit** : « Selon BOAD ESS (intermédiaire) » avec score `68/100`, un radar par pilier BOAD, une liste des critères manquants BOAD (4 critères).

Au-dessus, un bandeau pédagogique : **« Goulot d'étranglement : référentiel GCF (45/100). Pour décrocher cette offre, renseignez en priorité ces 3 critères GCF manquants. »** Trois critères critiques sont listés avec un bouton « Renseigner maintenant » qui redirige vers `/esg` filtré sur ces indicateurs. Un message d'éligibilité effective : `min(GCF, BOAD) = 45/100 < seuil 60` → « Non éligible actuellement. ». La PME comprend immédiatement que la limite est GCF (pas BOAD) et où concentrer ses efforts.

**Why this priority** : C'est l'« activation contextuelle » du brainstorming Module 2.3.3 (« quand un projet cible une Offre, deux scores côte-à-côte, min des deux = éligibilité réelle »). C'est ce qui justifie la valeur de l'entité Offre (F07) : sans dual scoring, la PME découvre seulement après dépôt qu'elle est bloquée par un référentiel qu'elle n'avait pas vu venir. Sans cette story, la promesse différenciante de F13 n'est pas livrée.

**Independent Test** : Seeder une offre `GCF × BOAD` (F07), seeder les référentiels GCF et BOAD ESS avec leurs indicateurs et seuils, créer une `EsgAssessment` PME finalisée, appeler `compute_referential_score_for_offer(assessment_id, offer_id)` et vérifier la structure `(score_fonds, score_intermediaire)`. Ouvrir `/financing/offers/{offer_id}` et vérifier l'affichage `<DualReferentialView>` avec goulot identifié.

**Acceptance Scenarios** :

1. **Given** une offre `GCF × BOAD` avec `fund.referential_id=GCF_uuid` et `intermediary.referential_id=BOAD_uuid`, et une `EsgAssessment` PME finalisée, **When** le service `compute_referential_score_for_offer(assessment_id, offer_id)` est appelé, **Then** il retourne `(score_fonds: ReferentialScore, score_intermediaire: ReferentialScore)` avec les deux scores calculés depuis les mêmes indicateurs PME et persistés dans `referential_scores` (pas de duplication).
2. **Given** la PME ouvre `/financing/offers/{offer_id}`, **When** la page se charge, **Then** le composant `<DualReferentialView>` affiche les deux scores côte-à-côte (gauche fonds, droite intermédiaire), le radar par pilier de chaque, et les listes critères manquants de chaque.
3. **Given** `score_fonds=45 < score_intermediaire=68`, **When** le `<DualReferentialView>` se rend, **Then** un bandeau pédagogique affiche « Goulot d'étranglement : référentiel GCF (45/100) » avec les 3 critères GCF les plus impactants à renseigner et un bouton « Renseigner maintenant » qui redirige vers `/esg?focus=indicator_X,Y,Z`.
4. **Given** l'éligibilité effective `min(45, 68) = 45 < seuil 60`, **When** la page se rend, **Then** le statut d'éligibilité affiche un badge rouge « Non éligible actuellement » avec l'explication chiffrée.
5. **Given** une offre où `fund.referential_id IS NULL` (catalogue F01 incomplet), **When** la page se rend, **Then** le côté gauche affiche le score ESG Mefali avec un badge « Référentiel Mefali — fallback » et une note « Le référentiel spécifique de ce fonds n'est pas encore catalogué » ; le côté droit affiche le score BOAD réel.

---

### User Story 3 — PME génère un rapport PDF avec sélection multi-référentiels (Priority: P1)

Aïssa veut envoyer un dossier de candidature à la BOAD avec son score IFC PS pour démontrer son alignement aux standards internationaux. Sur la page `/esg/results`, elle clique sur « Générer un rapport PDF ». Une modale apparaît avec les options :

- Référentiels à inclure (cases à cocher) : ☑ ESG Mefali (par défaut), ☐ GCF, ☑ IFC PS, ☐ BOAD ESS, ☐ GRI 2021, ☐ ODD.
- ☑ Inclure l'annexe « Sources et références ».

Elle coche `[Mefali, IFC PS]` et clique « Générer ». L'API `POST /api/reports/esg/{id}/generate` reçoit `{referentials: ["mefali", "ifc_ps"], include_appendix_sources: true}`. Le PDF généré contient :

1. Page de garde avec score Mefali principal (`78/100`).
2. Section « Selon référentiel ESG Mefali » : score, radar 3 piliers (E/S/G), critères couverts, recommandations.
3. Section « Selon référentiel IFC Performance Standards » : score `52/100`, radar 8 piliers (PS1-PS8), critères couverts, critères manquants avec sources cliquables (URL).
4. Tableau comparatif : indicateur × référentiel (qui couvre quoi, ✓/✗).
5. **Annexe « Sources et références »** : liste de toutes les sources F01 citées dans le rapport (URL, page, date d'extraction, statut `verified`).

Elle télécharge le PDF, l'envoie à la BOAD avec son dossier.

**Why this priority** : Le PDF est l'artefact final certifiable que la PME présente aux financeurs. Sans cette story, le rapport reste mono-référentiel (limitation actuelle de F06) et ne reflète pas la richesse du scoring multi-référentiels. C'est la matérialisation de la valeur F13 dans un format délivrable.

**Independent Test** : Avec une `EsgAssessment` finalisée et 5 référentiels calculés, appeler `POST /api/reports/esg/{id}/generate` avec body `{"referentials": ["mefali", "ifc_ps"], "include_appendix_sources": true}` et vérifier que le PDF résultant contient les 2 sections référentiels, le tableau comparatif, et l'annexe sources avec tous les `<SourceLink>` cliquables. Tester aussi avec `referentials=["mefali"]` seul et vérifier que la sortie est mono-référentiel (rétrocompatibilité).

**Acceptance Scenarios** :

1. **Given** une `EsgAssessment` finalisée avec 5 `referential_scores` calculés, **When** la PME appelle `POST /api/reports/esg/{id}/generate` avec body `{"referentials": ["mefali", "ifc_ps"], "include_appendix_sources": true}`, **Then** la réponse `202 Accepted` retourne un `report_id` et un job background génère le PDF en < 30 s.
2. **Given** le PDF est généré, **When** la PME ouvre le fichier, **Then** elle voit (a) une page de garde avec score Mefali, (b) une section dédiée « Selon ESG Mefali », (c) une section dédiée « Selon IFC PS » avec radar 8 piliers IFC, (d) un tableau comparatif indicateur × référentiel, (e) une annexe « Sources et références » avec toutes les URLs cliquables.
3. **Given** la PME envoie body `{"referentials": ["mefali"], "include_appendix_sources": false}`, **When** le PDF est généré, **Then** le rapport est mono-référentiel (rétrocompatibilité F06) sans annexe sources et sans section IFC PS.
4. **Given** la PME envoie un référentiel inexistant `{"referentials": ["xyz_invalid"]}`, **When** le système traite la requête, **Then** la réponse est `422 Unprocessable Entity` avec liste des codes de référentiels valides connus.
5. **Given** un référentiel sélectionné a `coverage_rate < 0.5` (ex : IFC PS à 48 %), **When** le PDF est généré, **Then** une bannière « Rapport préliminaire — couverture insuffisante pour le référentiel IFC PS » apparaît en première page et au-dessus de la section IFC.

---

### User Story 4 — Recalcul asynchrone après modification d'un indicateur (Priority: P2)

Aïssa réalise qu'elle a sous-estimé son indicateur « % de déchets recyclés » : elle pense être à 60 % mais en réalité c'est 75 %. Sur `/esg`, elle ouvre le formulaire indicateur, modifie la valeur 60 → 75, clique « Sauvegarder ». L'API `PATCH /api/esg/assessments/{id}/indicator-values` reçoit la modification et :

1. Persiste l'indicateur immédiatement (réponse 202 Accepted, `recompute_request_id`).
2. Enqueue un background task qui recalcule **tous les référentiels actifs** (5 en MVP) en parallèle.
3. La PME revient sur `/esg/results` ; les scores existants sont affichés avec un badge « Mise à jour en cours » et un spinner.
4. Le frontend polling toutes les 2 s sur `GET /api/esg/assessments/{id}/referential-scores` ; après 8 s les nouveaux scores sont retournés.
5. Le score Mefali passe `78 → 80`, GCF `45 → 51`, IFC PS `52 → 55`, BOAD ESS `68 → 72`, GRI `61 → 64` : tous mis à jour à partir d'**une seule** mutation indicateur, sans duplication de saisie.

**Why this priority** : Le pattern « 1 saisie = N scores » est la clé d'usage du module 0.7 du brainstorming (« pas de duplication de saisie »). Sans recalcul asynchrone, la latence saisie → score visible bloque l'utilisateur 5-15 s par modification, ce qui détruit l'expérience exploratoire (« je teste 60, puis 70, puis 75 pour voir l'impact »).

**Independent Test** : Avec une `EsgAssessment` ayant 5 scores calculés, appeler `PATCH /api/esg/assessments/{id}/indicator-values` avec une modification d'un indicateur ; vérifier la réponse 202 + `recompute_request_id` ; vérifier que les 5 lignes `referential_scores` sont mises à jour avec un nouveau `computed_at` après le job background ; vérifier qu'un seul `IndicatorValue` est persisté (pas de duplication).

**Acceptance Scenarios** :

1. **Given** une `EsgAssessment` avec 35 `IndicatorValues` et 5 `referential_scores` calculés, **When** la PME envoie `PATCH /api/esg/assessments/{id}/indicator-values` avec une seule modification (ex : `pct_dechets_recycles: 75`), **Then** la réponse est `202 Accepted` avec `recompute_request_id`, et exactement 1 `IndicatorValue` est mis à jour en base (pas de duplication).
2. **Given** le job background démarre, **When** il s'exécute, **Then** les 5 lignes `referential_scores` sont recalculées en parallèle et leur `computed_at` est mis à jour ; les anciens scores ne sont visibles qu'avant la complétion du job.
3. **Given** le frontend polling, **When** il appelle `GET /api/esg/assessments/{id}/referential-scores`, **Then** la réponse contient les scores avec `computed_at` ≥ `recompute_started_at` une fois le job terminé, signal de complétion pour l'UI.
4. **Given** le job échoue (timeout LLM, exception), **When** le service traite l'erreur, **Then** les anciens scores sont conservés, un événement `audit_log` est créé (`action='referential_score_recompute_failed', entity_id=assessment_id`), et la PME voit un toast « Recalcul partiellement échoué — réessayez ».
5. **Given** la PME ne modifie qu'un indicateur qui ne concerne aucun pilier de IFC PS, **When** le job se termine, **Then** `referential_scores[IFC].overall_score` est éventuellement inchangé mais `computed_at` est tout de même mis à jour (snapshot de version).

---

### User Story 5 — Versioning F04 : un score historique reste défendable même après évolution du référentiel (Priority: P2)

Aïssa avait calculé son score IFC PS le 2026-03-01 sous la version `IFC_PS@1.1.0` du référentiel IFC. Le 2026-04-15, l'admin Mefali ajoute 3 nouveaux indicateurs IFC et incrémente la version vers `IFC_PS@1.2.0` (workflow 4-yeux F01). Le score historique d'Aïssa reste affiché « 52/100 (selon IFC PS v1.1.0, calculé le 2026-03-01) » dans l'historique de ses évaluations. Sur le dashboard, une notification apparaît : « Le référentiel IFC PS a évolué vers v1.2 (3 nouveaux indicateurs). Voulez-vous recalculer votre score selon la dernière version ? » Elle clique « Recalculer » : un nouveau `referential_scores` est créé avec `referential_version='1.2.0'`. Le précédent (v1.1.0) reste en base et accessible via l'historique. Cela permet à Aïssa de défendre son score auprès de la BOAD : « Le 2026-03-01, j'étais à 52 selon IFC PS v1.1, version officielle à cette date. ».

**Why this priority** : Le versioning F04 est critique pour la traçabilité légale (cf. F08 attestation). Sans cette story, une PME qui montre un score à un financeur 6 mois plus tard ne peut pas prouver qu'il était valide à la date de génération. C'est aussi la base pour les attestations vérifiables.

**Independent Test** : Créer une version `IFC_PS@1.1.0` de référentiel, calculer un score (snapshot version), incrémenter à v1.2.0, vérifier que le score initial reste en base avec `referential_version='1.1.0'` ; déclencher un nouveau calcul, vérifier qu'une nouvelle ligne est créée avec `referential_version='1.2.0'`.

**Acceptance Scenarios** :

1. **Given** un référentiel IFC PS en v1.1.0 et une `EsgAssessment` calculée, **When** le calcul se produit, **Then** la ligne `referential_scores` enregistre `referential_version='1.1.0'` snapshot.
2. **Given** l'admin met à jour le référentiel IFC vers v1.2.0 (workflow F01/F04), **When** un PME visualise son historique, **Then** il voit le score précédent avec mention « selon IFC PS v1.1.0, calculé le 2026-03-01 ».
3. **Given** le PME clique « Recalculer selon la dernière version », **When** le service traite la demande, **Then** une **nouvelle ligne** est créée dans `referential_scores` avec `referential_version='1.2.0'` (la précédente n'est PAS supprimée, l'index unique `(assessment_id, referential_id)` est ajusté pour permettre versioning ou bien la précédente est marquée `superseded_by` selon le pattern F04).
4. **Given** une notification dashboard « le référentiel a évolué », **When** la PME ouvre la page, **Then** elle voit clairement le delta de la nouvelle version (« 3 nouveaux indicateurs ajoutés ») avant de cliquer Recalculer.

---

### User Story 6 — Tools LangChain permettent au chat de recalculer et comparer (Priority: P2)

Aïssa interagit avec le chat conversationnel : « Compare-moi mes scores selon Mefali et IFC PS pour mon évaluation actuelle. » Le chat utilise le tool LangChain `compare_referentials(assessment_id, referentials=["mefali", "ifc_ps"])` qui retourne une structure typée `ComparisonResult` avec les deux scores, les piliers, les critères divergents (couverts par Mefali mais pas IFC, et vice versa). Le chat formule une réponse en français avec accents : « Votre score Mefali est de 78/100 (Bon), votre score IFC PS est de 52/100 (À améliorer). L'écart de 26 points est principalement dû à 3 critères IFC non couverts par Mefali : PS6 Biodiversité, PS7 Peuples autochtones, PS8 Patrimoine culturel. Voulez-vous que je vous guide pour les renseigner ? »

Plus tard, après modifications, Aïssa demande : « Recalcule mon score IFC. » Le chat utilise le tool `recompute_score(entity_id=assessment_id, referentiel_id=ifc_ps_uuid)` qui enqueue un recalcul ciblé sur IFC seulement (pas tous les référentiels) et retourne un `recompute_request_id`. Le chat répond : « Recalcul IFC en cours, je vous notifie dès que c'est terminé… ». Quand la PME finalise son évaluation, le chat utilise le tool `finalize_esg_assessment(assessment_id, referentials_to_compute=["mefali", "ifc_ps", "boad_ess"])` qui calcule les 3 référentiels en finalisation atomique.

**Why this priority** : L'interface chat est le pilier UX du produit (Module 1.1) ; sans tools, le chat reste un commentateur passif des scores et perd sa valeur conversationnelle. Cette story fait du chat un acteur dynamique du scoring multi-référentiel.

**Independent Test** : Tester chaque tool LangChain en isolation via un test unitaire pytest qui invoque le tool avec des arguments mockés et vérifie la structure de retour (Pydantic schema). Tester aussi l'intégration : envoyer un message PME au chat, capturer le tool call exécuté, vérifier la réponse formulée par le LLM.

**Acceptance Scenarios** :

1. **Given** une `EsgAssessment` finalisée avec scores Mefali=78 et IFC=52, **When** le chat appelle `compare_referentials(assessment_id, referentials=["mefali", "ifc_ps"])`, **Then** le tool retourne `ComparisonResult(scores=[{ref:"mefali", score:78}, {ref:"ifc_ps", score:52}], gap=26, divergent_criteria=[{ref:"ifc_ps", criteria:[...]}])` typé Pydantic.
2. **Given** la PME demande « Recalcule mon score IFC », **When** le chat appelle `recompute_score(entity_id=assessment_id, referentiel_id=ifc_ps_uuid)`, **Then** le tool enqueue un job ciblé (un seul référentiel) et retourne `{recompute_request_id: ...}`.
3. **Given** la PME finalise son évaluation, **When** le chat appelle `finalize_esg_assessment(assessment_id, referentials_to_compute=["mefali", "ifc_ps", "boad_ess"])`, **Then** le tool calcule les 3 référentiels en transaction unique (atomicité) et retourne les 3 scores.
4. **Given** le chat appelle un tool avec un `referentiel_id` invalide, **When** le tool s'exécute, **Then** il retourne une erreur structurée (pas une exception non gérée) que le LLM peut interpréter pour formuler un message à l'utilisateur.
5. **Given** chaque tool call, **When** il est exécuté, **Then** un événement est ajouté dans `tool_call_logs` (F12) avec le payload et la réponse (instrumentation).

---

### User Story 7 — Multi-tenant : les scores d'un compte ne fuient pas vers un autre (Priority: P3)

L'utilisateur Bob (compte `account_id=B`) ne doit jamais pouvoir voir les scores de l'utilisateur Aïssa (compte `account_id=A`), même via une URL devinée du type `/api/esg/assessments/{aissa_assessment_id}/referential-scores`. Les RLS PostgreSQL filtrent strictement par `account_id` sur la table `referential_scores`. Si Bob tente l'URL d'Aïssa, il reçoit `404 Not Found` (pas `403 Forbidden`, pour ne pas révéler l'existence du document). Le partage d'un score entre comptes (cas où Aïssa veut montrer son score à un consultant de l'extérieur) passe par la feature F08 (attestation vérifiable Ed25519, hors-scope F13).

**Why this priority** : Conformité F02 (multi-tenant strict). Pas de fuite cross-tenant. Cette story est `P3` car elle est mécanique (RLS appliquée par migration) mais doit être testée end-to-end pour éviter une régression.

**Independent Test** : Créer 2 comptes A et B, créer une `EsgAssessment` pour A avec scores, tenter `GET /api/esg/assessments/{A_id}/referential-scores` en tant que Bob ; vérifier réponse 404. Tenter aussi via SQL direct (simulation utilisateur DB) et vérifier que les RLS bloquent.

**Acceptance Scenarios** :

1. **Given** une `EsgAssessment` appartenant au compte A avec 5 `referential_scores`, **When** un utilisateur du compte B (Bob) appelle `GET /api/esg/assessments/{A_id}/referential-scores`, **Then** la réponse est `404 Not Found` (pas `403 Forbidden`).
2. **Given** la table `referential_scores` a une RLS PostgreSQL `account_id = current_setting('app.current_account_id')`, **When** une session DB pour le compte B fait `SELECT * FROM referential_scores WHERE assessment_id = {A_id}`, **Then** le résultat est 0 lignes (RLS filtre).
3. **Given** un super-admin (`is_admin=true`) appelle l'endpoint, **When** la requête est traitée, **Then** il voit les scores des 2 comptes (bypass RLS via `app.bypass_rls`).
4. **Given** l'endpoint `POST /api/admin/recompute-referential-scores` est appelé sans le rôle admin, **When** la requête est traitée, **Then** la réponse est `403 Forbidden`.

---

### Edge Cases

- **Que se passe-t-il quand un `referential_id` actif est désactivé (admin marque `is_active=false` sur la table `referentials`) ?** Les `referential_scores` historiques pour ce référentiel restent en base et restent affichables dans l'historique PME, mais le `compute_all_referential_scores` ne calcule plus ce référentiel pour de nouvelles évaluations. Une note s'affiche dans l'UI : « Référentiel archivé — scores historiques conservés. ».
- **Comment le système gère-t-il un appel `compute_score_for_referential` sur un référentiel qui n'a aucun indicateur lié (catalogue F01 vide) ?** Le service retourne `coverage_rate=0`, `overall_score=null`, et un `notes` warning « Aucun indicateur lié à ce référentiel — score non calculable ». L'UI cache la card de ce référentiel.
- **Que se passe-t-il quand la PME a renseigné des indicateurs mais qu'aucun référentiel ne les couvre (cas extrême) ?** Tous les `referential_scores` ont `coverage_rate=0`, `overall_score=null`. L'UI affiche un message pédagogique : « Vos indicateurs ne sont pas encore couverts par un référentiel actif. L'équipe Mefali est en train d'enrichir le catalogue. ».
- **Comment éviter de recalculer 7 référentiels alors que la modification d'indicateur n'en concerne qu'1 ?** Le service `compute_all_referential_scores` accepte un paramètre optionnel `only_referentials_using_indicators=[indicator_id_X]` qui filtre les référentiels concernés via la table `referential_indicators` (F01). Si un indicateur est utilisé par 3 référentiels seulement, seuls ces 3 sont recalculés.
- **Que se passe-t-il pour une offre dont les fund.referential et intermediary.referential sont identiques (cas d'un fonds national distribué par lui-même) ?** Le `<DualReferentialView>` affiche un seul score (pas de duplication visuelle) et le bandeau pédagogique indique « Référentiel unique pour cette offre : pas de goulot d'étranglement ».
- **Comment le système gère-t-il le PDF si la PME demande 7 référentiels mais que 3 ont coverage < 50 % ?** Le PDF est généré avec les 7 sections, mais une bannière « Rapport préliminaire » apparaît en première page listant les 3 référentiels avec coverage insuffisante.
- **Que se passe-t-il si un job de recalcul background plante (exception non gérée) en plein milieu de 7 référentiels (ex : 4 calculés, 3 non) ?** Les 4 lignes sont persistées (atomicité par référentiel), les 3 manquantes ne sont pas créées. Un événement `audit_log` `action='referential_score_recompute_partial'` est créé. L'UI détecte que `len(referential_scores) < len(active_referentials)` et propose un bouton « Recompléter le calcul » qui relance les manquants.
- **Que se passe-t-il quand l'admin supprime un référentiel (cas extrême, devrait être une désactivation) ?** L'`ondelete='RESTRICT'` empêche la suppression tant que des `referential_scores` historiques existent. L'admin doit d'abord archiver / soft-delete via `is_active=false`.

## Requirements *(mandatory)*

### Functional Requirements

#### Domaine `ReferentialScore` (entité nouvelle)

- **FR-001** : Le système DOIT créer une nouvelle table `referential_scores` représentant le résultat du calcul d'un référentiel pour une évaluation ESG donnée.
- **FR-002** : Chaque `ReferentialScore` DOIT comporter `id` (UUID PK), `account_id` (UUID FK `accounts.id` NOT NULL, RLS F02), `assessment_id` (UUID FK `esg_assessments.id` ON DELETE CASCADE), `referential_id` (UUID FK `referentials.id` ON DELETE RESTRICT), `referential_version` (chaîne semver `major.minor.patch` snapshot au moment du calcul, F04).
- **FR-003** : Chaque `ReferentialScore` DOIT comporter `overall_score` (Numeric(5,2), nullable si coverage=0), `pillar_scores` (JSONB structuré `{pilier_code: {score, weight, criteria_count}}`), `coverage_rate` (Numeric(4,3) entre 0 et 1, % indicateurs renseignés sur indicateurs liés au référentiel).
- **FR-004** : Chaque `ReferentialScore` DOIT comporter `covered_criteria` (JSONB array de `{indicator_id, score, weight, source_id}`), `missing_criteria` (JSONB array de `{indicator_id, reason, source_id}`), `gap_to_threshold` (Numeric(5,2), positif si overall_score >= seuil), `eligibility` (bool `overall_score >= referentials.threshold`).
- **FR-005** : Chaque `ReferentialScore` DOIT comporter `computed_at` (timestamptz), `computed_by` (enum `manual|llm|auto`), `computed_request_id` (UUID nullable, traçabilité du job background), `superseded_by` (UUID nullable FK self-référente vers `referential_scores.id` ON DELETE SET NULL, pour le pattern F04), `created_at` et `updated_at` (timestamps).
- **FR-006** : Le système DOIT garantir l'unicité du couple `(assessment_id, referential_id)` pour le score « courant » via un index unique partiel `(assessment_id, referential_id) WHERE superseded_by IS NULL` ; les versions historiques antérieures sont identifiées par `superseded_by NOT NULL` pointant vers l'UUID de la version qui les remplace (pattern F04 `superseded_by` self-référent nullable, cohérence avec Fund/Intermediary versioning).
- **FR-007** : Le système DOIT ajouter un index `(assessment_id, computed_at DESC)` pour permettre le tri chronologique rapide.
- **FR-008** : Le système DOIT ajouter un index `(referential_id, computed_at DESC)` pour les statistiques admin (« combien de PMEs ont un score IFC > 60 cette semaine »).
- **FR-009** : Le système DOIT appliquer une RLS PostgreSQL sur `referential_scores` filtrant par `account_id = current_setting('app.current_account_id')` (F02 invariant strict).

#### Service `compute_all_referential_scores`

- **FR-010** : Le système DOIT exposer une fonction `compute_all_referential_scores(assessment_id, only_referentials_using_indicators=None) → list[ReferentialScore]` accessible depuis `app/modules/esg/multi_referential_service.py`.
- **FR-011** : Le service DOIT charger l'évaluation, ses `IndicatorValues`, et la liste des `referentials` actifs (`is_active=true`).
- **FR-012** : Si `only_referentials_using_indicators` est fourni, le service DOIT filtrer les référentiels via la table `referential_indicators` (F01) pour ne calculer que ceux concernés par les indicateurs modifiés.
- **FR-013** : Le service DOIT appeler `compute_score_for_referential(referential, indicator_values)` pour chaque référentiel actif et persister chaque résultat dans `referential_scores` (UPSERT sur `(assessment_id, referential_id)`).
- **FR-014** : Le service DOIT calculer en parallèle (asyncio.gather) les N référentiels pour minimiser la latence totale.
- **FR-015** : Le service DOIT être idempotent : appeler 2 fois consécutivement avec les mêmes inputs produit le même résultat (UPSERT).

#### Service `compute_referential_score_for_offer`

- **FR-016** : Le système DOIT exposer une fonction `compute_referential_score_for_offer(assessment_id, offer_id) → tuple[ReferentialScore, ReferentialScore]`.
- **FR-017** : Le service DOIT récupérer l'`Offer` (F07) et identifier `fund.referential_id` et `intermediary.referential_id`.
- **FR-018** : Si `fund.referential_id IS NULL`, le service DOIT renvoyer le score ESG Mefali pour le fonds (fallback) avec un flag `is_fallback=true` dans la réponse.
- **FR-019** : Idem pour `intermediary.referential_id`.
- **FR-020** : Si les deux référentiels sont identiques (cas d'un fonds national auto-distribué), le service DOIT renvoyer un seul score (la deuxième position du tuple est NULL).
- **FR-021** : Le service DOIT identifier le « goulot d'étranglement » comme le `min(score_fonds.overall_score, score_intermediaire.overall_score)` et le retourner dans une structure annexe.

#### Refactor `esg_scoring_node` LangGraph

- **FR-022** : Le système DOIT refactorer le node `esg_scoring_node` (`backend/app/graph/nodes.py`) pour appeler `compute_all_referential_scores(assessment_id)` plutôt que `compute_overall_score` mono-référentiel.
- **FR-023** : Le `esg_scoring_node` DOIT injecter dans le state LangGraph la liste des `referential_scores` calculés pour permettre aux nodes downstream (financing_node, action_plan_node) de consommer.
- **FR-024** : Le `esg_scoring_node` DOIT continuer à mettre à jour les colonnes legacy `esg_assessments.overall_score|environment_score|social_score|governance_score` pendant les 2 sprints de transition (cohérence F11 dashboard).

#### Tools LangChain

- **FR-025** : Le système DOIT exposer le tool LangChain `finalize_esg_assessment(assessment_id, referentials_to_compute: list[str] = None)` qui finalise une évaluation ESG en calculant les référentiels demandés (default = tous les actifs). Le tool retourne une structure typée Pydantic avec les scores calculés.
- **FR-026** : Le système DOIT exposer le tool LangChain `recompute_score(entity_id: UUID, referentiel_id: UUID)` qui enqueue un recalcul ciblé sur un seul référentiel et retourne un `recompute_request_id`. Le `entity_id` peut référer à un assessment ou à un autre objet (extensibilité Module 1.1.3).
- **FR-027** : Le système DOIT exposer le tool LangChain `compare_referentials(assessment_id: UUID, referentials: list[str])` qui retourne une structure typée `ComparisonResult` avec les scores, les gaps, et les critères divergents.
- **FR-028** : Chaque tool LangChain DOIT être instrumenté via `tool_call_logs` (F12) — chaque appel persiste un événement avec arguments, réponse, et durée.
- **FR-029** : Aucun tool LangChain ne DOIT muter le catalogue (`referentials`, `indicators`, `sources`) — invariant projet n°7 (réservé Admin F09).

#### Endpoint API REST `POST /api/reports/esg/{id}/generate`

- **FR-030** : Le système DOIT refactorer l'endpoint existant `POST /api/reports/esg/{id}/generate` pour accepter un body JSON `{referentials: list[str], include_appendix_sources: bool}`.
- **FR-031** : Si `referentials` n'est pas fourni, le default DOIT être `["mefali"]` (rétrocompatibilité F06).
- **FR-032** : Si `include_appendix_sources` n'est pas fourni, le default DOIT être `true`.
- **FR-033** : L'endpoint DOIT valider que chaque code dans `referentials` correspond à un `referentials.code` actif ; sinon retourner 422 avec liste des codes valides.
- **FR-034** : L'endpoint DOIT renvoyer 202 Accepted avec un `report_id` et un statut `pending` (génération asynchrone) ; le PDF est récupérable via `GET /api/reports/{report_id}/download` une fois généré.
- **FR-035** : L'endpoint DOIT utiliser le RLS multi-tenant : un utilisateur ne peut générer un rapport que pour ses propres assessments.

#### Refactor template `esg_report.html`

- **FR-036** : Le système DOIT refactorer le template Jinja2 `esg_report.html` pour boucler sur la liste de référentiels sélectionnés et générer une section dédiée par référentiel.
- **FR-037** : Chaque section de référentiel DOIT contenir le score global, le radar par pilier (matplotlib SVG), la liste des critères couverts (avec sources F01 cliquables), et la liste des critères manquants (avec recommandations).
- **FR-038** : Le template DOIT inclure un tableau comparatif transverse `indicateur × référentiel` (qui couvre quoi).
- **FR-039** : Si `include_appendix_sources=true`, le template DOIT générer une annexe « Sources et références » listant toutes les `Source` F01 citées dans le rapport (URL, page, date d'extraction, statut `verified`).
- **FR-040** : Si un référentiel sélectionné a `coverage_rate < 0.5`, le template DOIT afficher une bannière rouge « Rapport préliminaire — couverture insuffisante » sur la première page et au-dessus de la section concernée.

#### Frontend — Composants

- **FR-041** : Le système DOIT créer le composant Vue `<ReferentialSelector :options="referentials" v-model="selectedReferential">` dans `frontend/app/components/esg/`.
- **FR-042** : Le système DOIT créer le composant Vue `<ReferentialScoreCard :score="referentialScore">` qui affiche un score, un radar par pilier, les critères couverts/manquants.
- **FR-043** : Le système DOIT créer le composant Vue `<DualReferentialView :scoreLeft :scoreRight :bottleneck>` pour la page `/financing/offers/[id]`.
- **FR-044** : Le système DOIT créer le composant Vue `<MissingCriteriaList :criteria>` qui liste les critères manquants avec un `<SourceLink>` (F01) cliquable par critère.
- **FR-045** : Tous les composants DOIVENT supporter le dark mode (variantes `dark:` Tailwind, palette définie dans `app/assets/css/main.css`).
- **FR-046** : Tous les composants DOIVENT être en français avec accents corrects (é, è, ê, à, ç, ù).

#### Frontend — Pages

- **FR-047** : Le système DOIT refactorer la page `frontend/app/pages/esg/results.vue` pour intégrer le `<ReferentialSelector>`, afficher dynamiquement le `<ReferentialScoreCard>` du référentiel sélectionné, et proposer un mode « vue côte-à-côte » pour comparer N référentiels.
- **FR-048** : Le système DOIT enrichir la page `frontend/app/pages/financing/offers/[id].vue` avec une section « Mon éligibilité pour cette offre » utilisant le `<DualReferentialView>` et le bandeau pédagogique de goulot d'étranglement.
- **FR-049** : Le système DOIT créer un composable `useEsgMultiReferential.ts` qui encapsule les appels API (`getReferentialScores`, `recomputeScore`, `compareReferentials`, `generateMultiReferentialReport`).
- **FR-050** : Le système DOIT mettre à jour le store Pinia `stores/esg.ts` pour exposer `referentialScores: ReferentialScore[]`, `selectedReferential: string`, `isRecomputing: bool`, `recomputeRequestId: string | null`.

#### Recalcul asynchrone

- **FR-051** : Le système DOIT introduire un service de background tasks (FastAPI `BackgroundTasks` en MVP, Redis post-MVP) qui orchestre les recalculs.
- **FR-052** : La mutation `PATCH /api/esg/assessments/{id}/indicator-values` DOIT enqueue un job de recalcul et répondre 202 Accepted avec un `recompute_request_id`.
- **FR-053** : Le frontend DOIT polling toutes les 2 s sur `GET /api/esg/assessments/{id}/referential-scores` jusqu'à voir un `computed_at` plus récent que `recompute_started_at` (signal de complétion).
- **FR-054** : Si le job échoue, les anciens scores DOIVENT être conservés et un événement `audit_log` créé (`action='referential_score_recompute_failed'`).

#### Coverage rate et seuils

- **FR-055** : Le service de calcul DOIT calculer `coverage_rate = count(indicators_renseignés_pour_ce_référentiel) / count(indicators_total_du_référentiel)`.
- **FR-056** : La pondération DOIT ignorer les indicateurs non renseignés (pas zéro par défaut) — le score est calculé sur la base des indicateurs effectivement renseignés.
- **FR-057** : Si `coverage_rate < 0.5` (seuil configurable), le frontend DOIT afficher un badge orange « Couverture indicateurs : X % — score indicatif » et désactiver le bouton « Inclure dans rapport PDF ».
- **FR-058** : Le seuil `min_coverage_for_pdf_inclusion` DOIT être configurable via `referentials.min_coverage_for_pdf` (default 0.5) — un admin peut forcer l'inclusion via override.

#### Versioning F04

- **FR-059** : Chaque calcul de score DOIT snapshoter `referentials.version` au moment du calcul dans `referential_scores.referential_version`.
- **FR-060** : Quand un référentiel évolue de version (admin incrémente v1.1 → v1.2 via F09), le système NE DOIT PAS recalculer automatiquement les scores existants ; un cron mensuel DOIT proposer un opt-in via notification dashboard.
- **FR-061** : L'historique des `referential_scores` (versions antérieures) DOIT être consultable via un endpoint `GET /api/esg/assessments/{id}/referential-scores/history?referential_id=X` qui retourne toutes les versions snapshot triées par `computed_at DESC` (filtrage `superseded_by IS NOT NULL` pour ne pas dupliquer le score courant déjà retourné par l'endpoint principal).
- **FR-061a** : Le système DOIT exposer un cron mensuel `scripts/check_referential_versions_evolution.py` qui parcourt les évolutions de version des référentiels actifs (`referentials.version` modifié depuis le dernier passage) et crée pour chaque PME concernée une entrée dans la table existante `reminders` (F11) avec `kind='referential_version_evolved'`, `metadata={referential_id, old_version, new_version, delta_summary}`. Le cron DOIT être idempotent (pas de doublon si exécuté 2 fois consécutives via un check `WHERE NOT EXISTS`).
- **FR-061b** : Le frontend DOIT consommer le reminder `kind='referential_version_evolved'` via le composable `useReminders.ts` (F11) pour afficher dans la cloche dashboard un bouton « Voir le delta » (modale détaillant les nouveaux indicateurs/pondérations via la diff `referentials.version_history` F04) et un bouton « Recalculer maintenant » (déclenche `POST /api/esg/assessments/{id}/recompute-score?referentiel_id=X`).

#### Backfill migration

- **FR-062** : La migration `030_create_referential_scores` DOIT seeder le référentiel « ESG Mefali » comme une ligne dans la table `referentials` (`code='mefali'`, `name='ESG Mefali'`, `version='1.0.0'`, `is_active=true`, `threshold=50`, `min_coverage_for_pdf=0.5`) avec ses 30 indicateurs E/S/G actuels liés via `referential_indicators` (seed idempotent `ON CONFLICT DO NOTHING`). L'UUID Mefali est stable et capturé dans une constante backend (`MEFALI_REFERENTIAL_UUID`).
- **FR-062a** : La migration `030_create_referential_scores` DOIT exécuter un backfill : pour chaque `EsgAssessment` existante, créer une ligne `referential_scores` avec `referential_id=MEFALI_REFERENTIAL_UUID`, `overall_score=esg_assessments.overall_score`, `pillar_scores={E: env_score, S: soc_score, G: gov_score}`, `referential_version='1.0.0'`, `computed_by='auto'`, `coverage_rate=NULL` (legacy, pas de tracking coverage avant F13), `superseded_by=NULL`.
- **FR-063** : Le backfill DOIT respecter la contrainte unique `(assessment_id, referential_id)` et utiliser `INSERT … ON CONFLICT DO NOTHING` pour idempotence.
- **FR-064** : La migration DOIT être réversible (`alembic downgrade -1` supprime la table `referential_scores` et restaure l'état antérieur).
- **FR-065** : Les colonnes legacy `esg_assessments.overall_score|environment_score|social_score|governance_score` DOIVENT être conservées 2 sprints en deprecated (les services F11 dashboard / F06 reports les lisent encore en parallèle) puis supprimées dans une migration post-F13.

### Key Entities

- **ReferentialScore** : Résultat du calcul d'un référentiel pour une évaluation ESG donnée. Lie `EsgAssessment` (F05) et `Referential` (F01) avec snapshot de la version (F04). Contient le score global, les scores par pilier, les critères couverts/manquants, le coverage rate, le gap au seuil, l'éligibilité bool.
- **Referential** (F01) : Catalogue read-only des référentiels actifs (Mefali, GCF, IFC PS, BOAD ESS, GRI, ODD, etc.). Contient les indicateurs liés via `referential_indicators`, les pondérations, le seuil d'éligibilité, la version semver, le `min_coverage_for_pdf`.
- **EsgAssessment** (F05) : Évaluation ESG d'une PME, contient les `IndicatorValues` saisis. C'est l'objet pivot qui alimente N `ReferentialScore`.
- **Indicator** (F01) : Définition d'un indicateur ESG (ex : « % de déchets recyclés ») lié à 1+ référentiels via `referential_indicators`. Relie une saisie PME à plusieurs scores.
- **Source** (F01) : Source documentaire vérifiée (URL, page, date d'extraction, statut `verified`) référencée par chaque indicateur, pondération, seuil.
- **Offer** (F07) : Couple (Fonds × Intermédiaire) qui détermine quels référentiels sont applicables (fonds.referential_id + intermediary.referential_id) lors d'une candidature.
- **AuditLog** (F03) : Journal append-only des mutations sur `referential_scores` (calcul, recalcul, échec, fallback).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Une PME peut basculer entre 5 référentiels (Mefali, GCF, IFC PS, BOAD ESS, GRI 2021) sur la page `/esg/results` en moins de 500 ms (changement local Vue, pas de rechargement page).
- **SC-002** : Le calcul `compute_all_referential_scores` pour 5 référentiels et 35 indicateurs s'exécute en moins de 5 secondes côté serveur (asyncio.gather parallèle).
- **SC-003** : Le PDF multi-référentiels (5 référentiels, annexe sources) est généré en moins de 30 secondes (background task).
- **SC-004** : Le sélecteur multi-référentiels permet à 90 % des PMEs de découvrir au moins une divergence significative (gap > 10 points) entre 2 référentiels (mesuré sur 30 jours après mise en production).
- **SC-005** : 80 % des PMEs qui consultent une offre dans `/financing/offers/[id]` voient un goulot d'étranglement clair (différence > 5 points entre fonds et intermédiaire) et identifient au moins 1 critère prioritaire à renseigner (mesuré via tracking « clic Renseigner maintenant »).
- **SC-006** : Une saisie d'indicateur dans `/esg` déclenche un recalcul background et la PME voit les nouveaux scores en moins de 10 secondes (mesure E2E Playwright).
- **SC-007** : Aucune saisie d'indicateur ne crée de duplication en base (un seul `IndicatorValue` par `(assessment_id, indicator_id)`) — vérifié par contrainte unique + test E2E.
- **SC-008** : 100 % des chiffres, scores, seuils, pondérations affichés sur les pages `/esg/results` et `/financing/offers/[id]` sont liés à une `Source` F01 vérifiée — vérifié par test d'intégration sur les payloads API.
- **SC-009** : Les RLS multi-tenant bloquent 100 % des tentatives d'accès cross-account aux `referential_scores` — vérifié par test E2E avec 2 comptes A et B.
- **SC-010** : La couverture de tests automatisés (unit + integration + E2E) sur les modules F13 atteint au minimum 80 % (mesure pytest-cov + vitest --coverage).
- **SC-011** : Le backfill de la migration `030_create_referential_scores` migre 100 % des `EsgAssessment` existantes vers `referential_scores` (Mefali) sans perte de score historique — vérifié par snapshot avant/après migration.
- **SC-012** : Au moins 5 référentiels (Mefali + GCF + IFC PS + BOAD ESS + GRI 2021) sont seedés et calculables en MVP, avec ODD ajoutable post-MVP via F09.

## Assumptions

- F01 (Source + Indicator + Referential catalogue) est mergée avant le démarrage de F13. Sans F01, le calcul multi-référentiels n'a pas de structure de catalogue à exploiter.
- F04 (versioning + Money typed) est mergée. La table `referentials` expose une colonne `version` semver gérée par admin.
- F07 (Offer = Fonds × Intermédiaire) est mergée. Les colonnes `fund.referential_id` et `intermediary.referential_id` existent (sinon F13 ajoute un fallback NULL → ESG Mefali).
- F02 (multi-tenant + RLS) est mergée. Les RLS PostgreSQL sont actives sur les tables ESG.
- F03 (audit log append-only) est mergée. Les mutations sur `referential_scores` passent par le mixin `Auditable`.
- Les 5 référentiels MVP (Mefali, GCF, IFC PS, BOAD ESS, GRI 2021) sont seedés par F01 ou par seed migration F13 si F01 ne couvre pas tous. ODD est ajouté post-MVP par F09.
- Le service de background tasks repose sur `FastAPI BackgroundTasks` en MVP (in-memory) ; Redis + Celery en post-MVP. Un redéploiement = perte des jobs en cours en MVP, l'utilisateur doit refresh.
- La latence saisie → score visible est tolérée jusqu'à 10 secondes en MVP (recalcul async). Si > 10 s, l'UX se dégrade (frustration utilisateur) mais ne bloque pas le parcours.
- Le PDF multi-référentiels est généré via WeasyPrint (déjà en place dans F06) avec template Jinja2 refactoré.
- Les colonnes legacy `esg_assessments.overall_score|environment_score|social_score|governance_score` sont conservées 2 sprints en parallèle de `referential_scores` pour éviter de casser F11 dashboard et F06 reports ; suppression dans une migration ultérieure (post-F13, F14 ou F15).
- L'invariant n°7 « aucun tool LLM ne mute le catalogue » est respecté : les tools `compare_referentials`, `recompute_score`, `finalize_esg_assessment` sont en lecture/calcul seul ; ils ne créent pas de référentiel ni d'indicateur (réservé Admin F09).
- Le seuil par défaut `min_coverage_for_pdf=0.5` est défini par référentiel et configurable admin. Un PME ne peut pas inclure un référentiel à coverage < 50 % dans son PDF, sauf override admin (F09).
- Les codes de référentiels (slugs) sont stables : `"mefali"`, `"gcf"`, `"ifc_ps"`, `"boad_ess"`, `"gri_2021"`, `"odd"`. Les API REST utilisent ces slugs (pas les UUID) pour la lisibilité externe.
- Tests E2E dans `frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts`, exécutables via `cd frontend && npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts`.

## Dependencies

- **F01 — Source + Indicator + Referential catalogue** (BLOQUANT) : sans le catalogue d'indicateurs lié aux référentiels, F13 n'a pas de structure à exploiter.
- **F04 — Versioning + Money typed** (BLOQUANT pour `referential_version` snapshot) : la colonne `referentials.version` doit exister et être semver.
- **F07 — Offer = Fonds × Intermédiaire** (BLOQUANT pour User Story 2 dual view) : les colonnes `fund.referential_id` et `intermediary.referential_id` doivent exister.
- **F02 — Multi-tenant + RLS** (BLOQUANT pour User Story 7) : les RLS PostgreSQL doivent être actives.
- **F03 — Audit log** (BLOQUANT pour FR-054 et observabilité) : le mixin `Auditable` doit exister.
- **F05 — ESG scoring assessment** (BLOQUANT) : la table `esg_assessments` et le service `compute_overall_score` existent (cible de la migration backfill).
- **F06 — ESG PDF reports** (BLOQUANT pour User Story 3) : l'endpoint `POST /api/reports/esg/{id}/generate` et le template `esg_report.html` existent et sont à refactorer.
- **F11 — Dashboard + action plan** (CONSOMMATEUR) : F11 lit les scores ESG ; pendant les 2 sprints de transition, les colonnes legacy sont conservées.
- **F12 — Tool calling LangGraph** (BLOQUANT pour User Story 6) : l'infrastructure tools LangChain et `tool_call_logs` existe.
