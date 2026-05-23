# Feature Flags — ESG Mefali

Liste des feature flags activables via env vars dans la plateforme.

## `USE_OFFER_VIEW` (F07)

**Description** : contrôle l'affichage de la home `/financing` côté PME.

| Valeur | Comportement |
|--------|-------------|
| `false` (default MVP F07) | Vue Cards Fonds legacy (avec modal d'intermédiaires) |
| `true` | Vue Cards Offres (couples Fonds × Intermédiaire) avec scoring décomposé |

**Env var** : `NUXT_PUBLIC_USE_OFFER_VIEW`

**Lecture** : `frontend/nuxt.config.ts` → `runtimeConfig.public.useOfferView`.

**Plan de bascule** :
- **MVP F07** : flag inactif par défaut. Les pages `/financing/offers/*` sont
  accessibles via lien direct uniquement.
- **Post-F14** (matching offre mature) : bascule vers `true` en production.
- **Post-bascule** : la vue Cards Fonds legacy est dépréciée 2 sprints puis
  retirée.

**Rollback** : pour revenir à la vue legacy en cas de problème, il suffit
de définir `NUXT_PUBLIC_USE_OFFER_VIEW=false` dans l'env de production.

## `NUXT_PUBLIC_ENABLE_PROJECT_ESG_ASSESSMENT` (F047)

**Description** : active ou masque le wizard d'évaluation ESG-projet côté frontend
(page `/profile/projects/[id]/esg`, composants `<ProjectEsgWizard>`,
`<EsgReferentialPicker>`, `<EsgCriterionWidget>`, `<EsgScoreDisplay>`,
`<EsgReportPreview>`).

| Valeur | Comportement |
|--------|-------------|
| `true` (default) | UI évaluation ESG-projet exposée |
| `false` | UI masquée (rollback) — les évaluations existantes restent en BDD |

**Env var** : `NUXT_PUBLIC_ENABLE_PROJECT_ESG_ASSESSMENT`

**Lecture** : `frontend/nuxt.config.ts` → `runtimeConfig.public.enableProjectEsgAssessment`.

**Rollback** : passer à `false` masque tout point d'entrée UI ; les tools
LangChain restent disponibles (utilisez `DISABLE_PROJECT_ESG_TOOLS=true` pour
les désactiver également).

## `DISABLE_PROJECT_ESG_TOOLS` (F047, backend)

**Description** : permet de retirer les 5 tools LangChain ESG-projet
(`create_project_esg_assessment`, `save_project_esg_criterion`,
`finalize_project_esg_assessment`, `get_project_esg_assessment`,
`list_project_esg_assessments`) du sélecteur, sans toucher au schéma BDD.

| Valeur | Comportement |
|--------|-------------|
| `false` (default) | Tools actifs, chat LLM peut piloter l'évaluation |
| `true` | Tools cachés, le LLM bascule sur lien UI |

**Env var** : `DISABLE_PROJECT_ESG_TOOLS` (backend uniquement).

**Lecture** : à câbler dans `app/graph/tool_selector_config.py` quand un
incident production l'exige — pour l'instant, valeur documentée, non lue
(les tools restent toujours actifs).

## `MATCHING_USE_PROJECT_ESG_ASSESSMENTS` (F047, backend)

**Description** : contrôle la cascade du sub-score `project_esg` dans le
matching projet-centric F045 (priorité ProjectEsgAssessment calculé vs
saisie manuelle F045 héritée).

| Valeur | Comportement |
|--------|-------------|
| `true` (default) | Cascade `calculated → manual_f045 → unsourced` (comportement 047) |
| `false` | Revient au comportement pré-047 (saisie manuelle F045 uniquement) |

**Env var** : `MATCHING_USE_PROJECT_ESG_ASSESSMENTS` (backend uniquement).

**Lecture** : à câbler dans
`app/modules/financing/matching_service.py::_get_project_esg_subscore` quand
un incident production l'exige — pour l'instant, valeur documentée, non lue.

## Autres flags

(Ajouter ici les flags futurs : `ENABLE_CHROME_EXT`, `ENABLE_F19_CRON_DISPATCHER`, etc.)
