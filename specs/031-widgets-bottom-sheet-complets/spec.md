# Feature Specification: Widgets Interactifs Bottom Sheet Complets (F10)

**Feature Branch**: `feat/F10-widgets-bottom-sheet-complets`
**SpecKit Folder**: `031-widgets-bottom-sheet-complets`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F10 — Widgets Interactifs Bottom Sheet Complets : compléter les 9 widgets manquants (yes_no, select, number, date, date_range, rating, file_upload, form, summary_card) dans le bottom sheet conversationnel pour respecter le contrat Module 1.1.1 et activer le pattern de confirmation des actions destructives Module 1.1.3."

## Clarifications

### Session 2026-05-07

- Q: Comment stocker les paramètres et la réponse spécifiques par variante de widget (bornes, devise, items de formulaire, modifications) sur la table `interactive_questions` ? → A: Deux colonnes `payload jsonb NOT NULL DEFAULT '{}'` (paramètres) et `response_payload jsonb NULL` (réponse structurée), schéma validé via Pydantic discriminé par `question_type` (pas de tables satellites, pas de colonnes typées dédiées).
- Q: Comment la double-confirmation visuelle d'un `ask_yes_no(destructive=True)` doit-elle être implémentée pour empêcher les clics accidentels ? → A: Click-and-hold 2 secondes sur le bouton « Oui » avec animation de progression (anneau qui se remplit), accessibilité clavier équivalente (touche Entrée maintenue 2 s ou re-confirmation par modal), pas d'autre validation requise.
- Q: D'où provient la valeur d'équivalent monétaire affichée par `<MoneyDisplay>` dans `NumberWidget` (ex : « ≈ 1 524 € » sous une saisie XOF) ? → A: Table de change locale `referential_fx_rates` (snapshot quotidien) avec fallback constants statiques côté frontend (XOF↔EUR=655.957, XOF↔USD=600 approx, XOF↔CDF=2.86 approx, refresh hebdomadaire), pas d'appel API tiers temps réel pour MVP.
- Q: Quel niveau de scan de sécurité appliquer aux fichiers uploadés via `ask_file_upload` ? → A: Validation stricte côté backend : type MIME et signature magique (`python-magic`), taille ≤ 10 Mo, extension whitelist, refus systématique si discordance MIME/extension. Pas d'antivirus ni sandbox MVP (à raccrocher post-MVP via S3 + Lambda).
- Q: Comment garantir la rétro-compatibilité des messages utilisateur historiques côté frontend après l'extension de l'enum `InteractiveQuestionType` ? → A: Le composant racine `InteractiveQuestionInputBar.vue` route par `question_type` ; pour les 4 valeurs existantes (`qcu`, `qcm`, `qcu_justification`, `qcm_justification`) le rendu reste inchangé (logique en place F18 conservée), pour les 9 nouvelles valeurs un dispatcher délègue au widget approprié, et un fallback `UnsupportedWidget.vue` (textarea + message « Type non supporté ») couvre les types inconnus pour permettre des futures extensions sans casser l'historique.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Confirmation d'une action destructive (Priorité : P1)

Le LLM doit supprimer une candidature de l'utilisateur. Avant d'exécuter, il pose une question oui/non avec un bouton « Oui, supprimer » en rouge, le bouton « Non, annuler » en gris, et une protection anti-clic accidentel (action irréversible). Une fois la réponse donnée, l'action s'exécute (ou est annulée) et un journal d'audit est écrit.

**Why this priority** : Sans `ask_yes_no` natif, le LLM utilise actuellement un QCU à deux options « Oui/Non » avec une heuristique fragile dans `useChat.ts`. Le pattern destructif (Module 1.1.3) n'est pas implémentable techniquement, ce qui expose les données utilisateur à des suppressions accidentelles par hallucination LLM. C'est la régression la plus dangereuse de l'architecture actuelle, donc P1.

**Independent Test** : Lancer une conversation, demander au LLM de supprimer un projet existant. Le widget rouge doit apparaître, l'utilisateur doit pouvoir cliquer « Oui, supprimer » ou « Non », et l'effet doit être : suppression effective + ligne d'audit_log F03 (cas oui) ou aucune mutation (cas non).

**Acceptance Scenarios** :

1. **Étant donné** une conversation avec un projet existant, **Quand** l'utilisateur demande « supprime mon projet "Panneaux solaires" », **Alors** le LLM appelle d'abord `delete_project(confirm=False)` qui retourne `{requires_confirmation: True}`, puis il invoque `ask_yes_no(destructive=True)` avec un libellé rouge « Oui, supprimer » et un libellé gris « Non, annuler ».
2. **Étant donné** un widget `ask_yes_no` destructif affiché, **Quand** l'utilisateur clique « Oui, supprimer », **Alors** le bouton exige une seconde confirmation visuelle (animation 2 secondes ou click-and-hold), puis le LLM rappelle `delete_project(confirm=True)` et le projet est supprimé en BDD avec une entrée `audit_log` (action=delete_project, account_id, user_id, target_id, before/after).
3. **Étant donné** un widget `ask_yes_no` destructif affiché, **Quand** l'utilisateur clique « Non, annuler », **Alors** aucune mutation ne se produit, le bottom sheet se ferme, et le message utilisateur dans le fil affiche « ✗ Non ».
4. **Étant donné** un widget `ask_yes_no` destructif affiché, **Quand** l'utilisateur clique « Répondre librement » et tape un message texte, **Alors** la question expire (state=`expired`), le message libre est envoyé normalement, et l'action destructive ne s'exécute pas tant que le LLM ne re-confirme pas.

---

### User Story 2 — Sélection dans une liste longue avec recherche (Priorité : P1)

L'utilisateur doit choisir un pays parmi 50+ pays africains, ou un fonds parmi un catalogue de 100+ entrées. Le widget doit proposer un champ de recherche full-text au-dessus, une liste scrollable virtualisée si > 50 options, un groupement optionnel (région, type), et la possibilité de saisir « Autre, préciser » si le LLM autorise.

**Why this priority** : Sans `ask_select`, le LLM doit poser un QCU plafonné à 8 options ou poser une question texte libre, ce qui dégrade fortement l'UX et empêche la sélection structurée d'éléments à fort cardinal (pays, fonds, secteurs). Critique pour les modules financement (F08) et profil entreprise (F03).

**Independent Test** : Demander au LLM « dans quel pays UEMOA est votre siège ? ». Le widget doit afficher 8 pays groupés, un champ de recherche fonctionnel, et un retour message lisible « ✓ Côte d'Ivoire » après sélection.

**Acceptance Scenarios** :

1. **Étant donné** une question avec 8+ options, **Quand** le widget s'affiche, **Alors** un champ de recherche apparaît au-dessus de la liste et permet de filtrer par préfixe ou sous-chaîne (insensible casse/accents).
2. **Étant donné** une question avec > 50 options, **Quand** le widget s'affiche, **Alors** la liste est virtualisée (vue-virtual-scroller) et le scroll reste fluide à 60 fps même avec 200 options.
3. **Étant donné** des options groupées par `group`, **Quand** le widget s'affiche, **Alors** chaque groupe est visuellement séparé avec un en-tête de section.
4. **Étant donné** un widget multi-sélection (`max_selections > 1`), **Quand** l'utilisateur sélectionne 3 pays, **Alors** un compteur « 3 / 5 max » s'affiche et le bouton Valider envoie un message « ✓ Côte d'Ivoire, Sénégal, Mali ».
5. **Étant donné** `allow_other=True`, **Quand** l'utilisateur clique « Autre, préciser », **Alors** un champ texte s'ouvre et la valeur saisie est envoyée comme `{id: "other", label: "<saisie utilisateur>"}`.

---

### User Story 3 — Saisie d'un montant monétaire avec devise (Priorité : P1)

L'utilisateur doit indiquer le chiffre d'affaires annuel, le montant d'un projet, ou un capital social. Le widget doit proposer un input numérique formaté (séparateurs de milliers), un sélecteur de devise (XOF/EUR/USD), des bornes min/max, des incréments via boutons +/-, et l'affichage automatique de l'équivalent dans une devise de référence.

**Why this priority** : Sans `ask_number`, l'utilisateur saisit en texte libre des montants ambigus (« 5M », « 5 000 000 », « 5 millions ») que le LLM doit parser à la main, avec un risque d'erreur à 6 zéros près. Critique pour la cohérence des données financières (F04 Money typed) et pour l'évaluation des projets (F08).

**Independent Test** : Demander au LLM « quel est votre chiffre d'affaires annuel ? ». Le widget doit afficher un input avec sélecteur XOF/EUR/USD, formatter « 1000000 » en « 1 000 000 », valider que la valeur est dans `[0, 1 000 000 000 000]`, et afficher l'équivalent EUR sous la valeur saisie.

**Acceptance Scenarios** :

1. **Étant donné** un widget `ask_number(currency=XOF)`, **Quand** l'utilisateur tape « 1000000 », **Alors** la valeur est formatée à l'écran en « 1 000 000 » (séparateurs espaces fines françaises), et un texte « ≈ 1 524 € » apparaît sous l'input.
2. **Étant donné** des bornes `min=0, max=1_000_000_000`, **Quand** l'utilisateur tape une valeur hors borne, **Alors** un message d'erreur en français s'affiche et le bouton Valider est désactivé.
3. **Étant donné** un widget avec sélecteur de devise, **Quand** l'utilisateur change la devise de XOF à EUR, **Alors** la valeur saisie est conservée mais l'affichage de l'équivalent change.
4. **Étant donné** un widget avec `step=1000`, **Quand** l'utilisateur clique sur le bouton +, **Alors** la valeur courante augmente de 1000.
5. **Étant donné** un widget validé avec valeur 1 200 000 XOF, **Quand** l'utilisateur clique Valider, **Alors** le message dans le fil s'affiche « ✓ 1 200 000 FCFA » avec un payload structuré `{value: 1200000, currency: "XOF", formatted: "1 200 000 FCFA"}` en métadonnée.

---

### User Story 4 — Création d'une entité en un seul formulaire (Priorité : P1)

Le LLM identifie qu'il a besoin de créer un projet (8 champs : nom, description, secteur, montant cible, durée, localisation, etc.) à partir d'une conversation. Plutôt que de poser 8 questions séquentielles (« et le secteur ? », « et le montant ? »), il appelle `show_form` qui rend un mini-formulaire validable en un clic, avec validation côté client.

**Why this priority** : Sans `show_form`, créer une entité demande 8 tours de conversation. C'est lent, frustrant et ne permet pas à l'utilisateur de revoir l'ensemble avant validation. Critique pour la création de projets (F25), de bilans carbone (F07), de candidatures (F09).

**Independent Test** : Demander au LLM « j'ai un projet de panneaux solaires de 5M FCFA en Côte d'Ivoire ». Le LLM doit appeler `show_form` avec 8 champs pré-remplis (nom, description, sector, target_amount, etc.), permettre la validation en un clic, et créer l'entité projet en BDD.

**Acceptance Scenarios** :

1. **Étant donné** un appel `show_form` avec 8 champs, **Quand** le widget s'affiche, **Alors** chaque champ est rendu avec son composant approprié (text input pour text, NumberWidget pour money, DateWidget pour date, SelectWidget pour select).
2. **Étant donné** un champ `required=true`, **Quand** l'utilisateur clique Valider sans remplir, **Alors** le bouton est désactivé et un message « Ce champ est requis » s'affiche en rouge sous le champ.
3. **Étant donné** une validation `validation: {min_length: 5, max_length: 200}`, **Quand** l'utilisateur saisit « ok » (3 caractères), **Alors** le champ est marqué invalide et le bouton Valider reste désactivé.
4. **Étant donné** un formulaire valide, **Quand** l'utilisateur clique Valider, **Alors** un seul payload structuré est envoyé au LLM (pas 8 tours), le LLM appelle l'outil métier (create_project), et le message dans le fil s'affiche « ✓ Projet créé : Panneaux solaires, 5M FCFA, énergie ».
5. **Étant donné** un formulaire en cours de saisie, **Quand** l'utilisateur clique Annuler, **Alors** le bottom sheet se ferme, la question expire, et aucun side-effect ne se produit.
6. **Le formulaire accepte au plus 10 champs**, et un type non whitelisté (ex : `array`) provoque une erreur côté backend (refus du tool).

---

### User Story 5 — Validation/correction d'extractions (Priorité : P2)

Après l'analyse d'un document (statuts.pdf), le LLM affiche une summary card « Voici ce qu'on a extrait : SARL, capital 5M, 12 employés. Validez ou corrigez ? » avec édition inline des champs marqués `editable=true`. L'utilisateur peut soit cliquer Valider directement, soit cliquer Corriger pour basculer en mode édition champ par champ.

**Why this priority** : Sans `show_summary_card`, après une extraction OCR/LLM, l'utilisateur doit relire un long texte et taper « le capital n'est pas 5M mais 6M ». Avec la summary card, il édite directement le champ, ce qui réduit drastiquement les frictions et les erreurs. P2 car c'est un confort UX, pas un bloquant.

**Independent Test** : Uploader un document, attendre l'extraction LLM, vérifier qu'une summary card s'affiche avec les champs extraits, cliquer « Corriger » sur le champ capital, modifier la valeur, cliquer Valider, et vérifier que le payload contient les modifications.

**Acceptance Scenarios** :

1. **Étant donné** une summary card affichée avec 5 items dont 3 `editable=true`, **Quand** le widget s'affiche, **Alors** une icône crayon apparaît à droite des 3 items éditables uniquement.
2. **Étant donné** une summary card en mode lecture, **Quand** l'utilisateur clique « Corriger », **Alors** tous les items `editable=true` basculent en mode édition (input inline) et un bouton « Valider mes corrections » remplace les boutons « Valider/Corriger ».
3. **Étant donné** une summary card en mode édition, **Quand** l'utilisateur modifie « capital : 5M » en « capital : 6M » et clique « Valider mes corrections », **Alors** le message dans le fil s'affiche « ✓ Corrigé : capital 6M (au lieu de 5M) » avec un payload `{validated: true, modifications: [{field: "capital", before: "5M", after: "6M"}]}`.
4. **Étant donné** une summary card sans modifications, **Quand** l'utilisateur clique « Valider », **Alors** le message s'affiche « ✓ Validé » avec un payload `{validated: true, modifications: []}`.

---

### User Story 6 — Saisie d'une date (Priorité : P2)

L'utilisateur doit indiquer une date de soumission, une période d'évaluation, ou la validité d'une attestation. Le widget rend un date picker natif HTML5, avec une alternative custom pour cohérence cross-browser, l'affichage en français (« 15 mars 2026 »), et des bornes min/max optionnelles.

**Why this priority** : Sans `ask_date`, l'utilisateur saisit « 15 mars 2026 » ou « 15/03/2026 » ou « 2026-03-15 » et le LLM doit parser, avec ambiguïté MM/DD vs DD/MM. P2 car contournable mais améliore la fiabilité.

**Independent Test** : Demander au LLM « jusqu'à quand votre attestation est-elle valide ? ». Le widget doit afficher un date picker en français, valider min=aujourd'hui+1, et retourner « ✓ 15 mars 2026 » dans le fil.

**Acceptance Scenarios** :

1. **Étant donné** un widget `ask_date(min=today)`, **Quand** l'utilisateur tente de sélectionner une date passée, **Alors** la sélection est désactivée et un message « Date doit être ≥ aujourd'hui » s'affiche.
2. **Étant donné** un widget `ask_date_range`, **Quand** l'utilisateur sélectionne du 1er janvier au 31 décembre, **Alors** la réponse est `{from: "2026-01-01", to: "2026-12-31"}` et le message s'affiche « ✓ Du 1 janvier au 31 décembre 2026 ».
3. **Étant donné** un widget `ask_date(default=today)`, **Quand** le widget s'affiche, **Alors** la date du jour est pré-sélectionnée.

---

### User Story 7 — Notation/évaluation (Priorité : P2)

L'utilisateur doit auto-évaluer une pratique ESG sur une échelle 1-5 (étoiles) ou 1-10 (points). Le widget affiche les étoiles/points avec hover preview et labels textuels optionnels sous chaque valeur.

**Why this priority** : Sans `ask_rating`, l'utilisateur saisit « 4 sur 5 » ou « bon » et le LLM doit parser. P2 car peu critique mais amélioration UX claire pour l'auto-évaluation ESG (F05).

**Independent Test** : Demander au LLM « comment évaluez-vous votre pratique de tri sélectif ? ». Le widget doit afficher 5 étoiles avec labels « Très mauvais → Excellent », et retourner « ✓ 4/5 (Très bien) ».

**Acceptance Scenarios** :

1. **Étant donné** un widget `ask_rating(scale=5, labels=["Très mauvais", ..., "Excellent"])`, **Quand** l'utilisateur passe la souris sur la 4e étoile, **Alors** le label « Très bien » apparaît en preview.
2. **Étant donné** un widget `ask_rating(scale=10)`, **Quand** le widget s'affiche, **Alors** 10 points cliquables sont rendus.
3. **Étant donné** un widget validé avec note 4/5, **Quand** l'utilisateur clique Valider, **Alors** le message s'affiche « ✓ 4/5 (Très bien) ».

---

### User Story 8 — Upload de fichier contextualisé (Priorité : P2)

Le LLM demande « pouvez-vous m'envoyer votre business plan ? ». Plutôt que d'imposer à l'utilisateur de fermer le bottom sheet et de cliquer le trombone séparé, un widget upload contextualisé apparaît dans le bottom sheet avec drag-and-drop, progress bar, et lien automatique au document dans le chat (le LLM reçoit le `document_id` après upload).

**Why this priority** : Sans `ask_file_upload`, l'utilisateur doit fermer le widget, retrouver le trombone, uploader, et le LLM perd le contexte (« qu'est-ce que je devais faire avec ce fichier ? »). P2 car il existe une voie de contournement (trombone existant).

**Independent Test** : Demander au LLM « envoyez-moi votre business plan ». Le widget doit afficher un drop zone, accepter un PDF, afficher la progress bar, et retourner un message « ✓ business_plan.pdf (uploaded) » avec le `document_id` en payload.

**Acceptance Scenarios** :

1. **Étant donné** un widget `ask_file_upload(accept=[".pdf"], max_size_mb=10)`, **Quand** l'utilisateur drag-and-drop un fichier .docx, **Alors** un message « Type non accepté » apparaît et le fichier est rejeté.
2. **Étant donné** un widget `ask_file_upload(max_size_mb=10)`, **Quand** l'utilisateur dépose un fichier de 15 Mo, **Alors** un message « Fichier trop volumineux (max 10 Mo) » apparaît.
3. **Étant donné** un upload en cours, **Quand** la progress bar atteint 100 %, **Alors** un message « ✓ business_plan.pdf (uploaded) » s'affiche et le `document_id` est transmis au LLM.

---

### User Story 9 — Compatibilité dégradée (Priorité : P3)

L'utilisateur préfère répondre librement plutôt qu'utiliser le widget. Tous les widgets doivent inclure un bouton « Répondre librement » qui ouvre un textarea, ferme le widget structuré, marque la question comme `expired`, et envoie le message comme un message texte normal.

**Why this priority** : Garantit qu'aucun widget ne piège l'utilisateur. P3 car déjà implémenté pour QCU/QCM (héritage F18), il s'agit de propager le pattern.

**Independent Test** : Pour chaque widget, vérifier que le bouton « Répondre librement » est visible, fonctionnel, et que le clic ferme le widget et ouvre une zone de saisie texte.

**Acceptance Scenarios** :

1. **Étant donné** un widget `ask_yes_no` destructif affiché, **Quand** l'utilisateur clique « Répondre librement », **Alors** la question passe en `expired`, l'action destructive n'est pas exécutée, et un textarea apparaît.
2. **Étant donné** un widget `show_form` à moitié rempli, **Quand** l'utilisateur clique « Répondre librement », **Alors** les valeurs partielles sont abandonnées et le formulaire ferme.

---

### Edge Cases

- **Une question pending existe déjà** : avant d'insérer une nouvelle question, marquer toutes les questions `pending` de la conversation comme `expired` (invariant 1 question pending max, déjà actif depuis F18).
- **Type de widget inconnu côté frontend** : router vers le composant fallback `UnsupportedWidget.vue` (textarea + libellé « Type de widget non supporté, répondez librement » + bouton « Envoyer » qui passe la question en `expired`), logger une erreur côté frontend (Sentry/console) ET côté backend (warning à la réception du marker SSE non interprétable). Garantit la résilience aux versions futures.
- **Type de widget connu mais payload invalide** (ex : `ask_select` avec 0 options) : refuser au niveau Pydantic backend, retourner une erreur tool, le LLM doit se rattraper.
- **Le LLM appelle un tool de mutation destructif sans `confirm=True`** : le tool retourne `{requires_confirmation: True}`, le LLM voit le résultat et invoque `ask_yes_no(destructive=True)`. Si le LLM ignore le pattern, le tool reste bloquant (jamais de mutation sans confirm explicite).
- **Le LLM oublie d'invoquer `ask_yes_no` après `requires_confirmation`** : le tool destructif refuse les appels suivants tant que `confirm=False`. Pas de bypass possible.
- **Mobile petit écran** : le bottom sheet doit être responsive, scroll interne, ne pas masquer les boutons d'action. Les animations gsap respectent `prefers-reduced-motion`.
- **Connexion SSE perdue pendant la saisie d'un formulaire** : le widget se verrouille (boutons désactivés via `disabled`), un toast informe l'utilisateur, la saisie locale est conservée jusqu'à reconnexion.
- **L'utilisateur recharge la page pendant un widget pending** : la question est rechargée depuis la BDD au démarrage de la conversation et le widget est restauré dans son état initial.
- **`ask_select` avec 200+ options** : la limite dure est 200 ; au-delà le tool refuse côté backend et le LLM doit filtrer en amont.
- **`show_form` avec 11+ champs** : le tool refuse côté backend (max 10 champs).
- **Justification > 400 caractères** : le textarea est borné à 400 et le serveur valide une seconde fois (défense en profondeur, conservée depuis F18).
- **Fichier uploadé avec MIME falsifié** (ex : extension `.pdf` mais signature magique `application/x-msdownload`) : `python-magic` détecte la discordance, le backend retourne 415 « Type de fichier incohérent », le widget affiche l'erreur en français et le LLM peut renvoyer la question.
- **Endpoint `referential_fx_rates` indisponible** (ex : avant déploiement F30 ou panne) : `<MoneyDisplay>` retombe sur les constantes statiques avec un indicateur visuel discret « approx. » à côté de la valeur convertie, sans bloquer la saisie.

## Requirements *(mandatory)*

### Functional Requirements

#### Backend — Modèle et persistance

- **FR-001** : Le système DOIT étendre l'enum `InteractiveQuestionType` avec 9 nouvelles valeurs : `yes_no`, `select`, `number`, `date`, `date_range`, `rating`, `file_upload`, `form`, `summary_card`. Les 4 valeurs existantes (`qcu`, `qcm`, `qcu_justification`, `qcm_justification`) DOIVENT être conservées pour rétro-compatibilité.
- **FR-002** : Le système DOIT ajouter une colonne `payload jsonb NOT NULL DEFAULT '{}'::jsonb` à la table `interactive_questions` pour stocker les paramètres spécifiques par variante (bornes numériques, devise, fichiers acceptés, champs de formulaire, etc.). Le contenu est validé côté Pydantic via une union discriminée par `question_type` (`InteractiveQuestionPayload = YesNoPayload | SelectPayload | NumberPayload | DatePayload | DateRangePayload | RatingPayload | FileUploadPayload | FormPayload | SummaryCardPayload | dict[str, Any]`), garantissant un typage strict sans nécessiter de tables satellites ni de colonnes typées dédiées (cf. clarification 2026-05-07 Q1).
- **FR-003** : Le système DOIT ajouter une colonne `response_payload jsonb NULL` à la table `interactive_questions` pour stocker les réponses structurées au-delà des simples `response_values` existants (ex : `{value: 1200000, currency: "XOF", formatted: "1 200 000 FCFA"}` pour ask_number, `{value: true, label: "Oui"}` pour ask_yes_no, `{validated: true, modifications: [...]}` pour show_summary_card). Le format de réponse est validé via les mêmes schémas Pydantic discriminés (cf. clarification 2026-05-07 Q1).
- **FR-004** : Le système DOIT créer une migration Alembic `031_extend_interactive_questions.py` avec `down_revision=030_create_referential_scores`, capable de monter (étendre l'enum + ajouter colonnes) et descendre (sans perte de données — les nouvelles valeurs d'enum présentes en BDD bloquent le downgrade, qui doit alors avorter avec un message clair).
- **FR-005** : Le système DOIT relâcher la contrainte `ck_iq_max_le_8` pour permettre `ask_select` (jusqu'à 200 options). La contrainte est remplacée par `max_selections <= 8 OR question_type IN ('select', 'form')`.

#### Backend — Tools LangChain

- **FR-006** : Le système DOIT exposer 9 nouveaux tools LangChain dans `backend/app/graph/tools/interactive_tools.py`, chacun avec un schéma Pydantic `extra="forbid"` strict :
  - `ask_yes_no(question, confirm_label="Oui", deny_label="Non", destructive=False)`
  - `ask_select(question, options, min_selections=1, max_selections=1, allow_other=False)`
  - `ask_number(question, unit, min=None, max=None, step=1, currency=None, default=None)`
  - `ask_date(question, min=None, max=None, default=None)`
  - `ask_date_range(question, min=None, max=None)`
  - `ask_rating(question, scale=5, labels=None)`
  - `ask_file_upload(question, accept=[".pdf", ".docx", ".xlsx", ".png", ".jpg"], max_size_mb=10, multi=False, doc_type_hint=None)`
  - `show_form(title, fields, submit_label="Enregistrer")`
  - `show_summary_card(title, items, confirm_label="Valider", correct_label="Corriger")`
- **FR-007** : Chaque tool DOIT, comme `ask_interactive_question` actuel, marquer toutes les questions `pending` de la conversation comme `expired` avant d'insérer la nouvelle, garantissant l'invariant « 1 question pending max par conversation ».
- **FR-008** : Chaque tool DOIT embarquer un marker SSE `<!--SSE:{"__sse_interactive_question__":true,...}-->` à la fin de son retour string, intercepté par `stream_graph_events` pour pousser l'événement frontend `interactive_question`.
- **FR-009** : Chaque tool DOIT être journalisé via `log_tool_call` avec `node_name=module_name`, `tool_name=<nom>`, `tool_args` tronqué (prompt limité à 200 caractères), `tool_result={"question_id": ..., "state": "pending"}`, `status="success"`.
- **FR-010** : Le système DOIT conserver le tool `ask_interactive_question` existant (4 variantes QCU/QCM) sans modification, pour éviter toute régression sur F18.

#### Backend — Pattern destructif

- **FR-011** : Le système DOIT ajouter un paramètre `confirm: bool = False` à TOUS les tools de mutation destructifs existants (`delete_*`, `revoke_*`, `cancel_*`). Si `confirm=False`, le tool DOIT retourner `{"requires_confirmation": True, "message": "Confirmation requise via ask_yes_no", "destructive_action": "<nom_action>"}` sans appliquer la mutation.
- **FR-012** : Le système DOIT exposer un helper backend `requires_destructive_confirmation(action_name: str)` réutilisable par tous les tools destructifs futurs, garantissant une trace cohérente du pattern.
- **FR-013** : La liste des tools destructifs initiaux DOIT inclure au minimum : `delete_project`, `delete_application`, `revoke_attestation`, `cancel_assessment`. Pour la phase F10, si certains de ces tools n'existent pas encore (modules pas livrés), créer un stub dans `interactive_tools.py` qui implémente le pattern, à raccrocher en Phase B.

#### Backend — Configuration tool selector

- **FR-014** : Le système DOIT inscrire les 9 nouveaux tools dans `tool_selector_config.py` selon une matrice de visibilité par contexte (ex : `ask_file_upload` exposé dans tous les nœuds, `show_summary_card` exposé après extraction document, `show_form` exposé sur les modules entité-création).
- **FR-015** : Le système DOIT définir la matrice de visibilité avec les paramètres suivants par défaut, modifiables :
  - Tous les nœuds (chat + 8 spécialistes) : `ask_yes_no`, `ask_select`, `ask_number`, `ask_date`, `ask_date_range`, `ask_rating`, `ask_file_upload`.
  - Nœuds entité-création (profiling, projets, candidatures, carbone) : `show_form`.
  - Nœuds extraction (document, esg_scoring, financing) : `show_summary_card`.

#### Backend — Prompts (préparation F22)

- **FR-016** : Le système DOIT mettre à jour le helper partagé `WIDGET_INSTRUCTION` (`backend/app/prompts/`) pour mentionner les 9 nouveaux tools dans le decision tree fourni au LLM, avec exemples concrets et cas d'usage.
- **FR-017** : Le système DOIT injecter ce `WIDGET_INSTRUCTION` étendu dans les 7 prompts modules (chat_node, esg_scoring, carbon, financing, application, credit, action_plan) sans casser l'existant (4 prompts QCU/QCM déjà présents).

#### Frontend — Composants Vue

- **FR-018** : Le système DOIT créer 9 nouveaux composants Vue dans `frontend/app/components/chat/widgets/`, chacun avec dark mode complet (variantes `dark:` Tailwind), accessibilité ARIA (roles, aria-checked, aria-describedby, aria-label), et props typées TypeScript strict :
  - `YesNoWidget.vue`
  - `SelectWidget.vue`
  - `NumberWidget.vue`
  - `DateWidget.vue`
  - `DateRangeWidget.vue`
  - `RatingWidget.vue`
  - `FileUploadWidget.vue`
  - `FormWidget.vue`
  - `SummaryCardWidget.vue`
- **FR-019** : Chaque composant DOIT inclure un bouton « Répondre librement » qui émet `abandon-and-send`, fermant le widget et ouvrant un textarea (pattern existant F18).
- **FR-020** : Chaque composant DOIT supporter une prop `disabled: boolean` qui verrouille tous les contrôles (utilisée en cas de perte SSE — pattern existant F18).
- **FR-021** : `SelectWidget.vue` DOIT virtualiser la liste avec vue-virtual-scroller si `options.length > 50`, intégrer un champ de recherche full-text (insensible casse/accents via `String.prototype.normalize('NFD').replace(/[̀-ͯ]/g, '')`), et grouper les options par `group` si fourni.
- **FR-022** : `NumberWidget.vue` DOIT formatter la valeur affichée avec séparateurs de milliers français (ex : `1 200 000`), valider les bornes min/max côté client, et afficher un équivalent monétaire via `<MoneyDisplay>` (F04) si `currency` est fourni. Les taux de change utilisés par `<MoneyDisplay>` proviennent en priorité d'un endpoint backend `GET /api/referential/fx-rates` (snapshot quotidien depuis la table `referential_fx_rates`, alimentée hebdomadairement depuis BCEAO/ECB) ; en cas d'échec API ou d'absence de table (avant déploiement du référentiel), un fallback de constantes statiques (XOF↔EUR=655.957 par parité fixe officielle, XOF↔USD≈600, XOF↔CDF≈2.86) est appliqué côté frontend avec un indicateur visuel discret « approx. ». Pas d'appel API tiers temps réel pour MVP (cf. clarification 2026-05-07 Q3).
- **FR-023** : `FormWidget.vue` DOIT rendre chaque champ via le composant approprié à son `type` (réutilisation de `NumberWidget`, `DateWidget`, etc. inline), supporter au plus 10 champs (validé côté backend), et offrir une validation client zod par champ avec messages d'erreur en français.
- **FR-024** : `SummaryCardWidget.vue` DOIT afficher chaque item en mode lecture par défaut, basculer en mode édition quand l'utilisateur clique « Corriger », et émettre un payload `{validated: true, modifications: [{field, before, after}]}` au submit.
- **FR-025** : `FileUploadWidget.vue` DOIT supporter le drag-and-drop, valider le type MIME et la taille côté client (pré-filtrage UX), afficher une progress bar pendant l'upload, et émettre un payload `{document_id: UUID, filename: str, size: int}` à la fin. Côté backend, l'endpoint `POST /api/documents/upload` DOIT valider strictement : (a) extension dans la whitelist du widget, (b) type MIME via `python-magic` (signature magique du contenu), (c) taille ≤ 10 Mo (ou valeur du paramètre `max_size_mb` si plus restrictive), (d) refus systématique en cas de discordance MIME/extension avec un code HTTP 415 + message « Type de fichier incohérent ». Pas d'antivirus ni sandbox MVP — à raccrocher post-MVP via S3 + Lambda ClamAV (cf. clarification 2026-05-07 Q4).

#### Frontend — Routing et composables

- **FR-026** : Le système DOIT étendre `frontend/app/components/chat/InteractiveQuestionInputBar.vue` pour router selon `question.question_type`. Pour les types `qcu`, `qcm`, `qcu_justification`, `qcm_justification` : conserver la logique existante (rétro-compat F18, aucune modification du rendu). Pour les 9 nouveaux types : déléguer au composant correspondant via un mapping statique `TYPE_TO_COMPONENT: Record<InteractiveQuestionType, Component>`. Pour tout type inconnu (ex : ajout futur via une feature ultérieure non encore livrée côté frontend) : afficher un composant fallback `UnsupportedWidget.vue` (textarea générique + libellé « Type de widget non supporté, répondez librement » + bouton « Envoyer » qui passe par la voie texte standard avec marquage de la question comme `expired`), sans casser le rendu de l'historique de la conversation (cf. clarification 2026-05-07 Q5).
- **FR-027** : Le système DOIT étendre `frontend/app/composables/useInteractiveQuestion.ts` pour exposer les nouveaux états et helpers (validation, formatage, équivalences monétaires) sans casser l'API existante.
- **FR-028** : Le système DOIT étendre `frontend/app/composables/useChat.ts:submitInteractiveAnswer` pour accepter les nouveaux types de payload (boolean pour yes_no, number+currency pour ask_number, date pour ask_date, etc.) et générer le message texte récapitulatif `"✓ ..."` adapté.
- **FR-029** : Le système DOIT supprimer l'heuristique fragile de mapping QCU « Oui/Non » dans `useChat.ts:121-130`, devenue obsolète avec `ask_yes_no` natif.

#### Frontend — UX et a11y

- **FR-030** : Le bouton « Oui, supprimer » d'un widget `ask_yes_no(destructive=True)` DOIT être visuellement distinct (rouge, ex : `bg-red-600 hover:bg-red-700`), inclure un tooltip ARIA « Action irréversible », et exiger un click-and-hold de 2 secondes pour valider, avec une animation de progression (anneau ou barre qui se remplit autour du bouton). Pour le clavier-only et l'accessibilité : touche Entrée maintenue 2 secondes équivalente, ou ouverture d'un modal de re-confirmation à un seul bouton « Oui, je confirme la suppression » lorsque le hold n'est pas possible (ex : screen reader). Aucune autre étape de validation n'est requise au-delà du click-and-hold (cf. clarification 2026-05-07 Q2).
- **FR-031** : Tous les composants widgets DOIVENT respecter `prefers-reduced-motion: reduce` (animations désactivées).
- **FR-032** : Tous les composants widgets DOIVENT être testés clavier-only (navigation tab, validation entrée, fermeture echap).
- **FR-033** : Le bottom sheet DOIT rester accessible sur mobile (largeur ≤ 480 px) avec scroll interne et boutons d'action toujours visibles.

#### Réponses dans le fil

- **FR-034** : Chaque widget validé DOIT envoyer un message utilisateur dans le fil avec le format texte canonique :
  - `ask_yes_no` → « ✓ Oui » / « ✗ Non »
  - `ask_select` (mono) → « ✓ Côte d'Ivoire »
  - `ask_select` (multi) → « ✓ Côte d'Ivoire, Sénégal, Mali »
  - `ask_number` → « ✓ 1 200 000 FCFA » (avec formatage devise)
  - `ask_date` → « ✓ 15 mars 2026 »
  - `ask_date_range` → « ✓ Du 1 janvier au 31 décembre 2026 »
  - `ask_rating` → « ✓ 4/5 (Très bien) »
  - `ask_file_upload` → « ✓ statuts.pdf (uploaded) »
  - `show_form` → « ✓ Projet créé : Panneaux solaires, 5M FCFA, énergie » (libellé synthétique défini par le tool)
  - `show_summary_card` → « ✓ Validé » ou « ✓ Corrigé : capital 6M (au lieu de 5M) »
- **FR-035** : Le payload structuré complet (valeur, devise, format, modifications, etc.) DOIT être conservé en métadonnée du message (champ `interactive_question_response` ou colonne extension de `messages`), accessible aux modules avals (audit, analytics).

#### Tests

- **FR-036** : Le système DOIT inclure des tests unitaires backend (pytest) pour chaque tool : validation Pydantic, persistance, marker SSE, gestion `pending → expired`, journalisation. Cible : ≥ 80 % de couverture sur `interactive_tools.py`.
- **FR-037** : Le système DOIT inclure un test backend dédié au pattern destructif : un tool `delete_project` (stub si nécessaire) refuse l'exécution sans `confirm=True`, retourne `{requires_confirmation: True}`, et le LLM (mocké) appelle `ask_yes_no(destructive=True)`.
- **FR-038** : Le système DOIT inclure des tests unitaires frontend (Vitest) pour chaque widget : rendu, validation des inputs, émission des events, dark mode, accessibilité.
- **FR-039** : Le système DOIT inclure un test E2E Playwright `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` couvrant les 5 scénarios critiques : (a) ask_yes_no destructif → suppression projet + audit_log, (b) ask_select recherche pays UEMOA, (c) ask_number CA avec XOF + équivalent EUR, (d) show_form création projet 8 champs, (e) show_summary_card édition inline + validation.
- **FR-040** : Le système DOIT inclure un test E2E de non-régression couvrant les 4 widgets QCU/QCM existants (F18), pour garantir l'absence de régression liée à l'extension de l'enum et du routing.

### Key Entities *(include if feature involves data)*

- **InteractiveQuestion** (existant, étendu) : représente une question interactive posée par le LLM. Attributs étendus :
  - `question_type` : enum élargi (4 valeurs existantes + 9 nouvelles).
  - `payload` : jsonb, paramètres spécifiques par variante (bornes, devise, fichiers acceptés, champs formulaire, items summary).
  - `response_payload` : jsonb, réponse structurée au-delà des simples `response_values`.
  - Relations conservées : `conversation`, `assistant_message`, `response_message`.
  - Cycle de vie conservé : `pending → answered | abandoned | expired`.

- **DestructiveActionLog** (concept logique, matérialisé via F03 audit_log) : trace de chaque appel à un tool destructif et de sa confirmation. Pas de nouvelle table : la table `audit_log` (F03) suffit, avec `action=delete_project`, `metadata.confirm=True/False`, `metadata.required_confirmation=True`.

- **WidgetPayloadByType** (concept structurel, schémas Pydantic) : un schéma par type de widget définit la forme du `payload` BDD :
  - `yes_no` : `{confirm_label, deny_label, destructive}`.
  - `select` : `{options: [{id, label, sublabel?, group?}], min_selections, max_selections, allow_other}`.
  - `number` : `{unit, min, max, step, currency, default}`.
  - `date` : `{min, max, default}`.
  - `date_range` : `{min, max}`.
  - `rating` : `{scale, labels}`.
  - `file_upload` : `{accept, max_size_mb, multi, doc_type_hint}`.
  - `form` : `{title, fields: [FormField], submit_label}` avec `FormField = {name, label, type, required, placeholder?, default?, validation?}`.
  - `summary_card` : `{title, items: [{label, value, editable}], confirm_label, correct_label}`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Aucune action destructive (suppression projet, candidature, attestation) n'est exécutable sans une étape de confirmation utilisateur explicite — vérifié sur 100 % des tools destructifs identifiés (delete_project, delete_application, revoke_attestation, cancel_assessment) avant et après F10.
- **SC-002** : Le temps moyen pour créer une entité (projet, bilan carbone, candidature) via une conversation passe d'au moins 8 tours (sans `show_form`) à au plus 2 tours (avec `show_form`), soit une réduction d'au moins 75 %, mesuré sur 5 conversations de test.
- **SC-003** : 95 % des sélections de valeurs structurées (pays, secteur, devise, date, fonds) sont effectuées via un widget structuré plutôt qu'en texte libre, mesuré sur 1 semaine de logs production après déploiement.
- **SC-004** : 0 régression sur les 4 widgets QCU/QCM existants (F18), validé par la suite de tests Playwright dédiée à la non-régression.
- **SC-005** : Couverture de tests ≥ 80 % sur les nouveaux fichiers backend (`interactive_tools.py`, schémas, models) et frontend (9 composants widgets, composables).
- **SC-006** : Temps de rendu d'un `ask_select` avec 200 options ≤ 200 ms (mesure Vitest + Playwright performance).
- **SC-007** : 100 % des widgets sont navigables au clavier seul (tab, entrée, échap) et passent l'audit Lighthouse a11y ≥ 95.
- **SC-008** : 100 % des widgets sont compatibles dark mode (vérifié visuellement + via screenshot tests Playwright).
- **SC-009** : 0 fuite des anciens types d'enum vers les nouveaux : la migration Alembic up/down/up est idempotente et ne perd aucune ligne existante (vérifié sur les 4 valeurs `qcu`, `qcm`, `qcu_justification`, `qcm_justification` après upgrade puis downgrade puis upgrade).
- **SC-010** : 100 % des nouveaux tools journalisent dans `tool_call_logs` avec succès, vérifié sur 9 cas (un par widget).
- **SC-011** : Un click instantané (< 200 ms) sur le bouton « Oui, supprimer » d'un widget destructif n'exécute jamais l'action ; l'action exige un hold ≥ 2 secondes (vérifié par test Playwright avec timing explicite).
- **SC-012** : 100 % des fichiers uploadés via `ask_file_upload` passent une validation MIME signature côté backend ; aucune extension `.pdf` portant un contenu non-PDF n'est jamais persisté en `documents` (vérifié par test backend dédié).

## Assumptions

- F02 (multi-tenant) est mergé : `account_id` disponible sur `interactive_questions` (déjà ajouté en migration F18 retro-portée). Les nouvelles questions héritent automatiquement du `account_id` de la conversation.
- F03 (audit_log) est mergé : la table `audit_log` est disponible et utilisée par les tools destructifs (delete_project, etc.). F10 ne crée pas la table mais s'appuie dessus pour FR-013 et SC-001.
- F04 (Money typed) est mergé : le composant `<MoneyDisplay>` et le type Pydantic `Money` sont disponibles pour `ask_number` et le champ `money` de `show_form`. Si F04 n'est pas encore livré au moment de l'implémentation, F10 retombe sur un input numérique simple avec sélecteur devise libre, à raccrocher en Phase B.
- F08 (financing) est mergé : `ask_file_upload` peut s'intégrer avec le pipeline document existant (F04 documents-upload-analysis). Le widget appelle l'API `POST /api/documents/upload` existante.
- F18 (interactive_questions initial) est mergé : la table `interactive_questions`, le tool `ask_interactive_question`, les composants `SingleChoiceWidget.vue` / `MultipleChoiceWidget.vue` / `JustificationField.vue` / `AnswerElsewhereButton.vue` existent et fonctionnent. F10 étend sans casser.
- Pas de versioning d'API REST (pas de `/v1/`, MVP).
- Devise par défaut XOF, multi-devise XOF/EUR/USD/CDF supportée (cohérent avec F04).
- Format dates en français (`15 mars 2026`), persistance ISO 8601 UTC.
- Le composant `vue-virtual-scroller` est disponible dans le projet ou sera ajouté au `package.json` lors de l'implémentation (à valider en Phase B). À défaut, fallback sur scroll natif jusqu'à 200 options sans virtualisation, l'écart de performance étant acceptable au-dessus de 50 mais sub-1s.
- Le projet utilise déjà zod (ou peut l'ajouter) pour la validation client de `show_form`. Si pas disponible, fallback sur validation manuelle dans le composable `useInteractiveQuestion.ts`.
- Aucun secret hardcodé : les bornes (max 200 options, max 10 champs, max 10 Mo upload) sont des constantes dans `interactive_tools.py`.
- Le pattern destructif est appliqué sur les tools existants ; si certains modules ne sont pas livrés (delete_project peut être un stub), F10 ajoute le pattern de manière à ce qu'au moment où le tool concret existe, il soit déjà conforme.
- Migration Alembic 031 : `down_revision=030_create_referential_scores`. Si une feature parallèle prend le numéro 031 avant la fusion, renuméroter en Phase B sans modifier le numéro de feuille SpecKit (031-widgets-bottom-sheet-complets reste).
- Disponibilité de `python-magic` (libmagic) sur l'environnement backend : ajouter à `backend/requirements.txt` si absent. Sur macOS : `brew install libmagic`, sur Linux : `apt install libmagic1` (Phase B verifications).
- Table `referential_fx_rates` (issue de F30 ou feature ultérieure) : si non livrée au moment de l'implémentation, F10 utilise uniquement les constantes statiques de fallback (XOF↔EUR=655.957 parité fixe, XOF↔USD≈600, XOF↔CDF≈2.86). L'introduction du référentiel reste rétro-compatible (l'API `GET /api/referential/fx-rates` retourne 404 ou un payload vide tant que la table n'existe pas).
- L'animation click-and-hold 2s utilise des CSS animations natives (Tailwind transitions + keyframes) et respecte `prefers-reduced-motion: reduce` en remplaçant l'animation par un compteur textuel « Maintenez 2 secondes... 2... 1... 0 » accessible.
