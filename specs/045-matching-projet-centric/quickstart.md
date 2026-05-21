# Quickstart — Feature 045 (Matching projet-centric)

**Date** : 2026-05-21
**Branche** : `045-matching-projet-centric`

Ce document guide l'équipe pour développer, tester et valider la feature 045 en local. Il suppose que l'environnement backend (Python 3.12 + venv) et frontend (Node + npm) est déjà configuré conformément au CLAUDE.md du projet.

---

## 1. Prérequis

### 1.1 Backend

```bash
# Activer le venv (UNE fois par session)
source backend/venv/bin/activate

# Vérifier la version Python
python --version   # Doit afficher 3.12.x

# Vérifier les dépendances LangChain / LangGraph
pip list | grep -E "langchain|langgraph"
```

### 1.2 Frontend

```bash
cd frontend && npm install
```

### 1.3 Base de données

```bash
# Vérifier que PostgreSQL 16 + pgvector tourne
docker compose ps | grep postgres

# Appliquer toutes les migrations existantes jusqu'à 044
alembic upgrade head
```

---

## 2. Démarrer la feature

### 2.1 Bascule sur la branche

```bash
git checkout 045-matching-projet-centric

# Vérifier qu'on est bien sur la branche
git branch --show-current   # → 045-matching-projet-centric
```

### 2.2 Vérifier l'état initial

```bash
# Doit afficher 0 — pas encore de migration 045
ls backend/alembic/versions/ | grep "^045" | wc -l

# Doit afficher la table offer_matches F14 existante
psql -h localhost -U mefali -d mefali_dev -c "\d offer_matches" | head -20

# Doit afficher les 3 skills MVP F23 existants
psql -h localhost -U mefali -d mefali_dev -c "SELECT name, status FROM skills"
```

---

## 3. Workflow de développement (TDD imposé)

### 3.1 Ordre recommandé (tâches granulaires en `/speckit.tasks`)

1. **Backend — Migration 045** : créer le fichier `backend/alembic/versions/045_xxx_matching_projet_centric.py` avec :
   - ALTER TABLE projects ADD 5 colonnes (cf. data-model.md §1.1)
   - ALTER TABLE offer_matches ADD 4 colonnes + backfill (cf. §2.1)
   - UPDATE indexes (BTREE taxonomie + GIN gcf_themes)
2. **Backend — Tests migration** : `test_migration_045_roundtrip.py` (round-trip up/down/up).
3. **Backend — Whitelists & schemas** :
   - `app/core/matching_constants.py` (whitelists FR)
   - `app/modules/projects/schemas.py` (étendre ProjectBase/Create/Update)
   - `app/modules/financing/matching_schemas.py` (`ProjectScoreBreakdown`, etc.)
4. **Backend — Tests schemas** : `test_project_schemas_extended.py`, `test_matching_schemas_project.py`.
5. **Backend — Sources F01 seed** : `app/scripts/seed_sources_045.py` (4 sources) + test idempotent.
6. **Backend — Algorithme scoring** :
   - `matching_service._compute_project_score(...)` (8 sub-scores)
   - `matching_service._compute_company_score(...)` (héritage F14 renommé)
   - `divergence_templates.build_divergence_explanation(...)` (4 gabarits)
   - Refactor `compute_offer_match(...)` pour produire les 2 scores
7. **Backend — Tests scoring** : `test_compute_project_score.py`, `test_compute_company_score.py`, `test_divergence_templates.py`.
8. **Backend — Endpoint API** : `matching_router.match_funds_endpoint` (POST /match-funds) + tests intégration.
9. **Backend — Tool LangChain** : `project_tools.match_funds_for_project` + tests.
10. **Backend — Event listener after_update** : `app/modules/projects/service.py` (debounce 30s) + tests.
11. **Backend — Skill seed** : étendre `seed_skills.py` + golden examples + tests conformity.
12. **Frontend — Constantes générées** : exécuter `scripts/sync-matching-constants.ts` pour générer `types/matching_enums.generated.ts`.
13. **Frontend — Composables & stores** : `useProjectMatching.ts`, `stores/projectMatching.ts` + tests Vitest.
14. **Frontend — Composants Vue** : `<DualScoreDisplay>`, `<ProjectMatchCard>`, `<MissingProjectCriteriaList>`, `<ProjectFundsSection>`, `<DivergenceBadge>` + tests Vitest.
15. **Frontend — Intégration pages** : `/profile/projects/[id].vue`, `/financing/offers/[offerId].vue`.
16. **Frontend — E2E Playwright** : `matching-project-centric.spec.ts` (parcours US2 complet).
17. **Quality gate** : run pytest + Vitest + Playwright + coverage report.

### 3.2 Démarrer le serveur dev

```bash
# Backend (terminal 1)
source backend/venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend && npm run dev   # → http://localhost:3000
```

### 3.3 Smoke test après chaque étape

```bash
# Backend : lancer les tests rapides
cd backend && pytest tests/unit/test_compute_project_score.py -v

# Frontend : lancer les tests d'un composant
cd frontend && npm run test -- DualScoreDisplay
```

---

## 4. Tests intégration end-to-end (parcours US1+US2)

### 4.1 Setup de données de test

```python
# backend/tests/fixtures/feature_045_data.py (NOUVEAU)
from app.scripts.seed_admin import ensure_admin_user
from app.scripts.seed_sources_045 import seed_sources_045
from app.scripts.seed_skills import seed_skills

async def setup_feature_045_data(db):
    """Fixture pour les tests E2E feature 045."""
    admin = await ensure_admin_user(db)
    await seed_sources_045(db, admin.id)
    await seed_skills(db, admin.id)
    # ... seed 1 fund GCF, 1 fund FEM, 1 fund Fonds d'Adaptation si absents
    # ... seed 1 PME Togo informelle (account_id, user)
    # ... pas de ESGAssessment finalisée
```

### 4.2 Test US1 — PME informelle + projet vert (FR-003, SC-002)

```python
# backend/tests/integration/test_us1_pme_informelle_projet_vert.py
@pytest.mark.integration
async def test_pme_informelle_obtient_3_fonds_min(db, client, auth_headers_pme_togo):
    # Setup : projet agroforesterie 200ha
    project = await create_project(db, account_id=..., data={
        "name": "Agroforesterie 200ha Togo",
        "sector": "agriculture",
        "objective_env": ["mitigation", "biodiversity"],
        "expected_impact_tco2e": 2400,
        "expected_beneficiaries": 850,
        "taxonomie_verte_uemoa_aligned": True,
        "gcf_priority_themes": ["atténuation", "REDD+"],
        "gender_inclusion": True,
        "vulnerable_populations": ["femmes"],
        "project_esg_score": None,    # Pas évalué
    })

    # Act : appel endpoint match-funds
    resp = await client.post(
        f"/api/projects/{project.id}/match-funds",
        headers=auth_headers_pme_togo,
    )

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["matches_count"] >= 3
    fund_names = {m["fund_name"] for m in body["top_matches"]}
    assert "Green Climate Fund" in fund_names
    assert "Fonds pour l'Environnement Mondial" in fund_names
    assert "Fonds d'Adaptation" in fund_names
    for match in body["top_matches"]:
        assert match["project_score"] >= 60
```

### 4.3 Test US2 — Chat lifecycle complet (E2E Playwright)

```typescript
// frontend/tests/e2e/matching-project-centric.spec.ts
import { test, expect } from "@playwright/test";

test("US2: création projet en chat → matching → update → re-match", async ({ page }) => {
  // 1. Login PME
  await page.goto("/login");
  await loginAsPme(page, "pme-togo@test");

  // 2. Ouvrir le chat
  await page.click("[data-testid='chat-link']");

  // 3. Décrire le projet
  await page.fill("[data-testid='chat-input']", "Je veux installer 50 panneaux solaires dans mon village");
  await page.click("[data-testid='chat-send']");

  // 4. Répondre aux widgets interactifs F18 (qcu impact, beneficiaries, etc.)
  await page.waitForSelector("[data-testid='interactive-question']");
  await page.click("[data-testid='qcu-option'][data-value='énergie']");
  // ... répondre aux 3-5 widgets

  // 5. Attendre confirmation create_project
  await expect(page.locator("[data-testid='chat-message']:last-child"))
    .toContainText("Projet créé");

  // 6. Lancer le matching
  await page.fill("[data-testid='chat-input']", "Lance le matching.");
  await page.click("[data-testid='chat-send']");

  // 7. Attendre les MatchCardBlock F11
  await page.waitForSelector("[data-testid='match-card-project-block']");
  const matchCards = page.locator("[data-testid='match-card-project-block']");
  await expect(matchCards).toHaveCount({ min: 1, max: 5 });

  // 8. Update CO2 impact
  await page.fill("[data-testid='chat-input']", "Augmente mon impact CO2 à 5000 tCO2e/an.");
  await page.click("[data-testid='chat-send']");

  // 9. Vérifier que update_project + re-match auto
  await page.waitForSelector("[data-testid='tool-call-indicator'][data-tool='update_project']");
  await page.waitForSelector("[data-testid='tool-call-indicator'][data-tool='match_funds_for_project']");

  // 10. Vérifier nouvelle liste affichée
  const newMatchCards = page.locator("[data-testid='match-card-project-block']:nth-child(n+2)");
  await expect(newMatchCards.first()).toBeVisible();

  // Performance : tout le parcours < 90s
  // (mesuré par fixture timer)
});
```

---

## 5. Validation du Constitution Check post-design

| Principe | Vérification post-design |
|---|---|
| I. Francophone-First | ✅ `matching_constants.py` whitelist FR avec accents (« atténuation », « énergie », « handicapés »). |
| II. Architecture Modulaire | ✅ Pas de nouveau module — extension de `financing/` et `projects/`. |
| III. Conversation-Driven | ✅ Skill F23 + tool `match_funds_for_project` + golden example US2 prouve le parcours chat. |
| IV. Test-First | ✅ Tests écrits AVANT chaque module (ordre `/speckit.tasks` impose TDD). |
| V. Sécurité | ✅ RLS F02 hérité (offer_matches déjà couvert), audit F03 via `Auditable` Project, sources F01 obligatoires. |
| VI. Inclusivité | ✅ Nouveaux champs `gender_inclusion` et `vulnerable_populations`, dark mode obligatoire. |
| VII. Simplicité | ✅ Enrichissement table existante (pas de nouvelle table), pas de Redis/Celery (asyncio.create_task in-process). |

---

## 6. Performance benchmark cible

À mesurer en fin de sprint avec `pytest-benchmark` ou équivalent :

| Cible | Métrique attendue | Outil |
|---|---|---|
| Endpoint `POST /match-funds` (cache hit) | < 300 ms | locust ou ab |
| Endpoint `POST /match-funds` (cold, 50 offres) | < 2 s | locust |
| Tool LangChain `match_funds_for_project` | < 2 s | pytest fixture timer |
| Event listener after_update debounce | < 100 ms overhead | pytest-benchmark |
| Parcours E2E Playwright complet | < 90 s | Playwright HAR |

---

## 7. Checklist pré-PR

Avant d'ouvrir la PR `045-matching-projet-centric` → `main` :

- [ ] Migration 045 round-trip up/down/up testée sur PostgreSQL réelle
- [ ] 4 sources F01 seedées et `status='verified'`
- [ ] Skill `skill_match_project_funds` seedé (draft ou published)
- [ ] Coverage backend ≥ 80 % sur modules nouveaux (`pytest --cov=app.modules.financing.matching_service --cov=app.modules.financing.divergence_templates --cov-report=term-missing`)
- [ ] Coverage frontend ≥ 80 % sur composants nouveaux (`npm run test:coverage`)
- [ ] E2E Playwright `matching-project-centric.spec.ts` vert
- [ ] 0 régression sur les baselines tests existants (`pytest -x` complet < 30 min)
- [ ] Lint clean : `ruff check backend/` + `npm run lint`
- [ ] Type check clean : `mypy backend/app` (ou pyright) + `npm run typecheck`
- [ ] CLAUDE.md ledger à mettre à jour avec entrée F045 en haut (cf. CLAUDE.md.bak format)
- [ ] Doc `docs/matching-projet-centric.md` créée (ou section ajoutée à `docs/financing.md`)

---

## 8. Rollback strategy

Si la feature pose problème en post-déploiement :

### 8.1 Côté frontend (rollback immédiat)

```typescript
// frontend/.env
NUXT_PUBLIC_USE_PROJECT_CENTRIC_MATCHING=false
```

Le composant `<ProjectFundsSection>` se cache, la page `/profile/projects/[id]` revient au comportement F14, les composants `<DualScoreDisplay>` sont remplacés par `<MatchCard>` F14 (qui lit `global_score`).

### 8.2 Côté backend (rollback ciblé)

- Garder la migration 045 appliquée (les colonnes ajoutées ne cassent rien — `global_score` continue de tourner).
- Désactiver le skill `skill_match_project_funds` via `POST /api/admin/skills/{id}/unpublish` (status → `draft`).
- Le tool `match_funds_for_project` reste disponible mais n'est plus auto-activé par le skill.
- Endpoint `POST /api/projects/{project_id}/match-funds` reste fonctionnel mais peut être désactivé via feature flag `ENABLE_PROJECT_CENTRIC_MATCHING_ENDPOINT=false`.

### 8.3 Rollback total (migration down)

```bash
alembic downgrade -1   # Revient à 044
```

⚠️ Perte des 4 colonnes ajoutées (`project_score`, `company_score`, `project_score_breakdown`, `divergence_explanation`) et des 5 colonnes projet. Les sources F01 et le skill restent en BDD (pas désirée mais acceptable — script de cleanup manuel disponible).

---

## 9. Documentation à jour après sprint

- `docs/matching-projet-centric.md` (NOUVEAU) — guide utilisateur métier
- `docs/financing.md` (MAJ) — référence feature F08 + F14 + F045
- `CLAUDE.md` (MAJ) — ledger F045 en haut, dépendances mises à jour
- `frontend/README.md` (MAJ si nouveaux composants requièrent une note)

Ces mises à jour sont automatisables via le skill `doc-updater` du projet (à invoquer en fin de sprint).
