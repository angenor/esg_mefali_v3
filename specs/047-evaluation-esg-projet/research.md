# Phase 0 — Research & Décisions Techniques

**Feature** : 047-evaluation-esg-projet
**Date** : 2026-05-21

Toutes les questions critiques structurantes ont été résolues par `/speckit.clarify` (cf. spec §Clarifications) :
- Q1 — Modèle de données : nouvelle table dédiée `project_esg_assessments`
- Q3 — Workflow saisie : hybride LLM widgets F18 + wizard UI éditable
- Q4 — Référentiel de repli : IFC PS universel + flag `is_fallback=true`
- Q6 — Cohabitation F045 : figée 409 quand évaluation finalisée existe
- Q8 — Pondération : par référentiel via `criterion.weight` F13

Les questions Q2, Q5, Q7 différées sont traitées ci-dessous (D2, D3, D4) car elles s'attaquent à des choix techniques structurants restants ou à des décisions d'implémentation produit.

---

## D1 — Stratégie d'orchestration LangGraph : noeud séparé vs branche conditionnelle de `esg_scoring_node`

**Decision** : **Branche conditionnelle dans `esg_scoring_node` existant**, avec extraction d'un helper privé `_route_esg_target(state)` qui dispatch entre `_score_company` (logique F05 inchangée) et `_score_project` (nouveau pipeline 047). Pas de nouveau noeud LangGraph.

**Rationale** :
- F05 entreprise utilise `esg_scoring_node` comme point d'entrée unique du graphe. Ajouter un noeud séparé `project_esg_scoring_node` doublerait les routes d'orchestration côté `tool_selector_config.py` et augmenterait la surface d'erreur de routing intention.
- Le dispatcher conditionnel est strictement borné (≤ 30 lignes) et chacune des deux branches reste indépendamment ≤ 50 lignes (respect contrainte constitutionnelle VII Limites de taille).
- Permet de partager la même mémoire contextuelle F12 et le même `tool_call_logs` sans duplication.
- F045 a déjà cette signature (`_compute_project_score` et `_compute_company_score` dans `matching_service.py`) ; on reproduit le pattern éprouvé.

**Alternatives rejetées** :
- Noeud séparé `project_esg_scoring_node` : refactor plus profond de `nodes.py` + risque de divergence des deux pipelines au fil du temps. Plus de code à maintenir.
- Polymorphisme via héritage Python (classe abstraite `EsgScorer` + 2 sous-classes) : sur-ingénierie pour 2 cas seulement (constitution VII : « pas d'abstraction prématurée »).

**Mitigation R3 (surcharge `esg_scoring_node`)** : `_score_company` et `_score_project` extraits comme fonctions privées dédiées, ≤ 50 lignes chacune. Test conformity `test_esg_scoring_node_dispatch.py` vérifie qu'aucune mutation de F05 ne pollue les branches projet.

---

## D2 — Sélection des critères MVP par référentiel (Q2 différée → ici)

**Decision** : **15-18 critères par référentiel MVP**, alignés sur les standards officiels :

| Référentiel | Couverture | Nb critères MVP | Source F01 |
|---|---|---|---|
| **IFC Performance Standards** | PS1 (Assessment & Management), PS2 (Labor), PS3 (Resource Efficiency), PS4 (Community Health & Safety), PS5 (Land Acquisition & Resettlement), PS6 (Biodiversity), PS7 (Indigenous Peoples), PS8 (Cultural Heritage) | **16** (2 par standard, agrégés en sous-critères opérables par PME informelle) | `ifc-performance-standards-2012` (IFC.org) |
| **GCF Environmental & Social Safeguards (ESS)** | ESS1 (Risk Assessment), ESS2 (Stakeholder Engagement), ESS3 (Gender), ESS4 (Indigenous Peoples), ESS5 (Resettlement), ESS6 (Climate Adaptation Co-benefits) | **15** (2-3 par standard) | `gcf-environmental-social-policy-2018` (GCF.org) |
| **BOAD Environmental & Social Standards** | 10 ESS aligné Banque mondiale ESF + spécificités UEMOA | **15** (concentration sur ESS1, ESS5, ESS9 i.e. genre, intermédiaires financiers, ouverture stakeholders) | `boad-ess-procedures-2023` (BOAD.org) |

**Total catalogue F13** : ~46 nouveaux critères seedés via `seed_sources_047.py` (idempotent).

**Validation métier** :
- Liste finale validée en interne par l'équipe ESG Mefali (responsable produit + lead pre-vente bailleurs verts).
- Validation externe (consultant E&S certifié IFC) prévue avant publication du skill F23 (gating eval ≥ 90 %), pas avant livraison du MVP 047 (les évaluations en mode draft pendant la validation sont acceptables).

**Rationale** :
- 15-18 critères représentent ~6-8 minutes d'évaluation via chat (SC-001 cible < 8 min), avec ≤ 12 widgets F18 actifs (SC-006), respecte budget MAX_TOOLS_PER_TURN=14.
- Plage 15-18 reste suffisamment dense pour produire un rapport ESIA-light crédible côté bailleur (≥ 1 critère par standard couvert + au moins 1 critère de redondance pour calibrer le score).
- Les critères concentrent les questions à fort signal métier (gestion eau, dialogue communautés, genre, M&E) et excluent les sous-points purement procéduraux (qui sont déjà couverts par les éléments d'engagement type ESIA).

**Alternatives rejetées** :
- 30 critères par référentiel : friction utilisateur, abandon prévisible avant finalisation (SC-001 raté).
- < 10 critères : pas crédible côté bailleur (rapport ESIA-light vide, sans diagnostic différencié par standard).
- Validation externe avant MVP : retarde la livraison, alors que le skill F23 reste en `draft` jusqu'à la validation (gating eval).

---

## D3 — Frontend URL pattern (Q5 différée → ici)

**Decision** : **`/profile/projects/[id]/esg`** — page Vue dédiée sous l'arborescence projet existante.

**Rationale** :
- Cohérence avec l'arborescence F045 `/profile/projects/[id]/index.vue` (fiche projet) : l'évaluation ESG-projet est conceptuellement une **propriété du projet**, pas un module séparé.
- Distinction nette avec `/esg` qui reste la page ESG entreprise (F05). Aucune ambiguïté côté breadcrumb : `Projets > {nom projet} > Évaluation ESG`.
- Le pattern `_PATH_TO_SLUG_PATTERNS` doit être enrichi : ajouter `^/profile/projects/[^/]+/esg(?:/|$)` AVANT `^/profile/projects(?:/|$)` pour router le LLM vers les bons tools.

**Alternatives rejetées** :
- `/esg/projects/[id]` : créerait une seconde top-level `/esg/*` mélangeant entreprise et projet ; aggravation de R1 (confusion UX).
- Section intégrée dans `/profile/projects/[id]/index.vue` : page principale projet deviendrait trop dense (déjà charge avec F045 DualScoreDisplay + projet info + financements). Cohérence visuelle dégradée.

---

## D4 — Régénération du rapport ESIA-light (Q7 différée → ici)

**Decision** : **À la demande explicite de la PME via un CTA dédié** (`<EsgReportPreview>` + bouton « Générer le rapport ESIA »). Pas de génération automatique à la finalisation.

**Rationale** :
- WeasyPrint + matplotlib coûte ~10-20 s par génération (cf. SC-003 ≤ 30 s). Générer à chaque finalisation alourdit la finalisation (SC-001 cible ≤ 3 s).
- La PME ne télécharge le rapport que pour un dossier bailleur concret (pas systématiquement). Un CTA explicite respecte la frugalité ressource (constitution VII : pas de calcul prématuré).
- Permet de proposer un preview structurel (sections, score, graphiques) avant le coût PDF, via `<EsgReportPreview>`.
- Le rapport est versionné par horodatage de génération ; chaque régénération produit un nouveau `ProjectEsgReport` traçable F03 (immuable).

**Alternatives rejetées** :
- Génération automatique à la finalisation : violente SC-001 (≤ 3 s), gaspille CPU si la PME ne télécharge pas.
- Génération différée en arrière-plan (Celery/Redis) : casse la frugalité MVP (constitution VII : « synchrone avant async »).

---

## D5 — Composants Vue réutilisés vs nouveaux

**Decision** :

| Composant | Source | Statut |
|---|---|---|
| `<DualScoreDisplay>` (`frontend/app/components/financing/DualScoreDisplay.vue`) | F045 (livré) | **Réutilisé** avec enrichissement mineur (T049) pour rendre le badge `is_fallback=true` — accepte déjà 2 scores avec breakdown |
| `<MissingProjectCriteriaList>` | F045 (livré) | **Réutilisé** sans modification — accepte critères F13 avec SourceLink |
| `<SourceLink>` | F01 (livré) | **Réutilisé** sans modification |
| `<MoneyDisplay>` | F04 (livré) | **Réutilisé** sans modification (budgets plan d'atténuation) |
| `<EsgTargetBadge>` | **NEW** | Crée 2 variants `company`/`project` (R1 mitigation, FR-042) |
| `<ProjectEsgWizard>` | **NEW** | Orchestrateur multi-étapes : choix référentiel → critères → revue → finalisation |
| `<EsgReferentialPicker>` | **NEW** | Liste IFC PS / GCF ESS / BOAD ESS avec descriptions FR + lien source F01 |
| `<EsgCriterionWidget>` | **NEW** | Un critère = libellé + widget F18 (qcu/qcm/justification) + SourceLink obligatoire |
| `<EsgScoreDisplay>` | **NEW** | Score 0..100 + breakdown par standard avec donut Chart.js |
| `<EsgReportPreview>` | **NEW** | Aperçu structuré 7 sections + bouton « Générer PDF » |
| `<ProjectEsgMatchImpact>` | **NEW** | Bloc « Impact sur le matching » (US4 étape 7) — réutilise `<DualScoreDisplay>` en sous-composant |

**Rationale** :
- Maximisation de la réutilisation F045 (cf. spec Assumptions). Aucune duplication.
- Les 7 nouveaux composants sont scopés à `frontend/app/components/esg/project/` pour isolation modulaire (constitution II).
- Dark mode et accessibilité ARIA FR appliqués systématiquement (FR-040, FR-041).

---

## D6 — Skill F23 `skill_project_esg_assessment` : golden examples

**Decision** : **4 golden examples** pour eval F23, mappés sur les user stories :

1. **GE-US1** : Coopérative agricole Togo, sans ESGAssessment entreprise, démarre évaluation IFC PS, complète 16 critères, finalise. Score attendu : 60-75.
2. **GE-US2** : PME avec 2 ProjectEsgAssessment finalisées (IFC PS 75, GCF ESS 60). Matching cible fonds GCF — attendu sub-score `project_esg=60`. Matching cible fonds BOAD — attendu CTA « démarrer évaluation BOAD ESS ».
3. **GE-US3** : PME finalise évaluation, demande rapport ESIA-light. PDF généré ≤ 30 s, contient 7 sections + annexe F01 + donut.
4. **GE-US4** : Conversation chat « Évalue mon projet d'agroforesterie pour GCF ». LLM enchaîne create → ≥ 5 widgets F18 → finalize → bloc F11 → matching relancé. Token budget respecté.

**Gating** : eval ≥ 90 % sur ces 4 golden examples avant publication du skill (`status='published'`). Tant que le score eval reste < 90 %, le skill reste en `draft` et n'est pas exposé au LLM en production (whitelist).

**Rationale** : alignement direct avec SC-008 (skill eval ≥ 90 %). 4 golden examples couvrent les 4 user stories majeures et incluent les pivots cross-functionality (chat ↔ matching ↔ PDF).

---

## D7 — Sources F01 nouvelles à seeder

**Decision** : **3 sources F01 obligatoires** seedées via `app/scripts/seed_sources_047.py` (idempotent, 4-yeux `captured_by ≠ verified_by`) :

| Source ID | Titre | URL/référence | Status cible |
|---|---|---|---|
| `ifc-performance-standards-2012` | IFC Performance Standards on Environmental and Social Sustainability (2012, version courante) | https://www.ifc.org/.../ifc-performance-standards | `verified` |
| `gcf-environmental-social-policy-2018` | GCF Revised Environmental and Social Policy (2018, incluant Gender Policy 2019) | https://www.greenclimate.fund/.../ess-policy | `verified` |
| `boad-ess-procedures-2023` | BOAD Procédures d'évaluation environnementale et sociale (2023, alignées Banque mondiale ESF) | https://www.boad.org/.../procedures-ess | `verified` |

Ces 3 sources alimentent les ~46 critères catalogués F13 (cf. D2). Pour chaque critère, le validator F01 `source_required.py` exige une citation explicite parmi ces 3 sources (ou une source plus spécifique parmi les ~30 sources déjà seedées F01 si pertinent).

**Rationale** :
- Gate SC-009 ≥ 95 % de critères avec source `verified` au go-live.
- 4-yeux respecté : captured par l'équipe Mefali ESG, vérifié par un second relecteur indépendant avant publication.
- Documents officiels publics → traçabilité maximale, citation reproductible (rapport ESIA-light annexe F01).

**Alternatives rejetées** :
- Sources secondaires (commentaires d'experts, papers académiques) en lieu et place des documents officiels : moins crédibles côté analyste bailleur, traçabilité plus faible.
- Création de nouvelles sources par critère (1 source = 1 critère) : duplication massive de la table `sources`, anti-pattern F01.

---

## D8 — Listener SQLAlchemy `after_insert/after_update` sur `ProjectEsgAssessment`

**Decision** : Listener Python in-process déclenché sur l'événement SQLAlchemy `event.listens_for(ProjectEsgAssessment, "after_update")` et `after_insert`. Le listener filtre sur la transition `state -> 'finalized'` puis :

1. UPDATE `projects.project_esg_score = NEW.score` (snapshot) pour le projet associé, **uniquement si NEW.state == 'finalized'**.
2. **Debounce in-process 30 s** par `project_id` (dict `{project_id: last_ts}` mémoire process) : évite N updates rapides si plusieurs ProjectEsgAssessment finalisent simultanément (par ex. lors d'un script de seed).
3. `asyncio.create_task` pour exécution non-bloquante (FR-032 : pas d'impact sur finalisation ≤ 3 s SC-001).

**Rationale** :
- Pattern réutilisé de F045 (listener after_update Project + debounce 30 s in-process) déjà éprouvé en production.
- Aucune dépendance externe (pas de Redis, pas de Celery → constitution VII).
- Le debounce in-process est volatile au restart du processus FastAPI : c'est acceptable car au restart la prochaine finalisation déclenchera correctement la mise à jour.
- Compatible avec multi-tenant F02 : le listener lit `account_id` depuis `ProjectEsgAssessment.account_id` et propage au UPDATE projects (RLS respecté).

**Alternatives rejetées** :
- Trigger PostgreSQL `AFTER INSERT/UPDATE` PL/pgSQL : harder to test, mauvaise lisibilité Python, casse compatibilité SQLite (tests).
- Job nightly de réconciliation : casse la garantie temps-réel attendue par US2 (matching consomme immédiatement le score finalisé).

---

## D9 — Pondération via `criterion.weight` F13

**Decision** : Le score 0..100 d'une `ProjectEsgAssessment` est calculé par la formule :

```
score = round(100 * Σ(response_value_i × criterion.weight_i) / Σ(criterion.weight_i))
```

où :
- `response_value_i` ∈ [0, 1] est la valeur normalisée de chaque réponse (calculée par `project_scoring.normalize_response(response, criterion.type)`)
- `criterion.weight_i` ∈ ℝ⁺ est le poids défini dans le catalogue F13 (table `criteria.weight`, déjà présent depuis F13)
- Seuls les critères répondus participent au calcul (les critères manquants sont identifiés séparément dans `missing_criteria`)

Les critères obligatoires (`is_required=true` dans F13) DOIVENT tous être répondus pour permettre la finalisation (FR-006). Si un critère obligatoire est manquant, la finalisation est refusée avec la liste explicite.

**Rationale** :
- Réutilise exactement le pattern `compute_referential_score_for_offer` (F13) côté entreprise — symétrie architecturale, code partagé via `app/lib/eval_matching.py` ou similaire.
- Pondération sourcée du catalogue F13 = pas de magie dans le code 047, configurabilité totale par les admins via `/admin/criteria`.
- Formule simple, transparente, testable unitairement (`test_project_scoring_weighted.py`).

**Alternatives rejetées** :
- Pondération codée en dur (constantes Python) : moins flexible, demande déploiement pour ajuster.
- Pondération multi-niveaux (par standard + par critère + par sévérité) : complexité MVP, attente Q8 → option C non retenue.

---

## D10 — Stratégie de migration Alembic 047

**Decision** : Migration Alembic unique `047_project_esg_assessments.py` créant **2 tables** + **2 RLS policies par table** + **triggers F03 audit log** :

```python
# Pseudo-code Alembic
def upgrade():
    op.create_table("project_esg_assessments", ...)
    op.create_table("project_esg_criterion_responses", ...)
    op.execute("ALTER TABLE project_esg_assessments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_esg_assessments FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY pme_access_own_account ON project_esg_assessments ...")
    op.execute("CREATE POLICY admin_full_access ON project_esg_assessments ...")
    # idem project_esg_criterion_responses
    # F03 audit log triggers déjà appliqués automatiquement via mixin Auditable

def downgrade():
    op.drop_table("project_esg_criterion_responses")
    op.drop_table("project_esg_assessments")
```

**Round-trip validé** sur PostgreSQL réelle (script test `test_migration_047_round_trip.py`) :
1. `alembic upgrade head` (047 appliquée)
2. Création de fixtures dans les 2 nouvelles tables
3. `alembic downgrade -1` (drop des 2 tables, données fixtures perdues — comportement attendu)
4. `alembic upgrade head` (re-création vide)
5. Vérification : `projects.project_esg_score` saisies F045 historiques inchangées (SC-007).

**Backfill** : aucune ligne à backfiller (les 2 tables partent vides). Les évaluations passées entreprise F05 restent dans la table `esg_assessments` strictement séparée.

**Rationale** :
- Round-trip up/down/up validé sur PostgreSQL = SC-007 satisfait.
- Aucun risque de perte de données F045 (la colonne `projects.project_esg_score` n'est pas touchée par la migration 047).
- Triggers F03 audit log automatiques via mixin `Auditable` (pattern existant, pas de code SQL custom).

**Alternatives rejetées** :
- Migration en 2 étapes (table parent puis table dépendante) : sans gain, ajoute du bruit dans l'historique Alembic.
- Backfill défensif `project_esg_score → ProjectEsgAssessment.score` artificiel : invente des données là où il n'y en a pas (les saisies F045 manuelles ne sont pas des évaluations sourcées) ; viole F01.

---

## Synthèse des décisions et impact sur le plan

| Décision | Impact backend | Impact frontend | Impact tests |
|---|---|---|---|
| D1 — Branche `esg_scoring_node` | `nodes.py` modifié (≤ 30 lignes ajoutées), 2 helpers privés ≤ 50 lignes | aucun | `test_esg_scoring_node_dispatch.py` |
| D2 — 15-18 critères par référentiel | `seed_sources_047.py` seed ~46 critères catalogue F13 | `<EsgCriterionWidget>` boucle générique | tests fixtures ~46 critères |
| D3 — URL `/profile/projects/[id]/esg` | Pattern `_PATH_TO_SLUG_PATTERNS` enrichi | Nouvelle page Vue dédiée | E2E Playwright `project-esg-assessment.spec.ts` |
| D4 — Rapport ESIA à la demande | Endpoint POST `/report` dédié (synchrone, ≤ 30 s) | `<EsgReportPreview>` + CTA | `test_project_report_pdf.py` |
| D5 — Composants Vue F045 réutilisés | aucun | 7 nouveaux composants ESG-project | tests Vitest pour chaque composant |
| D6 — Skill F23 4 golden examples | Seed `skill_project_esg_assessment.json` | aucun | `test_skill_project_esg_eval.py` (gating 90 %) |
| D7 — 3 sources F01 seedées | `seed_sources_047.py` UPSERT 3 sources | aucun | `test_seed_sources_047_idempotent.py` |
| D8 — Listener after_insert/after_update | `project_listener.py` + wiring | aucun | `test_project_listener_snapshot.py` |
| D9 — Pondération `criterion.weight` F13 | `project_scoring.py` lit `criteria.weight` | aucun | `test_project_scoring_weighted.py` |
| D10 — Migration Alembic 047 | `047_project_esg_assessments.py` + RLS | aucun | `test_migration_047_round_trip.py` |

**Output** : `research.md` complet, aucune `NEEDS CLARIFICATION` restante. Prêt pour Phase 1 (data-model + contracts + quickstart).
