# Feature Specification: Évaluation ESG-projet (extension F05 au mode projet)

**Feature Branch**: `047-evaluation-esg-projet`
**Created**: 2026-05-21
**Status**: Draft
**Input**: User description: "Feature 047 — Étendre l'évaluation ESG au niveau projet : adapter ou décliner `esg_scoring_node` pour qu'il puisse évaluer un projet vert contre IFC PS, GCF ESS ou BOAD ESS, produire un score ESG-projet calculé, un rapport ESIA-light PDF consommable par le bailleur, et remplacer le sub-score `project_esg` du matching F045 par cette évaluation. F05 entreprise reste intact."

---

## Contexte métier

ESG Mefali expose aujourd'hui deux notions ESG distinctes mais incohérentes par rapport au métier réel des bailleurs verts :

1. **`ESGAssessment` (F05)** : évaluation entreprise sur 30 critères E-S-G sectoriels, scoring automatisé via `esg_scoring_node` LangGraph, rapport PDF WeasyPrint, alimente le pilier `esg` (poids 0,30) du `company_score` du matching F14/F045. Référentiels disponibles via F13 : Mefali, GCF, IFC PS, BOAD ESS, GRI 2021.

2. **`project_esg_score` (F045)** : simple colonne `INT NULL` (0..100) sur la table `projects`, saisie manuelle par la PME, alimente le sub-score `project_esg` (poids 0,10) du `project_score` F045.

Cette dualité est inversée par rapport au marché. Les bailleurs cibles (GCF, FEM, Fonds d'Adaptation, BOAD, AFD, Banque mondiale) **n'évaluent pas l'ESG corporate** des PME quand ils étudient un dossier de financement vert. Ils évaluent le **risque et l'impact environnemental & social du PROJET** via des référentiels normalisés au niveau projet :

| Référentiel | Niveau | Statut F13 actuel |
|---|---|---|
| IFC Performance Standards (PS1-PS8) | Projet | Seedé F13 |
| GCF Environmental & Social Safeguards (ESS) | Projet | Seedé F13 |
| BOAD Environmental & Social Standards (ESS) | Projet | Seedé F13 |
| World Bank ESF (10 ESS) | Projet | Pas seedé (hors-scope MVP) |
| Equator Principles | Projet | Pas seedé (hors-scope MVP) |
| GRI 2021 | Entreprise (reporting) | Seedé F13 |
| Mefali | Entreprise/Projet (interne) | Seedé F13 |

Livrables E&S typiquement demandés par un fonds GCF/FEM/BOAD :
- ESIA (Environmental & Social Impact Assessment) du projet
- Plan d'engagement des parties prenantes du projet
- Mécanisme de griefs du projet
- Plan d'action genre du projet (cohérence avec F045 `gender_inclusion`)
- Plan de réinstallation involontaire si applicable
- Système de gestion E&S du projet

Aucun de ces livrables ne porte sur l'entreprise globale. Une coopérative agricole informelle au Togo n'a pas de système de management ESG corporate — mais son projet d'agroforesterie 200 ha doit absolument produire un ESIA pour être éligible GCF.

---

## Objectif de la feature

Étendre l'évaluation ESG au niveau projet : adapter ou décliner `esg_scoring_node` pour qu'il puisse **évaluer un projet vert** contre IFC PS, GCF ESS ou BOAD ESS (référentiels déjà seedés F13), produire un **score ESG-projet calculé** (et non saisi manuellement), un **rapport ESIA-light PDF** consommable par le bailleur, et **remplacer le sub-score `project_esg`** du matching F045 par cette évaluation. F05 entreprise reste intact comme module satellite (reporting GRI, crédit bancaire classique, score corporate pour bailleurs qui le demandent).

---

## Clarifications

### Session 2026-05-21

- Q: Modèle de données pour persister les évaluations ESG-projet — polymorphisme F05 (A), nouvelle table dédiée (B), ou réutilisation `ReferentialScore` F13 (C) ? → A: **Nouvelle table dédiée `project_esg_assessments`** (option B), accompagnée d'une table dépendante `project_esg_criterion_responses`. Cette décision sépare proprement F05 (entreprise) de 047 (projet), parallélise l'architecture avec la table `ReferentialScore` F13, et garantit zéro risque de régression sur les 3 136 tests baseline F05.
- Q: Workflow de saisie des critères — 100 % LLM via widgets F18 (A), formulaire UI dédié uniquement (B), ou hybride (C) ? → A: **Hybride LLM + UI** (option C). Le LLM peut poser les critères via widgets F18 (US4 chat-first), et la PME peut également remplir/réviser les réponses via un wizard UI dédié (US1 form-first). Les deux parcours écrivent sur la même `ProjectEsgAssessment` et restent compatibles avec la reprise multi-session F12.
- Q: Référentiel de repli quand le matching cible un fonds sans ESS déclaré — IFC PS universel (A), Mefali interne (B), ou ne pas calculer (C) ? → A: **IFC PS comme référentiel universel de repli** (option A). IFC Performance Standards est la baseline de facto en finance verte (référencée par BAD, AFD, Banque mondiale comme plancher). Le breakdown matching expose un flag `is_fallback=true` pour transparence, et la PME peut produire un dossier IFC PS réutilisable pour la majorité des fonds.
- Q: Pondération des critères dans le calcul du score 0..100 — égale (A), pondérée par référentiel (B), ou pondérée par sévérité impact × probabilité (C) ? → A: **Pondération définie par référentiel via `criterion.weight` du catalogue F13** (option B). Chaque référentiel publie ses propres coefficients (IFC PS1/PS2 fondamentaux, GCF ESS1 obligatoire, etc.). Réutilise le pattern existant `compute_referential_score_for_offer` côté entreprise. Pas de nouveaux champs `impact_score`/`probability_score` à introduire dans le catalogue F13 pour le MVP.
- Q: Cohabitation `project_esg_score` (F045 manuel) vs `ProjectEsgAssessment.score` (047 calculé) — la saisie manuelle reste-t-elle modifiable après une évaluation finalisée (A), figée lecture seule via API (B), ou modifiable mais ignorée silencieusement (C) ? → A: **Figée lecture seule via API dès qu'une évaluation `finalized` existe** (option B). L'API publique renvoie HTTP 409 (Conflict) avec un message clair (« supprimer ou ré-évaluer pour modifier ») en cas de tentative de modification. Tant qu'aucune évaluation n'existe encore pour le projet, le champ legacy reste modifiable pendant les 2 sprints de cohabitation (rétrocompat préservée pour les clients pré-047). L'UI cache déjà le champ (FR-033).
- Q: Frontend URL — `/profile/projects/[id]/esg` (A), `/esg/projects/[id]` (B), ou section intégrée dans `/profile/projects/[id]/index.vue` (C) ? → A: **`/profile/projects/[id]/esg`** (option A). Page Vue dédiée sous l'arborescence projet existante, cohérence avec F045 (`/profile/projects/[id]/index.vue`). Distinction nette avec `/esg` qui reste réservée à F05 entreprise. Décision documentée dans `research.md` D3. Le pattern `_PATH_TO_SLUG_PATTERNS` doit être enrichi côté backend (cf. T066).
- Q: Régénération du rapport ESIA-light — automatique à chaque finalisation (A) ou à la demande explicite via CTA (B) ? → A: **À la demande explicite via CTA dédié `<EsgReportPreview>`** (option B). Évite le coût WeasyPrint 10-20 s à chaque finalisation (préserve SC-001 ≤ 3 s) et permet un preview structurel avant export PDF. Chaque génération crée une ligne `ProjectEsgReport` versionnée traçable F03. Décision documentée dans `research.md` D4.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — PME informelle évalue son projet ESG sans bilan entreprise (Priority: P1)

Une coopérative agricole au Togo, sans `ESGAssessment` entreprise finalisée, porte un projet d'agroforesterie 200 ha (taxonomie verte UEMOA alignée, thèmes GCF atténuation + REDD+, 850 femmes bénéficiaires). Elle souhaite savoir si son projet est bancable pour le GCF. Elle déclenche l'évaluation ESG-projet contre le référentiel IFC PS depuis la fiche projet ou le chat. Le système collecte progressivement ses réponses sur 15 à 20 critères E&S projet (impact biodiversité, gestion eau, dialogue communautés, intégration genre, suivi M&E, etc.), score le projet sur 0..100, identifie les critères à renforcer avec sources F01 cliquables, et persiste le score qui alimente immédiatement le sub-score `project_esg` du matching F045. L'évaluation projet est strictement indépendante du score entreprise.

**Why this priority** : c'est le cas d'usage central qui justifie la feature. Sans US1, la feature n'a pas de raison d'être. Elle permet à une PME informelle d'obtenir une éligibilité GCF/FEM crédible sans devoir d'abord produire un référentiel ESG corporate qu'elle ne possède pas.

**Independent Test** : créer un compte PME sans ESGAssessment entreprise, créer un projet vert minimal, déclencher la création d'une évaluation ESG-projet contre IFC PS, compléter au moins 15 critères, finaliser et vérifier (a) que la finalisation retourne un score 0..100 et (b) que le matching projet reflète immédiatement ce score dans son sub-score `project_esg` au prochain appel.

**Acceptance Scenarios** :

1. **Given** une PME authentifiée sans `ESGAssessment` entreprise finalisée et un projet vert minimal créé, **When** elle déclenche l'évaluation ESG-projet contre IFC PS depuis la fiche projet, **Then** une évaluation est créée à l'état `draft` rattachée au projet et au référentiel choisi.
2. **Given** une évaluation ESG-projet à l'état `draft` avec 0 critère répondu, **When** la PME répond progressivement à chaque critère (au minimum 15), **Then** chaque réponse est persistée individuellement et l'évaluation expose un pourcentage d'avancement.
3. **Given** une évaluation ESG-projet avec ≥ 15 critères complétés, **When** la PME demande la finalisation, **Then** le système calcule un score 0..100, identifie la liste des critères manquants ou faibles, et passe l'évaluation à l'état `finalized`.
4. **Given** une évaluation ESG-projet `finalized` avec un score calculé, **When** le matching projet est relancé pour ce projet, **Then** le sub-score `project_esg` du `project_score_breakdown` reflète exactement le score de cette évaluation.
5. **Given** une PME sans `ESGAssessment` entreprise, **When** elle finalise une évaluation ESG-projet, **Then** aucun pré-requis d'évaluation entreprise n'est exigé et le score est valide pour le matching financement.
6. **Given** une évaluation ESG-projet finalisée, **When** la PME consulte le résultat, **Then** chaque critère faible affiche une source F01 cliquable expliquant le standard attendu et l'écart constaté.

---

### User Story 2 — Le matching projet-centric pilote le référentiel selon le fonds ciblé (Priority: P1)

Quand la PME ouvre le matching financement pour un fonds donné, le sub-score `project_esg` doit être calculé contre le référentiel ESS approprié au fonds : **GCF ESS** pour un fonds GCF, **BOAD ESS** pour un fonds BOAD, et un référentiel de repli (à clarifier en Q4) pour un fonds sans référentiel ESS déclaré. Ce comportement est cohérent avec F13 `compute_referential_score_for_offer` qui applique déjà ce pattern côté entreprise. La PME peut donc avoir plusieurs `ProjectEsgAssessment` finalisées (une par référentiel) et le matching choisit celle qui correspond au fonds ciblé. Si aucune évaluation n'existe pour le référentiel cible, l'UI propose un appel à l'action « Démarrer l'évaluation ESG-projet contre {référentiel} » et le sub-score tombe à 0 avec un flag `unsourced=true`.

**Why this priority** : sans US2, la feature ne livre pas le rebranchement attendu côté matching F045. C'est le pont qui transforme l'évaluation en valeur métier mesurable. Sans ce rebranchement, US1 produit un score sans utilité opérationnelle.

**Independent Test** : créer deux évaluations ESG-projet finalisées sur un même projet (IFC PS et GCF ESS, scores volontairement différents). Lancer le matching ciblant un fonds GCF et vérifier que `project_score_breakdown.project_esg.score` reflète bien GCF ESS et non IFC PS. Refaire l'opération pour un fonds BOAD et vérifier le basculement sur BOAD ESS.

**Acceptance Scenarios** :

1. **Given** un projet avec une évaluation IFC PS finalisée (score 75) et une évaluation GCF ESS finalisée (score 60), **When** le matching évalue le projet contre un fonds GCF, **Then** le sub-score `project_esg` du breakdown affiche 60 (GCF ESS).
2. **Given** le même projet, **When** le matching évalue le projet contre un fonds BOAD, **Then** le sub-score `project_esg` est calculé contre BOAD ESS (et non IFC PS ni GCF ESS).
3. **Given** un projet sans aucune évaluation ESG-projet, **When** le matching évalue le projet contre n'importe quel fonds, **Then** le sub-score `project_esg` vaut 0 avec un flag `unsourced=true` et l'UI propose un CTA « Démarrer l'évaluation ESG-projet contre {référentiel ciblé} ».
4. **Given** un projet avec une seule évaluation IFC PS finalisée, **When** le matching évalue le projet contre un fonds GCF, **Then** le système ne réutilise pas IFC PS comme proxy de GCF ESS : le sub-score retombe à 0 + `unsourced=true` et le CTA propose de démarrer l'évaluation GCF ESS.
5. **Given** un projet avec une évaluation finalisée pour le référentiel cible, **When** la PME consulte la fiche fonds correspondante, **Then** elle voit le détail du sub-score `project_esg` avec lien direct vers l'évaluation source.

---

### User Story 3 — Rapport ESIA-light PDF généré pour bailleur (Priority: P2)

Une fois l'évaluation projet finalisée, la PME peut générer un dossier ESIA-light PDF structuré en 5 à 7 sections : executive summary, description du projet, baseline E&S, impacts identifiés (positifs et négatifs), mesures d'atténuation, plan d'engagement parties prenantes, indicateurs de suivi M&E. Le pipeline réutilise WeasyPrint + Jinja2 + matplotlib de F06 (rapports ESG entreprise) avec un template dédié `_esia_report.html`. Annexe « Sources et références » F01 obligatoire. Le document est consommable directement par l'analyste GCF/FEM/BOAD.

**Why this priority** : différenciant fort mais peut être livré après US1+US2 qui constituent déjà le MVP fonctionnel. Le score sans rapport reste exploitable côté matching ; le rapport ajoute la dimension dossier bailleur.

**Independent Test** : pour un projet avec une `ProjectEsgAssessment` finalisée, déclencher la génération du rapport ESIA et vérifier que le PDF retourné contient les 7 sections, l'annexe sources F01, et au moins un graphique (donut critères couverts vs manquants).

**Acceptance Scenarios** :

1. **Given** un projet avec une évaluation ESG-projet finalisée, **When** la PME demande la génération du rapport ESIA-light, **Then** un PDF est produit en moins de 30 secondes pour 20 critères et 3 graphiques.
2. **Given** le PDF généré, **When** un analyste l'ouvre, **Then** il contient exactement les 5 à 7 sections attendues, dans l'ordre prescrit, avec en-tête PME + projet + référentiel utilisé.
3. **Given** le PDF généré, **When** l'analyste consulte la fin du document, **Then** une annexe « Sources et références » liste toutes les sources F01 citées avec lien public ou identifiant.
4. **Given** une évaluation avec critères manquants, **When** la PME génère le rapport, **Then** le donut « critères couverts vs manquants » est présent et les critères manquants sont listés explicitement comme axes d'amélioration.
5. **Given** une évaluation `draft` non finalisée, **When** la PME tente la génération du rapport, **Then** le système refuse avec un message clair invitant à finaliser l'évaluation d'abord.

---

### User Story 4 — Le LLM orchestre l'évaluation depuis le chat (Priority: P2)

Depuis le chat, la PME peut dire « Évalue l'ESG de mon projet d'agroforesterie pour GCF ». Le LLM, via le skill F23 `skill_project_esg_assessment`, enchaîne automatiquement :

1. Identification du projet (widget F18 qcu si plusieurs projets).
2. Création d'une évaluation contre le référentiel approprié au fonds mentionné (GCF ESS dans l'exemple).
3. Pose des critères un par un via widgets F18 (qcu/qcm/justification selon le type de critère).
4. Citation des sources F01 obligatoires (validator `source_required.py` actif).
5. Finalisation de l'évaluation quand tous les critères sont collectés.
6. Affichage d'un bloc visualisation F11 avec score, critères manquants et lien rapport ESIA.
7. Relance automatique du matching projet pour montrer l'impact sur l'éligibilité.

**Why this priority** : aligne la feature sur l'identité conversationnelle de Mefali, mais peut être livré après US1+US2 qui supportent déjà l'évaluation via UI/API. US4 est une montée en gamme expérience, pas un bloquant fonctionnel.

**Independent Test** : démarrer une conversation chat fraîche sur la fiche projet, taper « Évalue mon projet contre GCF ESS », vérifier que le LLM enchaîne create_project_esg_assessment → au minimum 5 widgets F18 → finalize → bloc F11 affiché → matching relancé automatiquement.

**Acceptance Scenarios** :

1. **Given** une PME sur la fiche d'un projet vert sans évaluation ESG-projet existante, **When** elle écrit « Évalue mon projet contre GCF ESS » dans le chat, **Then** le LLM démarre l'évaluation et pose le premier critère via un widget F18.
2. **Given** une question critère ouverte dans le chat, **When** la PME répond via le widget F18 (qcu/qcm/justification), **Then** la réponse est persistée sur l'évaluation et le LLM pose le critère suivant.
3. **Given** une PME avec plusieurs projets, **When** elle écrit « Évalue l'ESG de mon projet d'agroforesterie », **Then** le LLM affiche un widget F18 qcu listant ses projets pour désambiguïser avant de démarrer.
4. **Given** que tous les critères du référentiel sont collectés, **When** le dernier critère est répondu, **Then** le LLM appelle automatiquement `finalize_project_esg_assessment` et affiche un bloc visualisation F11 avec score, critères manquants et lien rapport ESIA.
5. **Given** une évaluation finalisée par le chat, **When** le bloc résultat s'affiche, **Then** le matching projet est relancé automatiquement et un bloc de comparaison montre l'impact sur l'éligibilité du fonds ciblé.
6. **Given** la PME interrompt la conversation en cours d'évaluation, **When** elle revient plus tard, **Then** le LLM retrouve l'état (critères déjà répondus) via mémoire contextuelle F12 et reprend au critère suivant.
7. **Given** un critère réclame une source F01, **When** le LLM répond sans citer de source, **Then** le validator `source_required.py` retourne en retry 1× puis bascule en fallback texte explicite si la deuxième tentative échoue.

---

### User Story 5 — Migration douce du champ F045 `project_esg_score` (Priority: P3)

Le champ `projects.project_esg_score INT NULL` (héritage F045, saisie manuelle) devient un cache lecture seule alimenté par un listener sur `ProjectEsgAssessment` (after_insert / after_update). Les anciennes valeurs saisies manuellement restent en BDD (cohabitation 2 sprints). Le matching F045 priorise `ProjectEsgAssessment.score` (calculé) si disponible, sinon retombe sur `projects.project_esg_score` (saisie F045), sinon retourne 0 + `unsourced=true`. L'UI du formulaire d'édition de projet n'expose plus le champ saisie manuelle, mais le backend l'accepte encore via API pour rétrocompatibilité. Après deux sprints, la colonne F045 pourra être supprimée par une feature de cleanup hors-scope 047.

**Why this priority** : finition propre, mais pas bloquante pour les autres user stories. Peut atterrir en fin de sprint. Permet d'éviter de figer la dette F045 et garantit que le matching consomme bien la nouvelle évaluation calculée.

**Independent Test** : créer un projet avec `project_esg_score=42` (saisie F045 héritée), lancer une `ProjectEsgAssessment` IFC PS finalisée avec score 78, vérifier que `matching_service._compute_project_score` utilise 78. Réinitialiser l'évaluation et vérifier que le matching retombe sur 42 (fallback F045) puis sur 0 + `unsourced=true` après suppression de l'assessment et reset de `project_esg_score`.

**Acceptance Scenarios** :

1. **Given** un projet avec `project_esg_score=42` (saisie manuelle F045) et une `ProjectEsgAssessment` finalisée avec score 78, **When** le matching est calculé, **Then** le sub-score `project_esg` utilise 78 (priorité au calculé).
2. **Given** un projet avec `project_esg_score=42` et sans `ProjectEsgAssessment`, **When** le matching est calculé, **Then** le sub-score `project_esg` retombe sur 42 (fallback F045).
3. **Given** un projet sans aucune valeur (`project_esg_score IS NULL` et aucune `ProjectEsgAssessment`), **When** le matching est calculé, **Then** le sub-score `project_esg` vaut 0 avec `unsourced=true`.
4. **Given** une `ProjectEsgAssessment` finalisée, **When** le listener `after_insert/after_update` se déclenche, **Then** la colonne `projects.project_esg_score` est mise à jour avec le score calculé (snapshot).
5. **Given** une PME sur le formulaire d'édition d'un projet, **When** elle consulte le formulaire, **Then** le champ saisie manuelle `project_esg_score` n'est pas exposé dans l'UI (mais reste acceptable via API publique pour rétrocompat 2 sprints).

---

### Edge Cases

- **Évaluation orpheline** : que se passe-t-il si le projet est supprimé alors qu'une évaluation est en cours ou finalisée ? Comportement attendu : soft-delete cascade ou refus dur (à clarifier en research si non spécifié).
- **Changement de référentiel en cours** : la PME démarre une évaluation contre IFC PS et veut basculer vers GCF ESS à mi-parcours. Comportement attendu : créer une nouvelle évaluation distincte (1 évaluation = 1 référentiel = 1 snapshot), ne pas migrer les réponses.
- **Évolution versioning d'un référentiel F13** : si le référentiel GCF ESS passe en v2.0, les évaluations finalisées en v1.0 ne sont pas auto-recalculées. La PME reçoit une notification (cron F13 `check_referential_versions_evolution.py` à étendre) lui permettant de relancer une évaluation contre la nouvelle version.
- **Tenant tiers tentant d'accéder à une évaluation** : doit retourner 404 (jamais 403, pour ne pas révéler l'existence). RLS F02 garantit l'isolation.
- **PME finalise sans répondre à un critère obligatoire** : le système refuse la finalisation avec liste des critères obligatoires manquants. Distinguer obligatoire/optionnel selon le référentiel.
- **Score F045 manuel et score calculé identiques** : pas de conflit, le matching utilise le score calculé (priorité), comportement neutre observable.
- **Conversion d'une évaluation `draft` abandonnée** : le système conserve les réponses partielles indéfiniment, accessibles par mémoire contextuelle F12 ; la PME peut reprendre ou supprimer manuellement.
- **Génération PDF échoue (timeout WeasyPrint)** : retour HTTP 504 avec message explicite, possibilité de relance. Pas de PDF tronqué stocké.
- **LLM dépasse 12 widgets F18** : couplage avec `MAX_TOOLS_PER_TURN=14` ; comportement attendu : si la couverture critères dépasse 12 widgets, le LLM doit basculer sur formulaire UI (lien explicite) plutôt que d'épuiser sa fenêtre d'outils.
- **Référentiel F13 dépublié** (`status='outdated'`) : les évaluations finalisées restent lisibles, mais aucune nouvelle évaluation contre ce référentiel n'est démarrable.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Évaluation et scoring (US1)

- **FR-001** : Le système DOIT permettre à une PME de démarrer une évaluation ESG-projet contre un référentiel choisi (IFC PS, GCF ESS, BOAD ESS) sans pré-requis d'évaluation ESG entreprise (F05) finalisée.
- **FR-002** : Le système DOIT exposer la liste des référentiels disponibles pour une évaluation projet (sous-ensemble des référentiels F13 marqués comme applicables au niveau projet).
- **FR-003** : Le système DOIT persister chaque réponse à un critère individuellement, permettant une saisie progressive et la reprise multi-session. Les réponses DOIVENT pouvoir être saisies indistinctement via le chat (widgets F18 orchestrés par le LLM, US4) ou via un wizard UI dédié `<ProjectEsgWizard>` (US1) — les deux parcours écrivent sur la même `ProjectEsgAssessment` et la même collection `project_esg_criterion_responses`.
- **FR-003a** : Le wizard UI DOIT permettre à la PME de **réviser et corriger** les réponses précédemment fournies (via chat ou UI) tant que l'évaluation est à l'état `draft` ; une réponse modifiée écrase la précédente avec horodatage de mise à jour (et tracé par F03 audit log).
- **FR-004** : Le système DOIT exposer un pourcentage d'avancement (réponses fournies / total critères) pour toute évaluation `draft`.
- **FR-005** : Le système DOIT calculer un score 0..100 à la finalisation, identifier les critères manquants ou faibles, et faire passer l'évaluation à l'état `finalized` (immuable une fois finalisée). Le calcul du score DOIT appliquer la **pondération par référentiel** (`criterion.weight` du catalogue F13 ; cf. Clarifications Session 2026-05-21), de manière analogue à `compute_referential_score_for_offer` côté entreprise.
- **FR-006** : Le système DOIT refuser la finalisation si des critères marqués « obligatoires » par le référentiel n'ont pas reçu de réponse, et retourner la liste explicite des critères manquants.
- **FR-007** : Le système DOIT supporter plusieurs évaluations finalisées par projet, une par référentiel (un projet peut avoir simultanément une évaluation IFC PS et une évaluation GCF ESS finalisées).
- **FR-008** : Le système DOIT permettre la ré-évaluation : une nouvelle évaluation contre le même référentiel crée une nouvelle entité (pas de mutation d'une évaluation finalisée). Une seule évaluation `finalized` par projet × référentiel × version reste « active » pour la consommation matching.

#### Matching projet-centric (US2)

- **FR-009** : Le matching projet DOIT sélectionner automatiquement le référentiel ESG approprié au fonds ciblé : GCF → GCF ESS, BOAD → BOAD ESS, **fonds sans référentiel ESS déclaré → IFC PS** (référentiel universel de repli, cf. Clarifications Session 2026-05-21). Quand le repli est appliqué, le breakdown matching DOIT exposer un flag `is_fallback=true` pour transparence vis-à-vis de la PME.
- **FR-010** : Le matching projet DOIT consommer le score d'une évaluation `finalized` du référentiel cible si elle existe, comme valeur du sub-score `project_esg` dans `PROJECT_SCORE_WEIGHTS` (poids 0,10 inchangé).
- **FR-011** : Si aucune évaluation `finalized` n'existe pour le référentiel cible, le matching DOIT retourner `project_esg=0` avec flag `unsourced=true` dans le breakdown.
- **FR-012** : Le matching ne DOIT PAS utiliser une évaluation finalisée contre un référentiel A pour scorer un fonds réclamant un référentiel B (pas de proxy implicite entre référentiels).
- **FR-013** : L'UI matching DOIT proposer un appel à l'action « Démarrer l'évaluation ESG-projet contre {référentiel attendu} » quand le sub-score `project_esg` est nul faute d'évaluation.
- **FR-014** : L'UI matching DOIT exposer, depuis le détail d'un match offre, un lien direct vers l'évaluation source consommée pour le sub-score.

#### Rapport ESIA-light PDF (US3)

- **FR-015** : Le système DOIT générer à la demande un rapport ESIA-light PDF pour toute évaluation ESG-projet à l'état `finalized`.
- **FR-016** : Le rapport DOIT contenir 5 à 7 sections : (1) executive summary, (2) description du projet, (3) baseline E&S, (4) impacts identifiés (positifs et négatifs), (5) mesures d'atténuation, (6) plan d'engagement des parties prenantes, (7) indicateurs de suivi M&E.
- **FR-017** : Le rapport DOIT inclure une annexe « Sources et références » F01 listant toutes les sources citées dans l'évaluation.
- **FR-018** : Le rapport DOIT inclure au moins un graphique de couverture (donut critères couverts vs manquants) ; les autres graphiques sont optionnels selon les données disponibles.
- **FR-019** : Le système DOIT refuser la génération du rapport pour une évaluation à l'état `draft` avec un message d'erreur explicite indiquant qu'une finalisation préalable est nécessaire.
- **FR-020** : Le rapport DOIT être consultable par téléchargement (PDF) et tracé dans l'historique des rapports (réutilisation du pipeline rapports F06).

#### Orchestration conversationnelle (US4)

- **FR-021** : Le LLM DOIT pouvoir démarrer une évaluation ESG-projet depuis le chat via un skill F23 dédié, avec gating eval ≥ 90 % avant publication.
- **FR-022** : Le LLM DOIT poser chaque critère via un widget F18 (qcu, qcm, qcu_justification, ou qcm_justification selon le type de critère défini par le référentiel).
- **FR-023** : Le LLM DOIT respecter le validator F01 `source_required.py` (retry 1× puis fallback texte) pour chaque critère réclamant une source.
- **FR-024** : Le LLM DOIT, après finalisation d'une évaluation, afficher un bloc visualisation F11 contenant score, liste des critères manquants, et lien vers le rapport ESIA-light.
- **FR-025** : Le LLM DOIT, après finalisation et bloc F11, relancer automatiquement le matching projet pour montrer l'impact sur l'éligibilité.
- **FR-026** : Le LLM DOIT pouvoir reprendre une évaluation `draft` interrompue grâce à la mémoire contextuelle F12 (`recall_history`).
- **FR-027** : Le LLM DOIT respecter la contrainte « 1 question pending max/conversation » imposée par F18.
- **FR-028** : Le LLM DOIT pouvoir désambiguïser un projet via widget F18 qcu quand la PME a plusieurs projets et que sa demande est ambiguë.

#### Migration douce et cohabitation F045 (US5)

- **FR-029** : Le matching DOIT prioriser `ProjectEsgAssessment.score` (calculé) sur `projects.project_esg_score` (saisie F045).
- **FR-030** : Le matching DOIT utiliser `projects.project_esg_score` en fallback uniquement si aucune `ProjectEsgAssessment` `finalized` n'existe pour le référentiel cible (sous-priorité après FR-029).
- **FR-031** : Le matching DOIT retourner 0 + `unsourced=true` uniquement si ni `ProjectEsgAssessment` ni `projects.project_esg_score` ne sont disponibles.
- **FR-032** : Le système DOIT synchroniser `projects.project_esg_score` (snapshot) via un listener déclenché à la finalisation/modification d'une `ProjectEsgAssessment` (debounce 30 s in-process si pattern F045 réutilisé).
- **FR-033** : L'UI du formulaire d'édition d'un projet ne DOIT PLUS exposer le champ saisie manuelle `project_esg_score`. Le backend DOIT continuer à accepter ce champ via API publique pour rétrocompatibilité durant au moins 2 sprints **uniquement quand le projet n'a aucune `ProjectEsgAssessment` à l'état `finalized`**. Dès qu'au moins une évaluation finalisée existe pour le projet, toute tentative de modification du champ via API DOIT être rejetée avec HTTP 409 (Conflict) et un message indiquant à l'appelant de supprimer ou ré-évaluer pour modifier (cf. Clarifications Session 2026-05-21).

#### Exigences transverses (toutes user stories)

- **FR-034** : Chaque critère d'évaluation DOIT pouvoir citer une source F01 (validator post-LLM `source_required.py`, retry 1× puis fallback texte).
- **FR-035** : Toute nouvelle table métier DOIT être multi-tenant avec colonne `account_id` non-null et RLS F02 activée (`ENABLE + FORCE`) avec au minimum les policies `pme_access_own_account` et `admin_full_access`.
- **FR-036** : Toute entité user-facing (créée ou modifiée par la PME) DOIT être auditée via le mixin F03 `Auditable` (triggers PL/pgSQL existants couvrent automatiquement la garantie append-only).
- **FR-037** : Toute estimation monétaire (budget plan d'atténuation, coûts associés à un critère) DOIT utiliser le type Money F04 (Decimal + Currency).
- **FR-038** : Les conversations d'évaluation DOIVENT rester traçables via la mémoire contextuelle F12 (`recall_history`) pour la reprise multi-session.
- **FR-039** : Le pattern F13 `compute_referential_score_for_offer` DOIT être étendu côté projet de manière analogue à l'existant côté entreprise (réutilisation maximale).
- **FR-040** : Tous les composants Vue créés ou modifiés DOIVENT supporter le dark mode (cf. CLAUDE.md « Dark Mode OBLIGATOIRE »).
- **FR-041** : Tous les composants Vue créés ou modifiés DOIVENT être accessibles : ARIA labels FR complets, navigation clavier, focus visible.
- **FR-042** : L'UX DOIT distinguer clairement « ESG Entreprise » (page `/esg`) et « ESG Projet » (page projet) via un badge `<EsgTargetBadge>` réutilisable, et publier une note `docs/esg-projet-vs-entreprise.md` pour les équipes de support.
- **FR-043** : Le sourçage F01 ajouté pour les nouveaux référentiels (IFC PS officiel, GCF ESS 2022, BOAD ESS) DOIT respecter le workflow 4-yeux (captured_by ≠ verified_by) et atteindre le statut `verified` avant publication.
- **FR-044** : Le tri par défaut des listes d'évaluations pour un projet DOIT placer en premier l'évaluation `finalized` la plus récente par référentiel.

### Key Entities *(include if feature involves data)*

- **ProjectEsgAssessment** : représente une évaluation ESG d'un **projet** contre un **référentiel** donné. Persistée dans une **nouvelle table dédiée** `project_esg_assessments` (cf. Clarifications Session 2026-05-21 — option B). Attributs clés : identifiant tenant (`account_id` non-null + RLS F02), projet cible (`project_id` FK), référentiel cible (`referential_id` FK F13), version du référentiel au moment de la création (snapshot F04), état (`draft`/`finalized`), score 0..100 (calculé à la finalisation), date de finalisation, créateur, snapshot frozen des paramètres ayant servi au calcul.
- **ProjectEsgCriterionResponse** : représente la réponse d'une PME à un critère d'un référentiel pour une évaluation donnée. Persistée dans une nouvelle table dépendante `project_esg_criterion_responses` (FK CASCADE vers `project_esg_assessments`). Attributs clés : identifiant tenant (`account_id` non-null + RLS F02), évaluation parente, critère ciblé (FK F13), valeur de réponse (typée selon le widget F18 utilisé), justification éventuelle, sources F01 citées, horodatage.
- **ProjectEsgReport** : représente une instance de rapport ESIA-light PDF générée pour une évaluation finalisée. Attributs clés : identifiant tenant, évaluation source, horodatage de génération, chemin du document, version du template utilisé.
- **Project** (existant F045) : enrichi d'une relation vers ses évaluations ESG-projet ; la colonne `project_esg_score` est désormais un snapshot lecture seule alimenté par listener (cf. FR-032).
- **Referential** (existant F13) : enrichi d'une notion « niveau d'application » distinguant les référentiels projet (IFC PS, GCF ESS, BOAD ESS) des référentiels entreprise (GRI 2021) et hybrides (Mefali).
- **Source** (existant F01) : utilisé pour citer chaque critère ; nouvelles sources à seeder pour les référentiels MVP (IFC PS officiel, GCF ESS 2022, BOAD ESS officiel).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

| ID | Critère | Métrique mesurable | Cible | Méthode de mesure |
|---|---|---|---|---|
| **SC-001** | Évaluation accessible à une PME informelle | Temps de complétion bout-en-bout d'une évaluation IFC PS via chat pour une PME sans ESGAssessment | < 8 minutes médiane | 5 tests utilisateurs simulés (E2E Playwright) |
| **SC-002** | Matching consomme l'évaluation calculée | Proportion des matchings pour lesquels le sub-score `project_esg` reflète une `ProjectEsgAssessment.score` finalisée (vs saisie F045 ou 0) quand au moins une évaluation finalisée existe | ≥ 95 % | Test d'intégration sur 20 projets fixtures |
| **SC-003** | Rapport ESIA-light performant | Délai de génération d'un rapport ESIA-light PDF pour 20 critères + 3 graphiques + annexe sources F01 | < 30 secondes p95 | Benchmark pytest-benchmark |
| **SC-004** | Couverture tests modules nouveaux | Couverture lignes sur `app/modules/esg/project_*.py` (backend) et composants Vue F047 (frontend) | ≥ 80 % | `pytest --cov` (backend) et `npx vitest run --coverage` (frontend) |
| **SC-005** | Aucune régression | Tests passants suite pytest baseline et tests existants F05 entreprise après livraison 047 | = baseline pré-047 (3 136 passants minimum) | CI complet sur la PR de livraison |
| **SC-006** | Conversation efficace | Nombre de widgets F18 et de tours conversation utilisateur pour boucler une évaluation complète via chat | ≤ 12 widgets et ≤ 3 tours utilisateur | Fixture E2E Playwright sur un parcours nominal |
| **SC-007** | Migration sans perte de données | Round-trip Alembic up / down / up sur PostgreSQL réelle | 100 % des données F045 `project_esg_score` préservées | Test de migration intégré au CI |
| **SC-008** | Skill F23 prêt pour publication | Score eval golden examples pour `skill_project_esg_assessment` | ≥ 90 % | Eval runner skill F23 |
| **SC-009** | Sourçage F01 complet | Proportion de critères évaluables retournant une source F01 vérifiée (status `verified`) au cours d'une évaluation IFC PS / GCF ESS / BOAD ESS finalisée | ≥ 95 % | Audit automatisé post-finalisation |
| **SC-010** | Distinction UX entreprise vs projet | Taux d'utilisateurs PME identifiant correctement la cible (entreprise/projet) lors d'un test usability (5 sujets) | ≥ 4/5 sujets sans erreur de cible | Session usability test mobile + desktop |

---

## Scope

### In Scope

- Pipeline d'évaluation ESG-projet (nouveau noeud LangGraph ou branche conditionnelle de `esg_scoring_node` — choix tranché par recherche).
- 3 référentiels MVP : IFC PS (8 standards, 15-20 critères projet), GCF ESS (6 standards, 15-20 critères), BOAD ESS (15 critères).
- Schéma de persistance des évaluations projet : nouvelle table dédiée `project_esg_assessments` + table dépendante `project_esg_criterion_responses` (option B tranchée en clarification Session 2026-05-21).
- Outils LangChain pour orchestration : `create_project_esg_assessment`, `save_project_esg_criterion`, `finalize_project_esg_assessment`, `get_project_esg_assessment`, `list_project_esg_assessments`.
- Prompts FR avec sourçage F01 obligatoire.
- Page Vue dédiée (URL à clarifier en Q5) + composants `<ProjectEsgWizard>`, `<EsgCriterionWidget>`, `<EsgReferentialPicker>`, `<EsgReportPreview>`.
- Composable `useProjectEsg.ts`, store Pinia `projectEsg.ts`.
- Rapport ESIA-light PDF (WeasyPrint + Jinja2 + matplotlib SVG, template `_esia_report.html` dédié).
- Skill F23 `skill_project_esg_assessment` (draft initial, gating eval ≥ 90 % avant publication).
- Intégration matching F045 : extension de `compute_referential_score_for_offer` pour consommer le score projet calculé.
- Sources F01 nouvelles à seeder (IFC PS officiel, GCF ESS 2022, BOAD ESS) via `seed_sources_047.py` idempotent.
- Tests unitaires + intégration + E2E avec couverture ≥ 80 % sur les modules nouveaux.

### Out of Scope

- **Refonte de F05 entreprise** : reste tel quel ; `ESGAssessment.target_kind='company'` par défaut si polymorphisme retenu.
- **Référentiels au-delà des 3 MVP** : World Bank ESF, Equator Principles, GRI projet, Verra → post-MVP.
- **Certification tierce ou audit externe automatisé** : pas dans 047.
- **Synchronisation automatique avec systèmes externes** (SIGI, OpenESG, etc.).
- **Suppression définitive de la colonne F045 `projects.project_esg_score`** : différée d'au moins 2 sprints après livraison 047.
- **Multi-langue** : français uniquement en MVP ; anglais post-MVP.
- **Évaluation comparative projet vs projet** : hors-scope 047, post-MVP.
- **Versioning des évaluations projet** : une évaluation = un snapshot immuable ; toute ré-évaluation crée une nouvelle ligne. Le versioning au sens F04 (`version`, `valid_from`, `valid_to`, `superseded_by`) n'est pas appliqué au niveau évaluation (à l'inverse des référentiels, déjà versionnés F13).

---

## Fondations transverses à respecter (non-négociable)

- **F01 sourçage** : validator `source_required.py` actif sur chaque critère. Retry 1× puis fallback texte. Sources F01 nouvelles seedées avec four-eyes (captured_by ≠ verified_by).
- **F02 multi-tenant + RLS** : nouvelles tables avec `account_id UUID NOT NULL`, `ENABLE + FORCE` RLS, 2 policies minimum (`pme_access_own_account`, `admin_full_access`). Les bypass RLS identifiés dans la security review F045 ne doivent pas être reproduits.
- **F03 audit log append-only** : nouvelles entités auditées via mixin `Auditable` si elles sont user-facing (créées/modifiées par PME). Triggers PL/pgSQL existants couvrent automatiquement la garantie append-only.
- **F04 Money typed** : si des critères incluent des estimations de coûts (par exemple budget plan d'atténuation), utiliser `Money` (Decimal + Currency).
- **F11 visualisation** : score projet ESG affiché via `show_kpi_card`, comparaison référentiels via `show_comparison_table`, critères manquants via `<MissingProjectCriteriaList>` (réutiliser le composant F045).
- **F12 mémoire contextuelle** : conversations d'évaluation ESG-projet doivent rester traçables via `recall_history` pour la reprise multi-session.
- **F13 référentiels** : réutiliser `ReferentialScore` ou son pattern. `compute_referential_score_for_offer` doit être étendu côté projet.
- **F18 widgets interactifs** : tous les critères posés par le LLM doivent passer par `ask_interactive_question` (qcu, qcm, qcu_justification, qcm_justification). Contrainte « 1 question pending max/conversation » respectée.
- **F23 skills** : nouveau skill draft initial, gating eval ≥ 90 % avant publication.
- **F045 matching projet-centric** : le sub-score `project_esg` du `PROJECT_SCORE_WEIGHTS` consomme désormais l'évaluation calculée. **Aucun changement de poids** (reste 0,10).

---

## Contraintes techniques

- **Backward compat F045** : colonne `projects.project_esg_score INT NULL` conservée 2 sprints. Listener SQLAlchemy met à jour la colonne snapshot quand une `ProjectEsgAssessment` est finalisée (debounce 30 s in-process si pattern F045 réutilisé).
- **Backward compat F05** : `ESGAssessment` entreprise reste strictement inchangée (aucun discriminant, aucune colonne ajoutée). `esg_scoring_node` route l'intent projet vers une logique dédiée (nouveau noeud ou branche conditionnelle, cf. R3) qui lit/écrit la table `project_esg_assessments` sans toucher à la table F05 `esg_assessments`.
- **Migration Alembic** : round-trip up / down / up validé sur PostgreSQL réelle. Création de deux tables nouvelles (`project_esg_assessments`, `project_esg_criterion_responses`) avec RLS F02 + triggers F03 auditables. Aucune ligne F05 à backfiller (les tables nouvelles partent vides).
- **Performance** : finalisation d'une évaluation projet ≤ 3 s (calcul score + UPSERT + listener async). Rapport ESIA-light PDF ≤ 30 s pour un projet avec 20 critères + 3 graphiques.
- **Tests baseline** : 0 régression sur les 3 136 tests passants actuels. Suite `pytest -x` complète doit rester verte.
- **Couverture** : ≥ 80 % sur les modules nouveaux (`app/modules/esg/project_*.py`, composants Vue F047).
- **Dark mode** : obligatoire sur tous les nouveaux composants Vue (`bg-white dark:bg-dark-card`, etc.) — cf. `CLAUDE.md`.
- **Accessibilité** : ARIA labels FR complets, navigation clavier, focus visible (par exemple `focus:ring-emerald-500`).

---

## Risques identifiés et atténuations

| ID | Risque | Atténuation |
|---|---|---|
| **R1** | Confusion utilisateur entre ESG entreprise et ESG projet | Libellés UI explicites (« ESG Entreprise » sur `/esg`, « ESG Projet » sur fiche projet). Composant `<EsgTargetBadge>` clarifie la cible. Documentation `docs/esg-projet-vs-entreprise.md`. |
| **R2** | Référentiels MVP mal calibrés (trop nombreux critères = abandon, trop peu = pas crédible bailleur) | `research.md` R2 documente la sélection critère par critère avec justification + source F01. Validation par un expert métier avant implémentation. Plage cible : 15 à 20 critères par référentiel. |
| **R3** | Surcharge du noeud `esg_scoring_node` qui devient polymorphe | `research.md` R1 tranche entre noeud séparé et branche conditionnelle. Si branche conditionnelle, refactor strict avec ≤ 50 lignes par fonction. |
| **R4** | Bypass RLS reproduits (cf. security review F045) | Tous les endpoints du module nouveau doivent passer un test `test_*_rls.py` avec un compte tiers. Pattern strict : extraire `account_id` ET le propager à toutes les queries service. |
| **R5** | Régression matching F045 | Tests d'intégration `test_match_funds_consumes_project_esg.py` valident la priorité d'usage entre évaluation calculée et fallback F045. |
| **R6** | LLM dépasse la fenêtre d'outils par évaluation | `MAX_TOOLS_PER_TURN=14` ; couper les widgets F18 à 12 puis basculer sur formulaire UI explicite. |
| **R7** | Sources F01 nouvelles non vérifiées au moment du go-live | Pipeline de seed `seed_sources_047.py` exécuté avant la livraison ; gate de release : ≥ 95 % de critères évaluables ont une source `verified`. |

---

## Open Questions

> Statut après Session 2026-05-21 + résolution post-plan : **7 questions résolues sur 8** (Q1, Q3, Q4, Q5, Q6, Q7, Q8 — voir section Clarifications). Seule **Q2 (sélection des critères MVP)** reste différée à `research.md` R2 et à la validation métier (équipe ESG interne) — son impact est circonscrit à la composition du catalogue F13 et ne bloque ni l'architecture, ni le scoring, ni le matching, ni la rétrocompat F045.

- ~~**Q1 — Modèle de données**~~ — **résolue Session 2026-05-21 → option B (nouvelle table dédiée `project_esg_assessments`).**
- **Q2 — Sélection des critères MVP** *(différée — sera traitée dans `research.md` R2)* : qui valide la liste finale par référentiel (équipe métier interne ou expert externe) ? Quel niveau de détail visé (15, 20, 30 critères par référentiel) ?
- ~~**Q3 — Workflow de saisie**~~ — **résolue Session 2026-05-21 → option C (hybride LLM via widgets F18 + wizard UI dédié éditable).**
- ~~**Q4 — Référentiel par défaut quand le matching cible un fonds sans ESS déclarée**~~ — **résolue Session 2026-05-21 → option A (IFC PS universel + flag `is_fallback=true` dans le breakdown).**
- ~~**Q5 — Frontend URL**~~ — **résolue Session 2026-05-21 (post-clarify, dans `research.md` D3) → `/profile/projects/[id]/esg`** (page Vue dédiée sous l'arborescence projet existante, cohérence F045 ; distinction nette avec `/esg` qui reste F05 entreprise).
- ~~**Q6 — Cohabitation `project_esg_score` (F045 manuel) vs `ProjectEsgAssessment.score` (047 calculé)**~~ — **résolue Session 2026-05-21 → option B (figée lecture seule via API dès qu'une évaluation `finalized` existe ; rejet HTTP 409. Modification API tolérée 2 sprints uniquement si aucune évaluation finalisée).**
- ~~**Q7 — Régénération du rapport ESIA**~~ — **résolue Session 2026-05-21 (post-clarify, dans `research.md` D4) → CTA explicite via `<EsgReportPreview>`** (évite le coût WeasyPrint 10-20 s à chaque finalisation, préserve SC-001 ≤ 3 s, permet preview structurel avant export PDF).
- ~~**Q8 — Pondération des critères dans le score 0..100**~~ — **résolue Session 2026-05-21 → option B (pondération par référentiel via `criterion.weight` du catalogue F13).**

---

## Assumptions

- **Public cible inchangé** : PME africaines francophones (UEMOA/CEDEAO), secteur informel inclus, accès via web + extension Chrome F24.
- **Référentiels MVP suffisants pour le go-live** : IFC PS, GCF ESS et BOAD ESS couvrent au moins 80 % des bailleurs verts cibles selon les retours F045. Les référentiels World Bank ESF et Equator Principles sont reportés à un futur sprint.
- **Pipeline rapport F06 réutilisable** : le pipeline WeasyPrint + Jinja2 + matplotlib utilisé pour les rapports ESG entreprise (F06) est suffisamment paramétrable pour accueillir le template ESIA-light sans refactor profond.
- **Pattern F13 multi-référentiels transposable** : `compute_referential_score_for_offer` côté entreprise est conceptuellement transposable côté projet sans repenser le moteur de scoring.
- **Tests baseline stables** : la suite baseline (3 136 passants) est représentative ; les 201 tests `failed` actuels listés dans `/tmp/pytest_full2.log` sont préexistants à 047 et ne seront pas augmentés par cette feature.
- **Composants F045 réutilisables** : `<DualScoreDisplay>`, `<DivergenceBadge>`, `<MissingProjectCriteriaList>`, `<SourceLink>` du sprint 045 sont consommables sans modification structurelle.
- **Anglais hors-scope MVP** : tous les libellés UI/UX sont en français ; les rapports ESIA-light sont produits en français même quand le bailleur cible publie en anglais (post-MVP : traduction de l'annexe sources + executive summary).
- **Pas de versioning au niveau évaluation** : une évaluation finalisée est un snapshot immuable. La PME peut créer plusieurs évaluations contre le même référentiel, mais seule la plus récente `finalized` par projet × référentiel est consommée par le matching.
- **Seed F01 sources MVP** : trois sources nouvelles minimum (IFC PS officiel, GCF ESS 2022, BOAD ESS) suffisent au démarrage ; d'autres sources peuvent être ajoutées sans nouvelle migration grâce au catalogue F01 vivant.
- **Skills F23 publication différée** : le skill `skill_project_esg_assessment` peut être livré à l'état `draft` ; la publication (`status='published'`) est subordonnée au passage du gating eval ≥ 90 %.

---

## Dependencies

- **Sprints prédécesseurs livrés** : F01 sourçage (mig. 020), F02 multi-tenant + RLS (mig. 019), F03 audit log (mig. 021), F04 Money typed (mig. 022), F05 ESG entreprise (sprint 005), F06 rapports PDF (sprint 006), F11 visualisation (sprint 029), F12 mémoire contextuelle (mig. 023), F13 référentiels (mig. 030), F18 widgets interactifs (mig. 018), F23 skills (mig. 033), F045 matching projet-centric (mig. 046).
- **Référentiels F13 prérequis seedés** : IFC Performance Standards, GCF Environmental & Social Safeguards, BOAD Environmental & Social Standards (les trois sont déjà présents en BDD selon le tableau de contexte).
- **Pipeline rapports F06 opérationnel** : WeasyPrint + Jinja2 + matplotlib + fontconfig fonctionnels en CI et en production.
- **Sources F01 nouvelles à seeder** : IFC PS officiel (PDF), GCF ESS 2022 (PDF), BOAD ESS (PDF). Captured_by ≠ verified_by, statut `verified` avant go-live.

---

## Notes de livraison

- **Sprint number imposé** : `047` (la migration 046 a été consommée par F045 ; aucune feature 046 n'existe — comportement attendu).
- **Branche git** : `047-evaluation-esg-projet` créée depuis `main`.
- **Tests baseline actuels** : 3 136 passants / 201 échecs préexistants à F045 (cf. `/tmp/pytest_full2.log`).
- **Composants F045 à réutiliser** : `<DualScoreDisplay>`, `<DivergenceBadge>`, `<MissingProjectCriteriaList>`, `<SourceLink>`.
- **Risque principal à surveiller** : confusion UX entre ESG entreprise et ESG projet — bien séparer les libellés et les pages.
- **Workflow suite** : `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`.
