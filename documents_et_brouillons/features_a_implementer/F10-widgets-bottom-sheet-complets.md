# F10 — Widgets Interactifs Bottom Sheet Complets

**Module(s) source(s)** : Module 1.1.1 (Tools de Réponse en Bottom Sheet)
**Priorité** : P1 — important pour la qualité conversationnelle et confirmer les actions destructives (Module 1.1.3)
**Dépendances** : F02 (multi-tenant via session), F08 (file upload contextualisé pour attestation)
**Estimation** : 2 sprints

## Contexte & motivation

Module 1.1.1 spécifie 10 widgets interactifs dans un bottom sheet qui remplace la barre de saisie. Architecture stricte : **question dans la bulle LLM, réponse en bottom sheet — JAMAIS dans la bulle**.

**État actuel** :
- Bottom sheet OK (`InteractiveQuestionInputBar.vue`, slide-up gsap, contrat haut/bas respecté ✅)
- Tool générique `ask_interactive_question` (`backend/app/graph/tools/interactive_tools.py`) supporte 4 variantes : `qcu`, `qcm`, `qcu_justification`, `qcm_justification`
- Composants : `SingleChoiceWidget.vue`, `MultipleChoiceWidget.vue`, `JustificationField.vue`, `AnswerElsewhereButton.vue`

**Manquants** : 8 sur 10 widgets attendus :
- `ask_yes_no` ❌ (détourné via QCU à 2 options "Oui/Non" avec heuristique fragile dans `useChat.ts:121-130`)
- `ask_select` ❌ (liste longue avec recherche)
- `ask_number` ❌ (avec unité et bornes)
- `ask_date` / `ask_date_range` ❌
- `ask_rating` ❌ (1-5, 1-10)
- `ask_file_upload` ❌ (contextualisé dans le chat)
- `show_form` ❌ (mini-formulaire multi-champs)
- `show_summary_card` ❌ (carte récapitulative actionnable "corrige/valide")

**Conséquences** :
- `ask_yes_no` détourné = perte de sémantique (LLM doit poser un QCU à 2 options, fragile)
- Pas de `ask_yes_no` → confirmation des actions destructives (Module 1.1.3) impossible techniquement → risque destruction de données par LLM
- Pas de `ask_number` avec bornes → user peut saisir n'importe quoi en texte libre, validation manquante
- Pas de `ask_date` → tout passe par texte libre, parsing fragile
- Pas de `show_form` → impossible de créer un projet en une fois (UX dégradée vs spec)
- Pas de `show_summary_card` → après extraction documents, pas de "voici ce qu'on a compris, validez ou corrigez"

## User stories

- **PME** : « Quand le LLM me demande "êtes-vous certain de vouloir supprimer cette candidature ?", je veux deux gros boutons "Oui, supprimer" / "Non, annuler" en bas de l'écran, pas une question texte ouverte. »
- **PME** : « Quand le LLM me demande "dans quel pays UEMOA est votre siège ?", je veux un select avec recherche (8+ pays), pas un dropdown de 50+ pays africains à scroller. »
- **PME** : « Quand le LLM me demande "quel est votre CA annuel ?", je veux un widget numérique avec sélecteur de devise (XOF/EUR/USD), bornes raisonnables (min 0, max 1000 G FCFA), et formatage automatique avec séparateurs. »
- **PME** : « Quand le LLM crée un projet à partir de notre conversation, je veux voir un mini-formulaire avec 8 champs (nom, description, montant, secteur, ...) à valider en un clic, pas 8 questions séparées. »
- **PME** : « Après l'analyse de mon document "Statuts.pdf", je veux voir une summary card "Voici ce qu'on a extrait : SARL, capital 5M, 12 employés. Validez ou corrigez ?" avec champs éditables inline. »

## Périmètre fonctionnel

### `ask_yes_no` (urgence pour Module 1.1.3)

Tool LangChain `ask_yes_no(question: str, confirm_label: str = "Oui", deny_label: str = "Non", destructive: bool = False)` :
- Si `destructive=True` : bouton "Oui" en rouge, double-confirmation obligatoire (clic + 2 secondes)
- Réponse : `{value: bool, label: str}`

Composant `YesNoWidget.vue` :
- Deux gros boutons côte-à-côte
- Variante destructive : bouton "Oui" rouge + tooltip "Action irréversible"
- Bouton "Répondre librement" toujours présent

**Cas d'usage clé** : avant tout `delete_*`, `revoke_*`, modifications majeures par LLM (Module 1.1.3).

### `ask_select` (liste longue avec recherche)

Tool : `ask_select(question, options: list[{id, label, sublabel?, group?}], min_selections: int = 1, max_selections: int = 1, allow_other: bool = False)`.
- Différencié de `ask_qcu` (max 8 options) : `ask_select` accepte 8+ options avec recherche full-text et groupement.

Composant `SelectWidget.vue` :
- Champ recherche en haut
- Liste virtualisée (vue-virtual-scroller) si > 50 options
- Groupement par `group` si fourni
- Multi-sélection si `max_selections > 1`
- Option "Autre, préciser" si `allow_other=True` → ouvre champ texte

**Cas d'usage** :
- Pays UEMOA (8) + CEDEAO étendu (15) + monde
- Sélection d'un fonds dans 100+ catalogue
- Sélection d'un intermédiaire
- Sélection de secteurs d'activité

### `ask_number` (avec unité et bornes)

Tool : `ask_number(question, unit: str, min: float | null, max: float | null, step: float = 1, currency: Currency | null = None, default: float | null = None)`.
- Si `currency` spécifiée : c'est un Money typed (F04) avec sélecteur de devise.

Composant `NumberWidget.vue` :
- Input numérique avec validation min/max
- Sélecteur de devise si `currency` ou multi-devises (F04)
- Affichage formatté (séparateurs de milliers : `1 000 000`)
- Conversion automatique en équivalent (ex : "1 000 000 XOF (≈ 1 524 €)") via `<MoneyDisplay>` (F04)
- Boutons +/- avec step

**Cas d'usage** : CA annuel, effectifs, montant projet, tCO2e estimés.

### `ask_date` et `ask_date_range`

Tools :
- `ask_date(question, min: date | null, max: date | null, default: date | null)` → réponse : `{value: date, label: str}`
- `ask_date_range(question, min: date | null, max: date | null)` → réponse : `{from: date, to: date}`

Composant `DateWidget.vue` :
- Date picker natif HTML5 + alternative custom pour cohérence cross-browser
- Format affiché en français (ex : "15 mars 2026")

**Cas d'usage** : dates de soumission, périodes d'évaluation, validité d'attestation.

### `ask_rating` (échelle 1-5 / 1-10)

Tool : `ask_rating(question, scale: int = 5, labels: list[str] | null = None)`.
- Si `labels` fourni : label sous chaque valeur (ex : ["Très mauvais", "Mauvais", ..., "Excellent"]).

Composant `RatingWidget.vue` :
- Étoiles (1-5) ou points (1-10)
- Hover preview
- Optionnel : labels textuels sous

**Cas d'usage** : auto-évaluation pratiques ESG (1 = pas du tout / 5 = entièrement appliqué).

### `ask_file_upload` (contextualisé dans le chat)

Tool : `ask_file_upload(question, accept: list[str] = [".pdf", ".docx", ".xlsx", ".png", ".jpg"], max_size_mb: int = 10, multi: bool = False, doc_type_hint: str | null)`.

Composant `FileUploadWidget.vue` :
- Bouton drag & drop
- Liste fichiers en preview
- Progress bar upload
- Lien automatique au document dans le chat (le LLM reçoit le `document_id` après upload)

**Cas d'usage** : "Pouvez-vous me transmettre votre business plan ?" → bouton upload contextualisé. Aujourd'hui l'utilisateur doit cliquer le trombone séparé du chat (`ChatInput.vue:109-121`).

### `show_form` (mini-formulaire multi-champs)

Tool : `show_form(title, fields: list[FormField], submit_label: str = "Enregistrer")`.

`FormField` :
```json
{
  "name": "project_name",
  "label": "Nom du projet",
  "type": "text" | "number" | "select" | "date" | "textarea" | "money",
  "required": true,
  "placeholder": "...",
  "default": "...",
  "validation": {...}
}
```

Composant `FormWidget.vue` :
- Rend chaque field selon son type (réutilise les composants `NumberWidget`, `DateWidget`, etc. inline)
- Validation côté client (zod ou yup)
- Bouton submit
- Bouton "Annuler" qui ferme le bottom sheet

**Cas d'usage clé** :
- Création d'un projet en un seul widget (8 champs : nom, description, sector, target_amount, duration, location, etc.)
- Édition d'un profil entreprise complet
- Saisie d'un nouveau bilan carbone

### `show_summary_card` (carte récapitulative actionnable)

Tool : `show_summary_card(title, items: list[{label, value, editable: bool}], confirm_label: str = "Valider", correct_label: str = "Corriger")`.

Composant `SummaryCardWidget.vue` :
- Liste de champs `label: value`
- Si `editable=true` sur un item : icône crayon → ouvre input inline
- Bouton "Valider" → confirme tout
- Bouton "Corriger" → met tous les `editable=true` en mode édition

**Cas d'usage clé** :
- Après analyse document : "Voici ce qu'on a extrait de votre statuts.pdf : SARL, capital 5M, 12 employés. Valider ou corriger ?"
- Après calcul carbone : "Voici votre bilan : 45 tCO2e dont 30 électricité, 10 transport, 5 déchets. Valider ?"
- Après matching : "Voici les 3 offres compatibles avec votre projet. Choisir une à explorer ?"

### Contrat de validation/réponse

Toutes les réponses reviennent comme **message utilisateur normal** dans le fil :
- `ask_yes_no` → "✓ Oui" / "✗ Non"
- `ask_select` → "✓ Côte d'Ivoire" ou "✓ Côte d'Ivoire, Sénégal" si multi
- `ask_number` → "✓ 1 200 000 FCFA"
- `ask_date` → "✓ 15 mars 2026"
- `ask_rating` → "✓ 4/5 (Très bien)"
- `ask_file_upload` → "✓ statuts.pdf (uploaded)"
- `show_form` → "✓ Projet créé : Panneaux solaires, 5M FCFA, énergie"
- `show_summary_card` → "✓ Validé" ou "✓ Corrigé : capital 6M (au lieu de 5M)"

Le payload structuré est conservé en métadonnée du message (déjà fait pour QCU/QCM, étendre).

### Pattern destructif (Module 1.1.3)

Avant TOUT tool de mutation destructif (`delete_project`, `delete_application`, `revoke_attestation`, etc.), le tool doit invoquer **automatiquement** `ask_yes_no(destructive=True)` côté backend :

Pattern dans le tool :
```python
@tool(args_schema=DeleteProjectArgs)
async def delete_project(project_id: UUID, confirm: bool = False):
    if not confirm:
        # Ne pas exécuter, demander confirmation
        return {"requires_confirmation": True, "message": "Confirmation requise via ask_yes_no"}
    # Sinon exécuter
    ...
```

Le LLM, voyant `requires_confirmation`, invoque `ask_yes_no` puis re-appelle `delete_project(confirm=True)` avec la valeur user.

Le backend pourrait aussi imposer ça via un middleware qui scanne les tools de mutation destructifs (post-MVP).

## Hors-scope (post-MVP)

- Widget `ask_color`, `ask_priority`, etc.
- Auto-complétion intelligente (suggestion ML basée sur les saisies passées)
- Validation conditionnelle (si X = Y, alors Z requis)
- Multi-step forms (wizard)
- Upload d'images avec rotation/recadrage inline
- Audio recording widget

## Exigences techniques

### Backend

- Étendre `backend/app/models/interactive_question.py` :
  - Enum `InteractiveQuestionType` : ajouter `yes_no`, `select`, `number`, `date`, `date_range`, `rating`, `file_upload`, `form`, `summary_card`
  - Champs additionnels selon variante (peuvent être stockés dans `payload: jsonb`)
- Étendre `backend/app/graph/tools/interactive_tools.py` :
  - 9 nouveaux tools (un par widget, garder l'existant `ask_interactive_question` pour rétro-compat ou remplacer)
  - Schémas Pydantic stricts pour chaque (cf. F22 / Module 10.2)
- Migration Alembic `027_extend_interactive_questions.py`
- Mise à jour `tool_selector_config.py` : exposer ces tools sur tous les nœuds (la plupart sont génériques)
- Mise à jour des prompts pour mentionner les nouveaux tools dans le decision tree (F22)
- Tests :
  - Test ask_yes_no : valeur boolean, payload destructive bien transmis
  - Test ask_number : bornes respectées, currency parsée
  - Test show_form : champs validés, submit groupé
  - Test show_summary_card : édition inline, payload des modifications
  - Test pattern destructif : tool de delete refuse sans confirm=True

### Frontend

- Étendre `frontend/app/components/chat/InteractiveQuestionInputBar.vue` pour router selon `question_type`
- Nouveaux composants :
  - `frontend/app/components/chat/widgets/YesNoWidget.vue`
  - `frontend/app/components/chat/widgets/SelectWidget.vue`
  - `frontend/app/components/chat/widgets/NumberWidget.vue`
  - `frontend/app/components/chat/widgets/DateWidget.vue`
  - `frontend/app/components/chat/widgets/DateRangeWidget.vue`
  - `frontend/app/components/chat/widgets/RatingWidget.vue`
  - `frontend/app/components/chat/widgets/FileUploadWidget.vue`
  - `frontend/app/components/chat/widgets/FormWidget.vue`
  - `frontend/app/components/chat/widgets/SummaryCardWidget.vue`
- Composables :
  - `useInteractiveQuestion.ts` (extension)
- Mise à jour `useChat.ts` : étendre `submitInteractiveAnswer` pour gérer les nouveaux types de payload
- Tests :
  - Vitest unit : chaque widget rend correctement, valide les inputs
  - Playwright E2E : full flow conversationnel avec chaque type de widget

### Base de données

- Modifications schéma `interactive_questions` : enum élargi, payload structuré
- Pas de nouvelles tables

## Critères d'acceptation

- [ ] 9 nouveaux tools LangChain implémentés et exposés
- [ ] 9 nouveaux composants Vue créés avec dark mode et accessibilité
- [ ] Bottom sheet route correctement selon `question_type`
- [ ] Bottom sheet conserve sa propriété "remplace l'input texte, jamais dans la bulle"
- [ ] Bouton "Répondre librement" toujours présent et fonctionnel sur tous les widgets
- [ ] Réponse user dans le fil = représentation textuelle lisible (`✓ ...`)
- [ ] Pattern destructif appliqué : tool `delete_project` exige `confirm=True`, sinon LLM demande via `ask_yes_no(destructive=True)`
- [ ] Test E2E : LLM demande de supprimer un projet → `ask_yes_no` rouge → user clique "Oui" → projet supprimé + audit_log
- [ ] Test E2E : LLM demande pays → `ask_select` avec recherche → user tape "Cote" → "Côte d'Ivoire" surligné → click → message "✓ Côte d'Ivoire"
- [ ] Test E2E : LLM demande CA → `ask_number` avec XOF → user saisit 1000000 → affichage "1 000 000 FCFA"
- [ ] Test E2E : LLM crée projet → `show_form` 8 champs → user remplit → message "✓ Projet créé" + projet en BDD
- [ ] Test E2E : analyse document → `show_summary_card` → user clique "Corriger" sur capital → édite → "Valider"
- [ ] Couverture tests ≥ 80 % sur les widgets

## Risques & garde-fous

- **Risque** : trop de widgets → bottom sheet trop chargé. **Garde-fou** : limiter la complexité par widget (ex : `show_form` max 10 champs), encourager le LLM à découper si nécessaire.
- **Risque** : la confirmation `ask_yes_no(destructive=True)` est contournée si le LLM ne l'invoque pas. **Garde-fou** : pattern backend `confirm: bool = False` dans les tools destructifs (le tool retourne erreur si confirm=False), middleware optionnel post-MVP.
- **Risque** : `show_form` accepte des types qui ne marchent pas tous bien dans un bottom sheet (ex : ar dynamique). **Garde-fou** : whitelist des types supportés, error si type inconnu.
- **Risque** : performance du bottom sheet avec 50+ options dans `ask_select`. **Garde-fou** : virtualisation, recherche full-text, hard limit 200 options (au-delà : refuser et demander au LLM de filtrer en amont).
- **Risque** : un user mobile a un petit écran → bottom sheet prend tout. **Garde-fou** : design responsive, scroll interne au sheet, animations gsap qui ne masquent pas les boutons d'action.
- **Risque** : régressions sur les widgets QCU/QCM existants. **Garde-fou** : tests Playwright régression sur Story 18 + suite couvrant les anciens widgets.
