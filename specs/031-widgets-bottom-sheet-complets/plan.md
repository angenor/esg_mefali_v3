# Implementation Plan: Widgets Interactifs Bottom Sheet Complets (F10)

**Branch**: `feat/F10-widgets-bottom-sheet-complets` (SpecKit folder `031-widgets-bottom-sheet-complets`) | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/031-widgets-bottom-sheet-complets/spec.md`

## Summary

F10 complète l'architecture des widgets interactifs conversationnels en livrant les 9 widgets manquants (sur 10 prévus par le Module 1.1.1) :  `ask_yes_no`, `ask_select`, `ask_number`, `ask_date`, `ask_date_range`, `ask_rating`, `ask_file_upload`, `show_form`, `show_summary_card`. La feature étend l'enum `InteractiveQuestionType`, ajoute deux colonnes `payload`/`response_payload` jsonb à la table `interactive_questions`, expose 9 nouveaux tools LangChain typés avec Pydantic strict, et livre 9 composants Vue avec dark mode et accessibilité ARIA. Elle active surtout le **pattern de confirmation des actions destructives** (Module 1.1.3) en ajoutant un paramètre `confirm: bool = False` à tous les tools de mutation destructifs (`delete_*`, `revoke_*`, `cancel_*`), garantissant qu'aucune donnée ne peut être détruite par hallucination LLM sans une confirmation utilisateur explicite via un widget rouge avec click-and-hold de 2 secondes. L'approche technique réutilise intégralement l'infrastructure F18 (table satellite `interactive_questions`, marker SSE, dispatcher frontend) sans casser la rétro-compatibilité des 4 widgets QCU/QCM existants.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**:
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, LangGraph (>=0.2.0), LangChain (>=0.3.0), langchain-openai (>=0.3.0), Pydantic v2, python-magic (NEW pour la validation MIME des uploads)
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4, GSAP (animations existantes), DOMPurify, **vue-virtual-scroller** (NEW si absent du `package.json`, sinon réutilisation), **zod** (NEW si absent, sinon réutilisation)
**Storage**: PostgreSQL 16 + pgvector (embeddings non concernés par F10), table `interactive_questions` étendue (colonnes `payload jsonb`, `response_payload jsonb`)
**Testing**:
- Backend : pytest + pytest-asyncio + pytest-cov (cible ≥ 80 %)
- Frontend : Vitest + @vue/test-utils + happy-dom (cible ≥ 80 %)
- E2E : Playwright (`@playwright/test`) — `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts`
**Target Platform**: Linux server (backend Docker / venv local), navigateur web moderne (Chrome/Firefox/Safari Edge récents), responsive mobile (≤ 480 px)
**Project Type**: Web application — backend FastAPI + frontend Nuxt 4
**Performance Goals**:
- Rendu d'un `ask_select` avec 200 options ≤ 200 ms
- Animation slide-up bottom sheet 60 fps (déjà acquis F18)
- Création d'une question interactive en BDD < 100 ms (transaction unique)
- Hold de 2 secondes pour les actions destructives (délibérément contraint par UX, pas une cible de perf)
**Constraints**:
- Multi-tenant strict (F02) : `account_id` hérité de la conversation, RLS PostgreSQL
- Audit log append-only (F03) : toute mutation destructive trace son `confirm` dans `audit_log`
- Money typed (F04) : `<MoneyDisplay>` réutilisé pour les équivalents devise
- RGPD (F05) : aucune donnée sensible dans les payloads des widgets (le file_upload passe par l'API documents existante avec consent)
- Dark mode obligatoire pour les 9 nouveaux composants
- Français accentué dans les libellés UI
- Accessibilité : ARIA roles, navigation clavier, `prefers-reduced-motion: reduce`
**Scale/Scope**:
- 9 nouveaux tools LangChain
- 9 nouveaux composants Vue + 1 fallback (`UnsupportedWidget.vue`)
- 1 migration Alembic 031 (extension enum + colonnes + contrainte)
- ~40 tests unitaires nouveaux + 6 tests E2E Playwright (5 P1 + 1 régression)
- Cible utilisateurs : PME africaines francophones (UEMOA/CEDEAO), niveau numérique varié

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe constitution | Statut | Justification |
|---|---|---|
| I. Francophone-First & contextualisation africaine | PASS | UI 100 % en français accentué, devises XOF/EUR/USD/CDF supportées, secteur informel pris en compte (formulaires permettent des champs optionnels), bornes monétaires alignées sur les ordres de grandeur PME UEMOA. |
| II. Architecture modulaire | PASS | F10 ne crée aucun nouveau module ; il étend un module existant (Agent Conversationnel) avec 9 widgets supplémentaires. Aucun couplage ajouté entre modules. Les widgets sont stateless et n'altèrent que la table satellite `interactive_questions`. |
| III. Conversation-driven UX | PASS | Renforce le principe : F10 remplace 8 questions séquentielles par un seul `show_form`, et garantit que les choix structurés (devise, date, pays, rating) ne passent pas par du texte libre fragile. C'est le principe le plus directement valorisé par F10. |
| IV. Test-First (NON-NEGOTIABLE) | PASS | TDD strict : 1 test par tool écrit avant l'implémentation, tests Vitest avant les composants, Playwright E2E avant l'intégration. Cible ≥ 80 % couverture confirmée. |
| V. Sécurité & protection des données | PASS | Validation Pydantic stricte (`extra="forbid"`), bornes dures (max 200 options, max 10 fields, max 10 Mo upload), validation MIME via `python-magic`, pattern destructif avec `confirm=True` obligatoire. Aucune nouvelle donnée sensible collectée. |
| VI. Inclusivité & accessibilité | PASS | ARIA roles (`radiogroup`, `checkbox`, `combobox`, `dialog`), navigation clavier, `prefers-reduced-motion`, libellés en français clair, fallback `UnsupportedWidget.vue` pour la résilience. |
| VII. Simplicité & YAGNI | PASS | Réutilisation maximale de l'infra F18 (table, SSE, marker, dispatcher) ; aucune nouvelle table, aucun service supplémentaire, aucun microservice. Hors-scope explicitement listé : pas de wizard multi-step, pas d'auto-complétion ML, pas d'antivirus sandbox. Le pattern `payload jsonb` vs colonnes typées est délibérément choisi pour la simplicité. |

**Verdict** : Aucune violation de constitution. Pas de Complexity Tracking nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/031-widgets-bottom-sheet-complets/
├── plan.md                         # Ce fichier (output /speckit.plan)
├── research.md                     # Output Phase 0 (/speckit.plan)
├── data-model.md                   # Output Phase 1 (/speckit.plan)
├── quickstart.md                   # Output Phase 1 (/speckit.plan)
├── contracts/
│   ├── interactive_tools_schemas.md   # Schémas Pydantic des 9 tools
│   ├── widget_payloads.md             # Forme jsonb du payload BDD
│   ├── widget_responses.md            # Forme jsonb du response_payload
│   ├── sse_events.md                  # Marker SSE étendu
│   └── destructive_pattern.md         # Contrat des tools de mutation
├── checklists/
│   └── requirements.md             # Validation spec déjà créée
├── spec.md                         # Spec produite par /speckit.specify
└── tasks.md                        # Output /speckit.tasks (NON créé par /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 031_extend_interactive_questions.py   # NEW migration
├── app/
│   ├── models/
│   │   └── interactive_question.py               # MODIFIED enum + colonnes payload
│   ├── schemas/
│   │   └── interactive_question.py               # MODIFIED + 18 nouveaux schémas (9 payload + 9 response)
│   ├── graph/
│   │   ├── tools/
│   │   │   ├── interactive_tools.py              # MODIFIED + 9 nouveaux tools
│   │   │   ├── common.py                         # MODIFIED + helper requires_destructive_confirmation
│   │   │   ├── application_tools.py              # MODIFIED si delete_application existe ; ajout pattern confirm
│   │   │   ├── project_tools.py                  # MODIFIED (existe déjà depuis F25 avec delete_project) — ajout du paramètre confirm sur delete_project
│   │   │   ├── esg_tools.py                      # MODIFIED ajout pattern confirm sur delete_esg_assessment si présent
│   │   │   ├── carbon_tools.py                   # MODIFIED ajout pattern confirm sur delete_carbon_assessment si présent
│   │   │   └── attestation_tools.py              # NEW (stub) si revoke_attestation pas encore livré (raccrochage F26)
│   │   └── tool_selector_config.py               # MODIFIED matrice de visibilité
│   ├── prompts/
│   │   ├── widget.py                             # MODIFIED (étend WIDGET_INSTRUCTION existant F18)
│   │   ├── system.py                             # MODIFIED (refresh injection si nécessaire pour le chat global)
│   │   ├── esg_scoring.py                        # MODIFIED (vérification injection)
│   │   ├── carbon.py                             # MODIFIED (vérification injection)
│   │   ├── financing.py                          # MODIFIED (vérification injection)
│   │   ├── application.py                        # MODIFIED (vérification injection)
│   │   ├── credit.py                             # MODIFIED (vérification injection)
│   │   └── action_plan.py                        # MODIFIED (vérification injection)
│   ├── api/
│   │   └── routers/
│   │       └── documents.py                      # MODIFIED ajout validation magic MIME (FR-025)
│   └── core/
│       └── fx_rates.py                           # NEW utility constants statiques (XOF↔EUR/USD/CDF)
├── requirements.txt                              # MODIFIED ajout python-magic
└── tests/
    ├── unit/
    │   ├── graph/tools/
    │   │   ├── test_interactive_tools_yes_no.py
    │   │   ├── test_interactive_tools_select.py
    │   │   ├── test_interactive_tools_number.py
    │   │   ├── test_interactive_tools_date.py
    │   │   ├── test_interactive_tools_date_range.py
    │   │   ├── test_interactive_tools_rating.py
    │   │   ├── test_interactive_tools_file_upload.py
    │   │   ├── test_interactive_tools_form.py
    │   │   ├── test_interactive_tools_summary_card.py
    │   │   └── test_destructive_pattern.py
    │   └── schemas/
    │       └── test_interactive_question_payloads.py
    ├── integration/
    │   ├── test_widget_e2e_yes_no_destructive.py
    │   ├── test_widget_e2e_select_search.py
    │   ├── test_widget_e2e_number_money.py
    │   ├── test_widget_e2e_form_create.py
    │   ├── test_widget_e2e_summary_card_edit.py
    │   └── test_alembic_031_up_down_up.py
    └── conftest.py                               # MODIFIED si nécessaire pour fixtures payloads

frontend/
├── app/
│   ├── components/
│   │   └── chat/
│   │       ├── InteractiveQuestionInputBar.vue   # MODIFIED dispatcher type → composant
│   │       └── widgets/
│   │           ├── YesNoWidget.vue                # NEW
│   │           ├── SelectWidget.vue               # NEW
│   │           ├── NumberWidget.vue               # NEW
│   │           ├── DateWidget.vue                 # NEW
│   │           ├── DateRangeWidget.vue            # NEW
│   │           ├── RatingWidget.vue               # NEW
│   │           ├── FileUploadWidget.vue           # NEW
│   │           ├── FormWidget.vue                 # NEW
│   │           ├── SummaryCardWidget.vue          # NEW
│   │           └── UnsupportedWidget.vue          # NEW fallback
│   ├── composables/
│   │   ├── useInteractiveQuestion.ts             # MODIFIED extensions
│   │   └── useChat.ts                            # MODIFIED submitInteractiveAnswer + suppression heuristique fragile
│   └── types/
│       └── interactive-question.ts               # MODIFIED + 9 nouveaux types/payloads/responses
├── package.json                                  # MODIFIED ajout vue-virtual-scroller, zod si absents
└── tests/
    ├── unit/
    │   └── components/chat/widgets/
    │       ├── YesNoWidget.spec.ts
    │       ├── SelectWidget.spec.ts
    │       ├── NumberWidget.spec.ts
    │       ├── DateWidget.spec.ts
    │       ├── DateRangeWidget.spec.ts
    │       ├── RatingWidget.spec.ts
    │       ├── FileUploadWidget.spec.ts
    │       ├── FormWidget.spec.ts
    │       ├── SummaryCardWidget.spec.ts
    │       └── UnsupportedWidget.spec.ts
    │   └── composables/
    │       └── useInteractiveQuestion.spec.ts
    └── e2e/
        ├── F10-widgets-bottom-sheet-complets.spec.ts   # NEW 5 scénarios P1 + 1 régression QCU/QCM
        └── fixtures/                                    # NEW PDF de test, etc. si nécessaire
```

**Structure Decision**: Web application (Option 2) — backend FastAPI + frontend Nuxt 4, conforme à la stack imposée par `.cc-orchestrator.md` et au projet existant. Les répertoires sources `backend/app/` et `frontend/app/` (note : Nuxt 4 utilise `app/` au lieu de `src/`) hébergent les fichiers modifiés et les nouveaux fichiers selon le découpage standard du projet (modèles SQLAlchemy → `models/`, schémas Pydantic → `schemas/`, tools LangGraph → `graph/tools/`, composants Vue → `components/chat/widgets/`, composables → `composables/`, types TypeScript → `types/`).

## Phase 0 — Outline & Research

**Output**: `research.md` (généré séparément).

Sujets recherchés et résolutions :

1. **Persistance par variante** : décision `payload jsonb` discriminé Pydantic vs colonnes dédiées par type vs tables satellites — choix `payload jsonb` + Pydantic discriminé. Justification : simplicité (YAGNI), évite migrations futures à chaque nouveau widget, rétro-compatible avec F18.
2. **Click-and-hold 2 secondes** : recherche libs Vue (vue-pressable) vs implémentation native Tailwind+CSS. Choix : implémentation native (CSS keyframes + listeners `@mousedown/@mouseup` + accessibilité clavier). Justification : zéro dépendance, contrôle total des animations dark mode et `prefers-reduced-motion`.
3. **Virtualisation listes longues** : `vue-virtual-scroller` est le standard de fait pour Vue 3. Vérification de présence dans `package.json` ; ajout si absent. Alternative : `vue-virtual-list` mais maintien moins actif.
4. **Validation client formulaires** : `zod` est compatible TypeScript strict, large adoption. Vérification présence dans `package.json` ; ajout si absent. Alternative : `valibot` (plus léger), mais `zod` mieux documenté pour Vue 3.
5. **Validation MIME signature backend** : `python-magic` (wrapper Python pour libmagic) est le standard. Alternative : `filetype` (pure Python, signatures plus limitées). Choix : `python-magic` pour robustesse, ajout `libmagic` à la doc Docker/dev.
6. **Pattern destructif backend** : exploration des recettes LangChain/LangGraph pour return early avec confirmation. Choix : retour string sérialisé `{"requires_confirmation": True, ...}` interprété par le LLM via prompt instruction. Pattern simple, sans middleware.
7. **Taux de change XOF↔EUR/USD/CDF** : XOF↔EUR a une parité fixe officielle 655.957 (BCEAO) ; XOF↔USD/CDF varient. Choix : table `referential_fx_rates` future + fallback constants statiques côté backend (`backend/app/core/fx_rates.py`). MVP : constants only.
8. **Format dates français** : `Intl.DateTimeFormat('fr-FR', {dateStyle: 'long'})` natif navigateur, équivalent côté backend via `babel.dates.format_date(value, 'long', locale='fr')`. Choix : Intl natif côté frontend, pas de lib externe.
9. **Patterns d'extension d'enum PostgreSQL Alembic** : `op.execute("ALTER TYPE ... ADD VALUE IF NOT EXISTS '...'")` avec autocommit. Pattern bien documenté SQLAlchemy/Alembic. Down nécessite recréation enum + cast columns (procédure complexe ; documentée en research.md).
10. **Rétro-compatibilité widgets F18** : analyse de `InteractiveQuestionInputBar.vue` existant — refactor en dispatcher avec `<component :is="widgetComponent">`, pas de breaking change pour les 4 widgets existants.

## Phase 1 — Design & Contracts

**Outputs** : `data-model.md`, `contracts/*.md`, `quickstart.md`, agent context update.

### Data Model (résumé — détail dans `data-model.md`)

Entité étendue : `InteractiveQuestion`.
- Champ existant `question_type: str(24)` : enum élargi (4 valeurs existantes + 9 nouvelles).
- Nouveau champ `payload: jsonb NOT NULL DEFAULT '{}'` — paramètres spécifiques par variante, validés via `InteractiveQuestionPayload` (union discriminée Pydantic).
- Nouveau champ `response_payload: jsonb NULL` — réponse structurée, validée via `InteractiveQuestionResponse` (union discriminée).
- Contrainte `ck_iq_max_le_8` modifiée : `max_selections <= 8 OR question_type IN ('select', 'form')`.
- Index existant `ix_interactive_questions_module_state` conservé.

Pas de nouvelle table.

### Contracts (résumé — détail dans `contracts/`)

1. **interactive_tools_schemas.md** : signatures Pydantic des 9 tools (`AskYesNoArgs`, `AskSelectArgs`, ...).
2. **widget_payloads.md** : structure JSON du `payload` BDD pour chaque variante.
3. **widget_responses.md** : structure JSON du `response_payload` BDD pour chaque variante.
4. **sse_events.md** : marker SSE `<!--SSE:{"__sse_interactive_question__":true, "type":"...", "payload":{...}}-->` et événement frontend `interactive_question` étendu.
5. **destructive_pattern.md** : contrat des tools de mutation : signature `confirm: bool = False`, format de retour `{"requires_confirmation": True, "message": "...", "destructive_action": "..."}`, instruction LLM associée.

### Quickstart (résumé — détail dans `quickstart.md`)

Étapes pour un développeur :
1. `git checkout feat/F10-widgets-bottom-sheet-complets`
2. Backend : `cd backend && source venv/bin/activate && pip install -r requirements.txt` (vérifier python-magic + libmagic)
3. `alembic upgrade head` → applique 031
4. `uvicorn app.main:app --reload`
5. Frontend : `cd frontend && npm install` (vérifier vue-virtual-scroller, zod)
6. `npm run dev`
7. Démo : ouvrir une conversation, demander « supprime mon projet test » → widget rouge avec hold 2 s
8. Tests : `pytest tests/unit/graph/tools/test_interactive_tools_*.py -v` puis `npx playwright test tests/e2e/F10-*.spec.ts`

### Agent Context Update

Exécuter `.specify/scripts/bash/update-agent-context.sh claude` pour propager les nouvelles technos (python-magic, vue-virtual-scroller, zod) dans `CLAUDE.md` (section Active Technologies). Ajout incrémental sans casser les sections manuelles.

## Phase 2 — Tasks (NOT created by /speckit.plan)

`/speckit.tasks` génèrera `tasks.md` ordonné par dépendance et phase :
- Phase A : tests rouges (TDD strict)
- Phase B : implémentation backend (migration → models → schémas → tools → tool_selector → prompts → tests verts)
- Phase C : implémentation frontend (types → composables → composants → dispatcher → tests verts)
- Phase D : intégration E2E Playwright + non-régression QCU/QCM
- Phase E : doc + agent context update

## Complexity Tracking

> **Aucune violation de constitution. Tableau intentionnellement vide.**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (aucune) | (n/a) | (n/a) |
