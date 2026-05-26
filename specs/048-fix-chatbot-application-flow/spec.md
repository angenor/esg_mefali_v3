# Feature Specification: Fiabiliser la création de dossier de candidature et la mémoire ESG du chatbot

**Feature Branch**: `048-fix-chatbot-application-flow`
**Created**: 2026-05-25
**Status**: Draft
**Input**: User description: deux problèmes constatés en usage réel du chatbot — (1) des critères ESG remplis dans une session n'apparaissent plus (signalés « manquants ») dans une session ultérieure ; (2) le chatbot répond qu'il n'a « pas accès à l'outil de création de dossier de candidature », et le bouton « Candidater » sur `/financing/[id]` ne produit aucun effet.

## Contexte

L'objectif central de la plateforme est de permettre à l'utilisateur de **tout faire via le chatbot** : profilage, évaluation ESG, simulation de financement et création du dossier de candidature. Deux ruptures cassent aujourd'hui ce parcours pour une PME qui veut candidater à une offre de financement vert (ex. « GCF via BOAD » pour le projet « Solarisation Boulangerie Dakar ») :

1. Le travail ESG déjà réalisé n'est pas reconnu d'une session à l'autre, obligeant l'utilisateur à recommencer ou à douter de la fiabilité de la plateforme.
2. Le dossier de candidature ne peut être créé ni par le chatbot ni par l'interface, bloquant la dernière étape du parcours de financement.

## Clarifications

### Session 2026-05-25

- Q: Que produit « générer un dossier de candidature » ? → A: Créer le dossier **et** générer immédiatement le document de candidature téléchargeable, en une seule action.
- Q: Comment le chatbot retrouve-t-il l'évaluation ESG existante entre sessions ? → A: Hybride — résumé léger des évaluations existantes chargé proactivement au démarrage de session + outil de lecture détaillée des réponses par critère, appelé à la demande.
- Q: Comment l'outil de création de dossier devient-il disponible depuis n'importe quel contexte ? → A: Déclenché par l'intention — l'outil est exposé dès qu'une intention de candidature/création de dossier est détectée, indépendamment de la page d'origine.
- Q: Que faire si l'évaluation ESG est incomplète au moment de générer le dossier ? → A: Bloquer la génération tant que les critères requis ne sont pas complétés ; le chatbot guide d'abord l'utilisateur vers les critères manquants.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Créer un dossier de candidature via le chatbot, quel que soit le contexte (Priority: P1)

Une PME demande au chatbot, en langage naturel, de générer un dossier de candidature pour une offre de financement identifiée. Le chatbot doit aboutir à la création effective d'un dossier (statut brouillon) rattaché au bon projet et à la bonne offre, puis confirmer où le retrouver — sans jamais répondre que l'outil nécessaire est indisponible.

**Why this priority**: C'est la promesse fondatrice du produit (« tout via le chatbot ») et l'étape finale qui transforme l'accompagnement en action concrète. Sans elle, tout le parcours amont (profil, ESG, simulation) reste sans débouché.

**Independent Test**: Depuis une conversation démarrée sur n'importe quelle page de l'application (y compris `/documents`, `/dashboard`, `/chat`), demander « génère-moi un dossier de candidature pour [offre] » et vérifier qu'un dossier en statut brouillon est créé et accessible, sans message d'outil indisponible.

**Acceptance Scenarios**:

1. **Given** une PME avec un projet actif et une offre de financement identifiée, **When** elle demande au chatbot de générer un dossier de candidature, **Then** un dossier est créé en statut brouillon, rattaché au projet et à l'offre, son document de candidature est généré et téléchargeable, et le chatbot indique clairement où le consulter.
2. **Given** une conversation démarrée depuis une page qui n'est pas la page Financement (ex. `/documents`), **When** l'utilisateur demande la création d'un dossier, **Then** le chatbot crée bien le dossier au lieu de répondre que l'outil n'est pas disponible.
3. **Given** une PME sans projet actif rattaché, **When** elle demande un dossier de candidature, **Then** le chatbot guide l'utilisateur pour confirmer ou créer le projet cible avant de produire le dossier (pas d'échec silencieux).
4. **Given** une offre ambiguë (le nom saisi ne correspond pas exactement à une offre en base, ex. « BOAD – Fonds Vert » vs « GCF via BOAD »), **When** l'utilisateur fait sa demande, **Then** le chatbot confirme l'offre retenue avant de créer le dossier.
5. **Given** une évaluation ESG incomplète pour l'offre visée (critères requis manquants), **When** l'utilisateur demande la génération du dossier, **Then** le chatbot ne génère pas le document et guide d'abord l'utilisateur vers les critères manquants à compléter.

---

### User Story 2 - Retrouver le travail ESG d'une session à l'autre (Priority: P1)

Une PME ayant renseigné des critères ESG (ex. BOAD ESS 1 et ESS 2) lors d'une session précédente revient plus tard. Le chatbot doit reconnaître l'évaluation existante et les réponses déjà saisies, refléter le score et l'avancement réels, et ne pas présenter comme « manquants » des critères déjà remplis.

**Why this priority**: La perte apparente de données détruit la confiance et provoque du double travail. C'est aussi un prérequis qualité du dossier de candidature (combler les critères manquants suppose de connaître ceux déjà couverts).

**Independent Test**: Dans une session A, renseigner plusieurs critères d'une évaluation ESG d'un projet pour un référentiel donné, puis dans une session B distincte, demander « où en est mon évaluation ESG du projet X » et vérifier que les critères saisis en session A sont reconnus comme couverts (et non manquants).

**Acceptance Scenarios**:

1. **Given** des critères ESG saisis et enregistrés en session A pour un projet et un référentiel, **When** l'utilisateur reprend en session B, **Then** le chatbot retrouve l'évaluation et présente ces critères comme couverts.
2. **Given** une évaluation ESG existante pour un projet, **When** l'utilisateur demande l'état d'avancement sans fournir d'identifiant technique, **Then** le chatbot localise l'évaluation à partir du nom du projet et/ou du référentiel.
3. **Given** une liste de critères manquants présentée par le chatbot, **When** l'utilisateur affirme avoir déjà rempli certains d'entre eux, **Then** le chatbot vérifie l'état réel enregistré plutôt que de réaffirmer qu'ils manquent.
4. **Given** plusieurs évaluations pour un même projet (référentiels différents), **When** l'utilisateur reprend, **Then** le chatbot distingue les évaluations par référentiel et n'agrège pas à tort les critères.

---

### User Story 3 - Candidater depuis l'interface Financement (Priority: P2)

Une PME consultant le détail d'une offre de financement clique sur « Candidater ». Un dossier en statut brouillon doit être créé et l'utilisateur dirigé vers ce dossier (ou informé de sa disponibilité), avec retour visible en cas d'impossibilité.

**Why this priority**: Voie alternative au chatbot pour la même action ; importante pour les utilisateurs qui passent par l'UI, mais redondante avec US1 pour le MVP du parcours conversationnel.

**Independent Test**: Sur la page de détail d'une offre, cliquer sur « Candidater » et vérifier qu'un dossier brouillon est créé et accessible, sans page d'erreur ni absence de réaction.

**Acceptance Scenarios**:

1. **Given** une PME sur le détail d'une offre avec un projet cible, **When** elle clique sur « Candidater », **Then** un dossier brouillon est créé et l'utilisateur est conduit vers ce dossier ou informé de sa disponibilité.
2. **Given** un contexte incomplet (pas de projet sélectionné), **When** l'utilisateur clique sur « Candidater », **Then** un message clair invite à choisir/confirmer le projet, sans clic sans effet ni erreur muette.
3. **Given** une erreur côté traitement, **When** la création échoue, **Then** un message d'erreur compréhensible s'affiche.

---

### Edge Cases

- L'utilisateur désigne une offre par un nom approximatif ou un alias : le chatbot doit lever l'ambiguïté avant d'agir.
- Un dossier brouillon existe déjà pour le même couple projet/offre : le système doit éviter les doublons (reprendre l'existant plutôt que créer un second dossier).
- L'évaluation ESG concerne un projet, mais une ancienne évaluation au niveau entreprise existe aussi : le chatbot doit éviter de confondre les deux périmètres.
- L'utilisateur n'a aucun projet : la demande de dossier doit déclencher un guidage, pas un échec.
- L'offre ou le projet a évolué (versioning) depuis la dernière session : l'état présenté doit rester cohérent.
- Conversation démarrée hors de toute page « métier » connue : la création de dossier doit rester possible.

## Requirements *(mandatory)*

### Functional Requirements

**Création de dossier via le chatbot (US1)**

- **FR-001**: Le chatbot DOIT pouvoir créer un dossier de candidature à la demande de l'utilisateur, quelle que soit la page depuis laquelle la conversation est menée.
- **FR-001a**: L'outil de création de dossier DOIT être exposé dès que le chatbot détecte une intention de candidature/création de dossier, indépendamment de la page d'origine de la conversation (et non restreint aux seules pages Financement/Candidatures).
- **FR-002**: Le chatbot NE DOIT JAMAIS répondre que l'outil de création de dossier est indisponible lorsque l'utilisateur demande explicitement la création d'un dossier.
- **FR-003**: Le dossier créé DOIT être rattaché au projet cible et à l'offre confirmée, et être créé en statut brouillon.
- **FR-003a**: À la suite de la création du dossier, le chatbot DOIT générer immédiatement, dans la même action, le document de candidature téléchargeable, sans étape de confirmation intermédiaire. Le document est produit à partir des sections disponibles du dossier ; si les sections clés sont absentes, le chatbot DOIT au minimum les générer avant l'export afin que le document ne soit pas vide.
- **FR-003b**: Le système DOIT bloquer la génération du dossier/document tant que les critères ESG requis de l'offre ne sont pas complétés. Dans ce cas, le chatbot NE DOIT PAS produire de document mais guider d'abord l'utilisateur vers les critères manquants à compléter.
- **FR-004**: Le chatbot DOIT confirmer à l'utilisateur la création et indiquer où retrouver le dossier et son document généré (espace documents/candidatures).
- **FR-005**: En cas d'offre ambiguë ou de projet non déterminé, le chatbot DOIT solliciter une confirmation avant de créer le dossier, plutôt qu'échouer ou agir sur une hypothèse erronée.
- **FR-006**: Le système DOIT éviter la création de doublons pour un même couple projet/offre (reprise du brouillon existant).

**Mémoire et récupération ESG (US2)**

- **FR-007**: Les réponses aux critères ESG saisies dans une session DOIVENT rester persistées et associées à l'évaluation, au projet et au référentiel concernés.
- **FR-008**: Le chatbot DOIT pouvoir retrouver une évaluation ESG existante d'un utilisateur dans une nouvelle session, à partir du nom du projet et/ou du référentiel, sans que l'utilisateur fournisse un identifiant technique.
- **FR-008a**: Au démarrage de session, le système DOIT charger proactivement un résumé léger des évaluations ESG existantes de l'utilisateur (projet, référentiel, score, taux de couverture) afin que le chatbot en ait connaissance sans sollicitation préalable.
- **FR-008b**: Le chatbot DOIT disposer d'un moyen de lecture détaillée, à la demande, des réponses par critère d'une évaluation existante (pour vérifier l'état couvert/manquant sans charger systématiquement tout le détail dans le contexte).
- **FR-009**: Lorsqu'une évaluation existe, le chatbot DOIT présenter comme « couverts » les critères effectivement enregistrés et ne présenter comme « manquants » que les critères réellement non renseignés.
- **FR-010**: Le score et le taux de couverture présentés DOIVENT refléter l'état réel enregistré des réponses aux critères.
- **FR-011**: Le chatbot DOIT distinguer les évaluations par référentiel pour un même projet et ne pas mélanger leurs critères.
- **FR-012**: Lorsque l'utilisateur conteste l'état « manquant » d'un critère, le chatbot DOIT vérifier l'état enregistré avant de répondre.

**Candidature via l'interface (US3)**

- **FR-013**: Le bouton « Candidater » sur le détail d'une offre DOIT aboutir à la création d'un dossier brouillon (et non à une page inexistante ou à une absence de réaction).
- **FR-014**: Après création via l'interface, l'utilisateur DOIT être conduit vers le dossier ou informé de sa disponibilité.
- **FR-015**: En cas de contexte incomplet ou d'échec, l'interface DOIT afficher un message explicite plutôt qu'un clic sans effet.

**Transverses**

- **FR-016**: Les deux voies (chatbot et interface) DOIVENT produire un dossier équivalent et cohérent (même rattachement projet/offre, même statut initial).
- **FR-017**: Les actions de création de dossier et de mise à jour ESG DOIVENT rester traçables conformément aux exigences d'audit existantes de la plateforme.

### Key Entities *(include if feature involves data)*

- **Dossier de candidature**: Représente la candidature d'une PME à une offre de financement ; rattaché à un projet et à une offre ; possède un statut (au minimum brouillon) ; consultable par l'utilisateur.
- **Évaluation ESG de projet**: Évaluation d'un projet selon un référentiel donné ; agrège les réponses aux critères, un score et un taux de couverture ; persiste entre les sessions.
- **Réponse à un critère ESG**: Réponse individuelle à un critère d'un référentiel au sein d'une évaluation ; détermine si le critère est couvert ou manquant.
- **Offre de financement**: Combinaison fonds × intermédiaire à laquelle une PME peut candidater ; identifiable par un nom pouvant différer des termes employés par l'utilisateur.
- **Projet**: Projet vert de la PME servant de cible à l'évaluation ESG et à la candidature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des demandes explicites de création de dossier adressées au chatbot aboutissent à un dossier créé, sans message d'outil indisponible, quelle que soit la page d'origine de la conversation.
- **SC-002**: 0 cas où un critère ESG enregistré dans une session précédente est présenté comme « manquant » dans une session ultérieure pour le même projet et référentiel.
- **SC-003**: Le chatbot retrouve une évaluation ESG existante à partir du nom de projet/référentiel dans au moins 95 % des reprises de session, sans que l'utilisateur fournisse d'identifiant technique.
- **SC-004**: 100 % des clics sur « Candidater » aboutissent soit à un dossier créé, soit à un message d'erreur/guidage explicite — 0 clic sans effet.
- **SC-005**: Un utilisateur peut mener le parcours « offre identifiée → dossier de candidature créé » entièrement via le chatbot en moins de 3 échanges après confirmation du projet et de l'offre. *(Vérifié via le scénario 1 de quickstart.md en comptant les tours d'échange.)*
- **SC-006**: Aucun dossier en doublon n'est créé pour un même couple projet/offre lors de demandes répétées.

## Assumptions

- L'évaluation ESG concernée est l'évaluation **au niveau projet** (par projet et référentiel), conforme au parcours décrit (« Solarisation Boulangerie Dakar » évalué selon « BOAD ESS »), et non l'ancienne évaluation au niveau entreprise.
- Conformément à l'objectif produit « tout via le chatbot », l'outil de création de dossier doit être **mobilisable depuis n'importe quel contexte conversationnel**, et non restreint aux seules pages Financement/Candidatures.
- Le statut initial attendu d'un dossier créé est « brouillon », modifiable et soumis ultérieurement par l'utilisateur.
- Les entités existantes (projets, offres, référentiels, critères, évaluations ESG de projet, dossiers de candidature) sont réutilisées ; cette feature corrige la persistance/récupération et l'accessibilité des actions, sans introduire de nouveau type d'entité métier.
- La récupération ESG entre sessions s'appuie sur le compte/utilisateur authentifié et respecte le cloisonnement multi-tenant existant.
- L'espace de consultation des dossiers (« documents »/« candidatures ») existe déjà et sert de point de retrait du dossier créé.
