# F15 — Génération de Dossiers par Offre (FR/EN, Union Documents) + Correctifs Bugs

**Module(s) source(s)** : Module 3.3 (Générateur de Dossiers de Candidature)
**Priorité** : P1 — qualité produit + correctifs bugs critiques
**Dépendances** : F01 (sources templates), F06 (Project), F07 (Offer + accepted_languages), F08 (attestation intégrable), F23 (Skills par dossier)
**Estimation** : 2.5 sprints

## Contexte & motivation

Module 3.3 du brainstorming : « Templates pré-remplis **par offre** (un template = un format imposé par un couple Fonds-Intermédiaire) — chaque template référencé par une `Source`. »

**État actuel — bugs et lacunes** :
1. **Bug `company_context` hardcodé** : `backend/app/modules/applications/service.py:262` contient `company_context = "Aucun profil d'entreprise disponible."` codé en dur. Le service ne récupère JAMAIS le profil → **le LLM rédige le dossier sans le contexte PME**. ❌ critique
2. **Templates par catégorie** : seulement 4 valeurs `target_type` (`fund_direct/intermediary_bank/intermediary_agency/intermediary_developer`) — granularité grossière. Tous les fonds GCF via BOAD reçoivent le même template `intermediary_agency` qu'un projet OkenG via UNDP.
3. **Pas de sélecteur de langue** : tous les prompts en FR (`build_section_prompt`), aucun champ `language` sur `FundApplication`. Module 3.3 spécifie `accepted_languages` par offre.
4. **Checklist statique** : `CHECKLISTS` hardcodée par `target_type` (`templates.py:200-233`). Pas d'union réelle docs fonds + intermédiaire.
5. **Doublon tool** : 2 tools `create_fund_application` (un dans `financing_tools.py:191`, un dans `application_tools.py:131`).
6. **Bug AttributeError** : `application_tools._simulate_financing` lit `fund.max_amount` / `fund.min_amount` (lignes 108-109) qui **n'existent pas** sur le modèle (réels : `max_amount_xof`/`min_amount_xof`).
7. **Génération multi-offres parallèle** : possible théoriquement (FundApplication n'a pas d'unicité user/fund), mais sans Project pivot, **impossible de regrouper plusieurs candidatures sous un même projet**.
8. **Attestation ESG** : aucune intégration auto. Le rapport ESG existe mais n'est ni listé dans la checklist ni inclus dans les exports.
9. **Templates codés en Python** dans `templates.py:8-143` : aucune `Source`, aucune référence à un document officiel.

## User stories

- **PME** : « Quand je génère un dossier pour une candidature GCF via BOAD, le LLM doit avoir tout le contexte de mon entreprise et du projet — pas écrire des sections génériques. »
- **PME** : « Pour une offre dont la langue acceptée est EN (ex : GCF Direct Access), je veux que le LLM rédige le dossier en anglais. »
- **PME** : « La checklist documentaire doit être l'union des documents fonds + intermédiaire, dédupliquée. »
- **PME** : « Quand je génère un dossier, je peux y joindre automatiquement mon attestation crédit (F08) en pièce jointe. »
- **Architecte** : « Les templates de dossier sont éditables depuis le back-office admin (F09), liés à des sources officielles et à une Skill (F23). »

## Périmètre fonctionnel

### Fixes immédiats (bugs critiques)

1. **Fix `company_context` hardcodé** : remplacer ligne 262 par appel `get_or_create_profile(account_id)`. Utiliser le helper déjà existant dans `financing/router.py`.
2. **Fix AttributeError `fund.max_amount`** : remplacer par `fund.max_amount_xof` (ou Money typed F04).
3. **Fix doublon `create_fund_application`** : fusionner en un seul tool. Garder celui de `application_tools.py` (plus complet), retirer de `financing_tools.py`. Documenter dans `tool_selector_config.py`.

### Modèle `Template_dossier`

Nouvelle table `templates_dossier` :
- `id: UUID PK`
- `name: str(200) NOT NULL` (ex : "Dossier GCF via BOAD - Mitigation v2.3")
- `offer_id: UUID FK offers.id NOT NULL` (ou nullable si template générique)
- `language: enum('fr', 'en')` (langue par défaut)
- `sections: jsonb NOT NULL` : liste de `{key, title, instructions, target_length, tone, required: bool}`
- `required_documents: jsonb NOT NULL` : liste union docs fonds + interm
- `tone: str` (ton imposé : "formel banque", "narratif IFI", etc.)
- `vocabulary_hints: jsonb` (vocabulaire métier spécifique)
- `anti_patterns: list[str]` (ex : "ne jamais promettre un impact non quantifié")
- `skill_id: UUID FK skills.id NOT NULL` (F23 — chaque template a sa Skill)
- `source_id: UUID FK sources.id NOT NULL` (F01)
- `version`, `valid_from`, `valid_to` (F04)
- `publication_status` (F09)

### Refactor `FundApplication`

- `template_id: UUID FK templates_dossier.id NOT NULL`
- `language: enum('fr', 'en') NOT NULL` (issu de `offer.accepted_languages`)
- `attestation_id: UUID FK attestations.id NULL` (F08)
- `project_id` (déjà ajouté par F06)
- `offer_id` (déjà ajouté par F07)
- Garder `sections: jsonb` (contenu généré par le LLM)
- Champ `snapshot_data` (F04 — capture template + offer + project au moment soumission)

### Service de génération

`backend/app/modules/applications/service.py` (refactor) :

```python
async def generate_section(
    application_id: UUID,
    section_key: str,
    user_inputs: dict | None = None
) -> str:
    application = await get_application_full(application_id)
    template = application.template
    project = application.project  # F06
    offer = application.offer  # F07
    profile = await get_or_create_profile(application.account_id)  # FIX #1
    
    section_def = next(s for s in template.sections if s["key"] == section_key)
    
    # Charger la Skill F23 pour le prompt expert
    skill = await get_skill(template.skill_id)
    
    prompt = build_prompt(
        company_context=profile,  # FIX #1
        project=project,
        offer=offer,
        section=section_def,
        skill_prompt_expert=skill.prompt_expert,  # F23
        language=application.language,
        sources=skill.sources,  # F01 sources pré-injectées
    )
    
    return await llm.generate(prompt)
```

### Checklist union

```python
def build_checklist(offer: Offer) -> list[ChecklistItem]:
    fund_docs = offer.fund.required_documents
    inter_docs = offer.intermediary.required_documents
    union = deduplicate(fund_docs + inter_docs, by_title=True)
    return [
        ChecklistItem(
            title=doc["title"],
            mandatory=doc["mandatory"],
            source_id=doc["source_id"],  # F01
            uploaded=False,  # à mettre à jour selon documents attachés
            origin=detect_origin(doc, fund_docs, inter_docs)  # 'fund' | 'intermediary' | 'both'
        )
        for doc in union
    ]
```

### Génération parallèle multi-offres pour un même projet

Avec `project_id` (F06) + `offer_id` (F07), une `FundApplication` peut être créée pour chaque (project, offer) souhaité.

UI : page `pages/profile/projects/[id]/applications.vue` ou modal sur `[id].vue` :
- Liste des candidatures par projet
- Bouton "Candidater à une autre offre" → sélection multiple d'offres → création en batch

### Intégration attestation (F08)

UI dans `pages/applications/[id].vue` :
- Section "Pièces jointes" avec checkbox "Joindre mon attestation crédit ESG Mefali"
- Si cochée : `attestation_id` lié à l'application
- Au moment de l'export PDF, l'attestation est intégrée dans le bundle (avec QR code visible)

### Multilingue génération FR/EN

Détection automatique : si `offer.accepted_languages` contient `'fr'` ET `'en'`, demander à la PME (via `ask_qcu`).

Prompts paramétrés selon `application.language` :
- Section instructions, tone, vocabulary_hints en FR ou EN selon
- Skill F23 prompt_expert en FR ou EN selon

## Hors-scope (post-MVP)

- Templates pré-générés par IA (avec validation admin)
- Co-rédaction multi-utilisateurs sur la même section
- Versioning des sections (track changes)
- Bibliothèque de réponses-types (réutilisation cross-projets)
- Génération automatique de contenu pour 100% des sections sans intervention user
- Validation grammaticale automatique avant export
- Templates communautaires (consultants tiers)

## Exigences techniques

### Backend

- Fix bugs immédiats (#1, #2, #3 — patches small)
- Migration Alembic `031_templates_and_application_refactor.py` :
  - Table `templates_dossier`
  - Champ `template_id`, `language`, `attestation_id`, `snapshot_data` sur `fund_applications`
  - Backfill : pour chaque application existante, créer/lier un template par défaut basé sur `target_type`
- Modèle `app/models/template_dossier.py`, mise à jour `FundApplication`
- Service `app/modules/applications/service.py` refactor
- Service `app/modules/applications/template_service.py` (nouveau, gère catalogue)
- Tools LangChain (mise à jour) :
  - `create_fund_application` (fusionné, prend `project_id` + `offer_id` + `language`)
  - `generate_application_section`
  - `attach_attestation_to_application(application_id, attestation_id)`
  - `export_application(application_id, format: 'pdf' | 'docx')`
- Refactor `app/modules/applications/export.py` : intégration attestation
- Tests :
  - Test fix #1 : profil entreprise injecté dans le prompt
  - Test fix #2 : `simulate_financing` n'a plus AttributeError
  - Test fix #3 : doublon supprimé, le tool restant fonctionne
  - Test multilingue : `language='en'` → prompt EN → output EN
  - Test checklist : union docs fonds + intermédiaire dédupliquée
  - Test génération parallèle : 1 projet + 3 offres → 3 applications
  - Test attestation : application + attestation → export PDF inclut attestation

### Frontend

- Refactor `pages/applications/[id].vue` :
  - Sélecteur de langue (si offre multilingue)
  - Section "Joindre attestation"
  - Checklist documentaire (union)
  - Tabs par section avec preview génération
- Composant `<TemplateSelector>` pour choisir un template
- Composant `<MultilingualSelector>`
- Composable `useApplications.ts` (mise à jour)
- Dark mode

### Base de données

- Tables : `templates_dossier`
- Colonnes ajoutées sur `fund_applications`
- Index : `templates_dossier(offer_id, language, valid_to)`

## Critères d'acceptation

- [ ] Bug `company_context` hardcodé corrigé
- [ ] Bug AttributeError `fund.max_amount` corrigé
- [ ] Doublon tool `create_fund_application` supprimé
- [ ] Modèle `Template_dossier` créé avec `offer_id`, `language`, `skill_id`, `source_id`
- [ ] `FundApplication` enrichi avec `template_id`, `language`, `attestation_id`, `snapshot_data`
- [ ] Génération parallèle pour un même projet : N applications créées
- [ ] Checklist union docs fonds + intermédiaire fonctionnelle
- [ ] Attestation F08 intégrable au dossier exporté
- [ ] Multilingue FR/EN fonctionnel
- [ ] Test E2E : créer 2 applications pour même projet (GCF/BOAD + GCF/UNDP) → distinctes
- [ ] Test E2E : générer dossier en EN pour offre EN-only
- [ ] Test E2E : exporter PDF avec attestation jointe → QR vérifiable
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : la migration backfill crée des templates orphelins. **Garde-fou** : seed admin de templates pour les top 10 offres prioritaires, link manuel pour le reste, marquer les autres `draft`.
- **Risque** : multilingue dégrade la qualité (LLM moins bon en EN qu'en FR). **Garde-fou** : tester explicitement EN sur 5 cas, ajuster le prompt expert si besoin.
- **Risque** : la checklist union peut être longue (15+ documents). **Garde-fou** : grouper par catégorie, marquer mandatory/optional, progress bar de complétion.
- **Risque** : changement de template après génération partielle écrase le contenu. **Garde-fou** : versioning F04 sur les sections, demande de confirmation explicite, historique des changements (audit log F03).
