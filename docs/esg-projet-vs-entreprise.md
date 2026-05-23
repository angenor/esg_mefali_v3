# ESG entreprise vs ESG projet — note de clarification

> **Audience** : équipe produit, support PME, équipe LLM/prompts.
> **Mitigation** : risque R1 du spec 047 (« confusion entre les deux évaluations »).
> **Date** : 2026-05-21.

La plateforme Mefali propose désormais **deux évaluations ESG distinctes**, chacune
avec son propre référentiel, son propre score, son propre rapport et son propre
chemin produit. Cette note explique quand utiliser laquelle, comment l'interface
les différencie et comment les deux scores cohabitent dans le matching.

---

## En une ligne

| Si la PME … | Lance | Référentiels | Page |
|---|---|---|---|
| veut un score ESG global de son **entreprise** (crédit bancaire, dashboard) | `ESGAssessment` (F05/F13) | Mefali / GRI 2021 | `/esg` |
| veut postuler un **projet vert** à un bailleur (GCF, BOAD, AFD) | `ProjectEsgAssessment` (F047) | IFC PS / GCF ESS / BOAD ESS | `/profile/projects/[id]/esg` |

Les deux évaluations sont **indépendantes** : on peut avoir l'une sans l'autre,
ou les deux pour la même PME. Elles n'interfèrent **jamais** entre elles dans le
calcul de score.

---

## ESG entreprise (F05 / F13) — diagnostic interne

**Cible** : l'entreprise dans son ensemble (PME, secteur informel inclus).

**Référentiels disponibles** :
- **Mefali** (interne, défaut, calibré contexte UEMOA) — 30 critères E/S/G pondérés.
- **GRI 2021** (universel, reporting volontaire).

**Usage typique** :
- La PME vient se diagnostiquer pour comprendre où elle en est sur les piliers
  E (environnement), S (social), G (gouvernance).
- L'évaluation alimente le **score crédit alternatif** (F13/F45) si la PME demande
  un prêt bancaire ou veut suivre son progrès dans le temps.
- Score utilisé dans le matching projet (F045) comme sub-score `company_score`
  (poids 0,30 pilier ESG entreprise).

**Composants UI** :
- Page `/esg` — wizard `<EsgWizard>` (F05), `<EsgScoreCard>`, `<EsgPillarBreakdown>`.
- Badge **« ESG Entreprise »** (variant `entreprise` du `<EsgTargetBadge>` ajouté en 047).

**Rapport PDF** : généré via `/api/reports/esg/{id}/generate` (F13/F21) — modèle
classique 9 sections, annexe sources F01.

---

## ESG projet (F047) — évaluation d'un projet vert spécifique

**Cible** : un projet vert individuel d'une PME (agroforesterie, micro-hydro,
recyclage, etc.), pas l'entreprise.

**Référentiels disponibles** (seed `seed_sources_047.py`) :
- **IFC PS** (Performance Standards 2012) — universel, ~16 critères, fallback par
  défaut quand le bailleur n'a pas son propre référentiel ESS.
- **GCF ESS** (Environmental & Social Policy 2018) — ~15 critères, requis pour
  postuler au Green Climate Fund.
- **BOAD ESS** (procédures 2023) — ~15 critères, requis pour la Banque Ouest
  Africaine de Développement.

**Usage typique** :
- La PME veut postuler un projet précis à un bailleur vert (GCF, FEM, BOAD, AFD).
- Le LLM demande **« contre quel référentiel ? »** ou l'infère depuis le contexte
  (« je veux postuler au GCF » → GCF ESS).
- Le score 0..100 calculé alimente :
  - Le sub-score `project_esg` du matching projet-centric (poids 0,10 — F045).
  - Le rapport ESIA-light PDF (US3, 7 sections + annexe F01).
  - Le dossier de candidature généré pour le bailleur.

**Composants UI** :
- Page `/profile/projects/[id]/esg` — wizard `<ProjectEsgWizard>`,
  `<EsgReferentialPicker>`, `<EsgCriterionWidget>`, `<EsgScoreDisplay>`,
  `<EsgReportPreview>`.
- Badge **« ESG Projet »** (variant `projet` du `<EsgTargetBadge>`) affiché en
  haut du wizard pour éviter la confusion R1.
- Lien depuis la fiche projet `/profile/projects/[id]/index.vue` : section
  « ESG Projet » avec bouton « Démarrer l'évaluation ».

**Rapport PDF** : généré via `POST /api/projects/{id}/esg-assessment/{aid}/report`
ou — côté chat LLM — via le tool LangChain `generate_project_esg_report(assessment_id=…)`.
Modèle ESIA-light 7 sections (executive summary, description projet, baseline
E&S, impacts, mesures d'atténuation, plan d'engagement, M&E) + annexe sources F01
+ donut « critères couverts vs manquants ». p95 < 30 s pour 20 critères + 3
graphiques.

**Format du fichier** : **PDF** (`.pdf`) — volontaire. Les bailleurs verts
(GCF, BOAD, AFD, etc.) imposent quasi-systématiquement le PDF pour leurs
dossiers de candidature. Le rapport **ESG entreprise** F05 est lui en
`.docx` (Word) car destiné à un usage interne / bancaire où l'édition reste
nécessaire. **Ne pas confondre les deux** : si l'utilisateur demande
« rapport ESIA-light / dossier bailleur / rapport ESG-projet », le LLM doit
appeler `generate_project_esg_report` (PDF F047), pas `generate_esg_report`
(.docx F05).

Le fichier est écrit dans
`backend/uploads/reports/esia/{account_id}/{project_id}/esia_{assessment_id}_{timestamp}.pdf`.

---

## Comment les deux scores cohabitent dans le matching

Le matching projet-centric (F045) combine **2 scores séparés** affichés côte à
côte dans `<DualScoreDisplay>` :

```
project_score  = f(sector, taxonomy, gcf_themes, co2_impact, beneficiaries,
                   gender, vulnerable, project_esg)   ← consomme ProjectEsgAssessment
company_score  = f(sector, esg, size, location, documents, instrument)
                                                      ← consomme ESGAssessment
```

- **`project_esg` sub-score (poids 0,10 dans `project_score`)** : alimenté par
  `ProjectEsgAssessment.score` du référentiel ciblé par le fonds (GCF→GCF ESS,
  BOAD→BOAD ESS, autres→IFC PS fallback). Si aucune évaluation correspondante
  n'existe, sub-score = 0 + CTA « Démarrer l'évaluation ».
- **Le pilier `esg` de `company_score` (poids 0,30)** : alimenté par
  `ESGAssessment` Mefali — entièrement indépendant de `ProjectEsgAssessment`.

**Cascade priorité du sub-score `project_esg`** (FR-029) :

```
1. ProjectEsgAssessment finalized du référentiel cible          (calculated)
2. ProjectEsgAssessment finalized IFC PS fallback                (calculated + is_fallback)
3. projects.project_esg_score (saisie manuelle F045 héritée)    (manual_f045)
4. 0 + unsourced + CTA « Démarrer l'évaluation »                (unsourced)
```

Tant qu'une évaluation finalisée existe, **toute tentative API de modifier
`projects.project_esg_score` retourne 409** (FR-033, Q6) avec le message :
> « Une évaluation ESG-projet finalisée existe pour ce projet. Veuillez la
> supprimer ou ré-évaluer pour modifier le score manuel. »

---

## Cas d'usage support / FAQ

### « J'ai déjà fait mon évaluation ESG, pourquoi on me redemande pour mon projet ? »

Parce que ce sont **deux évaluations différentes**. La première (entreprise, F05)
mesure votre maturité globale ; la seconde (projet, F047) mesure les impacts E&S
spécifiques de votre projet vert candidat au financement. Le bailleur (GCF, BOAD)
exige la **seconde**, pas la première.

### « Je veux faire les deux, par où commencer ? »

1. Faire d'abord l'**ESG entreprise** (F05, page `/esg`) — utile dashboard,
   rapport bancaire, suivi maturité.
2. Créer ensuite un **projet vert** (`/profile/projects/new`) si vous avez un
   projet à financer.
3. Faire l'**ESG projet** (`/profile/projects/[id]/esg`) contre le référentiel
   du bailleur visé.

### « Je peux supprimer mon évaluation projet ? »

Oui, via `DELETE /api/projects/{id}/esg-assessment/{aid}` (ou bouton dans l'UI).
Le snapshot `projects.project_esg_score` est alors **automatiquement remis à jour**
par le listener D8 : il retombe sur la valeur précédente (autre évaluation
finalisée s'il y en a) ou sur NULL.

### « Le LLM peut-il faire l'évaluation pour moi ? »

Oui. Skill F23 `skill_project_esg_assessment` (statut publié après gating eval ≥
90 %) — depuis le chat, sur la page d'un projet, tapez « Évalue mon projet contre
[IFC PS | GCF ESS | BOAD ESS] ». Le LLM enchaîne les critères via widgets F18,
exige une source F01 à chaque réponse, et finalise. Budget : ≤ 12 widgets, ≤ 3
tours utilisateur (SC-006).

> **Note technique (bugfix 2026-05-22)** : sur la fiche projet
> `/profile/projects/{id}` (sans le suffixe `/esg`), `_route_esg_target`
> renvoie `"company"` et `_detect_esg_request` ne capture pas les mots-clés
> bailleurs (IFC PS, GCF ESS, BOAD ESS). Le LLM reste donc sur `chat_node`,
> qui possède bien les 5 tools F047 via `PAGE_TOOL_MAPPING['profile_projects']`.
> Pour empêcher le LLM de bifurquer vers `ask_interactive_question` au lieu
> d'appeler `create_project_esg_assessment`, deux garde-fous ont été ajoutés :
> (1) la procédure du skill F23 est désormais **impérative** (« TU DOIS …
> AVANT toute autre action ») ; (2) `chat_node` injecte une directive
> page-contextuelle quand `current_page` matche une fiche projet ET le dernier
> message exprime une intention ESG-projet (`_detect_project_esg_intent`).
> Cf. `backend/app/graph/nodes.py` (helpers `_detect_project_esg_intent`,
> `_is_project_page`, constante `_PROJECT_ESG_DIRECTIVE`) et
> `tests/modules/esg/project/test_project_esg_chat_dispatch.py`.

> **Note technique (bugfix 2026-05-23 — US3 hallucination)** : avant ce
> correctif, le LLM affirmait « le rapport ESIA-light est généré » sans
> appeler `generate_project_esg_report` (aucune ligne dans `tool_call_logs`,
> aucun PDF sur disque). Cause racine : (a) le LLM n'avait aucun moyen
> simple d'obtenir des `criterion_id` valides → il hallucinait des UUIDs
> qui étaient silencieusement rejetés par `save_project_esg_criterion` ;
> (b) la docstring de `generate_project_esg_report` n'interdisait pas
> explicitement l'auto-déclaration sans tool call. Trois mesures :
> (1) `create_project_esg_assessment` et `get_project_esg_assessment`
> retournent désormais `applicable_criteria` (id+code+label+is_required+
> weight) en plus du `assessment` — le LLM n'a plus à deviner ; (2) la
> docstring de `generate_project_esg_report` contient une clause
> ANTI-HALLUCINATION explicite ; (3) `_PROJECT_ESG_DIRECTIVE` inclut
> désormais une **séquence complète typique** (a→f) et un rappel
> « N'AFFIRME JAMAIS que le rapport est généré sans tool call ». Script
> de synchronisation : `python -m app.scripts.sync_skill_project_esg`
> pour aligner la BDD avec la nouvelle procedure du skill F23.

### « Score différent selon le référentiel pour le même projet, c'est normal ? »

Oui. IFC PS, GCF ESS et BOAD ESS ne pondèrent pas les mêmes critères, n'ont pas
les mêmes seuils, ni les mêmes obligations. Un projet peut scorer 75/100 contre
IFC PS et 60/100 contre GCF ESS — la valeur informe sur l'adéquation au
référentiel visé, pas sur la « qualité absolue » du projet.

---

## Références

- Spec : `specs/047-evaluation-esg-projet/spec.md`
- Plan : `specs/047-evaluation-esg-projet/plan.md`
- Tasks : `specs/047-evaluation-esg-projet/tasks.md`
- Quickstart : `specs/047-evaluation-esg-projet/quickstart.md`
- Migration : `backend/alembic/versions/047_project_esg_assessments.py`
- Skill F23 : `backend/app/modules/skills/seed.py` → `skill_project_esg_assessment`
- Sources F01 seedées : `backend/app/scripts/seed_sources_047.py`
- Matching projet-centric : `docs/matching-projet-centric.md`
- Financement consolidé : `docs/financing.md`
