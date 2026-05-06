# Feature Specification: Fondations Sourçage et Catalogue Source

**Feature Branch**: `feat/F01-fondations-sourcage-catalogue`
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description : « F01 — Fondations Sourçage et Catalogue Source. Sourçage obligatoire de toute affirmation factuelle (chiffres, scores, critères, formules, seuils, facteurs d'émission). Workflow 4-yeux pour validation Source. Tools cite_source / search_source / flag_unsourced exposés à l'agent IA. Validator backend qui rejette les chiffres sans citation. Composants UI (picto SourceLink, modal détail, badge statut). Annexe auto-générée dans rapports PDF. Migration des facteurs d'émission, des 30 critères ESG, des pondérations sectorielles et des constantes du simulateur financier vers des tables sourcées. »

## Contexte produit

L'application ESG Mefali revendique aujourd'hui une promesse marketing forte : « chaque chiffre cliquable vers sa source officielle ». Cette promesse est techniquement non tenue puisque les facteurs d'émission carbone, les 30 critères ESG, les pondérations sectorielles, les benchmarks et les constantes du simulateur financier sont des valeurs codées en dur, sans aucun lien vers un document officiel vérifiable. Pour un fund officer, un auditeur ou une PME exposée à un dossier d'investissement, une affirmation non sourcée n'a aucune valeur défendable. F01 est la fondation qui transforme la plateforme en outil traçable et auditable, et conditionne la crédibilité de toutes les autres features.

## Clarifications

> **Mode autonomie totale** — l'utilisateur est absent. Pour chaque question, le choix « recommandé » a été appliqué selon les invariants ESG Mefali et la stack imposée (cf. `.cc-orchestrator.md`). Chaque décision est tracée ci-dessous avec son rationale.

### Session 2026-05-06

- **Q : À quelle granularité une citation de source couvre-t-elle un chiffre détecté dans le texte de l'agent ? Une seule citation pour tout le tour, ou une citation par chiffre détecté ?**
  → **A : Une citation par grappe « chiffre + unité contigüe », rattachée par proximité textuelle (la même citation peut couvrir plusieurs grappes consécutives séparées de moins de 200 caractères dans la même phrase ou paragraphe).** *Rationale* : choix le plus simple et le plus testable (1 cas pour la rédaction nominale = 1 citation par paragraphe ; 1 cas pour les listes = 1 citation par item). Respecte la promesse « chaque chiffre cliquable » sans imposer la lourdeur d'une citation à chaque occurrence (les agrégats type « 30 critères répartis 10/10/10 » seraient sinon ingérables). Garde-fou explicite dans FR-014 modifié ci-dessous : si deux chiffres dans la même grappe relèvent de sources différentes, l'agent doit produire deux citations distinctes.

- **Q : Quelle est la stratégie de retry lorsque la couche de validation rejette une réponse de l'agent IA — combien d'itérations, et quel est le mode de repli ?**
  → **A : Une seule tentative de correction est demandée à l'agent. En cas d'échec, le système substitue automatiquement le ou les chiffres litigieux par un libellé de repli neutre (« je ne dispose pas d'une source vérifiée pour ce chiffre ») et journalise l'incident pour revue administrateur.** *Rationale* : valeur recommandée déjà présente dans le cahier des charges F01 (FR-015 / FR-016). Une seule itération limite le coût LLM, le temps de réponse perçu, et évite les boucles infinies. Le repli textuel reste cohérent avec la promesse de transparence (l'utilisateur voit l'absence de source plutôt qu'un chiffre inventé).

- **Q : Comment gère-t-on l'identité du « propriétaire » d'une Source en attendant la feature multi-locataire F02 ?**
  → **A : Champ provisoire `created_by_user_id` (FK `users.id`, NOT NULL) sur la table `sources` et sur les autres tables du catalogue ; un commentaire `# TODO(F02): account_id` sera attaché aux modèles SQLAlchemy correspondants pour faciliter la migration ultérieure vers `account_id`.** *Rationale* : invariant ESG Mefali #2 (multi-tenant strict introduit par F02). Cette approche minimise le couplage et respecte la convention déjà en vigueur dans les modules existants (cf. ownership des `companies`, `documents`, `esg_assessments`). La migration F02 ajoutera la colonne `account_id`, backfillera depuis `users.account_id`, puis la rendra NOT NULL.

- **Q : Quel est le comportement attendu de la couche de validation sur les motifs « techniques » ressemblant à des chiffres mais qui n'en sont pas (par exemple « ISO 14001 », « 802.1Q », « article 4.2 ») ?**
  → **A : Une liste de motifs « ignorés » paramétrable côté backend, partagée entre développement et production via une constante (`IGNORED_NUMERIC_PATTERNS`), initialisée avec les standards ISO les plus courants (ISO 9001, 14001, 14064, 14067, 26000, 27001, 50001), les références règlementaires (« article N.M »), et les identifiants techniques (« 802.1Q », « PCI-DSS 4.0 »). La liste est étendue itérativement à la lumière du jeu d'évaluation interne de 50 réponses annotées.** *Rationale* : déjà mentionné dans FR-017 mais clarifié ici pour fixer l'attente sur la testabilité. Choix simple (liste maintenue en code, pas de table dédiée en F01) cohérent avec l'objectif ≤ 5 % d'erreur sur le golden set (FR-018).

- **Q : Quelle action utilise l'agent IA pour réagir à une source devenue obsolète au moment où il s'apprête à la citer ?**
  → **A : Le tool `cite_source` rejette toute source dont le `verification_status` n'est pas `verified` ; l'agent reçoit une erreur structurée et doit invoquer `search_source` pour trouver une alternative ou `flag_unsourced` s'il n'en trouve pas. Le passage en `outdated` ne révoque pas rétroactivement les citations déjà faites dans des messages historiques (les anciennes réponses restent visibles avec un badge « obsolète » côté UI, mais ne sont pas re-générées).** *Rationale* : préserve l'historique conversationnel sans modifier les messages persistés (cohérent avec l'architecture LangGraph existante où les messages sont immuables). Force l'agent à reconstituer une citation valide pour ses nouvelles réponses, ce qui maintient l'invariant de sourçage. Affiche honnêtement l'obsolescence côté UI plutôt que de masquer la dérive temporelle des sources.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cliquer sur un chiffre affiché et voir sa source officielle (Priorité : P1)

Lorsque l'utilisateur PME consulte un score ESG, un facteur d'émission, un seuil d'éligibilité ou une recommandation, un picto « source » est affiché à côté de chaque valeur factuelle. En cliquant sur le picto, une fenêtre de détail s'ouvre et affiche la source utilisée : titre du document, organisme émetteur (publisher), version, date de publication, page et section, statut de vérification, et un bouton qui ouvre le document officiel dans un nouvel onglet.

**Pourquoi cette priorité** : c'est l'expression visible de la promesse produit. Sans cette story, il n'y a aucun moyen pour la PME ou un tiers de défendre les chiffres affichés. C'est la story la plus visible et la plus différenciante du MVP.

**Test indépendant** : un utilisateur ouvre la page de résultats ESG, voit un picto source à côté du score, clique dessus, voit la fenêtre de détail avec un lien fonctionnel vers le PDF officiel, vérifie que le statut affiché est « vérifiée » et que la version, la page et la date sont cohérentes.

**Scénarios d'acceptation** :

1. **Étant donné** que l'utilisateur consulte la page de résultats ESG, **quand** un score ESG global est affiché, **alors** un picto source est rendu à côté du score et est cliquable.
2. **Étant donné** que l'utilisateur clique sur le picto source d'un facteur d'émission carbone, **quand** la fenêtre de détail s'ouvre, **alors** elle affiche au minimum : titre, publisher, version, date de publication, page, statut de vérification, et un bouton « Ouvrir le document officiel » qui ouvre l'URL dans un nouvel onglet.
3. **Étant donné** qu'une source est affichée, **quand** son statut est « vérifiée », **alors** un badge visuel vert est rendu ; quand son statut est « en attente de validation » un badge orange est rendu ; quand son statut est « obsolète » un badge rouge avec la raison est rendu.
4. **Étant donné** qu'un utilisateur PME demande une source par son identifiant, **quand** la source n'est pas en statut « vérifiée », **alors** elle n'est pas accessible publiquement (404 visible côté PME) sauf si l'utilisateur a un rôle administrateur.

---

### User Story 2 — L'agent IA cite ses sources et est rejeté en cas d'omission (Priorité : P1)

Lorsque l'agent conversationnel produit une réponse contenant un chiffre, un score, un critère, une formule, un seuil ou un facteur d'émission, il doit explicitement référencer une source vérifiée du catalogue (action « citer une source ») ou explicitement marquer l'affirmation comme non sourçable (action « signaler une affirmation sans source »). Si l'agent affirme un chiffre sans déclarer de source ni signaler d'absence de source, le système rejette automatiquement la réponse, demande à l'agent de corriger sa réponse une fois, et bascule sur un message de repli neutre (« je ne dispose pas d'une source vérifiée pour ce chiffre ») si l'agent ne se corrige pas.

**Pourquoi cette priorité** : sans ce contrôle automatique, le sourçage devient déclaratif et rapidement contourné. C'est ce qui garantit que la promesse tient à l'échelle et que la base reste défendable même quand des centaines d'utilisateurs interrogent l'agent.

**Test indépendant** : un test orienté évaluation envoie 10 questions du jeu d'évaluation (golden set) qui appellent inévitablement un chiffre ; on vérifie que pour chaque réponse contenant un chiffre, une action « citer une source » correspondant à une source vérifiée du catalogue a bien été déclarée par l'agent dans le même tour. On vérifie aussi qu'une réponse construite artificiellement avec un chiffre sans citation est bien rejetée et que le message de repli apparaît.

**Scénarios d'acceptation** :

1. **Étant donné** que l'utilisateur demande à l'agent « quel est le facteur d'émission de l'électricité réseau en Côte d'Ivoire ? », **quand** l'agent produit sa réponse, **alors** il invoque l'action « citer une source » avec un identifiant de source vérifiée (par exemple ADEME ou IEA) avant que la réponse ne soit transmise à l'utilisateur.
2. **Étant donné** qu'un test simule une réponse contenant un chiffre sans citation associée, **quand** la réponse passe par la couche de validation, **alors** elle est rejetée, l'agent est sollicité une seule fois pour corriger, et si la correction échoue le système renvoie le message de repli sans le chiffre litigieux.
3. **Étant donné** que l'agent ne dispose d'aucune source vérifiée pour un chiffre légitimement demandé, **quand** il invoque l'action « signaler une affirmation sans source » avec un motif, **alors** la réponse n'est pas rejetée mais l'incident est journalisé pour revue administrateur et un libellé visible signale à l'utilisateur que ce chiffre est non sourcé.
4. **Étant donné** un seuil organisationnel de signalements « sans source » dépassé sur 24 heures, **quand** la valeur dépasse 20 % des réponses, **alors** un événement d'alerte est journalisé pour revue administrateur (la mise en place d'un canal d'alerte temps réel est hors-scope F01).

---

### User Story 3 — Administrateur saisit et fait valider une source (workflow 4-yeux) (Priorité : P1)

Un administrateur ESG Mefali peut saisir une nouvelle source dans le catalogue avec ses métadonnées obligatoires (URL, titre, publisher, version, date, page, section). À la création, la source est en statut « brouillon » puis l'administrateur peut la passer en « en attente de validation ». Un autre administrateur, différent du créateur, peut alors la passer en « vérifiée », ce qui la rend utilisable par l'agent IA et visible côté PME. Un administrateur peut aussi marquer une source en « obsolète » avec un motif (par exemple : « nouvelle version disponible »).

**Pourquoi cette priorité** : sans ce circuit, il est impossible de constituer le catalogue initial de 30 sources de référence ni d'enrichir le catalogue dans le temps. C'est ce qui assure aussi qu'aucune source ne devient visible à un utilisateur sans avoir été relue par deux personnes différentes (workflow 4-yeux), ce qui est une garantie d'intégrité.

**Test indépendant** : un administrateur A saisit une source minimale, la passe en « en attente de validation ». Un administrateur B (différent de A) passe la source en « vérifiée ». La source devient consommable par l'agent IA et visible sur la page publique du catalogue. On vérifie qu'un même administrateur ne peut pas à la fois créer et valider la même source.

**Scénarios d'acceptation** :

1. **Étant donné** un administrateur connecté, **quand** il crée une source avec URL, titre, publisher, version et date de publication, **alors** la source est enregistrée avec le statut « brouillon » et l'identité du créateur est conservée.
2. **Étant donné** une source en statut « en attente de validation » créée par l'administrateur A, **quand** l'administrateur A tente de la passer en « vérifiée », **alors** l'opération est rejetée (un même administrateur ne peut pas créer et valider la même source).
3. **Étant donné** une source en statut « en attente de validation » créée par l'administrateur A, **quand** l'administrateur B (différent de A) la passe en « vérifiée », **alors** la source devient visible côté PME et utilisable par l'agent IA, et l'identité et la date de validation sont conservées.
4. **Étant donné** une source « vérifiée » qui n'est plus à jour, **quand** un administrateur la marque « obsolète » avec une raison, **alors** la source n'est plus utilisable par l'agent IA, le badge « obsolète » est rendu côté UI, et la raison est affichée.

---

### User Story 4 — Annexe « Sources et références » auto-générée dans le rapport PDF (Priorité : P2)

Lorsqu'un rapport ESG (ou autre rapport produit) est généré au format PDF, une section finale « Sources et références » est automatiquement composée à partir de l'ensemble des sources réellement mobilisées pendant la production du rapport. Chaque source y est listée avec : numéro [n], titre, publisher, version, date, page, section, statut, et URL cliquable. Les chiffres et affirmations dans le corps du rapport portent un renvoi inline « [n] » qui pointe vers l'entrée correspondante.

**Pourquoi cette priorité** : c'est la matérialisation hors-écran de la promesse de traçabilité, indispensable quand le rapport est imprimé, transmis à un fund officer ou archivé. Sans cette story le rapport est rebadge cosmétique. P2 (et non P1) car un MVP minimal des stories 1, 2 et 3 produit déjà une expérience traçable en ligne.

**Test indépendant** : on génère un rapport ESG sur une PME fictive, on ouvre le PDF, on contrôle que la dernière section « Sources et références » liste toutes les sources mobilisées, et qu'au moins un chiffre du corps du rapport porte un renvoi numérique cohérent avec la liste finale.

**Scénarios d'acceptation** :

1. **Étant donné** une PME pour laquelle un rapport ESG est généré, **quand** le PDF est produit, **alors** une section finale « Sources et références » contient au minimum toutes les sources réellement mobilisées pendant la rédaction.
2. **Étant donné** un rapport contenant 5 références, **quand** un chiffre est affiché dans le corps, **alors** un renvoi inline « [n] » est présent et pointe vers l'entrée correspondante de l'annexe.
3. **Étant donné** qu'aucune source n'a été mobilisée (cas dégénéré), **quand** le rapport est généré, **alors** la section apparaît tout de même avec le libellé « Aucune source mobilisée pour ce rapport » au lieu d'être omise silencieusement.

---

### User Story 5 — Catalogue public consultable par la PME (page « Sources ») (Priorité : P2)

L'utilisateur PME peut accéder à une page « Sources » qui présente le catalogue des sources vérifiées du système. La page propose une recherche en texte libre, un filtre par publisher (par exemple ADEME, IPCC, UEMOA, BCEAO, GCF) et un affichage paginé. Cliquer sur une entrée ouvre le détail de la source (mêmes informations que la fenêtre de détail story 1) avec lien direct vers le document officiel.

**Pourquoi cette priorité** : la page renforce la promesse de transparence et permet à un utilisateur curieux ou à un fund officer interne de parcourir toutes les sources qu'il pourra rencontrer dans l'application. C'est P2 car non bloquant pour la trace conversationnelle et le rapport PDF.

**Test indépendant** : un utilisateur PME ouvre la page « Sources », tape un mot-clé, filtre par publisher, voit la liste des sources vérifiées correspondantes, clique sur une entrée et accède au détail.

**Scénarios d'acceptation** :

1. **Étant donné** que l'utilisateur PME ouvre la page « Sources », **quand** la page est chargée, **alors** seules les sources de statut « vérifiée » sont listées.
2. **Étant donné** un catalogue de 30 sources, **quand** l'utilisateur tape « ADEME » dans la recherche, **alors** seules les sources dont les champs textuels indexés correspondent à « ADEME » sont retournées.
3. **Étant donné** que l'utilisateur applique le filtre publisher « UEMOA », **quand** la liste se met à jour, **alors** elle ne contient que les sources de ce publisher.
4. **Étant donné** que l'utilisateur clique sur une entrée du catalogue, **quand** la fenêtre détail s'ouvre, **alors** elle affiche les mêmes champs que la fenêtre détail accessible depuis un picto inline.

---

### User Story 6 — L'agent IA recherche une source pertinente avant de citer (Priorité : P2)

Lorsque l'agent IA est confronté à une question factuelle pour laquelle il n'a pas immédiatement de source en mémoire, il dispose d'une action « rechercher une source » qui interroge le catalogue par mots-clés (et éventuellement par publisher) pour récupérer jusqu'à 5 sources pertinentes parmi celles qui sont vérifiées. Il choisit ensuite la source la mieux adaptée, déclare l'action « citer une source » avec son identifiant, et compose sa réponse.

**Pourquoi cette priorité** : sans cette action, l'agent doit connaître par cœur tous les identifiants de source, ce qui ne tiendra pas à grande échelle ni ne supportera l'enrichissement continu du catalogue. P2 car les stories 1-3 livrent déjà un produit utilisable en s'appuyant sur les sources les plus citées et seedées.

**Test indépendant** : un test envoie une question dont la réponse correcte exige une source connue du catalogue mais non explicitement nommée dans le prompt système ; on vérifie que l'agent invoque l'action « rechercher une source » avec une requête pertinente, qu'il reçoit au plus 5 résultats vérifiés, qu'il en choisit un et qu'il invoque ensuite « citer une source » avec son identifiant.

**Scénarios d'acceptation** :

1. **Étant donné** une question demandant un facteur d'émission spécifique, **quand** l'agent invoque l'action « rechercher une source » avec une requête comme « émission électricité Afrique de l'Ouest », **alors** il reçoit au plus 5 sources vérifiées triées par pertinence.
2. **Étant donné** que l'agent applique le filtre publisher = « ADEME », **quand** la recherche est exécutée, **alors** seules les sources « ADEME » sont retournées.
3. **Étant donné** qu'aucune source vérifiée ne correspond à la requête, **quand** l'agent reçoit un résultat vide, **alors** il invoque « signaler une affirmation sans source » avec un motif explicite (par exemple « aucune source disponible dans le catalogue pour ce chiffre »).

---

### User Story 7 — Migration du contenu actuel codé en dur vers des tables sourcées (Priorité : P1)

À la mise en production de F01, le contenu factuel actuellement codé en dur dans le code applicatif (facteurs d'émission carbone, les 30 critères ESG, les pondérations sectorielles, les constantes du simulateur financier) est migré dans des tables dédiées du catalogue, chaque enregistrement étant lié à une source. Quand une source officielle existe pour la valeur (par exemple les facteurs d'émission ADEME ou IPCC), elle est créée et liée. Quand aucune source officielle ne couvre la valeur (cas des constantes du simulateur historiquement inventées), l'enregistrement est marqué « en attente de validation » et journalisé pour traitement éditorial ultérieur.

**Pourquoi cette priorité** : sans cette migration, l'application affiche des chiffres et l'agent IA produit des chiffres qui ne pourront jamais passer la validation backend. C'est ce qui fait la différence entre un MVP démo et un MVP utilisable.

**Test indépendant** : après exécution de la migration, on vérifie en base que (a) chaque facteur d'émission utilisé a un identifiant de source vérifiée associé, (b) chaque critère ESG des 30 critères a un identifiant de source associé, (c) les pondérations sectorielles sont enregistrées en table avec un identifiant de source, (d) les constantes du simulateur sont migrées et marquées « en attente de validation » si aucune source officielle ne les couvre.

**Scénarios d'acceptation** :

1. **Étant donné** la valeur historique « facteur électricité réseau Côte d'Ivoire = 0,41 kgCO2e/kWh », **quand** la migration s'exécute, **alors** un enregistrement « facteur d'émission » est créé en table avec un identifiant de source associé pointant vers une source ADEME ou IEA vérifiée.
2. **Étant donné** les 30 critères ESG, **quand** la migration s'exécute, **alors** chaque critère devient un enregistrement « indicateur » en table, lié à une source pertinente (Taxonomie verte UEMOA, IFC, GRI ou ODD ONU selon le pilier).
3. **Étant donné** une constante du simulateur sans source officielle connue, **quand** la migration s'exécute, **alors** elle est créée avec le statut « en attente de validation » et un commentaire explicite signale que la source officielle reste à fournir.
4. **Étant donné** que la migration se termine, **quand** l'agent IA produit une réponse mobilisant un facteur d'émission, **alors** il peut citer la source associée à ce facteur via le catalogue (et non plus via une valeur codée en dur).

---

### Edge Cases

- **Une source vérifiée passe à « obsolète » alors qu'elle est utilisée par des objets publiés** : les objets publiés conservent leur état, mais l'agent IA ne peut plus la citer pour de nouvelles réponses. Une notification administrateur recense les objets impactés.
- **Un administrateur tente de publier une entité (par exemple un référentiel) dont une partie des sources liées n'est pas « vérifiée »** : la transition vers « publié » est bloquée et un message explique quelles sources doivent être validées d'abord.
- **L'agent IA invoque l'action « citer une source » avec un identifiant qui n'existe pas, ou qui pointe sur une source non « vérifiée »** : la citation est rejetée, traitée comme une omission de citation, et l'agent doit corriger ou signaler.
- **La détection automatique des chiffres détecte un faux positif** (par exemple « ISO 14001 » contient « 14001 » sans qu'il s'agisse d'un chiffre factuel à sourcer) : le système doit éviter le rejet sur ces formes connues. Une liste maintenue des motifs « ignorés » fait partie des paramètres de la couche de validation.
- **Aucune source vérifiée n'existe encore au catalogue (cas de la première mise en production)** : la séquence de migration / seed initial place 30 sources « vérifiées » directement, qui font foi sans passer par le workflow 4-yeux interactif (création « système » réputée pré-vérifiée par procédure éditoriale documentée hors-app).
- **Une source est créée puis le créateur perd son rôle administrateur ou son compte est désactivé** : la source reste valide, l'identifiant du créateur est conservé en historique, et la validation peut être réalisée par tout autre administrateur actif.
- **L'utilisateur PME tente d'accéder à une source de statut « brouillon » ou « en attente »** : l'accès renvoie une erreur 404 (et non 403) pour ne pas révéler son existence.
- **Le rapport PDF est régénéré : la liste de sources doit refléter les sources réellement mobilisées dans la dernière génération**, pas l'historique des générations précédentes.

## Requirements *(mandatory)*

### Functional Requirements

#### Catalogue Source (entité de premier rang)

- **FR-001** : Le système DOIT permettre de stocker des Sources avec, au minimum, les informations suivantes : identifiant unique, URL officielle, titre, publisher, version, date de publication, page (optionnelle), section (optionnelle), date de capture, identifiant de l'administrateur ayant créé la source, identifiant de l'administrateur ayant validé la source (le cas échéant), statut de vérification (parmi « brouillon », « en attente de validation », « vérifiée », « obsolète »), date de validation et raison d'obsolescence.
- **FR-002** : Le système DOIT empêcher qu'un même administrateur soit à la fois créateur et validateur d'une source donnée (workflow 4-yeux).
- **FR-003** : Le système DOIT permettre à un administrateur de marquer une source en « obsolète » avec une raison, et DOIT alors empêcher l'agent IA de la citer pour de nouvelles réponses.
- **FR-004** : Le système DOIT empêcher la suppression d'une source qui est référencée par au moins un objet du catalogue ; la transition vers « obsolète » doit être utilisée à la place.

#### Entités sourcées

- **FR-005** : Le système DOIT modéliser un catalogue d'entités factuelles couvrant : indicateurs (unité atomique de mesure ESG), référentiels (collections d'indicateurs avec seuils et poids), associations N-N entre indicateurs et référentiels (poids, seuil, source), critères logiques sur indicateurs, formules de calcul, seuils d'éligibilité, facteurs d'émission par catégorie et par pays, documents requis par fonds ou intermédiaire, et constantes de simulation.
- **FR-006** : Chaque entité factuelle DOIT être obligatoirement reliée à une Source via un lien explicite ; aucune entité factuelle ne PEUT exister sans source.
- **FR-007** : Chaque entité du catalogue DOIT porter un statut de publication parmi « brouillon » et « publié », et NE PEUT PASSER en « publié » que si toutes ses sources liées sont en statut « vérifiée ».
- **FR-008** : Le système NE DOIT PAS exposer à l'utilisateur PME ou à l'agent IA des entités factuelles dont le statut de publication est « brouillon ».

#### Actions de l'agent IA

- **FR-009** : L'agent IA DOIT disposer d'une action « citer une source » qui, étant donné un identifiant de source vérifiée, retourne les informations nécessaires (URL, titre, publisher, version, date de publication, page) pour étayer sa réponse.
- **FR-010** : L'agent IA DOIT disposer d'une action « rechercher une source » qui, étant donné une requête en texte libre et éventuellement un publisher, retourne au plus 5 sources vérifiées pertinentes.
- **FR-011** : L'agent IA DOIT disposer d'une action « signaler une affirmation sans source » qui, étant donné un texte d'affirmation et un motif, journalise l'incident pour revue administrateur.
- **FR-012** : Ces trois actions DOIVENT être mises à disposition de l'agent IA dans tous les contextes où il est susceptible de produire des chiffres, des scores, des critères, des formules, des seuils ou des facteurs d'émission.

#### Validation backend stricte

- **FR-013** : Après chaque tour de l'agent IA, le système DOIT analyser le texte produit pour y détecter les motifs caractéristiques d'affirmations factuelles à sourcer (chiffres avec unité, scores, pourcentages, montants en devise, équivalents tCO2e/kgCO2e, notations sur 100 ou sur 10).
- **FR-014** : Pour chaque grappe « chiffre + unité contigüe » détectée, le système DOIT vérifier qu'au moins une action « citer une source » a été déclarée par l'agent dans le même tour ; une même citation PEUT couvrir plusieurs grappes consécutives à condition qu'elles soient séparées de moins de 200 caractères dans le même paragraphe et qu'elles relèvent de la même source. Si deux grappes proches relèvent de sources différentes, l'agent DOIT produire deux citations distinctes.
- **FR-015** : Si un motif détecté n'est couvert ni par une « citation de source » valide (sur une source `verified`), ni par une action « signaler une affirmation sans source », le système DOIT rejeter la réponse et solliciter l'agent UNE SEULE FOIS pour qu'il corrige.
- **FR-016** : Si la correction unique échoue ou n'aboutit toujours pas à une couverture complète, le système DOIT remplacer la portion litigieuse par un libellé de repli explicite (« je ne dispose pas d'une source vérifiée pour ce chiffre ») et journaliser l'incident pour revue administrateur.
- **FR-017** : La couche de validation DOIT supporter une liste paramétrable de motifs à ignorer (`IGNORED_NUMERIC_PATTERNS`) initialisée avec : normes ISO usuelles (ISO 9001, 14001, 14064, 14067, 26000, 27001, 50001), références règlementaires (« article N.M »), identifiants techniques (« 802.1Q », « PCI-DSS 4.0 ») ; cette liste DOIT être étendue itérativement sur la base du jeu d'évaluation interne.
- **FR-018** : La couche de validation DOIT atteindre un taux d'erreur (faux positifs et faux négatifs combinés) inférieur ou égal à 5 % sur un jeu d'évaluation interne d'au moins 50 réponses annotées.
- **FR-018a** : Lorsqu'une action « citer une source » est invoquée avec un identifiant pointant sur une source dont le statut n'est pas `verified` (notamment `outdated`), le tool DOIT renvoyer une erreur structurée à l'agent, traitée comme une omission de citation. L'agent DOIT alors invoquer `search_source` pour trouver une source alternative ou `flag_unsourced` s'il n'en trouve aucune.
- **FR-018b** : Le passage d'une source en `outdated` NE DOIT PAS rétroactivement modifier le contenu des messages historiques persistés ; côté UI les anciennes citations apparaissent avec un badge « obsolète » qui signale la dérive sans réécrire la conversation.

#### Interface utilisateur (PME et fund officer)

- **FR-019** : Toute valeur factuelle affichée à l'utilisateur (score, critère, recommandation, facteur d'émission, montant, seuil, etc.) DOIT être accompagnée d'un picto cliquable « source » menant à la fenêtre de détail.
- **FR-020** : La fenêtre de détail d'une source DOIT afficher au minimum : titre, publisher, version, date de publication, page, section (si renseignée), date de capture, identifiant lisible du validateur, statut visuel et lien vers le document officiel ouvert dans un nouvel onglet.
- **FR-021** : Le statut de la source DOIT être exposé visuellement par un badge à code couleur (par exemple vert pour « vérifiée », orange pour « en attente », rouge pour « obsolète » avec sa raison).
- **FR-022** : Une page « Sources » DOIT être accessible à l'utilisateur PME, listant uniquement les sources « vérifiées », avec recherche en texte libre, filtre par publisher et pagination.
- **FR-023** : Aucune source de statut autre que « vérifiée » NE DOIT être exposée publiquement à un utilisateur non administrateur ; toute requête d'accès direct DOIT renvoyer une erreur 404.
- **FR-024** : L'ensemble des éléments d'interface introduits par F01 DOIT être conforme à la convention de présentation actuelle de l'application, y compris le mode sombre, et DOIT supporter la navigation au clavier et les attributs d'accessibilité (label descriptif, focus piégé dans la fenêtre détail).

#### Annexe « Sources et références » dans les rapports PDF

- **FR-025** : Lors de la génération d'un rapport PDF, le système DOIT collecter au fil de l'eau les sources mobilisées et générer une section finale « Sources et références ».
- **FR-026** : Cette section DOIT lister chaque source avec un numéro [n], titre, publisher, version, date, page, section (si renseignée), statut et URL.
- **FR-027** : Les chiffres affichés dans le corps du rapport DOIVENT porter un renvoi inline « [n] » cohérent avec la liste finale.
- **FR-028** : Si aucune source n'a été mobilisée, le système DOIT tout de même générer la section avec un libellé explicite (« Aucune source mobilisée »), et NE DOIT PAS l'omettre silencieusement.

#### Workflow administrateur

- **FR-029** : Un administrateur DOIT pouvoir lister, créer, modifier (avant validation), demander validation, valider et marquer obsolète une source via une interface dédiée ou une API administrative.
- **FR-030** : Le système DOIT conserver l'historique de qui a créé et qui a validé chaque source, ainsi que les dates correspondantes.
- **FR-031** : Le système DOIT empêcher la transition vers « publié » d'une entité (référentiel, indicateur, fonds, etc.) si l'une au moins de ses sources n'est pas « vérifiée », et DOIT communiquer un message d'erreur précisant les sources fautives.

#### Migration des données existantes

- **FR-032** : Lors de la mise en production de F01, le système DOIT migrer le contenu factuel actuellement codé en dur (facteurs d'émission, 30 critères ESG, pondérations sectorielles, constantes de simulation) dans les tables du catalogue.
- **FR-033** : Lorsqu'une source officielle existe pour la valeur migrée, l'enregistrement DOIT être lié à cette source vérifiée.
- **FR-034** : Lorsqu'aucune source officielle ne couvre la valeur migrée, l'enregistrement DOIT être créé en statut « en attente de validation » et journalisé pour traitement éditorial ultérieur.
- **FR-035** : Le seed de catalogue DOIT inclure au moins 30 sources de statut « vérifiée » pour les organismes : ADEME, IPCC, IEA, Taxonomie verte UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD ONU.

#### Non-régression et sécurité

- **FR-036** : Aucune action de l'agent IA introduite par F01 NE DOIT pouvoir muter le catalogue (création, modification ou suppression de sources, indicateurs, référentiels) ; ces opérations sont strictement réservées aux administrateurs.
- **FR-037** : La couche de validation DOIT s'appliquer uniformément à tous les contextes producteurs de chiffres, sans dépendre du module appelant.
- **FR-038** : L'introduction de F01 NE DOIT PAS dégrader les fonctionnalités existantes ; les modules consommateurs (carbone, ESG, financement, etc.) doivent continuer à fonctionner pendant la migration et basculer sur le catalogue dès que les données sont disponibles.

### Key Entities *(includes data)*

- **Source** : représente un document de référence officiel (taxonomie, standard, circulaire, base de données publique). Attributs principaux : identifiant unique, URL, titre, publisher, version, date de publication, page, section, date de capture, identifiant du créateur, identifiant du validateur, statut de vérification (brouillon, en attente, vérifiée, obsolète), raison d'obsolescence éventuelle. Relations : un objet du catalogue référence une source ; un administrateur peut créer ou valider plusieurs sources.
- **Indicateur** : unité atomique de mesure ESG (par exemple « pourcentage de déchets recyclés »). Attributs principaux : code, libellé, pilier (E/S/G), description, question type adressée à l'utilisateur, référence à une source.
- **Référentiel** : collection cohérente d'indicateurs, structurée en piliers, avec seuils et poids. Attributs principaux : code, libellé, statut de publication, référence à au moins une source structurante.
- **Association indicateur ↔ référentiel** : lien N-N entre un indicateur et un référentiel, porteur d'attributs propres : poids, seuil, référence à une source justifiant le poids ou le seuil retenus.
- **Critère** : condition logique sur un ou plusieurs indicateurs (par exemple : « éligible si l'indicateur X dépasse Y »). Attributs : libellé, expression, indicateurs concernés, référence à une source.
- **Formule** : formule de calcul mobilisant indicateurs et constantes (par exemple : score combiné). Attributs : libellé, expression, paramètres, référence à une source.
- **Seuil** : valeur de coupure d'éligibilité ou de classification (par exemple : seuil PME, seuil d'investissement minimal). Attributs : libellé, valeur, unité, référence à une source.
- **Facteur d'émission** : valeur kgCO2e par unité d'activité, par catégorie et par pays / zone (par exemple : électricité réseau Côte d'Ivoire). Attributs : code, libellé, catégorie, pays, valeur, unité, référence à une source.
- **Document requis** : élément de dossier exigé par un fonds ou un intermédiaire (par exemple : « registre des actionnaires »). Attributs : libellé, description, fonds ou intermédiaire concerné, référence à une source.
- **Constante de simulation** : paramètre numérique d'un calcul (par exemple : taux d'épargne projeté, impact carbone par million de FCFA investi). Attributs : libellé, valeur, unité, périmètre, référence à une source.
- **Statut de publication** : champ commun aux entités factuelles, parmi « brouillon » et « publié », avec règles de transition liées au statut de vérification des sources.
- **Citation de source** (élément conversationnel non persisté en base hors journalisation) : association éphémère entre une affirmation produite par l'agent IA et l'identifiant d'une source vérifiée mobilisée.
- **Signalement d'affirmation sans source** : journalisation d'un cas où l'agent IA reconnaît explicitement ne pas pouvoir sourcer une affirmation. Attributs : texte de l'affirmation, motif, contexte, horodatage, identifiant de session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des valeurs factuelles affichées dans les pages les plus consultées (dashboard, résultats ESG, résultats carbone, fiche fonds, fiche dossier) sont accompagnées d'un picto source cliquable et fonctionnel à la fin de F01.
- **SC-002** : Au moins 30 sources de statut « vérifiée » sont seedées dans le catalogue à la mise en production de F01, couvrant les principaux organismes de référence (ADEME, IPCC, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD ONU).
- **SC-003** : Sur un jeu d'évaluation interne de 10 questions imposant l'utilisation d'au moins un chiffre, l'agent IA déclare une « citation de source » conforme dans au moins 9 cas sur 10.
- **SC-004** : Sur un jeu d'évaluation interne de 50 réponses annotées, le taux d'erreur de la couche de validation (faux positifs et faux négatifs combinés) reste inférieur ou égal à 5 %.
- **SC-005** : 100 % des facteurs d'émission utilisés dans les calculs carbone et 100 % des 30 critères ESG sont migrés dans les tables sourcées et liés à au moins une source connue.
- **SC-006** : Toute valeur factuelle non couverte par une source officielle au moment de la migration est explicitement marquée « en attente de validation » et inscrite dans une liste de suivi (zéro valeur silencieusement non sourcée).
- **SC-007** : Aucun utilisateur non administrateur n'accède à une source de statut autre que « vérifiée » (vérification par test d'accès direct par identifiant : doit retourner 404).
- **SC-008** : Aucune source ne peut être validée par son propre créateur (vérification par test d'invariant 4-yeux : la tentative est rejetée).
- **SC-009** : Le temps perçu par l'utilisateur entre le clic sur un picto source et l'apparition de la fenêtre de détail reste inférieur à 1 seconde dans 95 % des cas.
- **SC-010** : Tout rapport PDF généré contient une section finale « Sources et références » exhaustive, et tous les chiffres du corps portent un renvoi numérique cohérent.
- **SC-011** : La page « Sources » côté PME charge la liste filtrée d'un publisher en moins de 2 secondes pour un catalogue d'au moins 100 sources.
- **SC-012** : Le taux de signalements « affirmation sans source » sur 24 heures glissantes reste inférieur à 20 % du total des affirmations factuelles produites par l'agent IA en régime nominal (au-delà, un événement d'alerte est journalisé pour revue administrateur).

## Assumptions

- L'application dispose déjà d'un mécanisme d'authentification et de rôles (utilisateur PME, administrateur) suffisant pour distinguer les profils ; F01 ne re-définit pas les rôles mais s'appuie sur eux.
- L'application dispose déjà d'un agent conversationnel structuré en nœuds spécialisés exposables à des actions outillées ; F01 ajoute trois actions et une couche de validation, sans refonte de l'agent.
- L'application dispose déjà d'un module de génération de rapports PDF ; F01 ajoute la collecte des sources mobilisées et la section finale, sans refonte du moteur de rendu.
- Les rôles administrateurs initiaux sont déjà créés et au moins deux administrateurs distincts existent à la mise en production pour permettre le workflow 4-yeux (à défaut, la procédure éditoriale interne assure le seed des 30 sources « vérifiées »).
- La feature de cloisonnement multi-locataire (F02 « comptes ») est planifiée dans une feature ultérieure ; pour F01, l'identifiant de propriétaire est `created_by_user_id` (FK `users.id`, NOT NULL) sur les tables du catalogue, avec un marqueur `# TODO(F02): account_id` sur les modèles SQLAlchemy correspondants pour faciliter la migration ultérieure.
- La feature d'audit trail global (F03) est planifiée dans une feature ultérieure ; pour F01, la journalisation des transitions de statut et des signalements est faite par les services existants.
- La présentation actuelle de l'application supporte un mode sombre généralisé ; tous les composants visuels introduits par F01 doivent en être compatibles dès leur première version.
- Les durées caractéristiques (1 seconde de temps perçu, 2 secondes pour la page catalogue) supposent un environnement web standard (réseau filaire ou 4G nominale) et un volume de catalogue de l'ordre de 30 à 200 sources en première année.
- Le hors-scope F01 inclut explicitement : la capture archivée d'un document source (Wayback / archive interne), le hash de contenu pour détecter les changements, la revalidation périodique automatique des URL, les scrapeurs automatisés des sites officiels, la marketplace de sources contributives par des consultants tiers.

## Dependencies

- **Aucune dépendance fonctionnelle bloquante** au sein du backlog : F01 est une feature de fondation à laquelle plusieurs autres features (carbone, ESG, financement, scoring, rapports) viendront ensuite se brancher.
- **Dépendance logicielle implicite** : présence de l'agent conversationnel et du module rapports déjà opérationnels (inchangés en F01).
- **Dépendance organisationnelle** : présence d'au moins deux administrateurs ESG Mefali distincts pour activer le workflow 4-yeux dès la mise en production.
