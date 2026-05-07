# Research — F10 Widgets Interactifs Bottom Sheet Complets

**Date** : 2026-05-07
**Phase** : 0 (Outline & Research)

Synthèse des décisions techniques résolvant les NEEDS CLARIFICATION du Technical Context et les choix d'architecture du plan.

---

## R1 — Persistance par variante de widget : payload jsonb discriminé Pydantic

**Decision** : Stocker tous les paramètres et réponses spécifiques par variante dans deux colonnes `payload jsonb NOT NULL DEFAULT '{}'` et `response_payload jsonb NULL` sur `interactive_questions`. Le typage est garanti en couche applicative via une union Pydantic discriminée par `question_type`.

**Rationale** :
- Simplicité (principe constitution VII) : aucune nouvelle table, aucune migration future à chaque ajout de widget.
- Rétro-compatibilité F18 : les colonnes existantes (`options`, `min_selections`, `max_selections`, `requires_justification`, `justification_prompt`) restent utilisables par les 4 widgets QCU/QCM ; les 9 nouveaux widgets délaissent ces colonnes au profit de `payload`.
- Pydantic v2 supporte les unions discriminées avec `Field(discriminator="question_type")`, garantissant un typage strict en lecture/écriture.
- jsonb postgresql autorise indexes GIN si besoin de recherches futures dans les payloads (post-MVP).
- Le décodage côté serveur passe par `InteractiveQuestionPayload.model_validate({"question_type": q.question_type, **q.payload})`.

**Alternatives considérées** :
1. **Colonnes typées dédiées par widget** (ex : `number_min`, `number_max`, `select_allow_other`, etc.) — rejeté : explosion combinatoire (>30 colonnes nullables), couplage fort avec chaque variante, migrations futures coûteuses.
2. **Tables satellites par type** (ex : `interactive_questions_select`, `interactive_questions_form`, ...) — rejeté : 9 nouvelles tables = sur-ingénierie pour un cas à faible volume, complexité de jointure.
3. **Polymorphic SQLAlchemy single-table inheritance** — rejeté : SQLAlchemy STI génère des colonnes nullables ; même problème que l'option 1, plus complexité ORM.

**Implementation notes** :
- Schémas dans `backend/app/schemas/interactive_question.py` :
  ```
  class YesNoPayload(BaseModel):
      question_type: Literal["yes_no"]
      confirm_label: str = "Oui"
      deny_label: str = "Non"
      destructive: bool = False

  class SelectPayload(BaseModel):
      question_type: Literal["select"]
      options: list[SelectOption]  # max 200
      ...

  InteractiveQuestionPayload = Annotated[
      YesNoPayload | SelectPayload | NumberPayload | ... | dict,
      Field(discriminator="question_type"),
  ]
  ```
- Le dernier `dict` est un fallback pour assurer la résilience aux types inconnus (utile en cas de rollback partiel).

---

## R2 — Click-and-hold 2 secondes pour confirmation destructive : implémentation native CSS

**Decision** : Implémenter le hold de 2 secondes en Vue 3 + CSS keyframes + listeners pointer events natifs (`pointerdown`, `pointerup`, `pointercancel`, `keydown`, `keyup`), sans dépendance externe.

**Rationale** :
- Zéro dépendance ajoutée → pas de surface d'attaque supplémentaire ni d'augmentation du bundle Nuxt.
- Contrôle total des animations (anneau de progression circulaire SVG ou barre Tailwind) et de l'adaptation `dark:` + `prefers-reduced-motion: reduce`.
- Accessibilité clavier équivalente : `keydown.Enter` démarre un timer 2 s, `keyup` ou `Escape` annule. Pour les screen readers, fallback en modal de re-confirmation simple si le hold échoue (FR-030).
- Pattern bien documenté dans la communauté Vue 3 (SFC + composable `useHoldToConfirm`).

**Alternatives considérées** :
1. **vue-pressable** — rejeté : maintenu sporadiquement, abstraction inutile pour 30 lignes de code.
2. **lottie + animation 2 s** — rejeté : surdimensionné, lottie-web ajoute ~200 Ko.
3. **Double-clic dans 1 seconde** — rejeté : pattern moins explicite et moins sûr (un clic accidentel peut être suivi d'un second clic accidentel).

**Implementation notes** :
- Composable `useHoldToConfirm.ts` (extrait dans `frontend/app/composables/`) exposant `{ isHolding, progress, onPointerDown, onPointerUp, onPointerCancel, onKeyDown, onKeyUp }`.
- Animation CSS : `@keyframes ring-fill { from { stroke-dashoffset: <full> } to { stroke-dashoffset: 0 } }` sur 2 s.
- Respect `@media (prefers-reduced-motion: reduce)` : remplacer l'animation par un compteur textuel « Maintenez... 2... 1... 0 ».

---

## R3 — Virtualisation listes longues `ask_select` : vue-virtual-scroller

**Decision** : Utiliser `vue-virtual-scroller` (`@vue-virtual-scroller/vue3` ou la dernière version compatible Nuxt 4) pour virtualiser les listes > 50 options dans `SelectWidget.vue`.

**Rationale** :
- Standard de fait pour Vue 3, ~30k téléchargements/semaine, maintenu activement.
- API simple : `<DynamicScroller :items="filteredOptions" :min-item-size="48">`.
- Performance prouvée : 1000+ items à 60 fps sur Chromium.
- Compatible Nuxt 4 SSR/CSR (rendu côté client via `<ClientOnly>` si besoin).

**Alternatives considérées** :
1. **vue-virtual-list** — rejeté : moins maintenu (dernier commit > 1 an).
2. **Pagination locale (page 25)** — rejeté : oblige des clics « page suivante » qui rompent le flux utilisateur dans un widget.
3. **Pas de virtualisation, scroll natif jusqu'à 200 options** — accepté en fallback si la dépendance ne peut pas être ajoutée. Performance dégradée mais acceptable (~300 ms à 200 options sur Chrome desktop).

**Implementation notes** :
- Vérifier `frontend/package.json` pour présence existante.
- Si absent, ajouter via `npm install vue-virtual-scroller@latest` en Phase B.
- Activer la virtualisation conditionnellement : `v-if="options.length > 50"`.

---

## R4 — Validation client formulaires `show_form` : zod

**Decision** : Utiliser `zod` (TypeScript-first schema validation) pour la validation côté client des `FormWidget.vue` (au moins 1 schéma par champ + composition pour le formulaire global).

**Rationale** :
- Compatible TypeScript 5.x strict, infère les types depuis les schémas (`z.infer<typeof schema>`).
- Adoption massive (>30M téléchargements/semaine npm), documentation excellente.
- Patterns de validation conditionnelle bien documentés (utile post-MVP pour l'extension F10+ avec validation conditionnelle).
- Permet une validation synchrone ET asynchrone (utile pour `unique_constraint` côté serveur si besoin futur).

**Alternatives considérées** :
1. **valibot** — rejeté : plus léger (~10 % du bundle zod) mais maturité moindre, moins de patterns documentés pour Vue 3.
2. **vee-validate** — rejeté : couplage fort avec composables Vue, plus complexe pour un usage simple.
3. **Validation manuelle dans `useInteractiveQuestion.ts`** — rejeté : duplication par champ, inefficace.

**Implementation notes** :
- Vérifier `frontend/package.json` pour présence existante.
- Si absent, ajouter via `npm install zod@latest`.
- Schémas par champ générés depuis le `FormField.validation` reçu du backend (mapping côté composable).

---

## R5 — Validation MIME signature backend : python-magic

**Decision** : Utiliser `python-magic` (binding Python pour libmagic) pour valider la cohérence MIME/extension des fichiers uploadés via `ask_file_upload` dans le router `documents.py`.

**Rationale** :
- libmagic est la référence de signatures de fichiers Unix (50+ années de maintenance).
- python-magic est le binding standard, ~5M téléchargements/mois.
- Permet une détection robuste des fichiers falsifiés (extension `.pdf` portant un binaire Windows).
- Léger (le binding est trivial, lib system-wide).

**Alternatives considérées** :
1. **filetype** (pure Python) — rejeté : signatures plus limitées, ne couvre pas tous les types Office/CAD.
2. **magic-bytes** — rejeté : maintien sporadique.
3. **Pas de validation MIME signature** — rejeté : faille de sécurité claire (FR-025).

**Implementation notes** :
- Ajouter `python-magic>=0.4.27` à `backend/requirements.txt`.
- Documenter la dépendance système : macOS `brew install libmagic`, Linux `apt install libmagic1`, Docker → s'assurer que l'image base inclut libmagic.
- API : `magic.from_buffer(file_bytes, mime=True)` retourne le MIME type. Comparer avec un mapping `{".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ...}`.
- En cas de discordance : retourner HTTP 415 avec message « Type de fichier incohérent ».

---

## R6 — Pattern destructif backend : retour string `{"requires_confirmation": True}`

**Decision** : Implémenter le pattern destructif via un retour JSON sérialisé en string par le tool, intercepté par le LLM via une instruction de prompt explicite. Pas de middleware LangGraph, pas de hook spécial.

**Rationale** :
- Pattern le plus simple compatible LangChain `@tool` : un tool retourne toujours une string ; le LLM peut interpréter une chaîne JSON.
- Pas de couplage avec un mécanisme spécifique LangGraph qui pourrait être bouleversé par un upgrade.
- Le LLM, vu le format `{"requires_confirmation": True, "message": "Confirmation requise via ask_yes_no", "destructive_action": "delete_project"}`, est instruit (via WIDGET_INSTRUCTION) à enchaîner avec `ask_yes_no(destructive=True)`.
- Vérifiable par tests : le tool refuse l'exécution sans `confirm=True`, donc même si le LLM oublie, aucune mutation.

**Alternatives considérées** :
1. **Middleware LangGraph qui scanne tous les tools `delete_*`** — rejeté : sur-ingénierie pour MVP, fragile face aux upgrades LangGraph.
2. **Décorateur `@destructive` sur les tools** — accepté en complément (helper `requires_destructive_confirmation`), mais le retour string reste le mécanisme principal.
3. **Tool wrapper `confirm_first(tool, ...)`** — rejeté : impose une réécriture de chaque tool, complique les tests.

**Implementation notes** :
- Helper `backend/app/graph/tools/common.py:requires_destructive_confirmation(action_name: str) -> str` :
  ```
  def requires_destructive_confirmation(action_name: str) -> str:
      return json.dumps({
          "requires_confirmation": True,
          "message": f"Action destructive '{action_name}' nécessite une confirmation utilisateur. Invoque ask_yes_no(destructive=True).",
          "destructive_action": action_name,
      })
  ```
- WIDGET_INSTRUCTION étendu : « Si un tool retourne `requires_confirmation: True`, invoque IMMÉDIATEMENT `ask_yes_no(destructive=True, question='...')`. Quand l'utilisateur confirme, rappelle le tool original avec `confirm=True`. »
- L'audit_log F03 trace l'enchaînement : appel destructif initial (`confirm=False`), appel `ask_yes_no`, appel destructif final (`confirm=True`).

---

## R7 — Taux de change XOF↔EUR/USD/CDF : table référentiel + fallback constants

**Decision** : Privilégier une table `referential_fx_rates` (à introduire dans une feature ultérieure F30 ou autre) comme source de vérité. À défaut (MVP F10), utiliser des constantes statiques dans `backend/app/core/fx_rates.py` exposées via un endpoint `GET /api/referential/fx-rates` qui retourne 200 avec les constants ou 404 si la table n'existe pas.

**Constantes initiales** :
- `XOF_PER_EUR = 655.957` (parité fixe officielle BCEAO/Banque de France)
- `XOF_PER_USD ≈ 600` (volatile, à raffraîchir hebdomadairement)
- `XOF_PER_CDF ≈ 0.35` (CDF franc congolais, volatile)

**Rationale** :
- Parité XOF↔EUR officiellement fixe → peut rester en constante éternellement.
- XOF↔USD/CDF volatiles → table refresh hebdomadaire post-MVP.
- Fallback indispensable car F10 doit livrer même si F30 n'est pas encore mergée.
- Côté frontend `<MoneyDisplay>` (F04) consomme cet endpoint avec cache 1 h.

**Alternatives considérées** :
1. **Appel API externe temps réel** (ex : exchangerate.host) — rejeté : dépendance réseau, coût latence, faille si l'API tombe.
2. **Hardcoder côté frontend** — rejeté : difficile à maintenir, pas de single source of truth.

**Implementation notes** :
- `backend/app/core/fx_rates.py` :
  ```
  XOF_PER_EUR = 655.957  # Parité fixe BCEAO
  XOF_PER_USD = 600.0    # Approx, à raffraîchir
  XOF_PER_CDF = 0.35     # Approx, à raffraîchir

  def get_fx_rates() -> dict[str, float]:
      """Retourne les taux courants. Fallback sur constants si table indisponible."""
      ...
  ```
- Endpoint `GET /api/referential/fx-rates` (à ajouter dans un router existant ou nouveau).
- Frontend marque un indicateur visuel discret « approx. » à côté de la valeur convertie.

---

## R8 — Format dates français : Intl.DateTimeFormat natif

**Decision** : Utiliser `Intl.DateTimeFormat('fr-FR', {dateStyle: 'long'})` natif pour formater les dates côté frontend (« 15 mars 2026 »). Côté backend, utiliser Babel `babel.dates.format_date(value, 'long', locale='fr')` si du formatage backend est nécessaire (ex : pour les emails).

**Rationale** :
- Natif navigateur (Chrome 24+, Firefox 29+, Safari 10+) → zéro dépendance.
- Locale `fr-FR` produit le format attendu : « 15 mars 2026 », « lundi 15 mars 2026 » (avec `weekday: 'long'`).
- Babel est déjà disponible côté Python (transitive deps).

**Alternatives considérées** :
1. **date-fns** — rejeté : ~150 Ko, surdimensionné pour 1 cas d'usage.
2. **dayjs** — rejeté : même raison.

**Implementation notes** :
- Helper Vue : `function formatDateFr(d: Date | string): string { return new Intl.DateTimeFormat('fr-FR', {dateStyle: 'long'}).format(typeof d === 'string' ? new Date(d) : d) }`.
- Date pickers : `<input type="date">` natif HTML5 (lang="fr") avec validation min/max.

---

## R9 — Extension d'enum PostgreSQL Alembic : ALTER TYPE ADD VALUE IF NOT EXISTS

**Decision** : Étendre l'enum `interactivequestiontype` PostgreSQL via `op.execute("ALTER TYPE interactivequestiontype ADD VALUE IF NOT EXISTS 'yes_no'")` répété pour les 9 valeurs, dans le bloc `upgrade()`. Pour `downgrade()`, il n'est pas trivial de retirer une valeur d'enum PostgreSQL (la valeur doit être inutilisée par toutes les lignes) : la migration documentera explicitement que le downgrade vérifie l'absence d'utilisation des nouvelles valeurs et avorte avec un message clair en cas d'utilisation.

**Rationale** :
- `IF NOT EXISTS` rend la migration idempotente (rejouable sans erreur).
- PostgreSQL >=10 supporte cette syntaxe nativement.
- L'impossibilité de retirer une valeur en down est une limitation connue PostgreSQL ; le projet la documente et fournit un fallback (recréation enum) en cas de besoin extrême.

**Alternatives considérées** :
1. **Migrer vers une table `interactive_question_types`** — rejeté : sur-ingénierie, perte de la sécurité enum.
2. **Stocker `question_type` en `varchar` simple sans enum** — rejeté : perte de la validation BDD, propice aux fautes de frappe.

**Implementation notes** :
- Skeleton migration `031_extend_interactive_questions.py` :
  ```
  def upgrade():
      with op.get_context().autocommit_block():
          for value in ["yes_no", "select", "number", "date", "date_range",
                        "rating", "file_upload", "form", "summary_card"]:
              op.execute(f"ALTER TYPE interactivequestiontype ADD VALUE IF NOT EXISTS '{value}'")
      op.add_column("interactive_questions",
          sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"))
      op.add_column("interactive_questions",
          sa.Column("response_payload", postgresql.JSONB(), nullable=True))
      # Relâcher la contrainte ck_iq_max_le_8
      op.drop_constraint("ck_iq_max_le_8", "interactive_questions", type_="check")
      op.create_check_constraint(
          "ck_iq_max_le_8_or_select_form",
          "interactive_questions",
          "max_selections <= 8 OR question_type IN ('select', 'form')"
      )

  def downgrade():
      # Vérifier qu'aucune ligne n'utilise les nouvelles valeurs
      result = op.get_bind().execute(text(
          "SELECT COUNT(*) FROM interactive_questions WHERE question_type IN "
          "('yes_no','select','number','date','date_range','rating','file_upload','form','summary_card')"
      ))
      count = result.scalar()
      if count > 0:
          raise RuntimeError(
              f"Downgrade impossible : {count} lignes utilisent les nouvelles valeurs d'enum. "
              "Migrez ces lignes manuellement avant de downgrader."
          )
      # Restaurer la contrainte initiale
      op.drop_constraint("ck_iq_max_le_8_or_select_form", "interactive_questions", type_="check")
      op.create_check_constraint(
          "ck_iq_max_le_8", "interactive_questions",
          "max_selections <= 8"
      )
      op.drop_column("interactive_questions", "response_payload")
      op.drop_column("interactive_questions", "payload")
      # Note : impossibilité PostgreSQL de retirer les valeurs d'enum.
      # Si besoin extrême : recréer le type avec UPDATE temporaire (procédure manuelle hors automation).
  ```
- Test up/down/up dans `backend/tests/integration/test_alembic_031_up_down_up.py`.

---

## R10 — Rétro-compatibilité widgets F18 : refactor en dispatcher

**Decision** : Refactorer `InteractiveQuestionInputBar.vue` en dispatcher utilisant `<component :is="widgetComponent">`. Mapping `TYPE_TO_COMPONENT: Record<InteractiveQuestionType, Component>` :
- `qcu`, `qcu_justification` → `SingleChoiceWidget` (existant F18)
- `qcm`, `qcm_justification` → `MultipleChoiceWidget` (existant F18)
- `yes_no` → `YesNoWidget` (NEW)
- `select` → `SelectWidget` (NEW)
- ... (9 nouveaux)
- défaut → `UnsupportedWidget` (NEW fallback)

**Rationale** :
- Pattern Vue 3 standard, performant, lisible.
- Préserve 100 % la logique existante des composants F18.
- Permet l'ajout de nouveaux types sans modifier le dispatcher (juste enregistrer le composant).
- Le fallback garantit la résilience aux versions de schéma futures.

**Alternatives considérées** :
1. **Switch dans le template** — rejeté : verbeux, difficile à maintenir.
2. **Conserver la logique inline F18 et ajouter les 9 nouvelles** — rejeté : explosion de la taille du composant > 800 lignes (limite constitution).

**Implementation notes** :
- Le dispatcher conserve les props communes (`question`, `loading`, `disabled`) et les events (`submit`, `abandon-and-send`) — aucun breaking change pour le parent `InteractiveQuestionHost.vue`.
- Tests Playwright de non-régression (1 par variante F18) garantissent zéro régression.

---

## Synthèse — Toutes NEEDS CLARIFICATION résolues

| # | Sujet | Décision | Source FR/SC |
|---|---|---|---|
| R1 | Persistance par variante | payload jsonb + Pydantic discriminé | FR-002, FR-003 |
| R2 | Click-and-hold 2 s | Native CSS + composable | FR-030, SC-011 |
| R3 | Virtualisation listes | vue-virtual-scroller | FR-021, SC-006 |
| R4 | Validation client form | zod | FR-023 |
| R5 | Validation MIME upload | python-magic | FR-025, SC-012 |
| R6 | Pattern destructif | Retour JSON string + helper | FR-011, FR-012, SC-001 |
| R7 | Taux de change | Constants + table référentiel | FR-022 |
| R8 | Format dates fr | Intl.DateTimeFormat natif | FR-034 |
| R9 | Extension enum Alembic | ALTER TYPE ADD VALUE IF NOT EXISTS | FR-001, FR-004 |
| R10 | Rétro-compat F18 | Dispatcher `<component :is>` | FR-026, SC-004 |

Toutes les décisions sont alignées avec la constitution ESG Mefali (Francophone-First, modulaire, conversation-driven, test-first, sécurité, inclusivité, simplicité).
