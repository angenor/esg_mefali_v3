# F23 — Skills (Playbooks Métier) : Modèle BDD + Loader + 3 Skills Critiques

**Module(s) source(s)** : Module 11 (Skills - Playbooks Métier)
**Priorité** : P1 — qualité génération dossier (Innovation 4)
**Dépendances** : F01 (sources liées), F02 (admin), F03 (audit log), F09 (back-office Skills CRUD), F22 (golden set pour eval gating)
**Estimation** : 2.5 sprints

## Contexte & motivation

Module 11 du brainstorming : « **Skill** = bundle métier réutilisable qui combine un prompt expert focalisé, un sous-ensemble de tools autorisés, une procédure pas-à-pas, des sources pré-résolues et des exemples gold. Chargées dynamiquement par le sélecteur LangGraph (Module 10.1) selon le contexte. »

**État actuel** :
- Aucun modèle SQLAlchemy `Skill` (`grep "class Skill" backend/app/models/` → 0)
- Aucune migration Alembic
- Aucun schéma Pydantic
- Aucun service
- Aucune API
- Aucun seed
- Ce qui en tient lieu : **prompts spécialisés monolithiques** par domaine (`backend/app/prompts/esg_scoring.py`, `carbon.py`, `financing.py`, `application.py`, `credit.py`, `action_plan.py`) — 7 fichiers statiques, non éditables depuis admin, non versionnés en BDD, non liés à des sources, pas de golden examples par module

**Conséquences** :
- Innovation 4 « Génération automatique de Dossiers pilotée par Skills » non livrée
- Génération de dossier (F15) ne peut pas avoir des skills par couple Fonds × Intermédiaire
- Évolution = redéploiement (pas de hot reload contenu)
- Pas de gating eval avant publication d'une nouvelle skill

## User stories

- **Admin** : « Je veux créer/éditer des Skills depuis le back-office (F09) avec : prompt expert, procédure étapes, tool whitelist, sources liées, golden examples. »
- **Admin** : « Quand je publie une Skill, le système exécute le golden set associé et bloque la publication si régression > 10 %. »
- **PME (indirectement)** : « Quand je génère un dossier GCF via BOAD, le LLM utilise une skill `skill_dossier_gcf_via_boad` qui sait : sections obligatoires GCF, ton imposé BOAD, langue acceptée, vocabulaire métier. »
- **Architecte** : « Au runtime, le Skill loader charge 1-2 skills max selon contexte (page, intent, offre ciblée), fusionne avec le system prompt, fournit les tools intersection. »

## Périmètre fonctionnel

### Modèle `Skill`

Table `skills` :
- `id: UUID PK`
- `name: str(100) UNIQUE NOT NULL` (ex : `skill_dossier_gcf_via_boad`)
- `domain: enum('diagnostic_esg', 'scoring_referentiel', 'carbon_calc', 'dossier', 'intermediaire', 'attestation', 'credit_score')`
- `version: str` (semver)
- `prompt_expert: text NOT NULL` (limit ≤ 5000 tokens, contrôlé)
- `procedure: text NOT NULL` (étapes ordonnées, critères entrée/sortie)
- `tool_whitelist: jsonb NOT NULL` (liste des `tool_name` autorisés ; multi-select sur enum code)
- `sources: jsonb NOT NULL` (liste de `source_id` FK Source — pré-résolues)
- `activation_rules: jsonb NOT NULL` :
  ```json
  {
    "page_slugs": ["financing", "applications"],
    "intent_keywords": ["dossier", "candidature", "GCF"],
    "active_module": ["application"],
    "offer_id": null,  // ou UUID si lié à une offre spécifique
    "fund_id": "uuid-gcf",  // ou null
    "intermediary_id": "uuid-boad"  // ou null
  }
  ```
- `golden_examples: jsonb NOT NULL` (5-15 cas d'eval, format compatible F22 golden_set.json)
- `status: enum('draft', 'published') NOT NULL DEFAULT 'draft'` (workflow F09)
- `created_by: UUID FK users.id NOT NULL`
- `verified_by: UUID FK users.id | null`
- `valid_from: date NOT NULL`
- `valid_to: date | null`
- (versioning F04)

Migration Alembic `035_create_skills.py`.

### Skill loader

`backend/app/graph/skill_loader.py` :

```python
async def load_skills_for_context(
    page_slug: str,
    active_module: str | None,
    intent: str | None,
    offer_id: UUID | None,
    fund_id: UUID | None,
    intermediary_id: UUID | None,
) -> list[Skill]:
    """
    Charge 1 à 2 skills max selon le contexte.
    Si plusieurs candidates : choisit la plus spécifique
    (skill avec offer_id > skill avec fund_id+intermediary_id > skill avec page_slug).
    """
    candidates = await query_skills_matching(
        page_slug, active_module, intent, offer_id, fund_id, intermediary_id
    )
    # Tri par spécificité décroissante
    candidates.sort(key=specificity_score, reverse=True)
    return candidates[:2]  # max 2 skills
```

### Fusion prompt

```python
async def fuse_prompt(
    base_system_prompt: str,
    skills: list[Skill],
    user_context: dict
) -> str:
    fused = base_system_prompt
    for skill in skills:
        # Injection du prompt expert
        fused += f"\n\n## SKILL ACTIVE: {skill.name}\n{skill.prompt_expert}\n"
        # Injection des sources pré-résolues
        sources = await load_sources(skill.sources)
        fused += format_sources_for_prompt(sources)
        # Injection de la procédure
        fused += f"\n## PROCÉDURE\n{skill.procedure}\n"
    return fused
```

### Intersection tool whitelist

```python
async def select_tools_with_skills(
    page_slug: str,
    skills: list[Skill],
    base_tools: list[str],
) -> list[str]:
    if not skills:
        return base_tools
    # Intersection
    skill_whitelist = set()
    for skill in skills:
        skill_whitelist |= set(skill.tool_whitelist)
    return [t for t in base_tools if t in skill_whitelist]
```

### Intégration dans LangGraph (Module 11.5)

Refactor `backend/app/graph/nodes.py` (chaque nœud) :
```python
async def chat_node(state: ConversationState):
    # 1. Skill loader
    skills = await load_skills_for_context(
        page_slug=state.current_page_slug,
        active_module=state.active_module,
        intent=detect_intent(state.last_user_message),
        offer_id=state.context.get("offer_id"),
        fund_id=state.context.get("fund_id"),
        intermediary_id=state.context.get("intermediary_id"),
    )
    
    # 2. Fusion prompt
    fused_prompt = await fuse_prompt(BASE_PROMPT, skills, state.user_context)
    
    # 3. Sélection tools (intersection page + skill whitelist)
    base_tools = select_tools_for_node("chat_node", state.current_page_slug)
    tools = await select_tools_with_skills(state.current_page_slug, skills, base_tools)
    
    # 4. Bind LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # 5. Invoke
    ...
```

### Catalogue MVP : 11 skills

Lister les noms (Module 11.2) — créer 3 critiques d'abord, puis 8 progressivement par admin (F09) :
- ✅ MVP : `skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad`
- 📅 Itératif via admin : `skill_score_boad`, `skill_score_ifc`, `skill_carbon_calc`, `skill_dossier_sunref_ecobank`, `skill_dossier_fem_via_pnud`, `skill_intermediaire_boad`, `skill_attestation`, `skill_credit_score`

Seed initial des 3 skills critiques en migration ou via fixtures.

### CRUD Admin Skills (F09 admin)

Pages admin `pages/admin/skills/*` :
- `index.vue` : liste, filtres
- `new.vue` : formulaire création
- `[id].vue` : édition
- Onglets : Identité, Prompt expert, Procédure, Tools, Sources, Activation rules, Golden examples, Tests

### Eval gating à la publication (Module 11.4)

Avant transition `draft → published` :
- Backend exécute `skill.golden_examples` via le test runner (F22)
- Si taux de réussite < 90 % → publication bloquée, rapport d'erreur affiché
- Workflow : admin doit corriger le prompt ou les exemples avant de re-tenter

### Anti-injection (Module 11.4)

Validation au save de `prompt_expert` :
- Détection patterns suspects : "ignore previous instructions", "tu es désormais", "system prompt", "user is admin", etc.
- Si détecté : refus de save, alerte admin
- Liste de patterns dans `app/core/prompt_injection_detector.py`

### Tools réservés admin

Garde-fou : le LLM ne peut JAMAIS modifier les Skills (Module 11.4 #7). Aucun tool `create_skill`, `update_skill`, `delete_skill` n'est exposé au LLM.

### Versioning (lien F04)

- Éditer une skill publiée crée une nouvelle version
- Conversations en cours conservent la version active au tour où elles ont été démarrées (snapshot dans le state LangGraph)

## Hors-scope (post-MVP)

- Marketplace skills externes (consultants tiers)
- Sous-skills composables (héritage)
- A/B testing de versions
- Génération assistée de skill par le LLM (drafting)
- Skill multi-modèle (différents LLM par skill)
- Skill DSL custom

## Exigences techniques

### Backend

- Migration Alembic `035_create_skills.py`
- Modèle `app/models/skill.py`
- Module `app/modules/skills/` :
  - `service.py` : CRUD, query_skills_matching
  - `schemas.py`
  - `validator.py` : validation tools whitelist + sources verified + prompt anti-injection
  - `eval_runner.py` : exécution golden_examples avant publication
- Module `app/modules/admin/skills_router.py` (F09)
- Backend `app/graph/skill_loader.py`, `app/graph/prompt_fusion.py`
- Refactor des 7 nœuds LangGraph pour intégrer le skill loader
- Seed initial : 3 skills critiques (`skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad`)
- Tests :
  - Test load skills : sélection par contexte respecte spécificité
  - Test fusion prompt : skill prompt + sources + procédure injectés
  - Test intersection tools : tool whitelist filtre bien
  - Test eval gating : skill avec exemples failing → publication bloquée
  - Test versioning : éditer skill publiée crée nouvelle version, conversations en cours conservent l'ancienne
  - Test anti-injection : patterns suspects rejetés au save

### Frontend

- Pages admin `pages/admin/skills/*` (F09)
- Composants `components/admin/skills/` :
  - `SkillList.vue`, `SkillForm.vue`, `SkillEvalRunner.vue`
  - `ToolWhitelistPicker.vue`, `SourceMultiPicker.vue` (réutilise F09)
  - `GoldenExamplesEditor.vue`
- Composable `useAdminSkills.ts`
- Dark mode

### Base de données

- Table `skills`
- Indexes : `(domain, status, valid_to)`, `(name)`, GIN sur `activation_rules`

## Critères d'acceptation

- [ ] Modèle `Skill` créé avec tous les champs
- [ ] CRUD admin fonctionnel (F09)
- [ ] Skill loader charge 1-2 skills max selon contexte
- [ ] Fusion prompt active dans les 7 nœuds LangGraph
- [ ] Intersection tools avec page + skill whitelist
- [ ] 3 skills critiques seedées : `skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad`
- [ ] Eval gating bloque publication si golden examples failing
- [ ] Anti-injection détecte patterns suspects
- [ ] Versioning F04 actif
- [ ] Aucun tool LLM ne mute les Skills (catalogue protégé)
- [ ] Test E2E : publish skill avec exemples failing → blocked
- [ ] Test E2E : générer dossier GCF/BOAD → skill `skill_dossier_gcf_via_boad` chargée → vocabulaire métier dans le résultat
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : skill mal écrite cause hallucinations LLM. **Garde-fou** : eval gating obligatoire, taux de réussite > 90 %, audit log F03 sur édition.
- **Risque** : conflit entre 2 skills activées (instructions contradictoires). **Garde-fou** : max 2 skills + tri par spécificité, documentation guideline.
- **Risque** : prompt injection via prompt_expert. **Garde-fou** : détecteur de patterns + revue admin obligatoire avant verified.
- **Risque** : explosion du token budget si plusieurs skills longues. **Garde-fou** : limit `prompt_expert` ≤ 5000 tokens (test au save), monitoring.
- **Risque** : conversations en cours cassent quand skill éditée. **Garde-fou** : snapshot version dans state LangGraph, conserve l'ancienne pour conversations actives.
