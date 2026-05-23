# Quickstart — Validation manuelle de l'évaluation ESG-projet (047)

**Feature** : 047-evaluation-esg-projet
**Audience** : développeurs et QA après implémentation

## Pré-requis

```bash
# Backend (venv activé)
source backend/venv/bin/activate
alembic upgrade head           # applique migration 047
python -m app.scripts.seed_sources_047  # seed 3 sources F01 + ~46 critères F13
uvicorn app.main:app --reload

# Frontend (autre terminal)
cd frontend && npm run dev
```

Comptes nécessaires :
- 1 compte PME standard (créé via signup ou `python -m app.scripts.seed_admin --pme`).
- 1 compte PME tiers (pour tester RLS F02).
- 1 compte ADMIN (créé via `python -m app.scripts.seed_admin`).

---

## Parcours US1 — PME informelle évalue son projet ESG (P1)

1. Se connecter avec le compte PME.
2. Vérifier qu'**aucune ESGAssessment entreprise n'existe** (ne pas remplir `/esg`).
3. Créer un projet vert minimal sur `/profile/projects/new` :
   - Nom : « Agroforesterie 200 ha »
   - Pays : Togo
   - Statut : `draft`
   - Cocher `taxonomie_verte_uemoa_aligned=true`, `gcf_priority_themes=["atténuation","REDD+"]`, `vulnerable_populations=["femmes_rurales"]`, `gender_inclusion=true`
4. Sur la fiche projet, cliquer sur « Démarrer l'évaluation ESG-projet ».
5. **Vérifier** : redirection vers `/profile/projects/{id}/esg`.
6. Choisir le référentiel **IFC PS** dans `<EsgReferentialPicker>`.
7. **Vérifier** : `<EsgTargetBadge>` affiche « ESG Projet » (et pas « ESG Entreprise »).
8. Répondre aux 16 critères IFC PS via le wizard `<ProjectEsgWizard>` :
   - Chaque critère affiche le libellé + widget F18 (qcu/qcm/justification) + champ `<SourceLink>`.
   - Saisir une source F01 (`ifc-performance-standards-2012` proposée par défaut) pour chaque critère.
9. Cliquer sur « Finaliser l'évaluation ».
10. **Vérifier** : réponse en < 3 s, score 0..100 retourné (cible 60-75 selon réponses), `<EsgScoreDisplay>` affiche donut + breakdown PS1..PS8.
11. **Vérifier** : `<MissingProjectCriteriaList>` est vide (si tous critères obligatoires répondus) ou liste les critères manquants si refus.
12. Revenir sur la fiche projet `/profile/projects/{id}`.
13. **Vérifier** : la section « ESG Projet » affiche le score finalisé + lien vers l'évaluation.

---

## Parcours US2 — Matching pilote le référentiel selon le fonds (P1)

1. PME du parcours US1 (1 évaluation IFC PS finalisée existante).
2. Créer une **seconde évaluation GCF ESS** sur le même projet :
   - Démarrer l'évaluation contre GCF ESS depuis la fiche projet.
   - Répondre aux 15 critères GCF ESS (volontairement différents pour produire un score différent, ex : 60 vs 75).
   - Finaliser.
3. **Vérifier** sur `/profile/projects/{id}` : deux évaluations finalisées listées (IFC PS, GCF ESS).
4. Aller sur `/financing/offers` et trouver un fonds GCF (créé via fixtures `seed_sources_047.py`).
5. Cliquer sur « Voir les détails du matching » pour ce projet vs fonds GCF.
6. **Vérifier** : breakdown matching affiche `project_esg.score = 60` (GCF ESS, pas IFC PS).
7. **Vérifier** : `<DualScoreDisplay>` montre le sub-score et `is_fallback=false` (référentiel explicitement déclaré par le fonds).
8. Refaire avec un fonds BOAD :
   - **Vérifier** : matching propose CTA « Démarrer l'évaluation ESG-projet contre BOAD ESS » (car aucune évaluation BOAD ESS n'existe encore).
   - **Vérifier** : `project_esg.score=0`, `unsourced=true`.
9. Refaire avec un fonds sans référentiel ESS déclaré (ex : un fonds bilateral local).
10. **Vérifier** : matching utilise **IFC PS** (référentiel fallback Q4), `is_fallback=true`, score reflète l'évaluation IFC PS existante (75).

---

## Parcours US3 — Rapport ESIA-light PDF (P2)

1. PME avec une évaluation finalisée (US1 ou US2).
2. Sur `/profile/projects/{id}/esg`, sélectionner l'évaluation.
3. Cliquer sur l'onglet `<EsgReportPreview>`.
4. **Vérifier** : preview structuré 7 sections affiché en HTML avant export PDF.
5. Cliquer sur « Générer le rapport ESIA-light ».
6. **Vérifier** : génération en < 30 s p95 (chronométrer DevTools Network).
7. **Vérifier** : PDF téléchargé, ouvert dans un lecteur (Aperçu macOS, Adobe Reader).
8. **Vérifier** sections présentes (7 sections obligatoires + annexe F01) :
   - Executive summary
   - Description du projet (réutilise les champs F045 du projet)
   - Baseline E&S
   - Impacts identifiés (positifs et négatifs, basé sur les réponses critères)
   - Mesures d'atténuation
   - Plan d'engagement des parties prenantes
   - Indicateurs de suivi M&E
   - Annexe « Sources et références » F01
9. **Vérifier** : au moins 1 graphique donut « critères couverts vs manquants » présent.
10. **Vérifier** : tenter de générer un rapport sur une évaluation `draft` → 422 avec message FR explicite.

---

## Parcours US4 — LLM orchestre via skill F23 (P2)

1. PME, ouvrir une **conversation chat fraîche** sur `/profile/projects/{id}` (projet sans évaluation).
2. Taper : « Évalue l'ESG de ce projet pour GCF ».
3. **Vérifier** : le LLM enchaîne via skill `skill_project_esg_assessment` :
   - Appel `create_project_esg_assessment(project_id, referential='gcf_ess')` → confirmation
   - Pose le premier critère via widget F18 (qcu ou qcm)
4. Répondre à 15 critères en suivant le widget F18 chacun.
5. **Vérifier** : à chaque réponse, le LLM cite une source F01 (validator `source_required.py` actif).
6. **Vérifier** : à mi-parcours, fermer l'onglet et revenir 1 h plus tard. Re-ouvrir le chat sur le même projet. Taper : « On reprend l'évaluation GCF ESS ».
7. **Vérifier** : le LLM retrouve l'état (via F12 `recall_history`) et reprend au critère suivant.
8. Une fois les 15 critères répondus, **vérifier** :
   - Appel automatique `finalize_project_esg_assessment` → score retourné
   - Bloc visualisation F11 affiché avec score + critères manquants + lien rapport ESIA
   - Appel automatique `match_funds_for_project` → bloc « Impact sur le matching » `<ProjectEsgMatchImpact>` montre le breakdown mis à jour pour les fonds GCF
9. **Vérifier SC-006** : compteur widgets ≤ 12, tours utilisateur ≤ 3.

---

## Parcours US5 — Migration douce F045 manuel (P3)

### Scénario 1 — Calculé prend la priorité

1. Sur un projet existant (avant tout 047), forcer en BDD `projects.project_esg_score=42` (saisie F045 manuelle héritée).
2. Lancer une `ProjectEsgAssessment` IFC PS finalisée avec score 78 via US1.
3. Lancer le matching projet.
4. **Vérifier** : `project_score_breakdown.project_esg.score = 78` (calculé prime, FR-029), `source_kind = "calculated"`.

### Scénario 2 — Fallback F045

1. Sur un autre projet avec `project_esg_score=42` (saisie F045), **sans** évaluation calculée.
2. Lancer le matching.
3. **Vérifier** : `project_score_breakdown.project_esg.score = 42`, `source_kind = "manual_f045"`.

### Scénario 3 — Aucun score

1. Sur un projet avec `project_esg_score=NULL` et aucune évaluation.
2. Lancer le matching.
3. **Vérifier** : `project_score_breakdown.project_esg.score = 0`, `unsourced = true`, `source_kind = "unsourced"`, CTA « Démarrer l'évaluation ESG-projet contre {IFC PS|GCF ESS|BOAD ESS selon fonds ciblé} ».

### Scénario 4 — Tentative de modification API après évaluation finalisée (409)

1. Sur le projet du scénario 1 (évaluation IFC PS finalisée existe).
2. Via API REST, tenter `PATCH /api/projects/{id}` avec `{"project_esg_score": 50}`.
3. **Vérifier** : retour HTTP 409 Conflict avec message FR « Une évaluation ESG-projet finalisée existe pour ce projet. Veuillez la supprimer ou ré-évaluer pour modifier le score manuel. » (FR-033 clarification Q6).

### Scénario 5 — Listener D8 met à jour le snapshot

1. Vérifier en BDD : après finalisation US1, `projects.project_esg_score = ProjectEsgAssessment.score` (75 dans l'exemple).
2. Supprimer l'évaluation finalisée via `DELETE /api/projects/{id}/esg-assessment/{assessment_id}`.
3. **Vérifier** : `projects.project_esg_score` retombe à la valeur précédente (ou NULL si aucune évaluation antérieure).
4. **Vérifier** que le matching reflète correctement (cascade FR-029 → FR-030 → FR-031).

---

## Tests RLS / Sécurité (R4 mitigation)

1. Compte PME tier (différent de celui de US1).
2. Tenter `GET /api/projects/{id_du_US1}/esg-assessment/{assessment_id_du_US1}`.
3. **Vérifier** : 404 Not Found (pas 403). Le tenant tiers ne peut même pas inférer l'existence (RLS F02 filtre la ligne).
4. Tenter via fixtures de SQL direct (sans `app.account_id` configuré) : 0 ligne retournée.

---

## Edge cases à valider

- **Évaluation orpheline** : supprimer un projet ayant une évaluation finalisée → CASCADE supprime les évaluations + responses, listener D8 ne se déclenche pas (projet inexistant).
- **Changement de référentiel en cours** : démarrer une évaluation IFC PS draft, puis démarrer une évaluation GCF ESS sur le même projet → deux évaluations draft coexistent.
- **Évolution version référentiel F13** : changer la version de GCF ESS de 1.0 à 2.0 dans le catalogue F13. Vérifier qu'une évaluation finalisée en v1.0 reste lisible avec `referential_version='1.0'`. Cron F13 envoie un reminder à la PME.
- **Critère obligatoire manquant à la finalisation** : tenter finalize sans répondre à un critère `is_required=true` → 422 + liste des critères manquants.
- **PDF échoue (timeout)** : forcer WeasyPrint à dépasser 30 s (par ex. via grand nombre de critères mock) → 504 + message clair + pas de ProjectEsgReport partiel créé.
- **LLM dépasse 12 widgets** : configurer un référentiel de test avec 20 critères. Vérifier que le LLM bascule sur lien wizard UI après le 12e widget.
- **Référentiel dépublié** : marquer `referentials.status='outdated'` pour GCF ESS. Tenter `POST /api/projects/{id}/esg-assessment` avec ce référentiel → 422 « Référentiel dépublié ».
- **Dark mode** : basculer le thème → tous les nouveaux composants (`<ProjectEsgWizard>`, `<EsgCriterionWidget>`, etc.) parité claire/sombre, pas de zone blanche persistante.
- **Accessibilité** : naviguer au clavier dans `<ProjectEsgWizard>` (Tab/Shift+Tab/Enter/Space) ; lecteur d'écran (VoiceOver macOS) annonce correctement chaque étape et chaque widget.

---

## Tests automatisés à exécuter avant merge

```bash
# Backend — modules nouveaux
cd backend && pytest tests/modules/esg/project/ -v --cov=app.modules.esg --cov-report=term

# Backend — non-régression F05 + matching
cd backend && pytest tests/modules/esg/test_esg_assessment.py tests/modules/financing/test_matching_service.py -v

# Backend — full baseline (SC-005)
cd backend && pytest -x

# Frontend unitaires
cd frontend && npm run test -- esg/project

# E2E
cd frontend && npx playwright test project-esg-assessment
```

---

## Critères de succès (SC-001..SC-010) — comment les mesurer

| SC | Méthode |
|---|---|
| SC-001 | Chronométrer le parcours US4 (chat-driven) sur 5 sujets test ; médiane < 8 min |
| SC-002 | Fixtures pytest `test_matching_consumes_project_esg.py` sur 20 projets, ≥ 95 % de matchings utilisent le calculé |
| SC-003 | `pytest-benchmark` sur `test_project_report_pdf.py` ; p95 < 30 s |
| SC-004 | `pytest --cov=app.modules.esg` (backend) et `npx vitest run --coverage` (frontend) ; lignes ≥ 80 % |
| SC-005 | `pytest -x` complet ; égal ou supérieur à 3 136 passants pré-047 |
| SC-006 | Compteur widgets dans `tool_call_logs` pour le parcours US4 ; ≤ 12 widgets, ≤ 3 tours utilisateur |
| SC-007 | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` ; comparer `projects.project_esg_score` avant/après |
| SC-008 | `pytest tests/modules/skills/test_skill_project_esg_eval.py` ; score eval ≥ 90 % |
| SC-009 | Audit post-finalisation : `SELECT COUNT(*) FROM project_esg_criterion_responses WHERE source_id IS NOT NULL AND unsourced=false` / total ≥ 95 % |
| SC-010 | Session usability test 5 sujets ; ≥ 4/5 identifient correctement la cible (entreprise vs projet) via `<EsgTargetBadge>` et libellés |

---

## Rollback plan (si besoin en post-déploiement)

1. Désactiver l'écriture côté frontend : feature flag `NUXT_PUBLIC_ENABLE_PROJECT_ESG_ASSESSMENT=false` cache `<EsgReferentialPicker>` et `<ProjectEsgWizard>`.
2. Désactiver les tools LangChain `create_project_esg_assessment` / `finalize_project_esg_assessment` via env `DISABLE_PROJECT_ESG_TOOLS=true` (filtre dans `tool_selector_config.py`).
3. Si bug critique : `alembic downgrade -1` (drop des 2 tables, pas de perte F045).
4. Restore matching à son état pré-047 via feature flag `MATCHING_USE_PROJECT_ESG_ASSESSMENTS=false` (cohabitation F045 manuel).
