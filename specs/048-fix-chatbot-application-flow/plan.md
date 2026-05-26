# Implementation Plan: Fiabiliser la création de dossier de candidature et la mémoire ESG du chatbot

**Branch**: `048-fix-chatbot-application-flow` | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/048-fix-chatbot-application-flow/spec.md`

## Summary

Trois ruptures cassent le parcours « tout via le chatbot » d'une PME qui veut candidater à une offre de financement vert. L'investigation a localisé les trois causes racines dans le code existant :

1. **Le chatbot ne peut pas créer le dossier** (FR-001/002) — `create_fund_application` n'est exposé qu'aux slugs de page `financing`/`candidatures` (et nœuds `financing`/`application`) dans `PAGE_TOOL_MAPPING`. Quand l'intention est exprimée depuis une autre page (ex. `/documents` → slug `documents`), le sélecteur (`select_tools_for_node`, logique « page OU nœud » mutuellement exclusive) filtre le tool → le LLM hallucine « outil indisponible ».
2. **Le travail ESG n'est pas reconnu entre sessions** (FR-007/012) — la persistance est correcte (le draft est dédoublonné côté service, les réponses sont en UPSERT), mais `_load_full_context_for_state` ne charge que profil + projets actifs : aucun résumé proactif des évaluations ESG-projet n'est injecté dans le contexte LangGraph, et le LLM doit deviner d'appeler `list_project_esg_assessments`/`get_project_esg_assessment` (déjà disponibles via `GLOBAL_WHITELIST`).
3. **Le bouton « Candidater » est mort** (FR-013/015) — `handleApply()` (`frontend/app/pages/financing/offers/[offer_id].vue:89`) navigue vers `/financing/offers/{id}/apply`, une route inexistante (« Préparation pour F15 »). Aucun appel API. De plus, l'endpoint REST `POST /api/applications/` et `create_application(service)` n'acceptent ni `offer_id` ni `project_id` et ne dédoublonnent pas — un dossier UI ne serait pas équivalent au dossier chat.

**Approche technique** (détaillée dans [research.md](./research.md)) :

- **Sélecteur de tools piloté par l'intention** : refactorer `select_tools_for_node` pour **unir** les tools du nœud LangGraph en cours d'exécution (= intention classifiée par le routeur F013) aux tools de la page, avec une troncature qui **priorise** `GLOBAL_WHITELIST` puis les tools du nœud (intention) puis les tools de page. `create_fund_application` survit ainsi dès que le routeur route vers le nœud `financing`/`application`, quelle que soit la page.
- **Contexte ESG proactif** : enrichir `_load_full_context_for_state` d'un résumé léger des évaluations ESG-projet (par projet : référentiel, state, score, coverage_rate, compteurs couverts/manquants), propagé dans `ConversationState` et injecté dans les prompts financement/application/ESG.
- **Génération réelle du document** (Q1=B) : câbler le tool chat `export_application` (stub) au vrai module `applications/export.py`, persister le fichier dans `/uploads/applications/` et l'enregistrer comme document utilisateur visible dans `/documents`.
- **Gating ESG** (Q4=A) : avant génération du dossier, vérifier la couverture des critères requis du référentiel de l'offre ; si incomplet, bloquer et guider vers les critères manquants.
- **Parité UI/chat** : étendre `ApplicationCreate` + `create_application(service)` pour accepter `offer_id`/`project_id` et dédoublonner (FR-006/016) ; réécrire `handleApply()` pour appeler l'API et naviguer vers le dossier créé.

**Aucune nouvelle table ni migration** : réutilisation stricte des entités existantes (`fund_applications`, `projects`, `offers`, `referentials`/`criteria`, `project_esg_assessments`, `project_esg_criterion_responses`, `documents`).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy async, Pydantic v2, LangGraph (>=0.2), LangChain (>=0.3), WeasyPrint/python-docx (export) ; Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS
**Storage**: PostgreSQL 16 + pgvector — **aucune nouvelle table, aucune migration Alembic** (réutilisation des tables existantes)
**Testing**: pytest (backend, SQLite in-memory + asyncio) ; Vitest + Playwright E2E (frontend)
**Target Platform**: Serveur Linux (backend), navigateurs modernes (frontend)
**Project Type**: web (monolithe modulaire backend FastAPI + frontend Nuxt)
**Performance Goals**: sélection de tools déterministe et pure (pas d'I/O) ; chargement contexte ESG ≤ 1 requête supplémentaire bornée (limit 20 projets) au démarrage de session
**Constraints**: borne `MAX_TOOLS_PER_TURN = 36` à respecter après union nœud+page ; RLS multi-tenant F02 ; sourçage F01 obligatoire sur chiffres ; audit F03 sur mutations
**Scale/Scope**: périmètre limité à 3 modules (graphe conversationnel, ESG-projet, candidatures) + 1 page frontend ; pas d'élargissement fonctionnel

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Évaluation | Statut |
|----------|-----------|--------|
| I. Francophone-First | Messages chatbot, erreurs UI et confirmations en français ; code en anglais | ✅ PASS |
| II. Architecture Modulaire | Changements confinés à `app/graph/` (sélecteur + contexte), `app/modules/applications/` (service/endpoint/tool export), `app/api/chat.py` (contexte), `frontend/.../financing/offers/[offer_id].vue` (+ composable). Frontières modules respectées | ✅ PASS |
| III. Conversation-Driven UX | Cœur de la feature : rend l'action faisable via chat + restaure la mémoire ESG persistante entre sessions (principe III explicite) | ✅ PASS (renforce) |
| IV. Test-First (NON-NÉGOCIABLE) | TDD imposé : tests unitaires sélecteur, contexte, gating ; intégration endpoint ; E2E bouton + parcours chat. Cible 80 % | ✅ PASS (à respecter en Phase tasks) |
| V. Sécurité & Données | RLS F02 conservée (account scoping) ; pas de secret ; requêtes paramétrées SQLAlchemy ; audit F03 préservé sur création dossier + maj ESG | ✅ PASS |
| VI. Inclusivité & Accessibilité | Messages d'erreur FR clairs et actionnables (FR-015) ; bouton avec feedback visible (plus de clic mort) | ✅ PASS |
| VII. Simplicité & YAGNI | Réutilisation totale des entités existantes ; aucune table/migration ; modifications chirurgicales sur le sélecteur plutôt que nouvelle couche d'intention | ✅ PASS |

**Verdict** : aucun écart constitutionnel. Section Complexity Tracking laissée vide.

## Project Structure

### Documentation (this feature)

```text
specs/048-fix-chatbot-application-flow/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification (clarifiée)
├── research.md          # Phase 0 output — décisions techniques
├── data-model.md        # Phase 1 output — entités touchées + invariants
├── quickstart.md        # Phase 1 output — scénarios de validation manuelle
├── contracts/           # Phase 1 output — contrats tools/endpoints/contexte
│   ├── tool-selector.md
│   ├── chat-context-esg.md
│   ├── application-creation.md
│   └── frontend-apply.md
└── checklists/
    └── requirements.md  # Spec quality checklist (déjà créée)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── graph/
│   │   ├── tool_selector.py            # MODIF — union nœud(intention)+page, troncature priorisée
│   │   ├── tool_selector_config.py     # MODIF éventuelle — n/a si union suffit (pas d'ajout GLOBAL_WHITELIST)
│   │   ├── tools/
│   │   │   └── application_tools.py     # MODIF — export_application câblé au vrai export ; gating ESG amont
│   │   ├── nodes.py                    # MODIF éventuelle — directive prompt « dossier via chat » + injection résumé ESG
│   │   └── state.py / ConversationState # MODIF — nouveau champ résumé ESG-projet
│   ├── api/
│   │   └── chat.py                     # MODIF — _load_full_context_for_state + propagation state
│   └── modules/
│       └── applications/
│           ├── service.py              # MODIF — create_application accepte offer_id/project_id + dédup
│           ├── schemas.py              # MODIF — ApplicationCreate + offer_id/project_id
│           ├── router.py               # MODIF — POST / propage offer_id/project_id
│           └── export.py               # RÉUTILISÉ — vrai rendu DOCX/PDF
└── tests/
    ├── unit/                           # sélecteur, contexte ESG, gating
    ├── integration/                    # endpoint create_application, tool export
    └── ...

frontend/
├── app/
│   ├── pages/financing/offers/[offer_id].vue   # MODIF — handleApply → appel API + navigation
│   ├── composables/useApplications.ts          # AJOUT/MODIF — createApplication(offerId, projectId)
│   └── components/financing/OfferDetail.vue     # vérif — émission @apply
└── tests/                                       # Vitest (handler) + Playwright (E2E bouton)
```

**Structure Decision** : application web existante (Option 2 — backend + frontend). Tous les chemins ci-dessus sont des fichiers **existants modifiés** (sauf composable applications potentiellement nouveau). Aucune nouvelle arborescence ni module créé, conforme au principe VII (YAGNI) et à l'absence de migration.

## Complexity Tracking

> Aucun écart constitutionnel à justifier — section intentionnellement vide.
