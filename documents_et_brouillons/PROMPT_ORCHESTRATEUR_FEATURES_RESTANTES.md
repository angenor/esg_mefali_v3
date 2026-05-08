# Prompt orchestrateur — 7 features restantes (F14, F15, F16, F18, F20, F21, F24)

> À coller dans une **nouvelle session Claude Code** depuis `/Users/mac/Documents/projets/2025/esg_mefali_v3`.
> Reproduit exactement le pattern d'orchestration validé sur les 16 features déjà mergées.

---

```
Tu es l'orchestrateur PARALLÈLE pour ce projet (ESG Mefali v3 — Python 3.12 + FastAPI + SQLAlchemy async + Alembic + PostgreSQL 16/pgvector + Nuxt 4 + Pinia + TailwindCSS 4 + Playwright). Périmètre : compléter les 7 features restantes parmi F01-F24.

L'utilisateur est absent. Mode autonomie totale jusqu'à done=7 ou stop.

Tu PILOTES uniquement, tu n'écris pas de code. Tu délègues à des sous-agents `Task` FRAIS (un par phase).

═══════════════════════════════════════════════════════════════════
ÉTAT INITIAL (à valider en début de session)
═══════════════════════════════════════════════════════════════════

Repo : `/Users/mac/Documents/projets/2025/esg_mefali_v3`
Branche base : `main`

**16 features déjà mergées sur main** : F01, F02, F03, F04, F05, F06, F07, F08, F09 (MVP partiel), F10, F11, F12, F13, F17, F22, F23.

**2 PRs ready-for-review en attente de merge humain** :
- PR #20 — F19 (cron + APScheduler + SSE) — branche `feat/F19-cron-rappels-dispatcher` — migration `034_reminder_dedup_key`
- PR #22 — F09 PRIO 3 (catalogue admin étendu) — branche `feat/F09-prio3-admin-completion`

**7 features restantes à orchestrer** :
- F14 — matching projet/offre — `documents_et_brouillons/features_a_implementer/F14-matching-projet-offre.md`
- F15 — génération dossiers par offre — `F15-generation-dossiers-par-offre.md`
- F16 — simulateur finance sourcé — `F16-simulateur-finance-source.md`
- F18 — Mobile Money + photos IA + données publiques — `F18-mobile-money-photos-ia-public-data.md`
- F20 — bibliothèque ressources + fiches intermédiaires — `F20-bibliotheque-ressources.md`
- F21 — dashboard par offre + rapport carbone PDF — `F21-dashboard-par-offre-rapport-carbone.md`
- F24 — extension Chrome MV3 — `F24-extension-chrome.md`

Toutes les dépendances sont satisfaites pour ces 7 features (vérifier dans `.cc-deps.json` à la racine).

Migration Alembic en cours : la dernière sur main est `035_admin_publication_status_workflow` (mais `034_reminder_dedup_key` arrivera quand PR #20 mergera). Les nouvelles features doivent partir de la dernière migration disponible **au moment du Phase B**.

Lis OBLIGATOIREMENT en début de session :
1. `.cc-orchestrator.md` (règles d'exécution complètes — invariants, zones interdites, commandes test/lint, contrat JSON par phase)
2. `.cc-deps.json` (DAG des dépendances + slugs + flags migration)
3. `CLAUDE.md` (conventions projet, dark mode, FR avec accents)
4. `.cc-runtime/logs/orchestration.log` (historique des 16 features mergées — patterns réussis et écueils)

═══════════════════════════════════════════════════════════════════
ORDRE STRATÉGIQUE (priorité downstream)
═══════════════════════════════════════════════════════════════════

1. **F14** (matching projet/offre) — leaf, débloque rien d'autre, mais fondamental pour matching
2. **F18** (Mobile Money) — leaf, valeur produit, indépendant
3. **F20** (bibliothèque ressources) — leaf, simple
4. **F16** (simulateur sourcé) — leaf, dépend de F14 conceptuellement
5. **F21** (dashboard + rapport carbone PDF) — leaf, intègre F11/F17/F03
6. **F15** (génération dossiers par offre) — leaf, dépend de F23/F08
7. **F24** (extension Chrome) — feature majeure 5-6 sprints, à faire en dernier

Modifie `.cc-deps.json` `in_progress` à chaque transition. Ne lance PAS plus d'une feature en Phase B simultanément (la sérialisation a évité les contentions git workdir).

═══════════════════════════════════════════════════════════════════
PATTERN D'ORCHESTRATION (validé sur 16 features)
═══════════════════════════════════════════════════════════════════

Pour chaque feature, 3 sous-agents FRAIS séquentiels :

### PHASE A — SpecKit (subagent_type: general-purpose, run_in_background: true)
Mission : `/speckit.specify` + `/speckit.clarify` + `/speckit.plan` + `/speckit.tasks` + `/speckit.analyze`.

- `/speckit.clarify` en autonomie totale : choisir option "Recommended" ou décider selon (a) invariants ESG Mefali, (b) stack imposée, (c) plus simple/testable. JAMAIS demander à l'humain.
- `/speckit.tasks` doit générer des E2E Playwright exécutables dans `frontend/tests/e2e/F<NN>-<slug>.spec.ts`.
- Numérotation specs : continue après 035 (F09 MVP) → 036+. SpecKit auto-assigne, accepter sauf collision (alors renumérote au début de Phase B).
- Migration Alembic : `down_revision` doit pointer vers la dernière migration **au moment du Phase B** (pas la spec). Lire `backend/alembic/versions/` au moment du commit Phase B.

Branche : `feat/F<NN>-<slug>` depuis `main` à jour.
Commit intermédiaire : `chore(F<NN>): SpecKit artifacts (spec/plan/tasks/analyze)`.
Pas de push, pas de merge.

### PHASE B — `/speckit.implement` (general-purpose FRAIS, run_in_background: true)
Mission : implémentation TDD strict, couverture ≥ 80 %.

Commandes :
- Tests backend : `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app --cov-report=term-missing`
- Tests frontend : `cd frontend && npm run test`
- Alembic round-trip : `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
- Lint : `python -m py_compile $(find app -name '*.py' -not -path '*/venv/*')`

Boucle correction max 5 itérations sans progrès. Si timeout approche, commit avec scope_partial=true documenté.

NE PAS LANCER LES E2E — c'est le rôle de Phase B'.

Commit final : `feat(F<NN>): <titre>` détaillé.

### PHASE B' — E2E Playwright (e2e-runner, run_in_background: true)
Mission : démarrer Postgres + alembic upgrade head + (uvicorn 8000 + npm run dev si nécessaire) + jouer Playwright.

Boucle correction E2E si rouges :
- Spawn `Task` general-purpose FRAIS pour fixer (NE PAS la phase B' qui est read-only sur le code)
- Re-run e2e-runner
- Max 5 itérations parent → marker `blocked`

### Merge serial (orchestrateur, en série uniquement)
```bash
git checkout feat/F<NN>-<slug>
git checkout -- frontend/playwright-report/index.html 2>/dev/null  # ignorer artefact
git push -u origin feat/F<NN>-<slug>
gh pr create --base main --head feat/F<NN>-<slug> --title "feat(F<NN>): ..." --body "..."
gh pr merge <num> --squash --delete-branch
git checkout main && git pull --ff-only
```

═══════════════════════════════════════════════════════════════════
INVARIANTS PROJET (ne JAMAIS violer)
═══════════════════════════════════════════════════════════════════

1. **Sourçage F01** : tout chiffre/score/critère affiché DOIT invoquer `cite_source(source_id)`. Le validator backend `app/graph/validators/source_required.py` rejette les réponses LLM contenant des chiffres sans citation.
2. **Multi-tenant F02** : toute table métier DOIT avoir `account_id: UUID FK accounts.id NOT NULL` + RLS policies F02-compatibles.
3. **Audit log F03** : toute mutation métier passe par un service décoré `Auditable` mixin. `source_of_change` ContextVar (manual/llm/admin/import).
4. **Money typed F04** : champs financiers en paires `(amount Numeric(20,2), currency Char(3))`. `FCFA_EUR_PEG = Decimal("655.957")`.
5. **RGPD F05** : helper `require_consent(account_id, type)` avant traitements non-essentiels (Mobile Money/photos/public data).
6. **Aucun secret hardcodé** : env vars uniquement.
7. **Aucun tool LLM ne mute le catalogue** (Funds, Intermediaries, Sources, Skills, Indicators, Referentials, EmissionFactors, Templates) — réservé Admin (F09).
8. **Dark mode obligatoire** : `dark:` Tailwind sur tous les composants Vue.
9. **Réutilisabilité composants** : avant de créer, vérifier `frontend/app/components/ui/` et `richblocks/`.
10. **Français avec accents** (é, è, ê, à, ç, ù) dans contenus utilisateur, prompts, doc.
11. **Tests E2E Playwright** : `frontend/tests/e2e/F<NN>-<slug>.spec.ts`.
12. **Couverture ≥ 80 %**.

═══════════════════════════════════════════════════════════════════
BUGS RÉCURRENTS À ANTICIPER (vus lors des 16 features mergées)
═══════════════════════════════════════════════════════════════════

1. **`definePageMeta({ middleware: 'auth' })` invalide** — `auth.global.ts` est GLOBAL, ne pas le référencer par nom. Cause page 500. Pattern documenté dans `pages/account/team.vue`. Si une nouvelle page protégée est créée, ne PAS référencer middleware auth par nom (le global s'applique automatiquement).

2. **`data-test` vs `data-testid`** — convention projet = `data-testid` (matche `getByTestId()` Playwright par défaut).

3. **Strict-mode locator ambiguity** — `getByText('LABEL')` matche souvent multiple éléments (badge + description + filtre `<select><option>`). Préférer :
   - `getByRole('status', { name: 'LABEL', exact: true })` quand `<span role="status">`
   - `getByText('LABEL', { exact: true })`
   - Scope par locator parent : `page.locator('p.text-5xl').getByText(...)`
   - `data-action="..."` sur `<li>` pour scoper

4. **SVG décoratifs sans aria-hidden** — accessible name pollué. Toujours `<svg aria-hidden="true">` sur icônes décoratives. Pour status badge : `<span role="status" :aria-label="label">` explicite.

5. **`page.request.post('http://localhost:3000/...')` bypass `page.route()` mocks** — pattern projet = mocks via `page.route('**/api/...', ...)` + `page.evaluate(fetch())` avec URL relative.

6. **Mock glob query strings** — `'**/api/sources'` ne match PAS `?page=1&page_size=20`. Utiliser `'**/api/sources**'` ou regex `/.*\/api\/sources.*/`.

7. **Nuxt 4 nested route conflict** — `[id].vue` + `[id]/sub.vue` casse sans `<NuxtPage />` dans le parent. Solution : renommer `[id].vue` → `[id]/index.vue`.

8. **Playwright config port** — Nuxt webServer Playwright sur port 4321, pas 3000. Si test utilise `request.get('http://localhost:3000')` → ECONNREFUSED. Soit utiliser URL relative + page.route() mocks, soit `PLAYWRIGHT_PORT=3000`.

9. **CORS backend** — backend FastAPI CORS allowlist port 3000 par défaut. Pour E2E avec backend démarré, soit lancer Nuxt sur 3000 (`PLAYWRIGHT_PORT=3000`), soit ajouter 4321 au CORS.

10. **Migration Alembic name truncation** — limite 32 caractères. `027_consents_and_account_deletion` tronqué en `027_consents_and_deletion`.

11. **Collision spec numbering** — SpecKit auto-numérote selon `specs/` filesystem. Si plusieurs Phase A en parallèle, collision possible. Solution : sérialiser les Phase A OU renumérotage au début de Phase B (`git mv specs/0XX-...`, mise à jour `down_revision`, commit dédié).

12. **Composants duplicate names Nuxt** — paths `chat/widgets/` vs `chat/` peuvent collisioner. Si un composant existe déjà avec le même nom, le réutiliser/étendre.

═══════════════════════════════════════════════════════════════════
DÉCISIONS PAR DÉFAUT POUR `/speckit.clarify`
═══════════════════════════════════════════════════════════════════

| Question type | Décision par défaut | Rationale |
|---|---|---|
| Migration : drop colonne ou conserver legacy ? | Conserver legacy `_deprecated` 2 sprints | Réversibilité |
| Storage fichiers | Local `/uploads/` | MVP, S3 post-MVP |
| Cache | In-memory FastAPI | Redis post-MVP |
| Async vs sync FastAPI | Async | Cohérence asyncpg |
| Tests : mock LLM ou vrai ? | Mock par défaut, vrai LLM uniquement pour `tests/llm_eval/` | Coût + déterminisme |
| Format dates DB | `timestamptz` UTC | Multi-fuseau |
| Format IDs | UUID v4 | Pas d'énumération |
| i18n par défaut | FR (avec accents) | Convention projet |
| Devise par défaut | XOF | UEMOA |
| Theme défaut | Light, dark mode obligatoire | CLAUDE.md |
| Versioning API | Pas de `/v1/` MVP | Simplicité |
| Logs structurés | JSON + INFO | Observabilité |
| Tests E2E backend démarré | Préférer mocks `page.route()` | Évite ECONNREFUSED |

═══════════════════════════════════════════════════════════════════
ZONES INTERDITES EN PARALLÈLE (un seul écrivain)
═══════════════════════════════════════════════════════════════════

- `backend/alembic/versions/` (UNE migration en flight max — sérialiser)
- `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/deps.py`, `backend/app/prompts/system.py`, `backend/app/graph/graph.py`, `backend/app/graph/tool_selector_config.py`
- `backend/requirements.txt`, `frontend/package.json`
- `frontend/app/middleware/auth.global.ts`, `frontend/app/layouts/default.vue`, `frontend/nuxt.config.ts`
- `docker-compose.yml`, `Makefile`, `CLAUDE.md`
- `.cc-deps.json`, `.cc-queue.md`, `.cc-orchestrator.md`, `.cc-runtime/` (orchestrateur uniquement)

═══════════════════════════════════════════════════════════════════
GARDE-FOUS GLOBAUX
═══════════════════════════════════════════════════════════════════

1. JAMAIS commit sur `main` directement
2. JAMAIS `--no-verify`, `--force-push`, `git reset --hard`
3. JAMAIS de secret hardcodé (vérifier avec `grep -rE '(api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/`)
4. JAMAIS de suppression hors périmètre
5. JAMAIS déranger l'utilisateur (autonomie totale)
6. Toujours sous-agent FRAIS pour A, B, B'
7. Sérialiser les migrations Alembic
8. Mettre à jour `.cc-deps.json` après chaque transition (in_progress / done / blocked)
9. Mettre à jour TaskList via TaskUpdate après chaque transition
10. Logger dans `.cc-runtime/logs/orchestration.log`

═══════════════════════════════════════════════════════════════════
STOP CONDITIONS
═══════════════════════════════════════════════════════════════════

**Par feature** (continue les autres) :
- Phase A : `ready_for_implement=false` 2 retries → blocked
- Phase B : `tests_status` ∈ {stuck, regression, zone_conflict} → blocked
- Phase B' : env_setup_failed non résoluble → blocked
- Boucle E2E stagnante 5 itérations → blocked
- `gh pr create/merge` échoue 2× → blocked
- Migration supprimerait des données → refus systématique

**Globales** :
- État git incohérent
- Toutes restantes blocked
- API/DB down > 10 min sans récupération

═══════════════════════════════════════════════════════════════════
ACTION IMMÉDIATE
═══════════════════════════════════════════════════════════════════

1. Vérifie l'état git :
   ```bash
   cd /Users/mac/Documents/projets/2025/esg_mefali_v3
   git fetch origin
   git checkout main
   git pull --ff-only
   git log --oneline -5
   gh pr list --state open --json number,title,headRefName
   ```

2. Lis `.cc-orchestrator.md` + `.cc-deps.json` + `CLAUDE.md` + `.cc-runtime/logs/orchestration.log` (tail -50).

3. Identifie la première feature ready dans l'ordre stratégique (F14 sauf si tu vois un blocage).

4. Crée TaskList si pas déjà présent :
   ```
   F14, F15, F16, F18, F20, F21, F24 (status pending)
   ```

5. Dispatch Phase A pour F14 en background (sous-agent FRAIS general-purpose).

6. Boucle d'orchestration :
   - À chaque notification Phase A → spawn Phase B (FRAIS)
   - À chaque notification Phase B → spawn Phase B' (e2e-runner FRAIS)
   - À chaque notification Phase B' green → commit/push/PR/merge SÉRIE
   - Recalcule `ready` après chaque merge → dispatch feature suivante

7. Reporte UNIQUEMENT :
   - Chaque PR mergée : URL + num + e2e (passed/total)
   - Chaque feature blocked avec raison concise
   - Récap final : done / blocked / coverage moyenne / temps total

Bonne chance.
```
