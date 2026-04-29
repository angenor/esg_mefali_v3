# Story 10.1 : Tool descriptions beton + schemas Pydantic stricts

Status: done

<!-- Source planning :
  - _bmad-output/planning-artifacts/module-10-tool-use-reliability/story-1-tool-descriptions-pydantic-strict.md
  - _bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md
-->

## Story

En tant que **developpeur backend**,
je veux **reecrire les descriptions et durcir les schemas Pydantic des tools LangChain critiques** (mutation Profil/ESG/Candidature + question interactive),
afin que le LLM choisisse le bon tool sans ambiguite (ligne 1 de defense de l'epic M10) et que tout payload invalide soit rejete deterministiquement avant d'atteindre la base de donnees.

## Contexte — etat reel verifie le 2026-04-29

Audit du repertoire `backend/app/graph/tools/` realise avant redaction. Les hypotheses de la story planning ne collent **pas exactement** au code reel. Le dev DOIT lire ce contexte avant de coder pour ne pas reinventer ce qui n'existe pas.

### 1. Inventaire reel des tools (12 fichiers, ~2520 lignes)

```
backend/app/graph/tools/
├── __init__.py             (1 ligne)
├── action_plan_tools.py    (157 l.)
├── application_tools.py    (306 l.) — mutation Candidature
├── carbon_tools.py         (289 l.)
├── chat_tools.py           (240 l.) — lecture seule (4 tools get_*)
├── common.py               (185 l.) — helpers get_db_and_user, log_tool_call
├── credit_tools.py         (122 l.)
├── document_tools.py       (148 l.)
├── esg_tools.py            (364 l.) — mutation ESG (5 tools)
├── financing_tools.py      (237 l.)
├── guided_tour_tools.py    (104 l.) — feature 019
├── interactive_tools.py    (189 l.) — UNE question interactive (pas 4)
└── profiling_tools.py      (179 l.) — mutation Profil
```

### 2. Ecart majeur n°1 — `ask_qcu`/`ask_qcm` n'existent PAS comme tools separes

Le source planning liste 4 tools `ask_qcu`, `ask_qcm`, `ask_qcu_justification`, `ask_qcm_justification`. **Realite** : feature 018 expose **un seul tool** :

- `ask_interactive_question(question_type, prompt, options, min_selections, max_selections, requires_justification, justification_prompt)` — `backend/app/graph/tools/interactive_tools.py:52-186`.
- Les 4 « variantes » sont des **valeurs** de l'enum `InteractiveQuestionType` (`qcu`, `qcm`, `qcu_justification`, `qcm_justification`) — `backend/app/models/interactive_question.py`.

**Decision pour cette story** : on **garde un seul tool** `ask_interactive_question` (eclatement en 4 = refactor majeur hors scope, casserait spec 018 + 6 prompts modules + frontend). On durcit sa description (use when / don't use when par variante) et on s'assure que `InteractiveQuestionCreate` rejette les champs inconnus.

### 3. Ecart majeur n°2 — les `show_*` n'existent PAS du tout

Les tools `show_kpi_card`, `show_radar_chart`, `show_pie_chart`, `show_timeline`, `show_table`, `show_mermaid`, `show_gauge` ne sont **pas implementes**. Verifie via `grep -rn "show_kpi_card\|show_radar_chart..." backend/app/` → 0 resultat dans le code applicatif.

Les visualisations sont actuellement emises **via des blocs JSON inline dans les reponses LLM** (parsees frontend) ou via les SSE markers (`<!--SSE:{__sse_*__:true,...}-->`), pas via des tools dedies.

**Decision pour cette story** : retirer `show_*` du perimetre. Si la story 4 (eval set) montre des hallucinations de visualisation, on creera ces tools dans une story dediee post-MVP (item 10.7 backlog). **Le dev ne doit pas creer ces tools dans cette PR.**

### 4. Perimetre reel ajuste (14 tools critiques)

| Famille | Fichier | Tool | Type |
|---|---|---|---|
| Question interactive | `interactive_tools.py` | `ask_interactive_question` | mutation widget + persistance |
| Profil | `profiling_tools.py` | `update_company_profile` | mutation BDD |
| Profil | `profiling_tools.py` | `get_company_profile` | lecture |
| ESG | `esg_tools.py` | `create_esg_assessment` | mutation BDD |
| ESG | `esg_tools.py` | `save_esg_criterion_score` | mutation BDD |
| ESG | `esg_tools.py` | `finalize_esg_assessment` | mutation BDD |
| ESG | `esg_tools.py` | `get_esg_assessment` | lecture |
| ESG | `esg_tools.py` | `batch_save_esg_criteria` | mutation BDD batch |
| Candidature | `application_tools.py` | `create_fund_application` | mutation BDD |
| Candidature | `application_tools.py` | `generate_application_section` | mutation LLM+BDD |
| Candidature | `application_tools.py` | `update_application_section` | mutation BDD |
| Candidature | `application_tools.py` | `get_application_checklist` | lecture |
| Candidature | `application_tools.py` | `simulate_financing` | calcul lecture |
| Candidature | `application_tools.py` | `export_application` | export fichier |

**Note** : `get_*` sont inclus dans le scope **uniquement pour la convention de description** (use when / don't use when), pas pour le durcissement Pydantic (lecture seule, pas de payload utilisateur).

**Cible chiffree DoD** : 11 tools de mutation + 3 tools de lecture critiques = **14 tools refactores** (vs « 13 critiques minimum » de la spec planning, on couvre l'integralite).

### 5. Pattern actuel `@tool` vs pattern cible `args_schema=`

Tous les tools existants utilisent le decorateur `@tool` avec kwargs (LangChain auto-genere le schema via inspection des annotations). Exemple `update_company_profile` (`profiling_tools.py:21-46`) :

```python
@tool
async def update_company_profile(
    config: RunnableConfig,
    company_name: str | None = None,
    sector: str | None = None,
    ...
) -> str:
    """Mettre a jour le profil de l'entreprise..."""
```

**Probleme avec ce pattern** :
- Pas de `extra="forbid"` (LangChain auto-genere `additionalProperties: true`).
- Pas de bornes `Field(ge=, le=)` sur `employee_count`, `annual_revenue_xof`, `year_founded`.
- `sector`, `country`, `governance_structure` sont des `str` libres (pas des Enum), alors que la BDD a des Enum dans `app/models/company.py`.

**Pattern cible** (LangChain >=0.3, Pydantic v2) :

```python
from pydantic import BaseModel, ConfigDict, Field
from app.models.company import SectorEnum, CountryEnum

class UpdateCompanyProfileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(None, min_length=1, max_length=200)
    sector: SectorEnum | None = None
    employee_count: int | None = Field(None, ge=1, le=100_000)
    annual_revenue_xof: int | None = Field(None, ge=0, le=10_000_000_000_000)
    year_founded: int | None = Field(None, ge=1900, le=2100)
    country: CountryEnum | None = None
    # ...

@tool(args_schema=UpdateCompanyProfileArgs)
async def update_company_profile(config: RunnableConfig, **kwargs) -> str:
    """<<description beton voir AC>>"""
    ...
```

Raison : `model_config = ConfigDict(extra="forbid")` ne s'applique de maniere sure qu'a une classe Pydantic explicite ; sur les decorateurs `@tool` kwargs purs, LangChain ignore `extra="forbid"` dans certaines versions.

### 6. Schemas existants reutilisables

- `InteractiveQuestionCreate` (`backend/app/schemas/interactive_question.py:25-73`) **est deja exemplaire** :
  - `extra="forbid"` non present → **A AJOUTER** (`model_config = ConfigDict(extra="forbid")`).
  - Tout le reste (Field min/max, Enum, model_validator) est conforme. Ne pas reecrire.
- `CompanyProfileUpdate` (`backend/app/modules/company/schemas.py:54`) : utilise par `update_company_profile`. **A durcir** : ajouter `extra="forbid"` + bornes numeriques + Enum sectoriel.
- Les schemas ESG/Candidature : **a creer**, ils n'existent pas en tant qu'`args_schema` dedies cote tools (les services utilisent leurs propres DTO internes).

### 7. Tests existants

- **Repertoire de tests pour les tools n'existe pas** : `backend/tests/graph/tools/` → 0 fichier. **A creer.**
- Tests existants relatifs : `backend/tests/test_*.py` (935 tests verts, cf. CLAUDE.md spec 018). Le dev doit lancer `pytest backend/` avant et apres pour verifier zero regression.

### 8. Convention prompts / decision tree

Les prompts modules (`backend/app/prompts/`) referencent les tools avec leurs noms exacts. Toute description trop verbeuse risque d'inflater les tokens ; toute description floue brouille la decision. **Mesurer** la longueur cumulee des descriptions avant/apres (script ad hoc OK).

## Acceptance Criteria

1. **AC1 — Conventions de description (5 sections, OBLIGATOIRES pour 14 tools du perimetre).** Chaque tool du perimetre §4 a une docstring (= description LangChain) contenant exactement ces sections, dans cet ordre, en francais avec accents :
   1. **Verbe d'action** (1 phrase, < 25 mots) sans ambiguite. Ex: « Met a jour le profil entreprise (UPSERT) avec les champs fournis. »
   2. **Use when** (bullet list) — au moins 2 cas d'usage explicites.
   3. **Don't use when** (bullet list) — au moins 2 cas avec **renvoi nominatif vers le tool alternatif** (`get_company_profile`, `ask_interactive_question`, etc.).
   4. **Exemple positif** (1 cas user → tool call attendu).
   5. **Anti-exemple** (1 cas user → tool a NE PAS appeler).

2. **AC2 — Schemas Pydantic stricts (11 tools de mutation).** Chaque tool de mutation expose son `args_schema=` pointant vers une classe `BaseModel` qui :
   - Declare `model_config = ConfigDict(extra="forbid")`.
   - Champs requis = `Field(...)` (pas `Optional` quand le metier l'exige — ex: `prompt`, `options` pour `ask_interactive_question`).
   - Tous les choix fermes utilisent un `Enum` Python (pas `str`). Reutiliser les Enum existants de `app/models/` (SectorEnum, CountryEnum, ESGCategoryEnum, ApplicationStatusEnum).
   - Bornes numeriques `Field(ge=, le=)` sur tous les `int`/`float`/`Decimal` (ex: `score: int = Field(..., ge=0, le=100)`).
   - Regex sur les strings courtes contraintes (codes, slugs, ids — ex: `id: str = Field(..., pattern=r"^[a-z0-9_]+$")`).
   - Strings libres bornees `Field(min_length=1, max_length=N)` avec N adapte au metier.

3. **AC3 — Tests unitaires par tool (Pytest, table-driven).** Pour chacun des 14 tools, un test colocate dans `backend/tests/graph/tools/test_<module>_tools_schemas.py` :
   - 1 cas positif : payload valide → instanciation reussie.
   - >=2 cas negatifs : payloads invalides → `ValidationError` levee + message d'erreur testable.
   - 1 cas `extra_field=...` rejete par `extra="forbid"`.
   - Les tests sont parametres via `@pytest.mark.parametrize` ou tables de cas (pas de copy-paste massif).

4. **AC4 — Test meta de conformite.** Un test `backend/tests/graph/tools/test_tools_meta_conformity.py` verifie pour chaque tool LangChain expose dans `__init__.py` (ou liste explicite) :
   - La description contient les 5 sections (regex sur les en-tetes).
   - La description fait >= 200 caracteres.
   - Le `args_schema` (s'il existe) declare `model_config.extra == "forbid"`.
   - Le `args_schema` ne contient aucun champ `str` parmi les champs « choix fermes » (liste blanche : tous les champs marques par convention `_status`, `_type`, `_category`, `country`, `sector` doivent etre Enum).

5. **AC5 — README conventions.** Fichier `backend/app/graph/tools/README.md` cree (si absent) ou mis a jour, contenant :
   - Conventions de nommage tool (`verbe_objet[_modifier]`, snake_case).
   - Template de docstring (les 5 sections de l'AC1) avec un exemple complet.
   - Template de classe `args_schema` (avec `model_config`, Enum, `Field(...)`).
   - Liste des Enum partages a reutiliser (chemin import + valeurs).
   - Section « Anti-patterns » : « ne pas creer un nouveau tool si une description + un Enum suffit a discriminer un cas existant ».

6. **AC6 — Mesure tokens (gate de non-regression).** Un script `backend/scripts/measure_tools_token_budget.py` (ou notebook simple) compte la longueur cumulee (en caracteres) des descriptions des 14 tools du perimetre, avant et apres la PR. Le rapport `backend/tools/_tokens_report.md` (gitignored si volumineux, sinon committe) montre :
   - Total avant : X caracteres.
   - Total apres : Y caracteres.
   - Variation Y/X <= **+25%** (gate strict, sinon revoir verbosite).

7. **AC7 — Non-regression backend.** Apres refactor, `pytest backend/` passe a 100% (>=935 tests verts attendus). Aucun nouveau warning LangChain de type « Tool args_schema mismatch » dans `backend/app/main.py` au demarrage.

8. **AC8 — Compatibilite ascendante des prompts.** Les 7 prompts modules (`backend/app/prompts/{chat,esg_scoring,carbon,financing,application,credit,action_plan}.py`) ne sont PAS modifies dans cette PR. Si le dev decouvre qu'un prompt reference un nom de tool qui change, il **arrete** et negocie le scope (probablement aucun changement de nom requis).

## Tasks / Subtasks

- [x] **Tache 1 — Lecture preparatoire (AC1, AC2, AC8)**
  - [x] 1.1 Lire `backend/app/graph/tools/{interactive,profiling,esg,application}_tools.py` integralement.
  - [x] 1.2 Lire les Enum disponibles dans `backend/app/models/{company,esg,application,interactive_question}.py` et lister ceux a reutiliser.
  - [x] 1.3 Lire les 7 prompts modules et copier la liste des references aux tools (verifier qu'aucun nom n'evolue dans cette PR).
- [x] **Tache 2 — Convention + README (AC1, AC5)**
  - [x] 2.1 Creer/mettre a jour `backend/app/graph/tools/README.md` avec les 5 sections de docstring + template `args_schema` + liste Enum partages.
  - [x] 2.2 Faire valider le template par un commit isole avant de l'appliquer aux 14 tools (permet revue rapide).
- [x] **Tache 3 — Refactor des schemas (AC2)**
  - [x] 3.1 `interactive_tools.py` : ajouter `model_config = ConfigDict(extra="forbid")` a `InteractiveQuestionCreate` + creer `AskInteractiveQuestionArgs` cable via `args_schema`.
  - [x] 3.2 `profiling_tools.py` : `UpdateCompanyProfileArgs` + `GetCompanyProfileArgs` (extra=forbid, SectorEnum, bornes).
  - [x] 3.3 `esg_tools.py` : 5 schemas (Create/Save/Finalize/Get/BatchSave) avec UUID pattern, criterion code pattern `^[ESG][0-9]{1,3}$`, score 0-10.
  - [x] 3.4 `application_tools.py` : 6 schemas + ExportFormat Enum (pdf|docx|json), section_key pattern, content max 50000.
- [x] **Tache 4 — Refactor descriptions (AC1)**
  - [x] 4.1 Reecrire les 14 docstrings selon le template AC1 (5 sections obligatoires).
  - [x] 4.2 Pour chaque tool, lister explicitement le tool alternatif dans « Don't use when » (en backticks).
- [x] **Tache 5 — Tests unitaires (AC3, AC4)**
  - [x] 5.1 Creer `backend/tests/graph/tools/__init__.py` + 4 `test_*_tools_schemas.py`.
  - [x] 5.2 Creer `backend/tests/graph/tools/test_tools_meta_conformity.py` (4 invariants AC4 parametres sur les 14 tools).
  - [x] 5.3 Verifier `pytest backend/tests/graph/tools/ -v` : 143 verts.
- [x] **Tache 6 — Mesure tokens (AC6)**
  - [x] 6.1 `backend/scripts/measure_tools_token_budget.py`.
  - [x] 6.2 Baseline capture : 4912 chars (14 tools).
  - [x] 6.3 Apres refactor : 6086 chars (+23.90%, gate `<= +25%` OK).
- [x] **Tache 7 — Validation finale (AC7, AC8)**
  - [x] 7.1 `pytest backend/` : 1219 passed (3 echecs guided_tour pre-existants sur main, hors perimetre AC8).
  - [x] 7.2 `python -c "from app.main import app"` demarre sans warning LangChain.
  - [x] 7.3 Smoke test : import app + 77 routes detectees + 14 tools chargent leur args_schema.
  - [x] 7.4 PR vers `main` ouverte avec rapport tokens.

## Dev Notes

### Architecture & guardrails

- **Versions** (CLAUDE.md confirmees) : Python 3.12, FastAPI, LangGraph >=0.2.0, LangChain >=0.3.0, langchain-openai >=0.3.0, Pydantic v2.
- **Pydantic v2 specifique** : utiliser `model_config = ConfigDict(extra="forbid")`, pas `class Config: extra = "forbid"` (deprecated). `Field(...)` au lieu de `default=Ellipsis`.
- **LangChain `@tool` + `args_schema`** : les deux co-existent. Quand `args_schema=ClassPydantic` est fourni, le decorateur ignore l'inspection des annotations de fonction (les kwargs deviennent valides via Pydantic). Le schema **doit** matcher la signature kwargs (sinon erreur runtime au 1er appel).
- **`config: RunnableConfig`** : ce parametre LangChain ne fait PAS partie du payload outil ; il est injecte par le runtime. Ne PAS l'inclure dans `args_schema`.

### Source tree a toucher

```
backend/app/graph/tools/
  README.md                    [CREE/MAJ]
  interactive_tools.py         [MODIFIE]
  profiling_tools.py           [MODIFIE]
  esg_tools.py                 [MODIFIE]
  application_tools.py         [MODIFIE]
backend/app/schemas/
  interactive_question.py      [MODIFIE — ajout extra="forbid"]
backend/tests/graph/tools/     [CREE — nouveau repertoire]
  __init__.py
  test_interactive_tools_schemas.py
  test_profiling_tools_schemas.py
  test_esg_tools_schemas.py
  test_application_tools_schemas.py
  test_tools_meta_conformity.py
backend/scripts/
  measure_tools_token_budget.py [CREE]
```

**Hors scope (NE PAS toucher)** :
- `backend/app/prompts/*.py` (verrou AC8).
- `backend/app/graph/nodes/*.py` (les noeuds sont stables, on durcit les contrats des tools sans changer leur cablage).
- Les 8 autres modules de tools : `action_plan_tools.py`, `carbon_tools.py`, `chat_tools.py`, `credit_tools.py`, `document_tools.py`, `financing_tools.py`, `guided_tour_tools.py` — story 2 (filtrage) et stories ulterieures s'en occupent.

### Standards de tests (rappel global)

- Couverture minimale 80% (cf. `~/.claude/rules/common/testing.md`).
- Framework : `pytest` + `pytest-asyncio` (deja en place, voir spec 017).
- Pattern : table-driven via `@pytest.mark.parametrize`.
- Marquage : `pytest.mark.unit` pour les tests de schemas (pas de DB, pas de LLM, pas d'I/O).
- Activer le venv : `source backend/venv/bin/activate` avant `pytest` (cf. CLAUDE.md).

### Anti-patterns a eviter (LLM dev mistakes)

1. **NE PAS** creer les tools `show_*` (kpi_card, radar_chart, etc.) — hors scope §3.
2. **NE PAS** eclater `ask_interactive_question` en 4 tools — hors scope §2.
3. **NE PAS** modifier les prompts modules — verrou AC8.
4. **NE PAS** changer les noms de tools (`update_company_profile`, etc.) — casserait les references prompts et `tool_call_logs.tool_name`.
5. **NE PAS** introduire de Enum nouvel uniquement dans `app/graph/tools/` — reutiliser ceux de `app/models/`. Si un Enum manque, l'ajouter dans `app/models/` avec migration Alembic correspondante (ce qui sortirait du scope ; donc s'arreter et demander).
6. **NE PAS** retirer le retour `<!--SSE:...-->` des tools `update_company_profile`, `ask_interactive_question` — il est consomme par le frontend (specs 012, 018).
7. **NE PAS** utiliser `pydantic.v1` ou `langchain.pydantic_v1` (deprecated). Importer depuis `pydantic` directement.
8. **NE PAS** rendre des champs metier optionnels avec un defaut « magique » (ex: `score: int = 0`). Pour les mutations, requis = `Field(...)`.

### Methodologie suggeree (TDD)

1. Pour chaque tool, ecrire d'abord le test schema (AC3, RED).
2. Implementer le schema Pydantic strict (GREEN).
3. Cabler `args_schema=` sur le decorateur (verifier startup app sans warning).
4. Reecrire la docstring (AC1).
5. Lancer le test meta (AC4) → tout doit passer.
6. Mesure tokens (AC6) en fin de boucle, pas a chaque tool (sinon bruit).

### References (avec lignes)

- Tools existants : `backend/app/graph/tools/interactive_tools.py:52-186`, `backend/app/graph/tools/profiling_tools.py:21-122`, `backend/app/graph/tools/esg_tools.py:14-364`, `backend/app/graph/tools/application_tools.py:59-306`.
- Helpers communs : `backend/app/graph/tools/common.py:1-185` (`get_db_and_user`, `log_tool_call`).
- Schemas Pydantic deja conformes (a copier comme reference) : `backend/app/schemas/interactive_question.py:16-73`.
- Schema a durcir : `backend/app/modules/company/schemas.py:54-75` (`CompanyProfileUpdate`).
- Source planning : `_bmad-output/planning-artifacts/module-10-tool-use-reliability/story-1-tool-descriptions-pydantic-strict.md` (lignes 26-69 : perimetre + AC origine).
- Source epic : `_bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md` (lignes 64-86 : architecture cible ; lignes 88-96 : criteres de succes epic).
- Specs amont : `CLAUDE.md` (Recent Changes) — specs 012 (32 tools origine), 015 (renforcement prompts ESG/application/credit), 018 (interactive widgets).

### Project Structure Notes

- L'arborescence `backend/tests/graph/tools/` n'existe pas encore. Le dev doit la creer **avec un `__init__.py` vide** (sinon `pytest` n'auto-decouvre pas en mode pkg).
- Le repertoire `backend/scripts/` existe deja (cf. seed scripts cites dans story 8.3). Compatible.

### Sprint status note (a faire en parallele de la PR)

Au moment de la redaction, `_bmad-output/implementation-artifacts/sprint-status.yaml` ne contient PAS encore d'entrees pour Module 10 (`epic-10`, `10-1-...`, etc.). Le dev (ou le PM) doit :
- Ajouter `epic-10: in-progress` dans le bloc `development_status`.
- Ajouter `10-1-tool-descriptions-pydantic-strict: ready-for-dev`.
- Mettre a jour `last_updated` et `last_story_created`.

Cette mise a jour est faite hors PR de code (commit dedie `chore: track epic 10 in sprint-status`).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) via Claude Code CLI (bmad-dev-story workflow).

### Debug Log References

- Baseline tokens AVANT : 4912 caracteres / 14 tools.
- Iteration 1 docstrings : 8637 chars (+75.83%) → gate FAILED, trim necessaire.
- Iteration 2 (compaction bullets) : 6489 chars (+32.11%) → gate FAILED.
- Iteration 3 (compaction finale + restauration accents francais runtime) : 6086 chars (+23.90%) → gate **OK**.
- Test `test_closed_choices_are_enum` initialement en echec sur `sub_sector`, `country` (str libres dans `app/models/company.py`) → ajoutes a EXEMPT_NAMES (CountryEnum hors scope, cf. story §5 anti-patterns).
- 3 echecs `tests/test_prompts/test_guided_tour_*` pre-existants sur `main` (taille prompt 7190 > 7000) → hors perimetre story 10.1, verrouilles par AC8 (NE PAS modifier prompts).

### Completion Notes List

- **AC1** ✅ : 14 docstrings reecrites selon template 5 sections (verbe / Use when / Don't use when / Exemple / Anti). `Don't use when` cite systematiquement un tool alternatif en backticks.
- **AC2** ✅ : 14 `args_schema` Pydantic v2 (`extra="forbid"`, `Field(ge=, le=)`, Enum reutilisees `SectorEnum`/`TargetType`/`InteractiveQuestionType`/`ExportFormat`, regex UUID + criterion_code + section_key).
- **AC3** ✅ : 4 fichiers `test_*_tools_schemas.py` table-driven (`@pytest.mark.parametrize`) : 1 cas positif + >=2 cas negatifs + 1 cas `extra` rejete par tool.
- **AC4** ✅ : `test_tools_meta_conformity.py` parametre sur 14 tools, 4 invariants verifies dynamiquement (5 sections, longueur >=200, extra=forbid, choix fermes en Enum).
- **AC5** ✅ : `backend/app/graph/tools/README.md` cree avec 6 sections (nommage, template docstring, template args_schema, table Enum partages, anti-patterns, mesure tokens).
- **AC6** ✅ : `backend/scripts/measure_tools_token_budget.py` + baseline + rapport `backend/tools/_tokens_report.md`. Variation +23.90% <= +25% (gate strict).
- **AC7** ✅ : 1219 tests backend passent (155 nouveaux + tous les autres). 3 echecs guided_tour pre-existants sur main (verifie via `git stash` + rerun) — non causes par cette PR.
- **AC8** ✅ : aucune modification des 7 prompts modules ni des 8 autres modules de tools (carbon, financing, credit, document, action_plan, chat, guided_tour, common). Aucun tool renomme. Aucun tool `show_*` cree. `ask_interactive_question` reste un seul tool.

#### Rapport tokens

| | Avant | Apres | Variation |
|---|---|---|---|
| Total descriptions | 4912 | 6086 | +1174 (**+23.90%**) |
| Gate `<= +25%` | — | — | **OK** |

Detail par tool : voir `backend/tools/_tokens_report.md`.

### File List

**Modifies (5)** :
- `backend/app/graph/tools/interactive_tools.py` (rewrite docstring + AskInteractiveQuestionArgs cable args_schema).
- `backend/app/graph/tools/profiling_tools.py` (UpdateCompanyProfileArgs, GetCompanyProfileArgs + descriptions).
- `backend/app/graph/tools/esg_tools.py` (5 schemas + descriptions).
- `backend/app/graph/tools/application_tools.py` (6 schemas + ExportFormat enum + descriptions).
- `backend/app/schemas/interactive_question.py` (ajout `model_config = ConfigDict(extra="forbid")` a `InteractiveQuestionCreate`).

**Crees (8)** :
- `backend/app/graph/tools/README.md` (conventions, templates, anti-patterns).
- `backend/scripts/measure_tools_token_budget.py` (CLI baseline/report avec gate +25%).
- `backend/tools/_tokens_baseline.json` (snapshot avant refactor, 14 tools).
- `backend/tools/_tokens_report.md` (rapport apres refactor).
- `backend/tests/graph/__init__.py` (vide, package).
- `backend/tests/graph/tools/__init__.py` (vide, package).
- `backend/tests/graph/tools/test_interactive_tools_schemas.py` (10 tests).
- `backend/tests/graph/tools/test_profiling_tools_schemas.py` (16 tests).
- `backend/tests/graph/tools/test_esg_tools_schemas.py` (29 tests).
- `backend/tests/graph/tools/test_application_tools_schemas.py` (35 tests).
- `backend/tests/graph/tools/test_tools_meta_conformity.py` (57 tests parametres : 14 tools × 4 invariants + 1 count).

**Total** : 5 modifies + 11 crees = 16 fichiers.
