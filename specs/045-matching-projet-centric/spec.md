# Feature Specification: Matching financement vert centré projet (et non plus entreprise)

**Feature Branch**: `045-matching-projet-centric`
**Created**: 2026-05-21
**Status**: Draft
**Input**: User description: « Le projet doit devenir l'unité de matching, et l'éligibilité doit être calculée d'abord sur les attributs du projet — secteur, impact CO2 attendu, alignement taxonomie verte UEMOA, montant cible, calendrier, bénéficiaires — puis enrichie (et non plus dominée) par le profil entreprise. »

## Contexte et problème métier

Aujourd'hui, le matching `/financing` (F08 + F14 livré au commit `c9204c8`) compare une **PME** (secteur, CA, pays, score ESG entreprise, documents disponibles) à des **offres** = (fonds × intermédiaire). Le pilier ESG du score (pondération MVP F14 : `esg=0.30`) est celui de l'**évaluation entreprise** (`ESGAssessment`), pas du projet. Conséquence métier observée :

- Une PME du secteur informel ou avec un score ESG entreprise « rouge » est de facto écartée de fonds qui priorisent l'**impact du projet** (GCF, FEM, Fonds d'Adaptation), alors même qu'elle porte un projet de reforestation, de mini-grid solaire ou de mobilité électrique parfaitement éligible.
- Symétriquement, une entreprise « verte » bien notée peut soumettre un projet sans pertinence climatique et apparaître en tête des matches.

L'unité d'éligibilité réelle pour les fonds verts est le **projet**, pas la santé financière du porteur. Cette feature recentre le scoring sur les attributs du projet (impact CO2 attendu, alignement taxonomie verte UEMOA, thèmes prioritaires GCF, bénéficiaires, inclusion genre, populations vulnérables, score ESG projet) et présente le score entreprise séparément, sans l'utiliser comme goulot d'étranglement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — PME profil incomplet, projet vert ambitieux (Priority: P1)

Une coopérative agricole informelle au Togo, sans bilan ESG entreprise finalisé, démarre un projet d'**agroforesterie 200 ha** avec impact CO2 estimé `2 400 tCO2e/an`, alignement taxonomie verte UEMOA et bénéfices pour 850 femmes rurales. Elle ouvre une conversation avec l'agent et demande « quels fonds peuvent financer mon projet ? ».

**Why this priority** : c'est le cas d'usage central qui justifie la feature. Sans cette user story, la feature n'a pas de raison d'être. Si on ne livre que cette story, on a déjà un MVP qui débloque l'inclusion financière de centaines de PME informelles.

**Independent Test** : Créer un compte PME sans `ESGAssessment`, créer un projet avec les 4 attributs critiques (CO2 estimé, taxonomie UEMOA alignée, bénéficiaires renseignés, secteur agroforesterie), déclencher le matching et vérifier que la liste de fonds compatibles n'est pas vide et inclut au moins GCF, FEM et Fonds d'Adaptation.

**Acceptance Scenarios** :

1. **Given** une PME sans `ESGAssessment` finalisée (score entreprise indéterminé) et un projet vert avec `expected_impact_tco2e ≥ 1000`, `taxonomie_verte_uemoa_aligned=true` et au moins un thème prioritaire GCF renseigné, **When** la PME demande à l'agent « quels fonds peuvent financer ce projet ? », **Then** le système renvoie au minimum 3 fonds (incluant GCF, FEM, Fonds d'Adaptation) classés par score projet décroissant, **et** chaque match affiche `project_score ≥ 60`, indépendamment du score entreprise.
2. **Given** la même PME et le même projet, **When** elle ouvre la fiche d'un match (par exemple « GCF via BOAD »), **Then** elle voit deux scores séparés (« Match projet : X% » et « Match entreprise : Y% »), une mention claire qui explique que le score projet est celui qui pilote l'éligibilité, et la liste des critères projet manquants avec leur source (F01).

---

### User Story 2 — Pilotage du cycle de vie projet en chat (Priority: P1)

Une PME démarre sans projet en BDD. En une seule conversation, elle décrit son idée, saisit progressivement les champs critiques via widgets interactifs (F18), déclenche le matching, modifie un champ après avoir vu les résultats, relance le matching et compare avec la nouvelle liste — sans jamais quitter le chat pour aller remplir un formulaire.

**Why this priority** : c'est l'objectif différenciant vs F14. F14 a câblé le calcul mais l'UX reste form-driven (création projet dans `/profile/projects/new`, matching ailleurs). L'agent conversationnel doit boucler la boucle pour les PME africaines qui préfèrent un flux dialogué.

**Independent Test** : Démarrer une nouvelle conversation, sans projet en BDD pour la PME. Vérifier que l'agent peut (a) créer un projet via tool `create_project`, (b) lancer le matching via tool `match_funds_for_project`, (c) modifier un champ via tool `update_project`, (d) relancer le matching, (e) afficher la nouvelle liste en `MatchCardBlock` — le tout dans la même conversation, sans handover UI.

**Acceptance Scenarios** :

1. **Given** une conversation vide et un compte PME sans projet, **When** la PME décrit son projet en langage naturel (« je veux installer 50 panneaux solaires dans mon village »), **Then** l'agent collecte progressivement les champs via widgets interactifs F18 (qcu/qcm/justification) puis appelle `create_project` et confirme la création.
2. **Given** un projet créé en chat, **When** la PME demande « lance le matching », **Then** l'agent appelle `match_funds_for_project(project_id)`, attend la réponse, et émet jusqu'à 5 `<MatchCardBlock>` F11 (un par offre top-N) avec ancrage `SourceLink` F01 pour chaque critère projet mobilisé.
3. **Given** la liste de matches affichée, **When** la PME dit « augmente mon impact CO2 à 5 000 tCO2e/an », **Then** l'agent appelle `update_project(project_id, expected_impact_tco2e=5000)`, **puis** relance automatiquement le matching projet et affiche la nouvelle liste mise à jour — le tout dans le même tour de conversation.

---

### User Story 3 — Filtrage des projets sans pertinence climatique (Priority: P2)

Une PME crée un projet sans aucun attribut vert (négoce de produits manufacturés, pas d'impact CO2 estimé, taxonomie UEMOA non alignée, aucun thème GCF). Le matching projet doit renvoyer une liste vide ou quasi-vide avec une **explication métier** claire, plutôt que de retourner les fonds génériques ou de propager le score entreprise comme proxy.

**Why this priority** : protège la cohérence métier de la feature. Sans cette story, on ne distingue pas l'impact de la feature vs F14 (le système renverrait des matches creux). Mais c'est un comportement défensif, pas un débouché commercial direct.

**Independent Test** : Créer un projet avec `expected_impact_tco2e=NULL`, `taxonomie_verte_uemoa_aligned=false`, `objective_env=[]` ou non vert. Lancer le matching et vérifier que la réponse contient soit une liste vide, soit une explication structurée des thèmes à renforcer.

**Acceptance Scenarios** :

1. **Given** un projet sans alignement climatique (taxonomie UEMOA `false`, aucun thème GCF, impact CO2 nul ou non renseigné), **When** la PME lance le matching, **Then** la réponse retourne une liste vide **et** une explication structurée : « Aucun fonds n'aligne ses critères avec ce projet. Pour augmenter votre éligibilité, renseignez les thèmes suivants : [liste de 2-3 thèmes prioritaires manquants avec leur source F01] ».
2. **Given** un projet partiellement vert (taxonomie UEMOA alignée mais sans impact CO2 chiffré), **When** le matching est lancé, **Then** la liste n'est pas vide mais chaque match affiche un badge « Score projet incomplet — chiffrez votre impact CO2 pour améliorer le matching » avec le critère manquant cliquable.

---

### User Story 4 — Double score séparé avec explication de divergence (Priority: P2)

L'utilisateur voit explicitement deux scores côte à côte (« Match projet : 78% » et « Match entreprise : 12% ») et obtient une explication métier de la divergence sans avoir besoin de creuser dans la documentation technique.

**Why this priority** : c'est le contrat de transparence avec l'utilisateur. Sans ça, la PME pourrait être confuse de voir un « bon » match alors que son score entreprise est rouge. Indispensable pour la confiance mais peut être livré après la story P1.

**Independent Test** : Sur un match donné, vérifier que la fiche affiche `project_score` et `company_score` séparés, avec une zone explicative qui décrit pourquoi les deux peuvent diverger (cas typique : « Votre projet est éligible parce qu'il aligne X critères impact ; votre entreprise reste à renforcer sur Y critères financiers et ESG »).

**Acceptance Scenarios** :

1. **Given** un match avec `project_score=78` et `company_score=12`, **When** la PME ouvre la fiche du match, **Then** elle voit deux scores séparés avec libellés explicites (« Match projet » et « Match entreprise »), un indicateur visuel (badge couleur) qui clarifie lequel pilote l'éligibilité, et un paragraphe explicatif généré côté backend (pas un freetext LLM, un texte gabarit paramétré par les divergences détectées).
2. **Given** un match où les deux scores sont alignés (écart ≤ 15 pts), **When** la PME ouvre la fiche, **Then** l'explication indique « Votre projet et votre entreprise sont alignés sur les critères de ce fonds » sans badge de divergence.

---

### User Story 5 — Section UI « Fonds compatibles avec ce projet » (Priority: P3)

Sur la fiche projet `/profile/projects/[id]`, une nouvelle section affiche le top N (5 par défaut) des fonds compatibles avec ce projet précis, indépendamment du parcours `/financing`. Permet à un utilisateur qui consulte un projet existant de voir d'un coup d'œil ses options de financement.

**Why this priority** : confort d'usage et navigation, mais le chat (story 2) et l'endpoint API (story 1) sont prioritaires. Si on doit couper, on coupe cette story sans casser le MVP.

**Independent Test** : Créer un projet, déclencher le matching, ouvrir `/profile/projects/[id]` et vérifier que la section « Fonds compatibles » s'affiche avec 5 cards max, chacune liant vers la fiche fonds.

**Acceptance Scenarios** :

1. **Given** un projet avec au moins 1 match calculé, **When** l'utilisateur ouvre la fiche projet, **Then** une section dédiée affiche les 5 meilleurs matches projet (triés par `project_score` décroissant) sous forme de `<MatchCard>` (F11) avec lien vers la fiche fonds correspondante.
2. **Given** un projet sans match, **When** l'utilisateur ouvre la fiche, **Then** un empty state explicite est affiché : « Aucun fonds ne correspond encore à ce projet. Complétez les champs suivants pour améliorer votre matching : [liste 2-3 champs critiques manquants] ».

---

### Edge Cases

- **Projet `status='draft'`** : le matching est-il déclenché avant la transition `seeking_funding` ? Décision documentée en Assumptions (matching disponible dès `draft` pour MVP).
- **Projet `status='cancelled'` ou `'closed'`** : ces statuts désactivent le matching (cohérent avec F06 — pas de matching pour un projet annulé).
- **Devises mixtes** : projet en EUR, fonds en USD. La conversion utilise `currency_service` (F04 / peg + table `exchange_rates`). Si conversion impossible, le critère `size_match` retourne `0` avec flag `factor_status='unavailable'` (et non `false` qui dégraderait silencieusement le score).
- **Source non vérifiée** : si un critère projet (ex. impact CO2 chiffré) cite une source `pending` ou `outdated`, le match est calculé mais affiche un badge « Source projet à vérifier » au lieu de bloquer.
- **Projet sans `account_id` (impossible par contrainte F02)** : refus dur côté API avec 422.
- **Tool `match_funds_for_project` appelé sur un `project_id` d'un autre compte** : refus RLS PostgreSQL silencieux (retour vide, comportement standard F02), pas de 403 explicite (évite la fuite d'information sur l'existence du projet).
- **Migration en cours** : si la migration des nouveaux champs projet n'est pas encore appliquée, le matching projet refuse de tourner et l'API retourne `503 Service Unavailable` avec un message clair plutôt qu'un score erroné.
- **Recalcul en cascade** : si une PME modifie en chat 5 champs projet en moins d'1 minute, le système doit dédupliquer les déclenchements (debounce 30s côté event listener) pour ne pas générer 5 recalculs successifs.

## Clarifications

### Session 2026-05-21

- **Q1 — Pondération projet vs entreprise** : **(C) Double score persisté sans agrégation**. `project_score` et `company_score` sont calculés et stockés séparément en BDD, affichés côte à côte dans l'UI (« Match projet : X% / Match entreprise : Y% ») sans formule de fusion cachée. Le tri par défaut des matches utilise `project_score DESC`. Pas de constante d'agrégation, pas de table `matching_weights`. Le score entreprise reste informatif et n'agit jamais comme bottleneck.
- **Q2 — Persistance du matching projet** : **(A) Enrichir `offer_matches` F14**. La migration 045 ajoute `project_score INT NOT NULL CHECK 0..100`, `company_score INT NOT NULL CHECK 0..100`, `project_score_breakdown JSONB NOT NULL DEFAULT '{}'`, `divergence_explanation TEXT NULL` à la table existante `offer_matches` (créée par F14). Réutilise UNIQUE `(project_id, offer_id)`, RLS F02, audit F03 déjà câblés. Pas de nouvelle table, pas de doublon. Le champ `global_score` F14 devient déprécié (conservé 2 sprints en lecture seule, remplacé par `project_score` pour le tri).
- **Q3 — Champs projet à ajouter en migration** : **(A) 5 champs candidats tels quels**. La migration 045 ajoute à `projects` :
  - `taxonomie_verte_uemoa_aligned BOOLEAN NULL` (NULL = pas encore évalué, true/false explicite après évaluation, source F01 obligatoire si true)
  - `gcf_priority_themes JSONB NOT NULL DEFAULT '[]'` (array de Literal FR : atténuation, adaptation, cross_cutting, REDD+, forêts, eau, agriculture, énergie — whitelist applicative + check côté Pydantic)
  - `gender_inclusion BOOLEAN NULL` (NULL = non évalué, true/false après évaluation, source F01 si true)
  - `vulnerable_populations JSONB NOT NULL DEFAULT '[]'` (array de Literal FR : femmes, jeunes, handicapés, réfugiés, déplacés_internes — whitelist applicative)
  - `project_esg_score INTEGER NULL CHECK 0..100` (saisi manuellement par la PME, distinct du score entreprise F13)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** : Le système DOIT exposer un endpoint `POST /api/projects/{project_id}/match-funds` qui calcule (ou récupère du cache) la liste des fonds compatibles **avec le projet précis**, indépendamment du score entreprise.
- **FR-002** : Le système DOIT calculer `project_score INT 0..100` et `company_score INT 0..100`, **persistés séparément** dans `offer_matches` (colonnes dédiées NOT NULL), sans formule d'agrégation. Le tri par défaut des listes de matches utilise `project_score DESC, company_score DESC` (project prioritaire, company en tie-break).
- **FR-003** : Le système DOIT garantir qu'une PME avec score entreprise indéterminé ou < 30 obtient une liste de matches **non vide** si son projet aligne les 3 critères projet minimums (taxonomie UEMOA, impact CO2 chiffré, secteur compatible).
- **FR-004** : Le système DOIT ajouter à la table `projects` via migration Alembic 045 les 5 champs suivants — `taxonomie_verte_uemoa_aligned BOOLEAN NULL`, `gcf_priority_themes JSONB NOT NULL DEFAULT '[]'`, `gender_inclusion BOOLEAN NULL`, `vulnerable_populations JSONB NOT NULL DEFAULT '[]'`, `project_esg_score INTEGER NULL CHECK 0..100` — avec round-trip up/down/up validé sur PostgreSQL et whitelists Pydantic v2 strict côté schema. La même migration ajoute à `offer_matches` les colonnes `project_score INTEGER NOT NULL DEFAULT 0 CHECK 0..100`, `company_score INTEGER NOT NULL DEFAULT 0 CHECK 0..100`, `project_score_breakdown JSONB NOT NULL DEFAULT '{}'`, `divergence_explanation TEXT NULL` ; le champ `global_score` existant est conservé en lecture seule (déprécié) pour 2 sprints.
- **FR-005** : Le système DOIT calculer chaque critère projet (taxonomie UEMOA, thèmes GCF, impact CO2 vs seuils GCF, bénéficiaires, gender, vulnerable) en s'appuyant **uniquement** sur des sources F01 verified — le validator `source_required.py` DOIT bloquer toute valeur métier non sourcée avec retry 1× puis fallback texte.
- **FR-006** : Le système DOIT exposer un tool LangChain `match_funds_for_project(project_id, min_score=60, limit=10)` qui retourne JSON compact et émet jusqu'à 5 blocs visualisation F11 de type **`match_card_project`** (nouveau schema `MatchCardProjectBlockSchema`, distinct du `match_card` F14 — cf. contracts/tool-match-funds-for-project.md §3.2) via marker SSE `__sse_visualization_block__`. Le frontend route ce nouveau `block_type` vers le composant `<ProjectMatchCardBlock>`.
- **FR-007** : Le système DOIT garantir que les tools `create_project`, `update_project`, `delete_project`, `list_projects`, `get_project`, `duplicate_project`, `link_document_to_project` (F06 — déjà présents dans `app/graph/tools/project_tools.py`) restent disponibles dans le slug chat et `profile_projects`, **plus** le nouveau tool `match_funds_for_project`.
- **FR-008** : Le système DOIT déclencher automatiquement un recalcul des matches projet quand un champ critique du projet est modifié (event listener `after_update` SQLAlchemy avec debounce 30s pour éviter les cascades). Les champs critiques sont : `sector`, `target_amount_amount`, `target_amount_currency`, `objective_env`, `expected_impact_tco2e`, `expected_beneficiaries`, et les nouveaux champs Q3.
- **FR-009** : Le système DOIT permettre à l'utilisateur de déclencher un recalcul on-demand via tool LLM (`recompute_matches_for_project` — déjà F14) ou via bouton UI sur la fiche projet.
- **FR-010** : Le système DOIT persister le breakdown du score projet en JSONB structuré dans `offer_matches.project_score_breakdown` : `{ weights_version: str, sub_scores: { sector: int, taxonomy: int, gcf_themes: int, co2_impact: int, beneficiaries: int, gender: int, vulnerable: int, project_esg: int }, sources_used: [{ sub_score, source_id, source_name, url }], missing_criteria: [{ key, label_fr, source_id, kind, current_value, target_value }] (max 5), boost_applied: { rule_triggered: bool, rule_name: str|null }, factor_status: 'ok'|'sources_pending'|'unsourced_fallback', computed_at: ISO8601 }`. Le champ `divergence_explanation` est persisté **séparément** en colonne TEXT dans `offer_matches` (cf. FR-004), pas dans le breakdown JSONB. Le breakdown entreprise héritage F14 reste dans `offer_matches.score_breakdown` existant.
- **FR-011** : Le système DOIT respecter le multi-tenant F02 — la table de matches DOIT avoir `account_id NOT NULL` (déjà acquis si on enrichit `offer_matches` F14) et les policies RLS PME/ADMIN cohérentes.
- **FR-012** : Le système DOIT auditer (F03) toute mutation des champs projet critiques (les nouveaux + ceux existants déjà couverts par F03), avec `source_of_change` correct (manual/llm/import) selon le déclencheur.
- **FR-013** : Le système DOIT afficher dans la fiche match (`/financing/offers/[offer_id]`) deux scores séparés (« Match projet » / « Match entreprise ») avec un paragraphe gabarit (pas freetext LLM) d'explication de divergence quand l'écart entre les deux dépasse 30 points.
- **FR-014** : Le système DOIT afficher sur `/profile/projects/[id]` une section « Fonds compatibles avec ce projet » listant le top 5 des matches projet, avec lien vers chaque fiche offre.
- **FR-015** : Le système DOIT créer un skill F23 `skill_match_project_funds` (status `draft` puis `published` après éval ≥ 90 %) avec golden examples couvrant les 4 user stories P1+P2, et une activation rule qui le déclenche dès que la PME mentionne « financement », « fonds », « bailleur » ou « matching » — **sans exiger qu'un projet existe déjà** (`requires_active_project: false`), afin que le skill puisse aussi guider la création projet depuis zéro (cf. US2).
- **FR-016** : Le système DOIT supporter le dark mode complet sur tous les nouveaux composants Vue (`<ProjectMatchCard>`, `<DualScoreDisplay>`, `<MissingProjectCriteriaList>` éventuels).
- **FR-017** : Le système DOIT respecter le francophone-first : chaque champ enum projet (`gcf_priority_themes`, `vulnerable_populations`) DOIT avoir des libellés FR avec accents é è ê à ç côté UI, et les arguments tools typés `Literal[...]` DOIVENT documenter ces libellés.
- **FR-018** : Le système DOIT atteindre une couverture de tests ≥ 80 % sur les nouveaux modules backend (service de scoring projet, tool, endpoint, migration) et frontend (composables, store, composants).
- **FR-019** : Le système DOIT inclure une E2E Playwright pour le parcours critique : « création projet en chat → matching → ouverture fiche fonds → comparaison avec un autre fonds via F14 ».
- **FR-020** : Le système DOIT garantir que les anciens endpoints F08 et F14 (`get_fund_matches` entreprise, `list_matches_for_project` F14) restent fonctionnels en parallèle, sans rupture, pendant au moins 2 sprints (cohabitation contrôlée).

### Key Entities

- **Project (étendu F06)** : entité projet vert d'une PME. Reçoit en cette feature 5 nouveaux champs qui capturent l'alignement climatique fin : `taxonomie_verte_uemoa_aligned` (alignement taxonomie verte UEMOA/BCEAO), `gcf_priority_themes` (thèmes prioritaires GCF — atténuation, adaptation, cross-cutting, etc.), `gender_inclusion` (politique genre GCF 2019), `vulnerable_populations` (populations cibles), `project_esg_score` (score ESG propre au projet, saisi manuel, distinct du score entreprise F13). Lifecycle inchangé (draft → seeking_funding → funded → in_execution → closed/cancelled). Mixin `Auditable` F03 déjà actif sur tous les nouveaux champs.
- **OfferMatch (enrichi F14)** : entité de matching persistée — table `offer_matches` créée par F14, enrichie par la migration 045 avec `project_score`, `company_score`, `project_score_breakdown JSONB`, `divergence_explanation TEXT`. Le champ `global_score` est conservé déprécié 2 sprints (lecture seule, remplacé par `project_score` pour le tri). Conserve l'UNIQUE `(project_id, offer_id)`, le TTL 30 jours, le RLS F02 et l'audit F03.
- **MatchingCriterionSource** : association critère projet ↔ source F01 verified. Pas une nouvelle table — référence cross via `source_id` dans le breakdown JSONB. Le validator `source_required.py` F01 (déjà en place) garantit qu'aucun critère projet n'apparaît sans source.
- **Skill `skill_match_project_funds` (F23)** : playbook conversationnel nouveau. Tools whitelistés : les 8 tools projet + `match_funds_for_project` + tools sourçage F01 + visualisation F11. Golden examples : 4 conversations types (PME informelle + projet agroforesterie, PME bien notée + projet non vert, PME en draft, PME en chat continu avec recalcul).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des matches projet affichent `project_score` et `company_score` séparés et persistés ; aucun affichage agrégé caché par défaut (vérifié par test snapshot sur le payload API).
- **SC-002** : Pour une PME avec score entreprise indéterminé ou < 30 et un projet alignant 3 critères projet minimums, la liste de fonds compatibles contient au moins 3 fonds (incluant GCF, FEM, Fonds d'Adaptation) — vérifié par test d'intégration backend.
- **SC-003** : Le tool `match_funds_for_project` retourne en < 2 s pour un projet avec ≤ 50 offres publiées (pour respecter la SLA chat F12/F18 — pas d'attente perçue par l'utilisateur).
- **SC-004** : 100 % des critères projet mobilisés dans le scoring ont une source F01 verified référencée (vérifié par test conformity grep + assertion sur le breakdown JSONB).
- **SC-005** : Le parcours E2E « création projet en chat → matching → ouverture fiche fonds » s'exécute en < 90 s sur Playwright (3 tours de conversation max).
- **SC-006** : Round-trip Alembic 045 up/down/up validé sur PostgreSQL avec préservation intégrale des données existantes F06.
- **SC-007** : 0 régression sur les baselines tests backend (post-F25) et frontend (post-F25) — vérifié par CI.
- **SC-008** : Couverture de tests ≥ 80 % sur les nouveaux modules (mesurée par pytest-cov backend et @vitest/coverage-v8 frontend).
- **SC-009** : Le skill `skill_match_project_funds` atteint un score d'éval ≥ 90 % sur les 4 golden examples avant publication (F23 gating).
- **SC-010** : Aucun affichage UI nouveau sans variante `dark:` Tailwind (vérifié par grep automatisé sur les composants nouveaux).

## Assumptions

- **Cohabitation F14 préservée** : les composants F14 (`<MatchCard>`, page comparateur `/financing/compare/[fund_id]`, alertes `match_alerts_subscriptions`, cron `notify_new_offer_matches.py`) restent en place et fonctionnels. La feature 045 enrichit le breakdown mais ne casse pas les contrats existants.
- **Cas projet draft — matching autorisé** : le matching projet est disponible **dès** que le projet est en `status='draft'`, sans attendre la transition `seeking_funding`. Justification : la PME doit pouvoir explorer les fonds avant d'engager un parcours formel. Si la décision métier change, la zone grise reste ouverte à `/speckit.clarify`.
- **Recalcul — automatique + on-demand** : recalcul automatique avec debounce 30 s sur les champs critiques (FR-008), PLUS bouton on-demand UI et tool LLM `recompute_matches_for_project` (FR-009). Les deux mécanismes coexistent.
- **Sources F01 verified disponibles** : on assume que la taxonomie verte UEMOA et les thèmes prioritaires GCF (atténuation/adaptation/cross-cutting) sont déjà seedés ou seedables (sources `verified`) avant que le matching projet ne tourne en production. Si manquant, le seed est ajouté dans la même feature.
- **Pas de feature flag de bascule** : la feature remplace partiellement F14 sur l'algorithme de scoring (le pilier ESG entreprise devient pilier projet) ; un feature flag environnemental `NUXT_PUBLIC_USE_PROJECT_CENTRIC_MATCHING` peut être ajouté côté Nuxt pour permettre un rollback rapide en cas de régression UX, mais le calcul backend reste « project-centric » dès le déploiement.
- **Multi-projet non couvert** : un `fund_application` reste rattaché à 1 projet (cohérent F06 migration 025). Le multi-projet par dossier reste hors-scope (cf. brief).
- **Recalcul cap dur** : 50 offres maximum par recalcul (cohérent F14). Si la PME a 50+ offres compatibles, la pagination s'applique côté API et le matching couvre les 50 plus pertinentes triées par `(publication_date DESC, fund_type='multilateral' first)`.
- **Modèle de pondération** : Q1 résolu = (C) double score séparé. Aucune table `matching_weights` créée, aucune constante d'agrégation. Le tri reste `project_score DESC, company_score DESC`. Si plus tard l'équipe veut introduire un slider admin (option D), une nouvelle feature dédiée pourra ajouter la table versionnée F04.
- **Score projet ESG (`project_esg_score`)** : on assume MVP que ce score est saisi manuellement par la PME (champ optionnel, 0..100), pas calculé via un sous-référentiel ESG (qui serait F13 étendu projet — hors-scope MVP).
- **Pas de notification alerte nouvelle** : on s'appuie sur les alertes F14 (`match_alerts_subscriptions`) ; pas de canal alerte spécifique au matching projet en MVP.

## Hors-scope explicite

- Workflow d'édition admin du catalogue F25 (catalogue reste lecture seule).
- Soumission automatique du dossier à l'intermédiaire (F09 dossier préparation reste manuel).
- Refonte du scoring ESG entreprise (module 2 inchangé).
- Multi-projet par dossier de candidature (un `fund_application` reste rattaché à 1 projet, cf. F06 migration 025).
- ML scoring (apprentissage sur historique soumissions/acceptations) — post-MVP.
- Recommandations narratives IA personnalisées (« voici comment combler le critère taxonomie UEMOA ») — restent gabarits paramétrés, pas freetext.
- Score prédictif de probabilité d'acceptation — post-MVP.
- Email digest hebdo des nouvelles offres alignées — reste sur le canal F19/F14 in-app.
- Drop de l'ancienne logique entreprise-centric F08 — la cohabitation est explicite pour 2 sprints minimum.
- Pondération `matching_weights` modifiable par PME (admin uniquement si Q1=D).

## Dépendances et risques

### Dépendances obligatoires

- **F06 — Entité Projet Vert** (mig. 025) : modèle `Project`, service `app/modules/projects/`, 8 tools `project_tools.py` (les 7 existants + le nouveau `match_funds_for_project`).
- **F08 — Matching financement entreprise** : doit rester opérationnel en parallèle.
- **F14 — Matching projet ↔ offre** : table `offer_matches`, service `compute_offer_match`, tools `list_matches_for_project` / `compare_offers_for_fund` / `recompute_matches_for_project` / `get_match_details`. Selon Q2, on enrichit ou on duplique.
- **F07 — Offre = Fonds × Intermédiaire** : `compute_effective_offer` reste l'autorité pour les critères « le plus restrictif gagne » ; le scoring projet consomme `offer.effective_*`.
- **F01 — Sourçage obligatoire** : validator `source_required.py`, tools `cite_source` / `search_source` / `flag_unsourced`, composants `<SourceLink>` / `<SourceModal>` / `<SourceBadge>`.
- **F02 — Multi-tenant + RLS** : `account_id NOT NULL` sur toute table de matches, policies RLS PME/ADMIN.
- **F03 — Audit log** : mixin `Auditable` sur Project (déjà actif), trace des mutations critiques.
- **F04 — Money typed + versioning** : `target_amount` projet, conversion devise via `currency_service`.
- **F11 — Tools visualisation** : `<MatchCardBlock>`, `<ComparisonTableBlock>`.
- **F12 — Mémoire pgvector** : le contexte projet doit rester recall-able via `recall_history`.
- **F16 — Simulateur financement** : déjà projet-centré (`simulate_multi` par `project_id`). Le matching projet doit pouvoir feed le simulateur en amont (« voici 3 fonds compatibles, simule-les pour moi »).
- **F18 — Widgets interactifs** : `ask_interactive_question` pour collecter les champs projet manquants en chat.
- **F23 — Skills (playbooks)** : nouveau skill `skill_match_project_funds`.

### Risques identifiés

- **R1 — Divergence avec F14** : si on duplique la logique (Q2=B), risque de bugs croisés et de doublons en BDD. Atténuation : préférer enrichir `offer_matches` (Q2=A).
- **R2 — Sources manquantes** : si la taxonomie UEMOA et les thèmes GCF ne sont pas seedés `verified` avant le déploiement, le validator F01 bloquera tous les matches projet (retry → fallback texte). Atténuation : seed obligatoire dans la même feature, vérification CI conformity.
- **R3 — Confusion utilisateur** : afficher deux scores peut désorienter une PME peu mature. Atténuation : explication gabarit (pas LLM) systématique, badge couleur clair, tour guidé F31 (post-MVP).
- **R4 — Pression sur le ToolNode** : ajouter `match_funds_for_project` + le skill = +1 tool + skill activation rules. Vérifier que `MAX_TOOLS_PER_TURN` (actuel 14 — vérification à faire) tient ou bumper si besoin.
- **R5 — Performance recalcul cascade** : si la PME modifie 5 champs en chat en moins d'1 minute, sans debounce, 5 recalculs successifs (chacun ≤ 50 offres = 250 calculs). Atténuation : debounce 30 s déjà prévu en FR-008.
