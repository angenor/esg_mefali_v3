# Prompt speckit — 047-evaluation-esg-projet

À coller directement dans une session Claude Code sur la branche `047-evaluation-esg-projet`.

---

```
/speckit.specify

Feature : 047-evaluation-esg-projet — Évaluation ESG-projet (extension F05 au mode projet)

## Contexte métier (à reprendre tel quel dans spec.md §Contexte)

ESG Mefali expose aujourd'hui deux notions ESG distinctes mais incohérentes par rapport au métier réel des bailleurs verts :

1. **`ESGAssessment` (F05)** : évaluation entreprise sur 30 critères E-S-G sectoriels, scoring automatisé via `esg_scoring_node` LangGraph, rapport PDF WeasyPrint, alimente le pilier `esg` (poids 0.30) du `company_score` du matching F14/F045. Référentiels disponibles via F13 : Mefali, GCF, IFC PS, BOAD ESS, GRI 2021.

2. **`project_esg_score` (F045)** : simple colonne `INT NULL` (0..100) sur la table `projects`, saisie manuelle par la PME, alimente le sub-score `project_esg` (poids 0.10) du `project_score` F045.

Cette dualité est inversée par rapport au marché. Les bailleurs cibles (GCF, FEM, Fonds d'Adaptation, BOAD, AFD, Banque mondiale) **n'évaluent pas l'ESG corporate** des PME quand ils étudient un dossier de financement vert. Ils évaluent le **risque et l'impact environnemental & social du PROJET** via des référentiels normalisés au niveau projet :

| Référentiel | Niveau | Statut F13 actuel |
|---|---|---|
| IFC Performance Standards (PS1-PS8) | Projet | ✅ Seedé F13 |
| GCF Environmental & Social Safeguards (ESS) | Projet | ✅ Seedé F13 |
| BOAD Environmental & Social Standards (ESS) | Projet | ✅ Seedé F13 |
| World Bank ESF (10 ESS) | Projet | ❌ Pas seedé (hors-scope MVP) |
| Equator Principles | Projet | ❌ Pas seedé (hors-scope MVP) |
| GRI 2021 | Entreprise (reporting) | ✅ Seedé F13 |
| Mefali | Entreprise/Projet (interne) | ✅ Seedé F13 |

Livrables E&S typiquement demandés par un fonds GCF/FEM/BOAD :
- ESIA (Environmental & Social Impact Assessment) du projet
- Plan d'engagement des parties prenantes du projet
- Mécanisme de griefs du projet
- Plan d'action genre du projet (cohérence avec F045 `gender_inclusion`)
- Plan de réinstallation involontaire si applicable
- Système de gestion E&S du projet

Aucun de ces livrables ne porte sur l'entreprise globale. Une coopérative agricole informelle au Togo n'a pas de système de management ESG corporate — mais son projet d'agroforesterie 200 ha doit absolument produire un ESIA pour être éligible GCF.

## Objectif de la feature

Étendre l'évaluation ESG au niveau projet : adapter ou décliner `esg_scoring_node` pour qu'il puisse **évaluer un projet vert** contre IFC PS, GCF ESS ou BOAD ESS (référentiels déjà seedés F13), produire un **score ESG-projet calculé** (pas saisie manuelle), un **rapport ESIA-light PDF** consommable par le bailleur, et **remplacer le sub-score `project_esg`** du matching F045 par cette évaluation. F05 entreprise reste intact comme module satellite (reporting GRI, crédit bancaire classique, score corporate pour bailleurs qui le demandent).

## User Stories (à raffiner en acceptance scenarios complets)

**US1 (Priority P1) — PME informelle évalue son projet ESG sans bilan entreprise**

Une coopérative agricole au Togo sans `ESGAssessment` entreprise finalisée porte un projet d'agroforesterie 200 ha (taxonomie verte UEMOA alignée, thèmes GCF atténuation+REDD+, 850 femmes bénéficiaires). Elle veut savoir si son projet est bancable pour GCF. Elle déclenche l'évaluation ESG-projet contre le référentiel IFC PS depuis la fiche projet ou le chat. Le système collecte progressivement ses réponses sur ~15-20 critères E&S projet (impact biodiversité, gestion eau, dialogue communautés, intégration genre, suivi M&E…), score le projet 0..100, identifie les critères à renforcer avec sources F01 cliquables, et persiste le score qui alimente immédiatement le sub-score `project_esg` du matching F045. Indépendant du score entreprise.

Why P1 : c'est le cas d'usage central qui justifie la feature. Sans ça, la feature n'a pas de raison d'être. Permet à une PME informelle d'obtenir une éligibilité GCF/FEM crédible.

Independent test : créer un compte PME sans ESGAssessment, créer un projet vert minimal, déclencher `POST /api/projects/{id}/esg-assessment?referential=ifc_ps`, compléter ≥ 15 critères, vérifier `POST /finalize` retourne score 0..100 et que `match_funds_for_project` reflète ce score dans `project_score_breakdown.project_esg` au prochain appel.

**US2 (Priority P1) — Le matching projet-centric pilote le référentiel selon le fonds ciblé**

Quand la PME ouvre `match_funds_for_project` pour un fonds GCF, le sub-score `project_esg` doit être calculé contre **GCF ESS** automatiquement (pas Mefali ni IFC). Pour un fonds BOAD, contre **BOAD ESS**. Pour un fonds sans référentiel ESS déclaré, fallback IFC PS. Cohérent avec F13 `compute_referential_score_for_offer` qui fait déjà ce pattern côté entreprise. La PME peut donc avoir plusieurs `ProjectEsgAssessment` (un par référentiel) et le matching choisit celle qui correspond au fonds matché. Si aucune évaluation n'existe pour le référentiel cible, l'UI propose un CTA « Démarrer l'évaluation ESG-projet contre {référentiel} » et le sub-score tombe à 0 avec flag `unsourced=true`.

Why P1 : sans ça, la feature ne livre pas le rebranchement attendu côté matching F045. C'est le pont qui transforme l'évaluation en valeur métier mesurable.

Independent test : créer 2 ProjectEsgAssessment finalisées sur un même projet (IFC PS et GCF ESS, scores différents). Lancer `POST /match-funds` ciblant un fonds GCF. Vérifier que le `project_score_breakdown.project_esg.score` reflète la GCF ESS, pas IFC PS. Refaire pour un fonds BOAD et vérifier que c'est BOAD ESS.

**US3 (Priority P2) — Rapport ESIA-light PDF généré pour bailleur**

Une fois l'évaluation projet finalisée, la PME peut générer un dossier ESIA-light PDF structuré en 5-7 sections : executive summary, description du projet, baseline E&S, impacts identifiés (positifs et négatifs), mesures d'atténuation, plan d'engagement parties prenantes, indicateurs de suivi M&E. Réutilise le pipeline WeasyPrint + Jinja2 + matplotlib de F06 (rapports ESG entreprise) avec un template `_esia_report.html` dédié. Annexe sources F01 obligatoire. Document consommable directement par l'analyste GCF/FEM/BOAD.

Why P2 : différenciant fort mais peut être livré après US1+US2 qui constituent le MVP fonctionnel. Le score sans rapport est déjà utilisable côté matching.

Independent test : pour un projet avec ProjectEsgAssessment finalisée, appeler `POST /api/projects/{id}/esg-assessment/{assessment_id}/report` et vérifier que le PDF retourné contient les 7 sections + annexe sources F01 + ≥ 1 graphique (donut critères couverts vs manquants).

**US4 (Priority P2) — LLM orchestre l'évaluation depuis le chat**

Depuis le chat, la PME peut dire « Évalue l'ESG de mon projet d'agroforesterie pour GCF ». Le LLM via le skill F23 `skill_project_esg_assessment` :
1. Appelle `list_projects` pour identifier le projet (widget F18 qcu si plusieurs)
2. Appelle `create_project_esg_assessment(project_id, referential='gcf_ess')`
3. Pose les critères un par un via widgets F18 (qcu/qcm/justification selon type de critère)
4. Cite les sources F01 obligatoires (validator `source_required.py` actif)
5. Appelle `finalize_project_esg_assessment` quand tous les critères sont collectés
6. Affiche un bloc visualisation F11 avec score + missing criteria + lien rapport ESIA
7. Relance `match_funds_for_project` automatiquement pour montrer l'impact sur le matching

Why P2 : aligne la feature sur l'identité conversationnelle de Mefali, mais peut être livré après US1+US2 qui supportent déjà l'évaluation via UI/API.

Independent test : démarrer une conversation chat fraîche sur `/profile/projects/[id]`, taper « Évalue mon projet contre GCF ESS », vérifier que le LLM enchaîne create_project_esg_assessment → ≥ 5 widgets F18 → finalize → bloc F11 affiché → match-funds relancé automatiquement.

**US5 (Priority P3) — Migration douce du champ F045 `project_esg_score`**

Le champ `project_esg_score INT NULL` (héritage F045 saisie manuelle) devient un cache lecture seule alimenté par listener `after_update`/`after_insert` SQLAlchemy sur `ProjectEsgAssessment`. Les anciennes valeurs saisies manuellement F045 restent en BDD (cohabitation 2 sprints). Le matching F045 priorise `ProjectEsgAssessment.score` (calculé) si existe, sinon fallback `projects.project_esg_score` (saisie F045), sinon 0 + unsourced. L'UI du formulaire edit projet n'expose plus le champ saisie manuelle (mais le backend l'accepte encore via API pour rétrocompat). Après 2 sprints, suppression possible de la colonne F045 via feature de cleanup hors-scope 047.

Why P3 : finition propre mais pas bloquante pour les autres user stories. Peut atterrir en fin de sprint.

Independent test : créer un projet avec `project_esg_score=42` (saisie F045 héritée), lancer une ProjectEsgAssessment IFC PS finalisée avec score 78, vérifier que `matching_service._compute_project_score` utilise 78 (pas 42). Reset l'évaluation, vérifier que le matching retombe sur 42 (fallback F045) puis 0+unsourced après suppression de l'assessment et reset de `project_esg_score`.

## Périmètre

**Dans :**
- Pipeline d'évaluation ESG-projet (nouveau ou branche conditionnelle de `esg_scoring_node`)
- 3 référentiels MVP : IFC PS (8 standards → ~15-20 critères projet), GCF ESS (6 standards → ~15-20 critères), BOAD ESS (~15 critères)
- Schema BDD pour persister les évaluations projet (option A/B/C à clarifier)
- Tools LangChain : `create_project_esg_assessment`, `save_project_esg_criterion`, `finalize_project_esg_assessment`, `get_project_esg_assessment`, `list_project_esg_assessments`
- Prompts FR avec sourçage F01 obligatoire
- Page Vue dédiée (URL à clarifier) + composants `<ProjectEsgWizard>`, `<EsgCriterionWidget>`, `<EsgReferentialPicker>`, `<EsgReportPreview>`
- Composable `useProjectEsg.ts`, store Pinia `projectEsg.ts`
- Rapport ESIA-light PDF (WeasyPrint + Jinja2 + matplotlib SVG)
- Skill F23 `skill_project_esg_assessment` (draft initial, gating eval ≥ 90 %)
- Intégration matching F045 (consommation du score calculé via `compute_referential_score_for_offer` côté projet)
- Sources F01 nouvelles à seeder (IFC PS officiel, GCF ESS 2022, BOAD ESS) via `seed_sources_047.py` idempotent
- Tests unit + integration + E2E avec coverage ≥ 80 % sur modules nouveaux

**Hors-scope (à exclure explicitement) :**
- Refonte de F05 entreprise (reste tel quel — `ESGAssessment.target_kind='company'` par défaut si polymorphisme retenu)
- Référentiels au-delà des 3 MVP (World Bank ESF, Equator Principles, GRI projet, Verra → post-MVP)
- Certification tierce ou audit externe automatisé
- Synchronisation auto avec systèmes externes (SIGI, OpenESG, etc.)
- Suppression de la colonne F045 `projects.project_esg_score` (différée 2 sprints minimum)
- Multi-langue (français uniquement en MVP, anglais post-MVP)
- Évaluation comparative projet vs projet (post-MVP)
- Versioning des évaluations projet (1 évaluation = 1 snapshot, ré-évaluation crée nouvelle ligne)

## Fondations transverses à respecter (non-négociable)

- **F01 sourçage** : validator `source_required.py` actif sur chaque critère. Retry 1x puis fallback texte. Sources F01 nouvelles seedées avec four-eyes (captured_by ≠ verified_by).
- **F02 multi-tenant + RLS** : nouvelles tables avec `account_id UUID NOT NULL`, `ENABLE + FORCE` RLS, 2 policies minimum (pme_access_own_account, admin_full_access). Cf. RLS bypass identifiés dans la security review F045 — à ne pas reproduire.
- **F03 audit log append-only** : nouvelles entités auditées via `Auditable` mixin si elles sont user-facing (créées/modifiées par PME). Triggers PL/pgSQL existants couvrent automatiquement.
- **F04 Money typed** : si critères incluent estimations de coûts (ex. budget plan d'atténuation), utiliser `Money` (Decimal + Currency).
- **F11 visualisation** : score projet ESG affiché via `show_kpi_card`, comparaison référentiels via `show_comparison_table`, missing criteria via `<MissingProjectCriteriaList>` (réutilise composant F045).
- **F12 mémoire contextuelle** : conversations d'évaluation ESG-projet doivent rester traçables via `recall_history` pour reprise multi-session.
- **F13 référentiels** : réutiliser `ReferentialScore` ou son pattern. `compute_referential_score_for_offer` à étendre côté projet.
- **F18 widgets interactifs** : tous les critères posés par le LLM doivent passer par `ask_interactive_question` (qcu, qcm, qcu_justification, qcm_justification). 1 question pending max/conversation.
- **F23 skills** : nouveau skill draft initial, gating eval ≥ 90 % avant published.
- **F045 matching projet-centric** : le sub-score `project_esg` du `PROJECT_SCORE_WEIGHTS` consomme désormais l'évaluation calculée. Aucun changement de poids (reste 0.10).

## Contraintes techniques

- **Backward compat F045** : colonne `projects.project_esg_score INT NULL` conservée 2 sprints. Listener SQLAlchemy met à jour la colonne snapshot quand une ProjectEsgAssessment est finalisée (debounce 30s in-process si pattern F045 réutilisé).
- **Backward compat F05** : `ESGAssessment` entreprise inchangée, `esg_scoring_node` doit router intent projet vs entreprise sans casser les flux existants. Si polymorphisme retenu (option A clarify), ajouter `target_kind: Literal['company','project']` avec default 'company' et `target_project_id UUID NULL` avec CHECK XOR (`target_project_id IS NULL XOR target_company_id IS NULL`).
- **Migration Alembic** : round-trip up/down/up validé sur PostgreSQL réelle. Backfill : aucune row à backfiller si nouvelle table dédiée ; si polymorphisme, les rows existantes restent `target_kind='company'` par défaut.
- **Performance** : finalisation d'une évaluation projet ≤ 3s (calcul score + UPSERT + listener async). Rapport ESIA-light PDF ≤ 30s pour un projet avec 20 critères + 3 graphiques.
- **Tests baseline** : 0 régression sur les 3136 tests passing actuels. Suite full pytest -x doit rester verte.
- **Coverage** : ≥ 80 % sur modules nouveaux (`app/modules/esg/project_*.py`, composants Vue F047).
- **Dark mode** : obligatoire sur tous les nouveaux composants Vue (`bg-white dark:bg-dark-card`, etc.) — cf. CLAUDE.md.
- **Accessibilité** : ARIA labels FR complets, navigation clavier, focus visible (Tailwind `focus:ring-emerald-500`).

## Critères de succès mesurables

- **SC-001** : Une PME informelle sans ESGAssessment entreprise peut compléter une évaluation ESG-projet contre IFC PS en < 8 minutes via chat, mesuré sur 5 tests utilisateurs simulés (E2E Playwright).
- **SC-002** : Le sub-score `project_esg` du matching F045 reflète le résultat de la `ProjectEsgAssessment` finalisée (pas la saisie manuelle F045) pour ≥ 95 % des projets ayant ≥ 1 évaluation finalisée. Mesuré par un test d'intégration sur 20 projets fixtures.
- **SC-003** : Rapport ESIA-light PDF généré en < 30s pour un projet avec 20 critères + 3 graphiques + annexe sources F01. Mesuré par benchmark pytest-benchmark.
- **SC-004** : Couverture tests ≥ 80 % sur les nouveaux modules backend (`app/modules/esg/project_*.py`) et frontend (composants F047). Mesuré par `pytest --cov` et `npx vitest run --coverage`.
- **SC-005** : 0 régression sur la suite pytest baseline (3136 tests passing) et sur F05 entreprise (tests existants). Mesuré par CI complet.
- **SC-006** : Le LLM via skill F23 enchaîne l'évaluation complète en ≤ 12 widgets F18 et ≤ 3 tours conversation utilisateur. Mesuré par fixture E2E Playwright.
- **SC-007** : Round-trip Alembic up/down/up validé sur PostgreSQL réelle sans perte de données F045 existantes.

## Risques identifiés et atténuations

- **Risque 1 — Confusion utilisateur entre ESG entreprise et ESG projet.** Atténuation : libellés UI explicites (« ESG Entreprise » sur `/esg`, « ESG Projet » sur `/profile/projects/[id]/esg`). Composant `<EsgTargetBadge>` qui clarifie la cible. Documentation `docs/esg-projet-vs-entreprise.md`.
- **Risque 2 — Référentiels MVP mal calibrés (trop nombreux critères = abandon, trop peu = pas crédible bailleur).** Atténuation : research.md R2 documente la sélection critère par critère avec justification + source F01. Validation par un expert métier avant implémentation.
- **Risque 3 — Surcharge du `esg_scoring_node` qui devient polymorphe.** Atténuation : research.md R1 tranche entre node séparé et branche conditionnelle. Si branche conditionnelle, refactor strict avec ≤ 50 lignes par fonction.
- **Risque 4 — RLS bypass reproduits (cf. security review F045).** Atténuation : tous les endpoints du module nouveau doivent passer un test `test_*_rls.py` avec un compte tiers. Pattern strict : extraire `account_id` ET le propager à toutes les queries service.
- **Risque 5 — Régression matching F045.** Atténuation : tests d'intégration `test_match_funds_consumes_project_esg.py` qui valident la priorité d'usage entre évaluation calculée et fallback F045.

## Questions ouvertes (à traiter par /speckit.clarify automatique)

Q1 — Modèle de données : (A) polymorphisme `ESGAssessment.target_project_id`, (B) nouvelle table `project_esg_assessments`, (C) réutilisation pure `ReferentialScore` F13 ?

Q2 — Sélection des critères MVP : qui valide la liste finale par référentiel (équipe métier ? expert externe ?) ? Quel niveau de détail (15, 20, 30 critères) ?

Q3 — Workflow de saisie : 100 % LLM via widgets F18, formulaire UI dédié, ou hybride (LLM pose les questions, UI permet édition manuelle) ?

Q4 — Choix du référentiel par défaut quand le matching cible un fonds sans ESS déclarée : IFC PS (le plus universel), Mefali (interne), ou ne pas calculer (sub-score 0+unsourced) ?

Q5 — Frontend URL : `/profile/projects/[id]/esg`, `/esg/projects/[id]`, ou section intégrée dans `/profile/projects/[id]/index.vue` ?

Q6 — Cohabitation `project_esg_score` (F045 manuel) vs `ProjectEsgAssessment.score` (047 calculé) : la saisie manuelle reste-t-elle modifiable après une évaluation finalisée, ou devient-elle figée (lecture seule) ?

Q7 — Régénération du rapport ESIA : à chaque finalisation (auto) ou à la demande de la PME (CTA explicite) ?

Q8 — Score 0..100 d'un projet ESG : pondération des critères (égale ? pondérée par référentiel ? pondérée par sévérité) ?

---

Génère le `spec.md` complet avec :
- Tous les éléments ci-dessus structurés en sections normalisées speckit
- Acceptance scenarios détaillés Given/When/Then pour chaque user story
- Functional Requirements FR-001..FR-NN traçables vers les user stories
- Tableau Success Criteria avec métriques mesurables
- Section "Clarifications" vide (à remplir par /speckit.clarify)
- Section "Open Questions" reprenant Q1-Q8
- Header avec branch `047-evaluation-esg-projet`, status Draft, date du jour
```

---

## Notes complémentaires

- **Sprint name imposé** : `047-evaluation-esg-projet` (migration 046 utilisée par F045, prochaine = 047)
- **Branche git** : `git checkout -b 047-evaluation-esg-projet` depuis `main`
- **Lancement** : copier-coller le bloc dans une session Claude Code, le reste du workflow (`/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) suivra automatiquement à partir du spec.md généré
- **Tests baseline actuels** : 3136 passed / 201 failed (la plupart pré-existants à F045, voir `/tmp/pytest_full2.log`)
- **Composants F045 à réutiliser** : `<DualScoreDisplay>`, `<DivergenceBadge>`, `<MissingProjectCriteriaList>`, `<SourceLink>`
- **Risque principal à surveiller** : confusion UX entre ESG entreprise et ESG projet — bien séparer les libellés et les pages
