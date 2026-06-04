# Prompts Claude Code — Améliorations du conseiller IA (dossiers de candidature)

> Suite à l'analyse du chatbot autour des dossiers de candidature. Chaque prompt
> est **autonome** (à coller dans une nouvelle session) et **groundé** (fichiers +
> fonctions + lignes). Conventions du projet rappelées dans chaque prompt.
>
> **Note :** un 4ᵉ chantier — « découverte des dossiers + fourniture d'un document
> depuis le chat » (tools `list_applications`, `provide_checklist_document`,
> `detach_checklist_document`) — est **déjà en cours d'implémentation** dans une
> autre session, donc non inclus ici. Le prompt « Tools partout » ci-dessous le
> complète (rendre ces tools de découverte/statut accessibles depuis toute page).
>
> Ordre conseillé : **1 → 2 → 3**.

---

## Prompt 1/3 — Tools de statut/action disponibles depuis n'importe quelle route

```text
Projet ESG Mefali (FastAPI/LangGraph + Nuxt 4) : /Users/mac/Documents/projets/2025/esg_mefali_v3.
Lis CLAUDE.md d'abord. Conventions NON négociables : TDD (tests d'abord, échouent, puis
impl ; couverture ≥ 80 %), UI 100 % français AVEC accents, dark mode obligatoire,
réutiliser avant de créer, multi-tenant strict (account_id) + garde anti-IDOR (user_id),
pas de migration Alembic sauf nécessité. Nouvelle branche. Vérifie les n° de ligne avant
de coder.
PRÉREQUIS : le tool `list_applications` (découverte des dossiers) est en cours/déjà créé
dans app/graph/tools/application_tools.py ; réutilise-le (ne le recrée pas s'il existe).

OBJECTIF : depuis N'IMPORTE QUELLE page/route, l'utilisateur peut demander « génère mon
score ESG », « où en est mon dossier de candidature », etc. Aujourd'hui la sélection des
tools est page/nœud-scoped → depuis /chat ces actions ne sont pas exposées au LLM.

Faits / leviers (à confirmer) :
- app/graph/tool_selector_config.py : GLOBAL_WHITELIST, MODULE_TOOL_MAPPING,
  PAGE_TOOL_MAPPING, MAX_TOOLS_PER_TURN. ⚠️ CLAUDE.md dit MAX=14 et 6 tools whitelist,
  mais le code semble dire 36 et ~22 — VÉRIFIE et corrige la doc si écart.
- app/graph/tool_selector.py : select_tools_for_node (union whitelist ∪ nœud ∪ page,
  troncature priorisée whitelist > nœud > page). ⚠️ select_tools_for_node intersecte les
  mappings avec le catalogue RÉEL du nœud — ne pas estimer la troncature sur len() brut.
- app/graph/nodes.py : routing entre nœuds + _detect_*_request qui SE CHEVAUCHENT
  (un détecteur peut détourner une demande explicite — voir mémoire
  routing-detecteurs-overlap). esg_tools.py : tool de score ESG
  (get_esg_assessment / run_esg_assessment — localise le bon).

À FAIRE (TDD) :
- Rendre disponibles PARTOUT les tools de DÉCOUVERTE/STATUT en lecture seule :
  list_applications, get_application_checklist, le tool de score ESG, l'état
  d'avancement. Deux approches possibles (choisis et justifie) : (a) les ajouter à
  GLOBAL_WHITELIST ; (b) améliorer le routing pour qu'une intention « score ESG /
  statut dossier » route vers le bon nœud depuis n'importe quelle page.
- Respecte MAX_TOOLS_PER_TURN : ne fais pas exploser le nombre de tools/tour ; garde la
  troncature priorisée cohérente.
- Tests select_tools_for_node : depuis une page générique (ex. chat_global), ces
  intentions exposent bien les tools attendus. Couvre aussi un cas de chevauchement de
  détecteurs (demande ESG explicite non détournée vers financing/credit).

CRITÈRES : depuis /chat et toute autre page, « génère mon score ESG » et « où en est mon
dossier ? » fonctionnent sans navigation manuelle. CLAUDE.md mis à jour si tu modifies
GLOBAL_WHITELIST / MAX_TOOLS_PER_TURN / mappings.
```

---

## Prompt 2/3 — Proposer la génération des sections une par une

```text
Projet ESG Mefali (FastAPI/LangGraph + Nuxt 4) : /Users/mac/Documents/projets/2025/esg_mefali_v3.
Lis CLAUDE.md d'abord. Conventions NON négociables : TDD, UI français AVEC accents, dark
mode, réutiliser avant de créer, multi-tenant + anti-IDOR, pas de migration sauf besoin.
Nouvelle branche. Vérifie les n° de ligne avant de coder.

OBJECTIF : après avoir créé un dossier de candidature, le conseiller IA doit PROPOSER de
générer les sections UNE PAR UNE (widget oui/non par section). Si l'utilisateur refuse
une section, lui indiquer comment la générer plus tard depuis /applications/[id].

Faits établis (à confirmer) :
- Sections par target_type dans app/modules/applications/templates.py — ex.
  intermediary_agency : project_holder_id « Fiche d'identification du porteur de projet »,
  national_alignment « Alignement priorités nationales et programme-pays »,
  technical_description, budget_cofinancing, impact_indicators. (Chaque dossier a ses
  sections initialisées à status="not_generated".)
- generate_application_section (app/graph/tools/application_tools.py) génère 1 section.
- ask_interactive_question (app/graph/tools/interactive_tools.py, type yes_no/qcu) existe
  mais n'est PAS câblé pour proposer la génération.
- Le flux est piloté par _APPLICATION_FLOW_DIRECTIVE (app/graph/nodes.py ~l.283) + le
  prompt du nœud application (app/.../prompts application.py). create_fund_application ne
  propose rien après création.

À FAIRE (TDD) :
- Après un create_fund_application réussi, le conseiller DOIT, dans l'ordre du template,
  proposer chaque section via ask_interactive_question (yes_no) :
  « Voulez-vous que je génère la section "<titre>" ? ». Oui →
  generate_application_section, puis section suivante. Non → message clair « vous pourrez
  la générer plus tard depuis /applications/[id], onglet Sections, bouton Générer », puis
  proposer la suivante.
- Implémente via la directive/prompt du nœud application + éventuel petit tool helper qui
  renvoie la liste ORDONNÉE des sections non générées d'un dossier (réutilise
  templates.get_template_for_target + l'état sections). N'invente pas de framework lourd :
  réutilise ask_interactive_question et l'état interactif existant (F18/F10).
- Garde anti-IDOR sur le helper.

CRITÈRES : juste après la création, l'utilisateur voit un widget oui/non par section ;
refuser une section affiche le « comment faire depuis /applications/[id] » et passe à la
suivante ; accepter génère réellement le contenu (status=generated). Tests : flux + helper.
```

---

## Prompt 3/3 — Ancrer les dossiers sur le PROJET (pas seulement l'entreprise)

```text
Projet ESG Mefali (FastAPI/LangGraph + Nuxt 4) : /Users/mac/Documents/projets/2025/esg_mefali_v3.
Lis CLAUDE.md d'abord. Conventions NON négociables : TDD, UI français AVEC accents, dark
mode, réutiliser avant de créer, multi-tenant + anti-IDOR, pas de migration sauf besoin.
Nouvelle branche. Vérifie les n° de ligne avant de coder.

OBJECTIF : un dossier de candidature est lié 1:1 à un PROJET mais ce lien est « mort » —
la génération de contenu et l'affichage ignorent le projet. Corriger pour que sections et
UI reflètent le projet ciblé.

Faits établis (à confirmer) :
- FundApplication.project_id est NOT NULL en prod (relation application.project, lazy
  selectin) — app/models/application.py.
- MAIS generate_section (app/modules/applications/service.py ~l.382) n'injecte QUE
  build_company_context(profile) + contexte fonds dans build_section_prompt — JAMAIS
  application.project. La section « project_description » est donc inventée par le LLM.
- ApplicationResponse / ApplicationSummary (app/modules/applications/schemas.py) n'exposent
  pas project. frontend/app/pages/applications/[id].vue affiche fund/intermediary, pas le
  projet ; idem la carte de /applications/index.vue.

À FAIRE (TDD) :
1) Backend : ajouter build_project_context(project) (nom, description, secteur,
   localisation, budget/Money typé, statut, objectifs/impact si dispo) et l'injecter
   dans build_section_prompt (nouveau bloc « CONTEXTE PROJET ») utilisé par
   generate_section. Charge application.project ; gère proprement le cas null legacy
   (pas de crash).
2) Backend : exposer un sous-objet `project` (id, name, sector, description courte,
   status) dans ApplicationResponse ET ApplicationSummary.
3) Frontend : afficher le projet dans l'en-tête de pages/applications/[id].vue (nom +
   lien vers /projects/[id]) et un rappel discret sur la carte de pages/applications/
   index.vue. Dark mode + accents. Étendre l'interface ApplicationDetail/Summary du store.

CRITÈRES : une section générée (ex. « Description du projet ») reflète les VRAIES données
du projet lié (vérifie via un test qui asserte que le contexte projet est injecté dans le
prompt), et non des données génériques d'entreprise ; le dossier indique clairement à
quel projet il se rapporte (UI). Tests : service (contexte projet injecté), schéma
(champ project présent), composant (projet affiché).
```
