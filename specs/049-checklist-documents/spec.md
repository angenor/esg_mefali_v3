# Feature Specification: Fourniture des documents de la checklist d'un dossier de candidature (V1)

**Feature Branch**: `049-checklist-documents`
**Created**: 2026-06-03
**Status**: Draft
**Input**: User description: "Fourniture des documents de la checklist d'un dossier de candidature — V1 (depuis l'onglet Checklist)"

## Clarifications

### Session 2026-06-03

- Q: Où l'indicateur de progression de la checklist (M / N) doit-il apparaître ? → A: Dans l'onglet Checklist du dossier **et** sous forme d'indicateur compact (M / N) sur la liste / carte des dossiers.
- Q: Comment se comporter en cas de modifications concurrentes de la checklist (UI + chatbot, ou onglets multiples) ? → A: Mise à jour atomique par item — chaque rattachement / détachement ne modifie que l'item ciblé, sans écraser les modifications concurrentes sur d'autres items.
- Q: Un document téléversé depuis la checklist devient-il un document standard (visible sur /documents et sélectionnable ailleurs) ? → A: Oui — document standard de premier rang, visible sur /documents et sélectionnable pour d'autres items / dossiers, comme tout autre document.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Téléverser un fichier sur un item manquant (Priority: P1)

En tant que PME, sur un item « Manquant » de la checklist de mon dossier de financement, je téléverse un fichier depuis ma machine ; l'item passe immédiatement à « Fourni » et affiche le nom du fichier fourni. Le téléversement réutilise le flux d'upload existant (validations de type et de taille, analyse IA automatique), sans me demander la nature du fichier : c'est la ligne de checklist sur laquelle j'agis qui détermine à quel document requis le fichier correspond.

**Why this priority**: C'est le cœur de la valeur. Aujourd'hui la checklist est en lecture seule et chaque item reste « Manquant » sans recours possible. Permettre de fournir un fichier transforme la checklist d'un simple affichage en outil de préparation de dossier. À elle seule, cette story constitue un MVP viable : une PME peut compléter sa checklist et voir sa progression.

**Independent Test**: Ouvrir un dossier ayant au moins un item « Manquant », téléverser un fichier valide sur cet item, et vérifier que l'item bascule en « Fourni » avec le nom du fichier affiché, et que le document est consultable.

**Acceptance Scenarios**:

1. **Given** un dossier avec un item de checklist au statut « Manquant », **When** la PME téléverse un fichier de type et de taille valides sur cet item, **Then** un document est créé/rattaché à l'item, l'item passe à « Fourni » et affiche le nom du fichier.
2. **Given** un item « Manquant », **When** la PME tente de téléverser un fichier de type non supporté ou trop volumineux, **Then** un message d'erreur clair s'affiche, aucun document n'est rattaché et l'item reste « Manquant ».
3. **Given** un item passé à « Fourni » par téléversement, **When** la fiche de préparation ou le chatbot lit l'état de la checklist, **Then** ils voient l'item comme « Fourni » (même état, sans état parallèle).

---

### User Story 2 - Rattacher un document déjà téléversé (Priority: P2)

En tant que PME, sur un item « Manquant », je peux rattacher un document que j'ai déjà téléversé ailleurs (depuis le chatbot ou la page /documents), via un sélecteur qui liste mes documents existants. Après sélection, l'item passe à « Fourni ».

**Why this priority**: Évite de retéléverser des fichiers déjà présents dans la plateforme et favorise la réutilisation. Vient juste après le téléversement direct, car il s'appuie sur le même résultat (un document rattaché à un item) en partant d'un document existant.

**Independent Test**: Disposer d'au moins un document déjà téléversé sur le compte, ouvrir le sélecteur depuis un item « Manquant », choisir ce document, et vérifier que l'item devient « Fourni » et pointe vers le document choisi.

**Acceptance Scenarios**:

1. **Given** un item « Manquant » et au moins un document existant sur le compte, **When** la PME ouvre le sélecteur et choisit un document, **Then** ce document est rattaché à l'item et l'item passe à « Fourni ».
2. **Given** un document appartenant à un autre compte, **When** une tentative de rattachement de ce document est effectuée, **Then** l'opération est refusée et l'item reste inchangé.
3. **Given** un compte sans aucun document existant, **When** la PME ouvre le sélecteur, **Then** le sélecteur indique qu'aucun document n'est disponible et propose le téléversement.

---

### User Story 3 - Prévisualiser le document rattaché (Priority: P3)

En tant que PME, sur un item « Fourni », je peux ouvrir / prévisualiser le document rattaché sans quitter la page du dossier, en réutilisant l'aperçu de documents existant.

**Why this priority**: Permet de vérifier qu'on a fourni le bon fichier. Utile mais secondaire : la valeur principale (fournir et voir la progression) est déjà délivrée par P1/P2.

**Independent Test**: Sur un item « Fourni », déclencher l'aperçu et vérifier que le document rattaché s'affiche correctement.

**Acceptance Scenarios**:

1. **Given** un item « Fourni » avec un document rattaché, **When** la PME déclenche l'aperçu, **Then** le document s'ouvre / se prévisualise via le mécanisme d'aperçu existant, sans navigation hors de la page du dossier.

---

### User Story 4 - Détacher ou remplacer le document (Priority: P3)

En tant que PME, sur un item « Fourni », je peux détacher le document (l'item repasse à « Manquant ») ou le remplacer par un autre (téléversé ou sélectionné).

**Why this priority**: Corrige les erreurs de rattachement et permet la mise à jour d'un document. Complète le cycle de vie de l'item mais n'est pas indispensable au premier jet de valeur.

**Independent Test**: Sur un item « Fourni », détacher le document et vérifier le retour à « Manquant » ; puis rattacher un autre document et vérifier la mise à jour.

**Acceptance Scenarios**:

1. **Given** un item « Fourni », **When** la PME détache le document, **Then** l'item repasse à « Manquant » et n'affiche plus de fichier.
2. **Given** un item « Fourni », **When** la PME remplace le document par un autre (upload ou sélection), **Then** l'item reste « Fourni » mais pointe désormais vers le nouveau document.
3. **Given** un détachement effectué, **When** la PME (ou un administrateur) consulte l'historique d'audit du dossier, **Then** l'opération de détachement y figure.

---

### User Story 5 - Visualiser la progression de la checklist (Priority: P4)

En tant que PME, je vois la progression globale de ma checklist (nombre d'items fournis sur le total) pour chaque dossier : dans l'onglet Checklist du dossier ouvert, et sous forme d'indicateur compact (M / N) sur la liste / carte des dossiers.

**Why this priority**: Donne une vue d'ensemble de la complétude du dossier. Valeur réelle mais dérivée : la progression se calcule à partir des statuts produits par P1-P4.

**Independent Test**: Sur un dossier comportant N items dont M fournis, vérifier que l'indicateur affiche « M / N » et qu'il se met à jour après chaque rattachement / détachement.

**Acceptance Scenarios**:

1. **Given** un dossier avec N items de checklist dont M au statut « Fourni », **When** la PME ouvre l'onglet Checklist, **Then** l'indicateur de progression affiche le nombre d'items fournis sur le total (M / N).
2. **Given** un indicateur affichant M / N, **When** un item passe de « Manquant » à « Fourni » (ou l'inverse), **Then** l'indicateur se met à jour en conséquence.

---

### Edge Cases

- **Fichier non supporté ou trop volumineux** : message d'erreur clair (réutilisant les validations existantes), aucun rattachement, item inchangé.
- **Document rattaché puis supprimé depuis /documents** : l'item ne casse pas ; il repasse à « Manquant » (le statut étant dérivé de la présence d'un document valide rattaché).
- **Remplacement d'un document déjà fourni** : l'ancien rattachement est remplacé par le nouveau ; le document remplacé reste disponible ailleurs (il n'est pas supprimé).
- **Item dont la `key` n'existe pas, ou dossier inexistant** : erreur propre (l'opération échoue sans modifier d'état), message explicite.
- **Dossier sans aucun document requis** : la checklist affiche « Aucun document requis » au lieu d'une liste vide.
- **Document d'un autre compte** : toute tentative de rattachement d'un document n'appartenant pas au compte du dossier est refusée.
- **Même document réutilisé** : un document peut être rattaché simultanément à plusieurs items et/ou plusieurs dossiers, sans duplication du fichier.
- **Modifications concurrentes** : si deux actions modifient la checklist d'un même dossier presque simultanément (UI + chatbot, ou onglets multiples), chaque action n'affecte que son item ciblé ; une action sur un item n'écrase pas une action concurrente portant sur un autre item.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST permettre à une PME de téléverser un fichier directement depuis un item « Manquant » de la checklist, en réutilisant le flux d'upload de documents existant (validations de type et de taille, analyse IA).
- **FR-002**: À l'issue d'un téléversement réussi depuis un item, le système MUST rattacher le document obtenu à cet item précis ; la ligne de checklist détermine le document requis correspondant, sans saisie de nature par l'utilisateur.
- **FR-002a**: Un document téléversé depuis la checklist MUST être un document standard de premier rang : visible sur la page /documents et sélectionnable dans le sélecteur « rattacher un existant » pour d'autres items / dossiers, au même titre que tout autre document du compte.
- **FR-003**: Le système MUST permettre à une PME de rattacher à un item « Manquant » un document déjà existant sur son compte, via un sélecteur listant ses documents.
- **FR-004**: Le système MUST afficher le nom du fichier rattaché sur un item « Fourni ».
- **FR-005**: Le système MUST permettre à une PME d'ouvrir / prévisualiser le document rattaché à un item « Fourni », en réutilisant l'aperçu de documents existant.
- **FR-006**: Le système MUST permettre à une PME de détacher le document d'un item « Fourni », ce qui ramène l'item à « Manquant ».
- **FR-007**: Le système MUST permettre à une PME de remplacer le document rattaché à un item « Fourni » par un autre (téléversé ou sélectionné).
- **FR-008**: Le système MUST afficher la progression globale de la checklist (nombre d'items fournis sur le total) à deux endroits : (a) dans l'onglet Checklist du dossier ouvert, et (b) sous forme d'indicateur compact (M / N) sur la liste / carte des dossiers.
- **FR-009**: Le système MUST dériver le statut de chaque item de la présence d'un document valide rattaché : « Fourni » ⇔ un document est rattaché ; « Manquant » ⇔ aucun document.
- **FR-010**: Le système MUST refuser de rattacher à un dossier un document n'appartenant pas au même compte (`account_id`) que le dossier.
- **FR-011**: Le système MUST autoriser qu'un même document soit rattaché à plusieurs items et/ou plusieurs dossiers (réutilisable, sans duplication du fichier).
- **FR-012**: Le système MUST conserver les items de checklist et leur ordre tels que définis par le type de destinataire du dossier (fund_direct, intermediary_bank, etc.) ; la V1 MUST NOT créer d'items personnalisés ni modifier la liste des documents requis.
- **FR-013**: Le système MUST tracer dans l'audit toute modification de la checklist (rattachement, détachement, remplacement), le dossier étant déjà auditable.
- **FR-014**: Lorsqu'un document rattaché est supprimé depuis la gestion documentaire, le système MUST faire repasser l'item concerné à « Manquant » sans erreur ni état incohérent.
- **FR-015**: Le système MUST rejeter tout téléversement de fichier de type non supporté ou de taille excessive avec un message d'erreur clair, sans effectuer de rattachement (validations existantes réutilisées).
- **FR-016**: Le système MUST renvoyer une erreur propre lorsqu'une opération cible une `key` d'item inexistante ou un dossier inexistant, sans modifier d'état.
- **FR-017**: Lorsqu'un dossier n'a aucun document requis, le système MUST afficher « Aucun document requis ».
- **FR-018**: Le système MUST réserver la modification de la checklist d'un dossier à la PME propriétaire (même compte que le dossier).
- **FR-019**: L'état « Fourni » produit par cette fonctionnalité MUST être le même état déjà consommé par la fiche de préparation et le chatbot (aucun état parallèle).
- **FR-020**: Tous les nouveaux écrans / composants MUST être en français (avec accents obligatoires) et MUST supporter le dark mode, en réutilisant les composants UI existants (upload, liste, aperçu de documents) plutôt qu'en en recréant.
- **FR-021**: Chaque rattachement, détachement ou remplacement MUST s'appliquer de façon atomique au seul item ciblé (identifié par sa `key`), sans réécrire ni écraser l'état des autres items ; deux modifications concurrentes portant sur des items distincts du même dossier ne MUST PAS se perdre mutuellement.

### Key Entities *(include if feature involves data)*

- **Dossier de candidature** : représente la candidature d'une PME à un financement. Appartient à un compte (`account_id`). Porte une checklist : une liste ordonnée d'items de documents requis, dont la composition et l'ordre dépendent du type de destinataire (fund_direct, intermediary_bank, etc.). Déjà auditable.
- **Item de checklist** : un document requis au sein d'un dossier, identifié par une `key` stable, avec un libellé (`name`), un statut dérivé (« Manquant » / « Fourni »), une référence optionnelle vers le document rattaché (`document_id`), et l'origine de l'exigence (`required_by`). Non modifiable en V1 (ni ajout, ni suppression d'item).
- **Document** : fichier téléversé appartenant à un utilisateur et à un compte (`account_id`), avec une nature devinée automatiquement (`document_type`), un statut, et éventuellement une conversation d'origine. Partagé entre la page /documents et le chatbot. Réutilisable : rattachable à plusieurs items et/ou dossiers. Sa nature devinée n'impose aucune contrainte sur l'item auquel il est rattaché (la ligne de checklist fait foi).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Une PME peut faire passer un item de « Manquant » à « Fourni » (par téléversement) en moins d'une minute, sans quitter l'onglet Checklist.
- **SC-002**: 100 % des items ayant un document valide rattaché s'affichent « Fourni », et 100 % des items sans document s'affichent « Manquant » (statut toujours cohérent avec la présence d'un document).
- **SC-003**: Aucun document appartenant à un autre compte ne peut être rattaché à un dossier (0 rattachement inter-comptes possible).
- **SC-004**: L'indicateur de progression reflète à tout moment le nombre exact d'items fournis sur le total, y compris après chaque rattachement ou détachement (aucune dérive).
- **SC-005**: La suppression d'un document rattaché ne laisse jamais la checklist dans un état cassé : l'item concerné repasse à « Manquant » dans 100 % des cas.
- **SC-006**: Chaque rattachement, détachement ou remplacement est retrouvable dans l'historique d'audit du dossier.
- **SC-007**: Une PME peut prévisualiser n'importe quel document fourni directement depuis l'onglet Checklist, sans naviguer hors de la page du dossier.

## Assumptions

- Les endpoints et composants existants de gestion documentaire (upload, liste, aperçu) sont réutilisés tels quels ; cette fonctionnalité n'introduit aucune nouvelle règle de validation de type / taille.
- La nature attendue d'un item est déterminée uniquement par la ligne de checklist sur laquelle la PME agit, et non par la nature auto-devinée (`document_type`) du document : aucune validation de correspondance entre `document_type` et l'item n'est effectuée en V1.
- Lorsqu'un document rattaché est supprimé, l'item repasse silencieusement à « Manquant » (choix retenu pour la V1, plutôt qu'un badge « lien rompu » distinct, par cohérence avec la règle « statut dérivé de la présence d'un document » et pour la simplicité).
- La structure de la checklist (items et ordre) par type de destinataire existe déjà et n'est pas modifiée par cette fonctionnalité.
- L'isolation multi-tenant s'appuie sur le mécanisme `account_id` existant et ses garanties (RLS).
- Le rôle concerné est la PME propriétaire du dossier ; les parcours administrateurs sont hors périmètre fonctionnel (au-delà de la consultation d'audit déjà existante).
- Le pattern de mise à jour du champ checklist (JSON) déjà établi par la modification de section sert de base, sans imposer la conception technique.

### Hors périmètre (V1 — prévu en V2)

- Le sens inverse « Rattacher à un dossier / item » initié DEPUIS la page /documents (nécessiterait de lister les dossiers et leurs items côté API).
- La classification IA automatique qui pré-cocherait les items (suggestion). Aucune nouvelle saisie de nature n'est demandée au moment de l'upload.
- La modification de la liste des documents requis par dossier (ajout / suppression / réordonnancement d'items).
