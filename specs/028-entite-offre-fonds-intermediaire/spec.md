# Feature Specification: F07 — Entité Offre = Couple Fonds × Intermédiaire

**Feature Branch**: `feat/F07-entite-offre-fonds-intermediaire` (alias SpecKit `028-entite-offre-fonds-intermediaire`)
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F07 — Entité Offre = Couple Fonds × Intermédiaire (Module 3.1.3 + Module 3.1.1 + Module 3.1.2 du brainstorming). Promesse différenciante : la plupart des grands fonds verts ne décaissent jamais directement aux PME africaines. Trois entités — Fonds source, Intermédiaire accrédité, Offre (couple Fonds × Intermédiaire) — où c'est l'Offre qui est l'unité commercialement accessible à une PME. Enrichir Fund (instruments, theme, submission_mode, source_id, version, Money typed, fund_type renommé multilateral/bilateral/regional/national/private/carbon_marketplace), Intermediary (required_documents jsonb, fees_structured Money, processing_time_days, success_rate, source_id), FundIntermediary (accredited_from, accredited_to, max_amount_per_fund). Créer table offers avec calcul automatique compute_effective_offer (intersection critères, union documents, somme frais/délais, accepted_languages FR/EN). Refactor FundApplication pour offer_id. API REST module offers, 3+ tools LangChain, 4 pages Vue + 8 composants. Dépendances : F01 sources, F02 multi-tenant Admin, F04 versioning + Money typed, F06 entité Projet."

## Clarifications

### Session 2026-05-07

- Q: Pour une PME, l'unité commercialement actionnable est-elle l'Offre (couple Fonds × Intermédiaire) ou faut-il préserver la possibilité de candidater directement à un Fonds en mode `direct` (bypass intermédiaire) ? → A: **Offre est l'unité actionnable obligatoire**. Quand un fonds est nativement `access_type='direct'` (pas d'intermédiaire requis), une « offre fictive » `(fund_id, intermediary_id=NULL)` est créée — sauf que la contrainte `NOT NULL` interdit cela. Décision retenue : créer un **intermédiaire singleton « Direct (sans intermédiaire) »** identifié par un `code='DIRECT'` et le coupler à tous les fonds `access_type='direct'`. Cela uniformise le modèle (toujours via Offre), simplifie le parcours PME (toujours « cette Offre, ce flux »), et permet aux candidatures futures de pointer systématiquement vers une `offer_id NOT NULL`. Le seed initial crée cet intermédiaire singleton lors de la migration.
- Q: Pendant la migration, la vue PME bascule-t-elle immédiatement sur les Offres (`USE_OFFER_VIEW=true`) ou démarre-t-elle en mode hybride avec la vue fonds-centric encore disponible 2 sprints ? → A: **Mode hybride contrôlé par feature flag `USE_OFFER_VIEW` (default `false` en MVP F07)** : la vue Offres est créée et accessible via `/financing/offers/...` mais la home `/financing` continue d'afficher les Cards Fonds avec leur modal d'intermédiaires (vue actuelle préservée). Quand l'admin active le flag (env var ou table `feature_flags` ; défaut env var `USE_OFFER_VIEW=false`), la home bascule vers la vue Cards Offres. Les deux pages cohabitent donc 2 sprints, le rollout effectif vers la vue offre se fera dans une feature ultérieure (post-F14 quand le matching offre est mature). **Garde-fou** : les nouveaux dossiers (`POST /api/applications`) acceptent `offer_id` ET (`fund_id` + `intermediary_id`) durant cette phase pour ne pas casser F15 si elle livre avant la bascule.
- Q: Dans la migration backfill, quelles `Offer` créer ? Toutes les paires `FundIntermediary` existantes, ou uniquement celles qui ont au moins une `FundApplication` rattachée ? → A: **Toutes les paires `FundIntermediary` existantes ET tous les fonds `access_type='direct'` (via l'intermédiaire singleton DIRECT)**. Toutes ces offres sont créées avec `is_active=false`, `publication_status='draft'` et un nom auto-généré `{fund.name} via {intermediary.name}`. L'admin valide manuellement chaque offre avant publication. Pour les `FundApplication` existantes, le backfill cherche/crée l'offre correspondante et lie `offer_id`. Si une application avait `intermediary_id=NULL` (cas direct), elle est liée à l'offre `(fund_id, DIRECT)` créée. **Bénéfice** : pas d'orphelins, pas de double table à maintenir, tous les futurs flows pointent vers `offer_id`.
- Q: Pour le calcul automatique `compute_effective_offer`, comment traiter la déduplication des `effective_required_documents` quand `fund.required_documents` et `intermediary.required_documents` contiennent des entrées avec titres légèrement différents (ex : « Statuts juridiques » vs « Statuts de l'entreprise ») ? → A: **Déduplication exacte sur `(title.lower().strip(), source_id)` uniquement** ; pas de dédup fuzzy. Les doublons « apparents » mais sources/titres distincts sont conservés. Un document avec `mandatory=true` côté fund écrase un `mandatory=false` côté intermediary lors de la fusion finale (le plus restrictif gagne). L'admin peut éditer/supprimer les doublons manuellement après le calcul. **Rationale** : déduplication automatique fuzzy est risquée (faux positifs cachant un vrai document obligatoire), tandis que la dédup exacte par source garantit la traçabilité F01 et l'admin a le dernier mot.
- Q: La langue acceptée par défaut d'une Offre est-elle systématiquement `["FR"]`, ou faut-il que le calcul automatique infère la langue depuis le pays de l'intermédiaire (ex : `intermediary.country='UK'` → `["EN"]`) ? → A: **Default `["FR"]` toujours**, **mais le calculator hint l'admin** : si `intermediary.country` ∈ {`UK`, `US`, `CA`, `KE`, `GH`, `NG`, `ZA`, `DE`, `JP`} (pays anglophones ou non-francophones avec représentation forte), le draft `OfferDraft` retourné inclut un champ `accepted_languages_hint=["EN"]` ou `["FR","EN"]` que l'admin peut accepter ou rejeter dans l'UI. La valeur effectivement persistée dans `offers.accepted_languages` reste celle décidée par l'admin (default `["FR"]` si non modifié). **Rationale** : le calculator est un outil d'aide à la décision, pas une autorité ; l'admin connaît mieux le contexte commercial réel d'un intermédiaire qu'une heuristique pays.
- Q: Quand le cron quotidien détecte `accredited_to < today` sur un `FundIntermediary`, faut-il désactiver automatiquement les offres correspondantes (`is_active=false`) ou simplement alerter l'admin ? → A: **Désactivation automatique douce** : `is_active=false` ET `publication_status='draft'` (basculer du `published` vers `draft`), avec un email/notification interne à l'admin et entrée audit_log F03 (`entity_type='offer'`, `action='auto_unpublished_accreditation_expired'`, `metadata={accreditation_source_id, accredited_to}`). Une bannière d'alerte apparaît dans le back-office admin avec lien vers la liste des offres affectées. **Rationale** : une accréditation expirée est un changement légal certifiable (sourcé F01) — laisser l'offre publiée serait juridiquement risqué (la PME pourrait préparer un dossier inutile). L'admin peut toujours republier après revue (ex : si l'accréditation a été renouvelée mais le source_id n'est pas encore mis à jour).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — PME compare deux offres concurrentes pour un même fonds (Priority: P1)

Une PME ayant un projet d'agriculture durable cible le Green Climate Fund (GCF). Sur la page `/financing` (en mode `USE_OFFER_VIEW=true`), elle voit deux Cards d'Offres distinctes pour le GCF : « GCF via BOAD — Mitigation Afrique Ouest » et « GCF via UNDP — Adaptation Afrique ». Chaque card affiche un score de compatibilité décomposé (`fund_score=82`, `intermediary_score=74`), le badge de langue acceptée (`FR` pour BOAD, `FR + EN` pour UNDP), le mode de soumission (rolling vs CFP), et les frais effectifs cumulés en XOF. Elle clique sur la première offre, consulte le détail (critères effectifs, documents requis, frais effectifs Money typed, délais cumulés), revient en arrière, ouvre la seconde offre, puis clique sur le bouton « Comparer avec autres offres pour ce fonds » qui affiche un comparateur côte-à-côte (frais, délai de traitement, délai de décaissement, taux de succès, langue, documents requis additionnels). Elle décide de candidater à l'offre BOAD car le délai est plus court et la langue est FR seul.

**Why this priority** : C'est la promesse différenciante du brainstorming (« l'Offre est l'unité commercialement accessible à une PME »). Sans cette story, la PME voit un seul fonds GCF générique avec ses intermédiaires en modal, sans comparaison structurée — elle ne peut pas faire de choix éclairé sur l'intermédiaire à privilégier. Cette story est ce qui justifie la création de la table `offers` et la refonte frontend.

**Independent Test** : Créer deux paires `FundIntermediary` (GCF↔BOAD et GCF↔UNDP), seeder les frais et délais structurés sur chaque intermédiaire, lancer le calcul `compute_effective_offer` pour les deux paires, publier les offres (`publication_status='published'`, `is_active=true`), activer `USE_OFFER_VIEW=true`, ouvrir `/financing` en tant que PME, vérifier que les deux Cards Offres sont visibles, comparer leurs détails, ouvrir le comparateur côte-à-côte.

**Acceptance Scenarios** :

1. **Given** un fonds GCF lié à 2 intermédiaires actifs (BOAD et UNDP) avec frais structurés et délais sur chacun, **When** un admin appelle `compute_effective_offer(GCF, BOAD)` puis publie l'offre, et fait de même pour `(GCF, UNDP)`, **Then** la table `offers` contient 2 lignes distinctes, chacune avec `effective_criteria`, `effective_required_documents`, `effective_fees`, `effective_processing_time_days_min/max`, `effective_disbursement_time_days_min/max`, `accepted_languages` et `publication_status='published'`.
2. **Given** les 2 offres GCF publiées et `USE_OFFER_VIEW=true`, **When** une PME ouvre `/financing`, **Then** elle voit 2 Cards Offres distinctes avec scores décomposés, badge langue et frais effectifs.
3. **Given** la PME consulte l'offre `GCF via BOAD`, **When** elle clique sur « Comparer avec autres offres pour ce fonds », **Then** un comparateur côte-à-côte affiche les 2 offres avec colonnes `frais_effectifs`, `processing_time`, `disbursement_time`, `success_rate`, `accepted_languages`, `documents_additionnels` (différentiel).
4. **Given** la PME clique sur l'offre `GCF via BOAD`, **When** elle est sur la page détail, **Then** elle voit le bouton « Candidater » qui pré-charge `offer_id=<uuid>` dans le futur flow F15.

---

### User Story 2 — Admin crée une nouvelle Offre via calcul automatique (Priority: P1)

Un admin Mefali identifie qu'un nouvel intermédiaire (la BAD) vient d'être accrédité pour distribuer le GCF en Afrique de l'Ouest. Sur le back-office (post-F09 ou via API REST `POST /api/admin/offers`), il sélectionne `fund_id=GCF` et `intermediary_id=BAD`, clique sur « Calculer l'offre effective ». Le service `compute_effective_offer(GCF, BAD)` retourne un draft pré-rempli : critères effectifs (intersection des critères du fonds GCF et de l'éligibilité PME de la BAD), documents requis (union dédupliquée par titre+source), frais cumulés (somme `doc_fee_amount` de la BAD + frais GCF), délais cumulés (somme `processing_time_days` BAD + `typical_timeline_months` GCF). Le draft inclut un `accepted_languages_hint=["FR"]` (BAD est francophone). L'admin édite manuellement le `name` (« GCF via BAD — Mitigation Sahel »), ajuste un critère effectif (ex : âge minimum entreprise), accepte la suggestion `accepted_languages`, sauvegarde en `publication_status='draft'`. Plus tard, après revue interne (4 yeux), il bascule en `published`. L'offre devient visible côté PME.

**Why this priority** : Sans calcul automatique, l'admin doit dupliquer manuellement les critères, documents, frais et délais pour chaque nouvelle paire (Fonds × Intermédiaire), ce qui est source d'erreur et de retard. Cette story donne la productivité opérationnelle du back-office et garantit la cohérence des données présentées aux PME.

**Independent Test** : Seeder un fonds GCF avec critères + documents + frais + timeline ; seeder un intermédiaire BAD avec frais structurés + timing + documents ; appeler `POST /api/admin/offers/compute?fund_id=GCF&intermediary_id=BAD` ; vérifier la structure du draft retourné (intersection critères, union documents dédupliquée, somme frais, somme délais, hint langue) ; appeler `POST /api/admin/offers` avec le draft édité ; vérifier la persistance en base avec `publication_status='draft'`.

**Acceptance Scenarios** :

1. **Given** un admin authentifié avec rôle `admin`, un fonds actif GCF avec 5 critères + 3 documents + frais 0.5% + timeline 18 mois, et un intermédiaire actif BAD avec 4 critères + 4 documents (dont 2 communs) + frais structurés 50000 XOF doc fee + 2% rate + timing 90-120 jours, **When** il appelle `POST /api/admin/offers/compute?fund_id=GCF&intermediary_id=BAD`, **Then** la réponse 200 contient `effective_criteria` (intersection 5 ∩ 4 = X critères), `effective_required_documents` (union 3 ∪ 4 dédupliqué = 5 documents), `effective_fees` (somme cumulée Money typed), `effective_processing_time_days_min=540 + 90` et `effective_processing_time_days_max=540 + 120` (en jours), `accepted_languages_hint=["FR"]`, sans persistance en base.
2. **Given** le draft validé par l'admin, **When** il appelle `POST /api/admin/offers` avec le payload édité, **Then** une nouvelle ligne est insérée dans `offers` avec `publication_status='draft'`, `is_active=false` par défaut, version=1, `valid_from=today`, `source_id` requis (référence accréditation BAD-GCF F01).
3. **Given** un admin sans rôle `admin` (rôle `pme`), **When** il appelle `POST /api/admin/offers/compute`, **Then** la réponse est 403 Forbidden avec message « Accès réservé aux administrateurs ».
4. **Given** une offre en `publication_status='draft'`, **When** l'admin appelle `PATCH /api/admin/offers/{id}` avec `publication_status='published'`, **Then** la transition est acceptée seulement si `fund.publication_status='published'` ET `intermediary.publication_status='published'` ET `fund_intermediary.accredited_to IS NULL OR > today` (sinon 422 avec détail des prérequis manquants).

---

### User Story 3 — Migration et backfill : zéro perte de données existantes (Priority: P1)

Au déploiement de F07, la migration Alembic `028` enrichit les tables `funds`, `intermediaries`, `fund_intermediaries`, ajoute la colonne `offer_id NULL` sur `fund_applications`, crée la table `offers`, puis exécute un backfill : pour chaque paire `(fund_id, intermediary_id)` dans `fund_intermediaries`, créer une `Offer` correspondante avec calcul auto (`is_active=false`, `publication_status='draft'`). Pour chaque `Fund` avec `access_type='direct'` (sans intermédiaire), créer/récupérer l'intermédiaire singleton `DIRECT` et créer l'offre correspondante. Pour chaque `FundApplication` existante, lier `offer_id` à l'offre correspondante (recherche par `(fund_id, intermediary_id)` ou `(fund_id, DIRECT)` si `intermediary_id IS NULL`). Aucune `FundApplication` ne doit rester avec `offer_id IS NULL` après le backfill. La migration est testée up/down/up sans erreur.

**Why this priority** : La plateforme a déjà 12 fonds, 14 intermédiaires, ~50 paires `FundIntermediary` et un nombre potentiellement non-nul d'`FundApplication` créées via l'ancien flow F08. Sans backfill rigoureux, ces données sont perdues ou orphelines après la migration, ce qui casse les pages dashboard et action-plan.

**Independent Test** : Snapshot de la base avant migration (counts `funds`, `intermediaries`, `fund_intermediaries`, `fund_applications`) ; appliquer la migration `alembic upgrade head` ; vérifier counts après = counts avant pour ces tables ; vérifier que `offers` contient au moins `count(fund_intermediaries) + count(funds where access_type='direct')` lignes ; vérifier que `SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL = 0` ; faire `alembic downgrade -1` puis `alembic upgrade head` et revérifier.

**Acceptance Scenarios** :

1. **Given** la base avant migration avec N=12 fonds, M=14 intermédiaires, K=50 paires fund_intermediaries, J=3 fund_applications existantes, **When** `alembic upgrade head` est exécuté, **Then** la table `offers` contient au moins K + (count fonds direct) lignes, toutes avec `is_active=false` et `publication_status='draft'`.
2. **Given** la migration appliquée, **When** on requête `SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL`, **Then** le résultat est 0 (toutes les applications sont liées à une offer).
3. **Given** la migration appliquée, **When** on exécute `alembic downgrade -1`, **Then** la table `offers` est supprimée, `fund_applications.offer_id` est supprimée, et les colonnes ajoutées sur `funds`/`intermediaries`/`fund_intermediaries` sont retirées sans perte des données originales (counts = pre-migration).
4. **Given** la migration appliquée puis downgrade puis upgrade, **When** on revérifie les counts, **Then** les résultats sont identiques au premier upgrade (idempotence).

---

### User Story 4 — Calcul effectif respecte la sémantique métier (intersection critères, union documents, somme frais/délais) (Priority: P2)

Lorsque l'admin appelle `compute_effective_offer(fund_id, intermediary_id)`, le service applique des règles métier précises qui matérialisent la « politique de transparence » de Mefali envers les PME. Pour les critères : intersection avec règle « le plus restrictif gagne » (ex : si le fonds exige minimum 3 ans d'existence et l'intermédiaire 5 ans, le critère effectif est 5 ans). Pour les documents : union avec déduplication exacte sur `(title.lower().strip(), source_id)`, et règle « mandatory=true écrase mandatory=false » sur les doublons résiduels. Pour les frais : somme cumulée Money typed (conversion XOF si devises différentes via `app.modules.currency`). Pour les délais : somme min de min, somme max de max. Pour les langues : default `["FR"]`, hint basé sur `intermediary.country`. Toute incohérence (ex : `fund.min_amount > intermediary.max_amount_per_fund`) est signalée dans les `notes` du draft (warning, pas blocant).

**Why this priority** : La promesse de transparence envers les PME repose sur la fiabilité de ces calculs. Une erreur ici (mauvais total des frais, mauvaise langue, oubli d'un document obligatoire) peut conduire une PME à candidater sans préparer un document requis, et donc voir son dossier rejeté inutilement.

**Independent Test** : Créer 4 jeux de tests unitaires synthétiques (fonds A + intermédiaire B avec contraintes prédéterminées) ; exécuter `compute_effective_offer` ; assert sur chaque champ du draft retourné.

**Acceptance Scenarios** :

1. **Given** un fonds avec critère `min_company_age=3` et un intermédiaire avec critère `min_company_age=5`, **When** `compute_effective_offer` s'exécute, **Then** `effective_criteria.min_company_age = 5` (le plus restrictif gagne).
2. **Given** un fonds avec 2 documents `[{title:"Statuts", source_id:S1, mandatory:true}, {title:"Audit", source_id:S2, mandatory:false}]` et un intermédiaire avec 2 documents `[{title:"Statuts", source_id:S1, mandatory:false}, {title:"Plan d'affaires", source_id:S3, mandatory:true}]`, **When** le calcul s'exécute, **Then** `effective_required_documents` contient 3 entrées : Statuts (mandatory=true, dédupliqué), Audit (mandatory=false), Plan d'affaires (mandatory=true).
3. **Given** un fonds avec frais 0.5% (Money typed XOF) et un intermédiaire avec `doc_fee_amount=50000 XOF + fee_rate_min=2%`, pour un montant target de 100M XOF, **When** le calcul s'exécute, **Then** `effective_fees.total_min` ≈ 500000 (0.5%) + 50000 + 2000000 (2%) = 2 550 000 XOF (Money typed).
4. **Given** un fonds avec `typical_timeline_months=18` et un intermédiaire avec `processing_time_days_min=90, processing_time_days_max=180`, **When** le calcul s'exécute, **Then** `effective_processing_time_days_min = 540 + 90 = 630` et `effective_processing_time_days_max = 540 + 180 = 720`.
5. **Given** un fonds GCF (international, accepte FR+EN) et un intermédiaire BOAD (`country='SN'` francophone), **When** le calcul s'exécute, **Then** le draft contient `accepted_languages_hint=["FR"]` (déduit de `country` francophone).
6. **Given** une incohérence détectée (ex : `fund.min_amount=10M > intermediary.max_amount_per_fund=5M`), **When** le calcul s'exécute, **Then** le draft contient une entrée dans `notes` du type « Avertissement : le plafond de l'intermédiaire (5M) est inférieur au minimum du fonds (10M). Vérifier l'éligibilité réelle » sans bloquer la création de l'offre.

---

### User Story 5 — Cron quotidien désactive automatiquement les offres dont l'accréditation a expiré (Priority: P2)

Un cron quotidien (ex : `scripts/check_expired_accreditations.py`) parcourt les `FundIntermediary` ayant `accredited_to < today`. Pour chacune trouvée, il (a) trouve l'offre `(fund_id, intermediary_id)` correspondante, (b) si `is_active=true` ou `publication_status='published'`, met à jour `is_active=false` et `publication_status='draft'`, (c) journalise dans `audit_log` (F03) un événement `entity_type='offer', action='auto_unpublished_accreditation_expired', metadata={accreditation_source_id, accredited_to}`, (d) envoie une notification interne à l'admin (email + bannière dashboard admin). Une PME qui consultait cette offre auparavant ne la voit plus dans la liste publique. Toute candidature en cours sur cette offre n'est PAS supprimée mais reçoit un statut `requires_admin_review` (alerte côté admin pour décision).

**Why this priority** : Une accréditation expirée non reflétée est un risque juridique (offre commerciale présentée comme valide alors qu'elle ne l'est plus). Sans cette automatisation, l'admin doit vérifier manuellement chaque jour, ce qui est ingérable à l'échelle (50+ paires).

**Independent Test** : Seeder une `FundIntermediary` avec `accredited_to=2026-04-01` (passé), seeder l'offre correspondante en `published`/`active` ; exécuter `python scripts/check_expired_accreditations.py` (idempotent) ; vérifier que l'offre est désactivée + audit_log enrichi + bannière admin présente.

**Acceptance Scenarios** :

1. **Given** une `FundIntermediary` avec `accredited_to='2026-04-01'` (date passée) et une offre publiée (`publication_status='published'`, `is_active=true`), **When** le cron est exécuté le 2026-05-07, **Then** l'offre devient `publication_status='draft'`, `is_active=false`, et un événement `audit_log` est inséré avec `action='auto_unpublished_accreditation_expired'`.
2. **Given** la même configuration mais le cron est exécuté 2 fois consécutives, **When** la 2ème exécution se déroule, **Then** aucune nouvelle action n'est entreprise (l'offre est déjà `draft`/`inactive`) — idempotence garantie.
3. **Given** une `FundIntermediary` valide (`accredited_to=2027-01-01` futur), **When** le cron est exécuté, **Then** l'offre correspondante reste inchangée (`publication_status='published'`).
4. **Given** une `FundIntermediary` avec `accredited_to=NULL` (toujours accréditée), **When** le cron est exécuté, **Then** l'offre reste inchangée.

---

### User Story 6 — Multi-tenant : la liste d'offres est publique mais filtrée par publication_status (Priority: P3)

Le catalogue des offres est public (consultable sans authentification, ou en tant que PME de n'importe quel `account_id`), conformément à F02 invariant n°7 (« Aucun tool LLM ne mute le catalogue ; Funds, Intermediaries, ... réservés Admin »). Mais seules les offres `publication_status='published' AND is_active=true` sont retournées par l'API publique `GET /api/offers`. Les drafts sont uniquement visibles via les endpoints admin `GET /api/admin/offers?include_drafts=true`. Les RLS PostgreSQL n'appliquent PAS de filtre `account_id` sur `offers` (catalogue global), mais les endpoints publics filtrent strictement par `publication_status`. Les endpoints admin requièrent `is_admin=true` (helper F02).

**Why this priority** : Cette story protège l'intégrité commerciale de la plateforme : aucun draft ne doit fuiter côté PME (offres en cours d'élaboration, non validées légalement). Sans ce filtre strict, la PME pourrait candidater à une offre incomplète et engager du temps inutilement.

**Independent Test** : Créer 1 offre publiée et 2 offres draft ; appeler `GET /api/offers` sans auth (ou en tant que PME), assert que seule l'offre publiée est retournée ; appeler `GET /api/admin/offers?include_drafts=true` en tant qu'admin, assert que les 3 offres sont retournées.

**Acceptance Scenarios** :

1. **Given** 1 offre publiée et 2 offres draft, **When** une PME (ou un visiteur anonyme) appelle `GET /api/offers`, **Then** la réponse contient uniquement l'offre publiée.
2. **Given** la même configuration, **When** un admin appelle `GET /api/admin/offers?include_drafts=true`, **Then** la réponse contient les 3 offres avec leurs statuts.
3. **Given** une PME appelle `GET /api/admin/offers?include_drafts=true`, **When** la requête est traitée, **Then** la réponse est 403 Forbidden.
4. **Given** une offre `publication_status='published' AND is_active=false`, **When** une PME appelle `GET /api/offers`, **Then** elle n'est PAS retournée (les deux conditions doivent être satisfaites).

---

### Edge Cases

- **Que se passe-t-il si un fonds est supprimé alors que des offres y pointent ?** L'`ondelete='RESTRICT'` empêche la suppression du fonds tant que des offres existent. L'admin doit d'abord désactiver / supprimer les offres. Un message d'erreur clair est retourné.
- **Comment le système gère-t-il un appel `compute_effective_offer` avec un fonds ou un intermédiaire dans `publication_status='draft'` ?** Le calcul est autorisé (utile pour preview admin) mais retourne un avertissement explicite dans `notes` : « Attention : le fonds/intermédiaire est en draft, l'offre ne pourra pas être publiée tant qu'ils ne sont pas eux-mêmes publiés ».
- **Que se passe-t-il quand un admin tente de publier une offre dont le `source_id` réfère à une `Source` non `verified` (cycle 4-yeux F01) ?** La publication est refusée avec `422 Unprocessable Entity` et message « La source liée doit être vérifiée (workflow 4-yeux F01) avant publication de l'offre ».
- **Quel est le comportement lors d'une demande `compute_effective_offer` pour une paire `(fund, intermediary)` qui n'existe pas dans `fund_intermediaries` ?** Le calcul retourne 422 avec message « Aucune accréditation enregistrée pour ce couple (fund, intermediary). Créer d'abord la liaison via le module catalogue. » — sauf pour le couple `(fund, DIRECT)` qui est toujours autorisé.
- **Comment éviter qu'un admin mal informé crée 2 offres identiques pour le même couple ?** L'unique constraint `(fund_id, intermediary_id, version)` empêche les doublons. Pour créer une « v2 » de la même offre, l'admin doit incrémenter `version` (workflow F04).
- **Comment gérer les offres dont les frais cumulés deviennent supérieurs au montant min du fonds (offre commercialement inintéressante) ?** Détection automatique dans le calculator + notes warning ; l'admin peut publier malgré tout (cas de niche), mais l'UI PME affiche un badge « Frais élevés par rapport au montant minimum ».
- **Que se passe-t-il quand une PME a une `FundApplication` en cours sur une offre qui passe en `is_active=false` (cron expiration) ?** L'application n'est PAS automatiquement annulée. Le statut passe à `requires_admin_review` ; un email est envoyé à la PME : « L'accréditation de votre offre a expiré, nous vérifions la situation et reviendrons vers vous sous 48h ».

## Requirements *(mandatory)*

### Functional Requirements

#### Domaine `Fund` (enrichissement)

- **FR-001** : Le système DOIT permettre de catégoriser chaque fonds par un ou plusieurs `instruments` parmi : `subvention`, `pret_concessionnel`, `garantie`, `equity`, `blending` (champ JSONB array).
- **FR-002** : Le système DOIT permettre de catégoriser chaque fonds par un ou plusieurs `theme` parmi : `mitigation`, `adaptation`, `biodiversity`, `circular_economy`, `mixed` (champ JSONB array).
- **FR-003** : Le système DOIT supporter deux modes de soumission par fonds : `rolling` (toujours ouvert) et `call_for_proposals` (sessions datées).
- **FR-004** : Le système DOIT permettre de stocker un calendrier de soumission JSONB pour les fonds en mode `call_for_proposals` (liste d'objets `{name, opens_at, closes_at, status}`).
- **FR-005** : Chaque fonds DOIT être lié à une `Source` vérifiée (FK `source_id NOT NULL`) conformément à F01 invariant n°1.
- **FR-006** : Chaque fonds DOIT supporter le versioning F04 (`version`, `valid_from`, `valid_to`, `superseded_by`) déjà partiellement présent.
- **FR-007** : Chaque fonds DOIT avoir un statut de publication `publication_status` (enum `draft|published`) avec valeur par défaut `draft`.
- **FR-008** : Le système DOIT renommer l'enum `fund_type` en `multilateral|bilateral|regional|national|private|carbon_marketplace` ; les valeurs existantes sont migrées (`international` → `multilateral`, `carbon_market` → `carbon_marketplace`, `local_bank_green_line` → `private`).
- **FR-009** : Les montants min/max d'un fonds DOIVENT être Money typed (paires `amount + currency` Char(3)) conformément à F04 ; les colonnes legacy `min_amount_xof` et `max_amount_xof` sont conservées 2 sprints en deprecated.

#### Domaine `Intermediary` (enrichissement)

- **FR-010** : Le système DOIT permettre de stocker pour chaque intermédiaire une liste structurée de documents requis (`required_documents` JSONB) avec objets `{title, source_id, mandatory: bool, format_spec}`.
- **FR-011** : Le système DOIT remplacer le champ texte libre `typical_fees` par une structure `fees_structured` JSONB avec champs typés (`doc_fee_amount` Money, `fee_rate_min`, `fee_rate_max`, `fx_margin`, `guarantee_required_pct`, `source_id`). Le champ `typical_fees` texte libre reste conservé en deprecated 2 sprints.
- **FR-012** : Chaque intermédiaire DOIT pouvoir indiquer ses délais de traitement (`processing_time_days_min/max`) et de décaissement (`disbursement_time_days_min/max`).
- **FR-013** : Chaque intermédiaire DOIT pouvoir indiquer une URL de portail de soumission (`submission_portal_url`).
- **FR-014** : Chaque intermédiaire DOIT pouvoir indiquer un taux de succès historique (`success_rate Numeric(5,4)` entre 0 et 1) et un volume total financé (`total_funded_volume_amount + currency` Money typed).
- **FR-015** : Chaque intermédiaire DOIT être lié à une `Source` vérifiée (FK `source_id NOT NULL`) conformément à F01.
- **FR-016** : Chaque intermédiaire DOIT supporter le versioning F04 (déjà partiellement présent) et le `publication_status` (`draft|published`).
- **FR-017** : Le système DOIT créer un intermédiaire singleton (`code='DIRECT'`, `name='Direct (sans intermédiaire)'`) lors de la migration, utilisé pour modéliser les fonds `access_type='direct'` comme des offres uniformes.

#### Domaine `FundIntermediary` (enrichissement)

- **FR-018** : Chaque liaison `FundIntermediary` DOIT inclure une date de début d'accréditation (`accredited_from` date NOT NULL).
- **FR-019** : Chaque liaison `FundIntermediary` DOIT pouvoir inclure une date de fin d'accréditation (`accredited_to` date NULL = encore accréditée).
- **FR-020** : Chaque liaison `FundIntermediary` DOIT pouvoir inclure un plafond par fonds (`max_amount_per_fund` Money typed).
- **FR-021** : Chaque liaison `FundIntermediary` DOIT pouvoir inclure une FK vers la `Source` documentaire de l'accréditation (`accreditation_source_id`).

#### Domaine `Offer` (entité nouvelle)

- **FR-022** : Le système DOIT créer une nouvelle table `offers` représentant chaque couple (Fonds, Intermédiaire) commercialisable à une PME.
- **FR-023** : Chaque offre DOIT avoir un `name` lisible (200 caractères max) ex : « GCF via BOAD - Mitigation Afrique Ouest ».
- **FR-024** : Chaque offre DOIT spécifier les langues acceptées du dossier (`accepted_languages` JSONB array, default `["FR"]`).
- **FR-025** : Chaque offre DOIT pouvoir restreindre les secteurs cibles (`target_sector` JSONB) à un sous-ensemble des secteurs du fonds parent.
- **FR-026** : Chaque offre DOIT contenir les critères effectifs (`effective_criteria` JSONB) résultant de l'intersection des critères du fonds et de l'intermédiaire (avec règle « le plus restrictif gagne »).
- **FR-027** : Chaque offre DOIT contenir les documents requis effectifs (`effective_required_documents` JSONB) résultant de l'union dédupliquée par `(title, source_id)` des documents fonds et intermédiaire.
- **FR-028** : Chaque offre DOIT contenir les frais effectifs (`effective_fees` JSONB) résultant de la somme cumulée des frais Money typed.
- **FR-029** : Chaque offre DOIT contenir les délais de traitement et décaissement effectifs (`effective_processing_time_days_min/max`, `effective_disbursement_time_days_min/max`) résultant de la somme des délais fonds + intermédiaire.
- **FR-030** : Chaque offre DOIT supporter `is_active` (bool), `publication_status` (`draft|published`), `version`/`valid_from`/`valid_to` (F04), `notes` (text admin), `source_id` (F01).
- **FR-031** : Le système DOIT garantir l'unicité du couple `(fund_id, intermediary_id, version)` via un index unique.
- **FR-032** : Le système DOIT empêcher la publication d'une offre si `fund.publication_status != 'published'` OU `intermediary.publication_status != 'published'` OU `fund_intermediary.accredited_to <= today`.
- **FR-033** : Le système DOIT empêcher la publication d'une offre si la `Source` liée n'est pas en statut `verified` (workflow 4-yeux F01).

#### Service de calcul automatique `compute_effective_offer`

- **FR-034** : Le système DOIT exposer une fonction `compute_effective_offer(fund_id, intermediary_id) → OfferDraft` accessible depuis le module `app/modules/offers/calculator.py`.
- **FR-035** : Le calculator DOIT charger le fonds et l'intermédiaire via leurs `id` et lever 404 s'ils n'existent pas.
- **FR-036** : Le calculator DOIT lever 422 si la paire `(fund_id, intermediary_id)` n'existe pas dans `fund_intermediaries` (sauf cas de l'intermédiaire DIRECT pour les fonds `access_type='direct'`).
- **FR-037** : Le calculator DOIT calculer `effective_criteria` comme intersection des critères du fonds et de l'intermédiaire avec règle « le plus restrictif gagne » sur les valeurs numériques.
- **FR-038** : Le calculator DOIT calculer `effective_required_documents` comme union des documents avec déduplication exacte sur `(title.lower().strip(), source_id)` ; sur les doublons résiduels, `mandatory=true` écrase `mandatory=false`.
- **FR-039** : Le calculator DOIT calculer `effective_fees` comme somme cumulée Money typed (conversion XOF si devises différentes via `app.modules.currency`).
- **FR-040** : Le calculator DOIT calculer `effective_processing_time_days_min/max` et `effective_disbursement_time_days_min/max` comme somme des délais fonds (convertis depuis `typical_timeline_months × 30`) et intermédiaire.
- **FR-041** : Le calculator DOIT inférer un `accepted_languages_hint` basé sur `intermediary.country` (anglophone → `["EN"]`, autre → `["FR"]`).
- **FR-042** : Le calculator DOIT signaler les incohérences détectées (ex : `fund.min_amount > intermediary.max_amount_per_fund`) dans le champ `notes` du draft retourné.
- **FR-043** : Le calculator DOIT être stateless et ne JAMAIS persister directement en base ; il retourne un `OfferDraft` Pydantic que l'admin valide via `POST /api/admin/offers`.

#### Refactor `FundApplication` vers `offer_id`

- **FR-044** : Le système DOIT ajouter une colonne `offer_id` (UUID FK `offers.id`) sur la table `fund_applications`, NULL transitoirement.
- **FR-045** : La migration DOIT exécuter un backfill liant chaque `FundApplication` existante à l'`Offer` correspondante via `(fund_id, intermediary_id)` ou `(fund_id, DIRECT)` si `intermediary_id IS NULL`.
- **FR-046** : Après le backfill, le système DOIT faire passer `fund_applications.offer_id` à `NOT NULL` (post-migration via `op.alter_column`).
- **FR-047** : Les colonnes existantes `fund_applications.fund_id` et `fund_applications.intermediary_id` DOIVENT être conservées (deprecated, marquées dans le code) pour compatibilité descendante 2 sprints.

#### API REST `/api/offers` et `/api/admin/offers`

- **FR-048** : Le système DOIT exposer `GET /api/offers` (public ou PME authentifiée) avec filtres `fund_id`, `intermediary_id`, `theme`, `instrument`, `country`, `language`, et tri par `success_rate` ou `effective_processing_time_days_min`. Pagination via `limit/offset` (max 100/req).
- **FR-049** : Le système DOIT filtrer strictement par `publication_status='published' AND is_active=true` sur `GET /api/offers`.
- **FR-050** : Le système DOIT exposer `GET /api/offers/{id}` retournant le détail complet d'une offre (fund, intermediary, effective_*, source_id sourcés).
- **FR-051** : Le système DOIT exposer `GET /api/offers/comparator?fund_id=X` retournant toutes les offres publiées pour ce fonds avec scoring décomposé et données comparables côte-à-côte.
- **FR-052** : Le système DOIT exposer `POST /api/admin/offers` (admin only) pour créer une offre depuis un draft édité.
- **FR-053** : Le système DOIT exposer `PATCH /api/admin/offers/{id}` (admin only) pour éditer une offre existante (transitions `draft→published`, etc.).
- **FR-054** : Le système DOIT exposer `POST /api/admin/offers/compute?fund_id=X&intermediary_id=Y` (admin only) retournant un `OfferDraft` calculé sans persistance.
- **FR-055** : Le système DOIT exposer `GET /api/admin/offers?include_drafts=true` (admin only) listant toutes les offres y compris drafts.

#### Tools LangChain

- **FR-056** : Le système DOIT exposer un tool LangChain `list_offers(filters: dict) → list[OfferSummary]` accessible depuis les nœuds `chat` et `financing` du graphe.
- **FR-057** : Le système DOIT exposer un tool LangChain `get_offer(offer_id: str) → Offer` retournant le détail d'une offre.
- **FR-058** : Le système DOIT exposer un tool LangChain `compare_offers_for_fund(fund_id: str) → list[OfferComparison]`.
- **FR-059** : Le système DOIT mettre à jour le tool LangChain `create_fund_application` pour accepter `offer_id` et `project_id` (préparer F15) en plus du couple `(fund_id, intermediary_id)` legacy (acceptés en parallèle 2 sprints).

#### Frontend (pages et composants)

- **FR-060** : Le système DOIT exposer une page `/financing/offers/[offer_id]` affichant le détail d'une offre avec : header (nom, score compatibilité, badge langue, badge mode soumission), section « Fonds source » cliquable, section « Intermédiaire » cliquable, section « Critères effectifs » (avec sources cliquables F01), section « Documents requis » (avec sources F01), section « Frais effectifs » (Money typed F04), section « Délais effectifs », bouton « Comparer avec autres offres pour ce fonds », bouton « Candidater » (préparation F15).
- **FR-061** : Le système DOIT exposer une page `/financing/funds/[fund_id]` affichant le détail d'un fonds avec liste des offres associées.
- **FR-062** : Le système DOIT exposer une page `/financing/intermediaries/[intermediary_id]` affichant le détail d'un intermédiaire avec liste des offres associées.
- **FR-063** : La page `/financing/index.vue` DOIT être étendue pour, lorsque le feature flag `USE_OFFER_VIEW=true` est actif, afficher des Cards Offres (composant `OfferCard.vue`) avec score décomposé, badge langue, frais effectifs, délais effectifs ; sinon, conserver la vue actuelle Cards Fonds.
- **FR-064** : Le système DOIT créer 8 composants Vue dans `frontend/app/components/financing/` : `OfferCard.vue`, `FundCard.vue`, `IntermediaryCard.vue`, `OfferDetail.vue`, `EffectiveCriteriaList.vue`, `EffectiveDocumentsList.vue`, `EffectiveFees.vue`, `SubmissionModeBadge.vue`.
- **FR-065** : Tous les nouveaux composants Vue DOIVENT supporter le dark mode (variantes Tailwind `dark:` sur fonds, textes, bordures, hover, inputs) conformément à `CLAUDE.md` invariant.
- **FR-066** : Tous les nouveaux composants Vue DOIVENT être accessibles : navigation clavier (Tab, Enter, Esc), `aria-label` sur boutons icônes, rôles ARIA appropriés (`button`, `link`, `list`).
- **FR-067** : Le composable `useFinancing.ts` DOIT être étendu avec les méthodes `listOffers(filters)`, `getOffer(id)`, `compareOffersForFund(fundId)`.
- **FR-068** : Le store Pinia `financing.ts` DOIT être étendu avec un état `offers`, des actions de fetch, et un getter `offersForFund(fundId)`.

#### Cron quotidien d'expiration des accréditations

- **FR-069** : Le système DOIT fournir un script cron `backend/scripts/check_expired_accreditations.py` parcourant les `FundIntermediary` avec `accredited_to < today` et désactivant les offres correspondantes (`is_active=false`, `publication_status='draft'`).
- **FR-070** : Le cron DOIT être idempotent (2 exécutions consécutives n'ont d'effet qu'une fois).
- **FR-071** : Le cron DOIT journaliser chaque désactivation dans `audit_log` (F03) avec `entity_type='offer'`, `action='auto_unpublished_accreditation_expired'`, `metadata={accreditation_source_id, accredited_to}`.

#### Multi-tenant et sécurité

- **FR-072** : Les tables `funds`, `intermediaries`, `fund_intermediaries`, `offers` sont **catalogue global** : pas de filtre RLS PostgreSQL par `account_id`. Conformément à F02 invariant n°7, ces tables sont mutables uniquement par les admins (helper `is_admin` requis sur tous les endpoints `/api/admin/...`).
- **FR-073** : Aucun tool LangChain (`list_offers`, `get_offer`, `compare_offers_for_fund`) ne DOIT pouvoir muter les tables catalogue (read-only).
- **FR-074** : La table `fund_applications` (par contre) reste multi-tenant via `account_id` (F02) ; toute mutation est tracée par le mixin `Auditable` (F03).

### Key Entities *(include if feature involves data)*

- **Fund (enrichi)** : un fonds vert listé au catalogue Mefali. Identifié par `id` (UUID). Inclut désormais : `instruments` (JSONB array d'instruments financiers), `theme` (JSONB array de thèmes climat), `submission_mode` (rolling|call_for_proposals), `submission_calendar` (JSONB), `source_id` (FK `sources.id` F01), versioning F04 (`version`, `valid_from`, `valid_to`, `superseded_by`), `publication_status` (draft|published), Money typed (`min_amount + currency`, `max_amount + currency`), enum `fund_type` renommé. Catalogue global (pas d'`account_id`).
- **Intermediary (enrichi)** : un intermédiaire accrédité. Identifié par `id` (UUID). Inclut désormais : `required_documents` (JSONB array d'objets), `fees_structured` (JSONB), `processing_time_days_min/max`, `disbursement_time_days_min/max`, `submission_portal_url`, `success_rate` (Numeric 5,4), `total_funded_volume_amount + currency` (Money typed), `source_id` (FK `sources.id`), versioning F04, `publication_status`. Inclut un singleton `code='DIRECT'` représentant les fonds sans intermédiaire. Catalogue global.
- **FundIntermediary (enrichi)** : la relation N-N entre fonds et intermédiaires. Identifiée par `id` (UUID). Inclut désormais : `accredited_from` (date NOT NULL), `accredited_to` (date NULL), `max_amount_per_fund_amount + currency` (Money typed nullable), `accreditation_source_id` (FK `sources.id`).
- **Offer (nouvelle)** : un couple Fonds × Intermédiaire commercialisable à une PME. Identifiée par `id` (UUID). Champs : `fund_id` (FK), `intermediary_id` (FK), `name` (str 200), `accepted_languages` (JSONB array de codes ISO 639-1, default `["FR"]`), `target_sector` (JSONB), `effective_criteria` (JSONB), `effective_required_documents` (JSONB), `effective_fees` (JSONB), `effective_processing_time_days_min/max`, `effective_disbursement_time_days_min/max`, `notes` (text), `is_active` (bool), `publication_status` (draft|published), versioning F04, `source_id` (FK). Index unique `(fund_id, intermediary_id, version)`. Catalogue global.
- **OfferDraft** : structure Pydantic retournée par `compute_effective_offer` (pas persistée). Reflète le contenu d'une `Offer` à créer + un champ `accepted_languages_hint` et `notes` enrichis par les avertissements détectés.
- **FundApplication (refactoré)** : la candidature d'une PME. Identifiée par `id` (UUID). Inclut désormais : `offer_id` (FK `offers.id`, transitoirement NULL puis NOT NULL post-backfill). Conserve `fund_id` et `intermediary_id` deprecated 2 sprints. Reste multi-tenant via `account_id` (F02), Auditable (F03).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Une PME peut comparer côte-à-côte au moins 2 offres distinctes pour un même fonds (ex : GCF via BOAD vs GCF via UNDP) en moins de 10 secondes (chargement page + rendu comparateur).
- **SC-002** : Le calcul `compute_effective_offer` s'exécute en moins de 500 ms p95 sur un fonds avec ≤ 20 critères, ≤ 10 documents, ≤ 5 lignes de frais structurés.
- **SC-003** : 100 % des `FundApplication` existantes sont liées à une `Offer` après backfill (`SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL` retourne 0).
- **SC-004** : Migration Alembic `028` réversible : `up → down → up` sans erreur ni perte de données ; tested in CI.
- **SC-005** : 90 % des admins peuvent créer une nouvelle offre (depuis le calcul auto + édition + publication) en moins de 5 minutes après formation initiale.
- **SC-006** : 0 offre publiée avec une accréditation expirée à un instant donné (cron quotidien garantit la cohérence sous 24h).
- **SC-007** : 0 fuite de drafts côté API publique : test de sécurité automatisé dans pytest qui appelle `GET /api/offers` avec 1 offre published + 5 drafts seedées et assert que seul 1 résultat est retourné.
- **SC-008** : Couverture tests backend ≥ 80 % sur les modules `app/modules/offers/`, `app/models/financing.py` (parties enrichies), `app/graph/tools/financing_tools.py`.
- **SC-009** : Couverture tests frontend ≥ 80 % sur les composants `OfferCard`, `OfferDetail`, `EffectiveCriteriaList`, `EffectiveDocumentsList`, `EffectiveFees`, `SubmissionModeBadge`.
- **SC-010** : 4 tests E2E Playwright passent en CI : (a) admin crée offre → calcul auto → publication ; (b) PME consulte 2 offres GCF (BOAD + UNDP) et les compare côte-à-côte ; (c) PME tente d'accéder à `/api/admin/offers?include_drafts=true` → 403 ; (d) cron expiration désactive offre → invisible côté PME.

## Assumptions

- L'environnement F01 (sources catalogue), F02 (multi-tenant + roles), F04 (versioning + Money), F06 (entité Project) est livré et mergé sur main avant le démarrage de F07. Ces dépendances sont confirmées présentes dans la base actuelle (migrations 020, 019, 022, 025).
- Les 12 fonds et 14 intermédiaires actuellement seedés (issus de F08) seront tous re-validés par l'admin après backfill avant publication des offres correspondantes (donc `is_active=false, publication_status='draft'` au backfill est acceptable).
- La conversion devises pour `effective_fees` repose sur le module `app/modules/currency` (livré avec F04) ; aucune nouvelle intégration externe n'est nécessaire.
- Les `accepted_languages` se limitent à FR et EN pour le MVP F07. Les langues additionnelles (PT, AR) sont post-MVP.
- Le feature flag `USE_OFFER_VIEW` reste `false` par défaut en production MVP F07 ; la bascule effective vers la vue Offres est une décision métier post-F14 (matching offre).
- Aucune migration de données externe n'est requise (pas d'import depuis un système legacy externe).
- Le scoring décomposé `fund_score` / `intermediary_score` affiché sur les Cards Offres est calculé côté frontend à partir des données de l'offre (pour le MVP F07) ; le scoring backend complet est livré avec F14.
- Les performances p95 cible reposent sur PostgreSQL 16 avec ≤ 100 offres publiées, indexes appropriés, et async asyncpg.
- Le cron quotidien `check_expired_accreditations.py` est exécuté manuellement ou via un orchestrateur externe (Cron système ou GitHub Actions scheduled) — pas d'intégration runtime FastAPI dans cette feature ; F19 introduira un cron dispatcher dédié post-MVP.
- L'intermédiaire singleton `DIRECT` est créé une seule fois lors de la migration `028` ; il n'a pas vocation à être édité ou supprimé.
- L'admin Mefali (rôle F02 `admin`) existe déjà et est ré-utilisé tel quel pour autoriser les endpoints `/api/admin/offers/*`.

## Dependencies

- **F01 (Sources catalogue)** : `verified` requis pour publication d'offres ; FK `source_id` sur `funds`, `intermediaries`, `fund_intermediaries.accreditation_source_id`, `offers.source_id`.
- **F02 (Multi-tenant + roles)** : helper `is_admin` requis sur endpoints admin ; pas de filtre RLS sur tables catalogue.
- **F03 (Audit log append-only)** : journalisation des mutations sur `offers`, `funds` (champs enrichis), `intermediaries` (champs enrichis), `fund_intermediaries` (champs enrichis) — rappel `Fund/Intermediary/FundIntermediary` sont actuellement EXEMPT du mixin `Auditable` (catalogue admin only) ; cette policy est conservée. Pour `offers`, décision : EXEMPT également (catalogue admin), mais le cron `check_expired_accreditations.py` journalise explicitement via `app/core/audit_context` un événement `auto_unpublished_accreditation_expired`.
- **F04 (Versioning + Money typed)** : `VersioningMixin` réutilisé sur `offers` ; Money typed sur `funds.min_amount`, `funds.max_amount`, `intermediaries.fees_structured.doc_fee_amount`, `intermediaries.total_funded_volume`, `fund_intermediaries.max_amount_per_fund`, `offers.effective_fees.total_min/max`.
- **F06 (Entité Projet vert)** : `FundApplication.project_id` déjà présent ; F07 ne le modifie pas, mais le tool LangChain `create_fund_application` est étendu pour accepter `offer_id` ET `project_id`.
