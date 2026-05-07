# Feature Specification: F12 — Mémoire Contextuelle Conforme (15 messages bruts + recherche sémantique)

**Feature Branch**: `feat/F12-memoire-contextuelle-pgvector`
**Spec Number**: `021`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F12 - Mémoire Contextuelle Conforme : 15 derniers messages conservés en clair, historique ancien indexé pour recherche sémantique via tool `recall_history`, persistance des conversations en cours malgré redémarrage serveur, multi-tenant strict (F02), masquage des secrets avant indexation, suppression cascade des historiques quand un compte est purgé."

## Clarifications

### Session 2026-05-07

- Q: Quel mécanisme déclenche l'indexation asynchrone d'un message après son insertion ? → A: Tâche `asyncio.create_task` non bloquante côté FastAPI (référence conservée pour cycle de vie). Pas de queue Celery au MVP — son introduction est planifiée post-MVP (F19 ou ultérieur) sans changement d'API du service mémoire.
- Q: Comment découper les messages plus longs que la limite tolérée par le service d'embedding (8 191 tokens / ~32 000 caractères) ? → A: Si message ≤ 6 000 caractères → 1 chunk = 1 message (pas de découpe). Sinon → découpe par paragraphes, taille cible ≤ 6 000 caractères par chunk, recouvrement de 200 caractères entre chunks consécutifs ; chaque chunk est indexé indépendamment et porte un attribut `chunk_index` (0, 1, 2…).
- Q: Le tool `recall_history` doit-il chercher dans la conversation courante (déjà partiellement injectée via les 15 derniers messages) ? → A: Par défaut NON (`exclude_current=true`) pour éviter le doublon avec le contexte récent. Un paramètre booléen optionnel `include_current_conversation` permet d'inclure la conversation courante quand l'utilisateur cherche un détail au-delà des 15 derniers messages de la même conversation.
- Q: Quel format pour l'horodatage relatif des 15 messages bruts injectés en contexte LLM ? → A: Format français court : « il y a X minutes » (< 60 min), « il y a X heures » (< 24 h), « hier » (24-48 h), « il y a X jours » (≤ 30 j), « le DD/MM/YYYY » (> 30 j).
- Q: Faut-il introduire un cache court-terme côté backend pour éviter les invocations répétées du tool `recall_history` ? → A: Non au MVP F12. La borne `MAX_TOOL_CALLS_PER_TURN = 5` (déjà en vigueur) et la docstring du tool (« ne pas invoquer si l'info est dans les 15 derniers messages ») couvrent le risque. Un cache TTL court (60 s) sera évalué post-MVP si le monitoring SC-010 montre un dépassement durable du seuil de 30 % d'invocations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Reprise de conversation après redémarrage serveur (Priority: P1)

Une PME utilisatrice est en train d'échanger avec l'assistant ESG (par exemple un onboarding ESG en cours, ou une saisie de bilan carbone). Le serveur backend redémarre (déploiement, crash, scale up/down). Quand la PME envoie le message suivant, l'assistant reprend la conversation exactement où elle en était : il se souvient des 15 derniers échanges, du module en cours, de l'identité de la PME, et ne pose pas à nouveau les questions déjà répondues.

**Why this priority**: C'est le minimum vital de qualité conversationnelle. Aujourd'hui, l'utilisation d'un stockage volatile pour le checkpointer LangGraph signifie que tout redéploiement (plusieurs fois par semaine pendant la phase d'itération) efface toutes les conversations en cours. Cela bloque les modules longs (ESG 30 critères, bilan carbone multi-catégories) qui peuvent durer plusieurs sessions.

**Independent Test**: Démarrer une conversation, envoyer 5 messages utilisateur (avec réponses assistant), redémarrer le processus backend, envoyer un 6ᵉ message dans la même conversation : l'assistant doit citer correctement un détail du message 2 ou 3 sans le reposer.

**Acceptance Scenarios**:

1. **Given** une conversation avec 8 échanges (16 messages) sur un bilan carbone en cours, **When** le serveur redémarre puis l'utilisateur envoie le 9ᵉ message, **Then** l'assistant connaît toujours la catégorie d'émission en cours, les valeurs déjà saisies, et le module actif (`active_module = "carbon"`).
2. **Given** un onboarding ESG arrivé au critère 12/30 et le serveur redémarre, **When** l'utilisateur reprend, **Then** l'assistant repart au critère 13/30 (et non au critère 1).
3. **Given** une question interactive (widget F18) en attente de réponse au moment du redémarrage, **When** l'utilisateur répond, **Then** la question est résolue normalement (le checkpoint correspondant est restauré).

---

### User Story 2 — Charger les 15 derniers messages bruts en contexte (Priority: P1)

Quand un utilisateur reprend une conversation après quelques heures ou jours, l'assistant a accès non seulement à un résumé synthétique des conversations passées (3 résumés actuels) mais aussi aux 15 derniers messages bruts de la conversation courante. Cela permet à l'assistant de répondre avec précision sur les détails récents (montants, noms de fonds, codes critères ESG) plutôt qu'à partir d'un résumé qui aurait perdu les nuances.

**Why this priority**: Le résumé seul perd la précision factuelle (« on parlait d'un fonds » vs « on parlait du Green Climate Fund pour ton projet de panneaux solaires de 50 M FCFA »). Sans ces 15 messages, l'assistant peut reposer des questions, ou pire, halluciner des détails.

**Independent Test**: Créer une conversation de 20 messages utilisateur (40 messages au total), puis envoyer un 21ᵉ message qui fait référence à un détail du 18ᵉ message (qui doit donc tomber dans la fenêtre de 15 derniers). L'assistant doit y répondre correctement sans demander de répéter.

**Acceptance Scenarios**:

1. **Given** une conversation avec exactement 16 messages, **When** l'utilisateur envoie un 17ᵉ message, **Then** le contexte LLM reçoit les 15 derniers messages (du 2ᵉ au 16ᵉ) plus 0 à 3 résumés de conversations antérieures.
2. **Given** une conversation avec 5 messages seulement, **When** l'utilisateur envoie un 6ᵉ message, **Then** le contexte LLM reçoit les 5 messages disponibles (et non un padding artificiel).
3. **Given** un utilisateur qui revient sur sa conversation après 3 jours, **When** il envoie « Reprends où on en était », **Then** l'assistant cite un détail précis des 15 derniers messages sans le déformer.

---

### User Story 3 — Retrouver des informations anciennes via recherche sémantique (Priority: P1)

Un utilisateur écrit : « Tu te souviens du fonds qu'on évoquait pour mon projet de panneaux solaires il y a 2 mois ? ». L'assistant invoque automatiquement un outil de recherche sémantique sur l'historique conversationnel et retrouve les passages pertinents (au-delà de la fenêtre de 15 messages), puis répond avec le nom du fonds et les détails associés.

**Why this priority**: Sans cette capacité, toute information échangée il y a plus de 15 messages est perdue pour l'assistant — l'utilisateur doit la lui répéter, ce qui dégrade fortement l'expérience.

**Independent Test**: (a) Insérer en base 50 messages historiques mentionnant un projet « panneaux solaires » et un fonds spécifique. (b) Démarrer une nouvelle conversation et poser la question « Tu te souviens du fonds pour mes panneaux solaires ? ». (c) Vérifier que l'outil de recherche est invoqué et retourne les bons messages, et que l'assistant cite correctement le fonds.

**Acceptance Scenarios**:

1. **Given** des messages anciens contenant les mots clés du projet, **When** l'utilisateur fait référence à un échange ancien (formules « tu te souviens », « la dernière fois », « il y a X temps »), **Then** l'assistant invoque l'outil de recherche d'historique et retourne 1 à 5 passages les plus pertinents.
2. **Given** une question dont la réponse est dans les 15 derniers messages, **When** l'utilisateur la pose, **Then** l'assistant N'invoque PAS l'outil (il utilise le contexte récent — économie de coût et de latence).
3. **Given** une recherche qui ne retourne aucun passage suffisamment pertinent, **When** l'outil est invoqué, **Then** l'assistant répond honnêtement « Je ne retrouve pas ce détail dans notre historique ».
4. **Given** un même tour LLM, **When** le LLM a déjà invoqué l'outil avec la même requête, **Then** la borne `MAX_TOOL_CALLS_PER_TURN = 5` (déjà en vigueur) limite naturellement les abus ; aucun cache court terme n'est introduit côté F12 (clarification Q5 : déféré post-MVP, à activer si SC-010 dépasse 30 % d'invocations).

---

### User Story 4 — Isolation stricte multi-tenant des historiques (Priority: P1)

Un utilisateur de l'account A fait référence à une conversation passée. Le système ne doit JAMAIS lui retourner un passage appartenant à l'account B, même si la similarité sémantique est plus forte. Cette isolation est garantie au niveau de la base de données (Row-Level Security) et non uniquement au niveau applicatif.

**Why this priority**: Fuite de données inter-clients = atteinte critique RGPD et perte de confiance. Aucun défaut ne doit transiter par l'applicatif uniquement (défense en profondeur via RLS).

**Independent Test**: Insérer 100 messages historiques pour account A et 100 messages historiques pour account B contenant tous le mot « panneaux solaires ». Faire une recherche d'historique sur la query « panneaux solaires » dans le contexte de l'account A. Vérifier qu'aucun message d'account B n'apparaît dans les résultats, même en bypass applicatif (test direct sur la requête SQL).

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté à l'account A, **When** il déclenche la recherche d'historique, **Then** la requête de base de données filtre les passages par `account_id = A` au niveau RLS PostgreSQL.
2. **Given** un message d'account B très similaire à la requête, **When** la recherche est exécutée, **Then** ce message N'apparaît PAS dans les résultats même si sa similarité cosinus est > 0.9.
3. **Given** plusieurs utilisateurs au sein du même account A, **When** un utilisateur de A fait référence à une conversation tenue par un autre utilisateur de A, **Then** la recherche peut retourner ce passage (les utilisateurs d'un même account partagent le contexte — règle Module 7.3 documentée).

---

### User Story 5 — Masquage des secrets avant indexation (Priority: P2)

Si un utilisateur tape par inadvertance un secret (mot de passe, clé API, numéro de carte bancaire, IBAN, email) dans le chat, ce contenu sensible ne doit PAS être stocké dans l'index de recherche sémantique. L'index ne contient que la version masquée du contenu (« [EMAIL] », « [TOKEN] », « [BANK]‑XXX »).

**Why this priority**: Conformité RGPD et minimisation des données : si un secret se retrouve dans l'index, il pourrait remonter dans une recherche future avec un risque d'exposition. Le masquage offre une défense en profondeur même si l'utilisateur ou le LLM commet une erreur.

**Independent Test**: Envoyer un message contenant les 4 motifs sensibles (email, IBAN, numéro de carte 16 chiffres, token Bearer). Vérifier dans la base de données que la version indexée du chunk contient les marqueurs `[EMAIL]`, `[BANK]`, `[CARD]`, `[TOKEN]` à la place des valeurs originales (le message original reste intact dans `messages.content`, seul l'index est masqué).

**Acceptance Scenarios**:

1. **Given** un message contenant `mon iban est FR76 1234 5678 9012 3456 78`, **When** le message est indexé, **Then** le chunk indexé contient `mon iban est [BANK]` (24 caractères masqués au minimum).
2. **Given** un message contenant un email, **When** le message est indexé, **Then** le chunk indexé contient `[EMAIL]` (le message brut original n'est pas modifié dans la table `messages`).
3. **Given** un message ne contenant aucun motif sensible, **When** il est indexé, **Then** le chunk est identique au message brut.

---

### User Story 6 — Suppression cascade lors d'une fermeture de compte (Priority: P2)

Quand un account est purgé (cas RGPD F05 — droit à l'oubli avec délai 30 jours), toutes les données conversationnelles associées doivent disparaître : les conversations, les messages, les chunks indexés, et les checkpoints LangGraph (qui contiennent le state des conversations en cours). Aucun résidu indexé ne doit subsister.

**Why this priority**: Obligation légale RGPD — le droit à l'effacement doit être complet, y compris les structures techniques (checkpoints, embeddings).

**Independent Test**: Créer un account avec 50 messages, déclencher la suppression de l'account, vérifier qu'aucune ligne ne reste dans `conversations`, `messages`, `message_chunks`, ni dans les tables de checkpoint LangGraph (filtrées par `thread_id` rattaché à un user de l'account purgé).

**Acceptance Scenarios**:

1. **Given** un account avec des conversations et un index sémantique populé, **When** l'account est supprimé, **Then** la table des chunks indexés ne contient plus aucune ligne pour cet account.
2. **Given** un account avec des checkpoints en mémoire LangGraph, **When** l'account est supprimé, **Then** les enregistrements de checkpoint correspondants sont également effacés.
3. **Given** une suppression d'un seul utilisateur d'un account multi-utilisateurs, **When** l'account reste actif, **Then** les conversations et chunks de l'account sont préservés (la suppression de compte ne casse pas les autres utilisateurs).

---

### Edge Cases

- **Conversation très courte** : moins de 15 messages → toute la conversation est chargée, sans padding artificiel ni erreur.
- **Message très long** (> 4 000 caractères, ex. coller d'un extrait de document) : le message est découpé en plusieurs chunks pour rester sous la limite de tokens d'embedding (8 191 tokens), avec recouvrement minimal pour préserver la cohérence sémantique.
- **Embedding qui échoue** (timeout API, panne réseau) : le message est sauvegardé en base mais marqué comme « non indexé » ; un mécanisme de rattrapage (best-effort, prévu pour intégration scheduler ultérieur) le réessaie ; la réponse à l'utilisateur n'est PAS bloquée.
- **Recherche qui retourne un résultat avec faible similarité** (< 0.6) : ce résultat n'est pas remonté ; mieux vaut « je ne sais pas » qu'un faux positif.
- **Utilisateur d'un même account partagent les conversations** : c'est attendu (règle Module 7.3) ; documenté dans l'aide en ligne.
- **Message contenant uniquement un secret** (ex. l'utilisateur colle son mot de passe seul) : après masquage, le chunk peut devenir vide (« [TOKEN] ») — il est quand même stocké pour cohérence d'audit, mais il ne pourra rien remonter en recherche utile.
- **Question interactive (F18) en attente lors d'un reboot** : le checkpoint correspondant doit aussi être restauré, faute de quoi la résolution de la question échoue.
- **Migration depuis l'existant** : les conversations actuellement en cours (avant déploiement F12) basculent du stockage volatile au stockage persistant ; les nouvelles règles s'appliquent à partir du déploiement, sans migration rétroactive obligatoire des messages anciens (ils seront indexés au fil de l'eau si réécrits).
- **Indisponibilité temporaire du service d'embedding** : la conversation continue normalement ; l'index sera complété en différé.
- **Compteur d'invocations de l'outil de recherche** : si un utilisateur multiplie les références au passé dans le même tour, l'outil ne doit pas être invoqué plus de 5 fois consécutives (limite déjà imposée par MAX_TOOL_CALLS_PER_TURN).

## Requirements *(mandatory)*

### Functional Requirements

#### Persistance des conversations

- **FR-001**: Le système MUST persister l'état complet d'une conversation (messages, module actif, état des questions interactives, position dans un workflow ESG/carbone/financement) dans une base de données durable, de telle sorte qu'un redémarrage du serveur n'entraîne aucune perte.
- **FR-002**: La restauration de l'état d'une conversation après redémarrage MUST être transparente pour l'utilisateur : aucune action ne lui est demandée, et le premier nouveau message après redémarrage est traité avec le contexte complet.
- **FR-003**: Le système MUST conserver les états de conversation pendant au moins 30 jours d'inactivité avant éventuelle purge automatique. La purge nocturne sera intégrée à un planificateur ultérieur (F19) ; F12 expose simplement la fonction de purge appelable manuellement et documente sa fréquence cible.
- **FR-004**: Le mécanisme de persistance MUST être compatible avec l'asynchronicité du backend (pas de blocage de l'event loop pendant les écritures).

#### Chargement du contexte récent

- **FR-005**: À chaque tour de conversation, le système MUST injecter dans le contexte du LLM les 15 derniers messages bruts de la conversation courante (alternance utilisateur / assistant), classés du plus ancien au plus récent.
- **FR-006**: Si la conversation contient moins de 15 messages, le système MUST charger tous les messages disponibles, sans erreur ni padding.
- **FR-007**: Le système MUST continuer à charger les 3 résumés de conversations antérieures (mécanisme existant), en complément des 15 messages bruts.
- **FR-008**: Chaque message chargé en contexte MUST être annoté avec un horodatage relatif lisible. Format français court (clarification Q4) :
  - âge < 1 minute → « à l'instant »
  - âge < 60 minutes → « il y a N minutes »
  - âge < 24 heures → « il y a N heures »
  - âge < 48 heures → « hier »
  - âge ≤ 30 jours → « il y a N jours »
  - âge > 30 jours → « le DD/MM/YYYY »
  
  Le rendu est calculé au moment du chargement (pas figé à la création du message), pour rester cohérent quand l'utilisateur reprend la conversation après un long délai.

#### Indexation sémantique de l'historique

- **FR-009**: Pour chaque message créé (utilisateur ou assistant), le système MUST déclencher l'indexation sémantique du contenu en arrière-plan via une tâche `asyncio.create_task` détachée (clarification Q1), garantissant l'absence de blocage de la réponse utilisateur. La référence à la tâche est conservée pour la durée de vie du request scope afin d'éviter qu'elle soit garbage-collectée prématurément. Aucune dépendance Celery n'est introduite au MVP ; l'API du service mémoire reste compatible avec une bascule ultérieure vers une queue distribuée (post-MVP).
- **FR-010**: L'indexation MUST stocker une représentation vectorielle du contenu permettant une recherche par similarité sémantique.
- **FR-011**: L'indexation MUST tolérer un échec ponctuel du service d'embedding : le message reste sauvegardé, l'index reste à compléter ultérieurement, l'utilisateur n'est pas impacté.
- **FR-012**: Avant indexation, le système MUST appliquer un masquage sur les motifs reconnus comme sensibles : adresses email, IBAN, numéros de carte bancaire (Luhn), tokens d'authentification. Le masquage est server-side et obligatoire.
- **FR-013**: Le masquage MUST conserver la structure du texte autour du motif masqué (le mot remplacé par un marqueur générique, ex. `[EMAIL]`, `[BANK]`, `[CARD]`, `[TOKEN]`), pour ne pas casser la sémantique des phrases.
- **FR-014**: Le masquage NE MUST PAS modifier le message original stocké dans la table des messages — il s'applique uniquement à la version indexée (chunk).
- **FR-015**: Stratégie de chunking (clarification Q2) :
  - Si la longueur du message est ≤ 6 000 caractères, le système MUST créer exactement un chunk dont le texte est identique au message masqué (pas de découpe).
  - Si la longueur excède 6 000 caractères, le système MUST découper le message par paragraphes (séparateur double saut de ligne) en cibles de 6 000 caractères au plus, avec un recouvrement de 200 caractères entre chunks consécutifs pour préserver la continuité sémantique.
  - Chaque chunk porte un attribut `chunk_index` entier ≥ 0 ; le chunk d'un message court a `chunk_index = 0`.
  - Aucune découpe ne franchit le milieu d'un mot ; en dernier recours (paragraphe unique > 6 000 caractères), la découpe se fait à la frontière de phrase, puis à la frontière de mot.

#### Recherche d'historique (tool LLM)

- **FR-016**: Le système MUST exposer aux modèles LangGraph un outil de recherche dans l'historique conversationnel (`recall_history`) accessible depuis tous les nœuds spécialisés (chat général, ESG, carbone, financement, candidature, crédit, plan d'action).
- **FR-017**: L'outil MUST accepter quatre paramètres (clarification Q3) :
  - `query` : requête textuelle libre (obligatoire).
  - `max_results` : nombre maximal de résultats (défaut 5, plafonné à 10 — hard cap server-side).
  - `since` : date `ISO 8601` optionnelle (limite temporelle inférieure ; tous les chunks `created_at >= since`).
  - `include_current_conversation` : booléen optionnel, défaut `false`. Quand `false`, la conversation courante est exclue (les 15 derniers messages sont déjà dans le contexte récent). Quand `true`, la conversation courante est incluse — utile lorsque l'utilisateur cherche un détail au-delà de la fenêtre de 15 messages dans la même conversation.
- **FR-018**: L'outil MUST retourner uniquement des résultats dont la similarité sémantique avec la requête dépasse un seuil minimal (par défaut 0,6 sur l'échelle cosinus). Les résultats sous le seuil ne sont pas remontés.
- **FR-019**: Pour chaque résultat, l'outil MUST retourner : l'identifiant du message d'origine, le rôle (utilisateur / assistant), le contenu du chunk, l'horodatage, le titre de la conversation, et le score de similarité.
- **FR-020**: L'outil MUST filtrer les résultats par account de l'utilisateur courant. Cette restriction est garantie par la Row-Level Security au niveau de la base de données (défense en profondeur), pas uniquement par le code applicatif.
- **FR-021**: La description de l'outil (docstring) MUST guider explicitement le LLM : à invoquer quand l'utilisateur fait référence à un échange ancien ou que le contexte récent est insuffisant ; à NE PAS invoquer si l'information est déjà dans les 15 derniers messages ou dans le profil entreprise.

#### Multi-tenant et sécurité

- **FR-022**: Toute nouvelle ligne dans la table d'index MUST contenir un identifiant d'account non nul, FK vers la table des accounts, avec contrainte d'intégrité référentielle.
- **FR-023**: La table d'index MUST être protégée par Row-Level Security PostgreSQL avec deux policies : (a) accès complet aux administrateurs ; (b) accès restreint à `account_id = current_setting('app.current_account_id')` pour les utilisateurs PME.
- **FR-024**: Toutes les requêtes d'écriture / lecture sur la table d'index MUST se faire au sein d'une session SQL dans laquelle la variable de session `app.current_account_id` est positionnée correctement (via le helper RLS commun déjà en place pour F02).

#### Suppression et conformité RGPD

- **FR-025**: La suppression d'un account MUST entraîner la suppression cascade des conversations, des messages, des chunks indexés, et des enregistrements de checkpoint correspondants. Aucune donnée résiduelle ne doit subsister.
- **FR-026**: Le système MUST exposer une fonction utilitaire (callable depuis F05) capable de purger l'ensemble des artefacts liés à un account donné en une seule opération atomique.
- **FR-027**: La suppression d'un seul utilisateur d'un account multi-utilisateurs ne doit PAS déclencher la suppression des conversations partagées de l'account.

#### Observabilité et monitoring

- **FR-028**: Le système MUST journaliser le taux d'invocation de l'outil de recherche d'historique (par utilisateur, par conversation, par jour) pour permettre un ajustement du prompt si le LLM en abuse.
- **FR-029**: Le système MUST journaliser le pourcentage de messages effectivement indexés (succès vs échec d'embedding) pour permettre de détecter les pannes silencieuses du service d'embedding.
- **FR-030**: La latence d'overhead introduite par F12 sur le tour de conversation principal MUST rester inférieure à 100 ms au 99ᵉ percentile (mesurée entre l'instant où le serveur reçoit le message utilisateur et l'instant où il commence à répondre).

### Key Entities *(include if feature involves data)*

- **Chunk d'historique conversationnel (`message_chunks`)** : représente un fragment d'un message indexé pour la recherche sémantique. Attributs principaux : identifiant unique, account propriétaire, conversation et message d'origine, texte (potentiellement masqué) du fragment, représentation vectorielle (1536 dimensions), rôle (utilisateur / assistant), horodatage, `chunk_index` (entier ≥ 0 ; 0 pour les messages courts à chunk unique, 0..N pour les messages longs découpés). Relation : appartient à un message, qui appartient à une conversation, qui appartient à un account. Cardinalité 1 message → N chunks (typiquement 1, jusqu'à plusieurs dizaines pour un message exceptionnellement long).
- **Checkpoint de conversation LangGraph** : représente l'état complet d'une conversation à un instant donné (messages, module actif, état des outils en cours, etc.). Géré entièrement par la bibliothèque LangGraph (tables `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` créées automatiquement). Indexé par `thread_id` (qui correspond à `conversation_id` dans notre code).
- **Message** (existant) : pas d'attribut nouveau, mais devient la source de l'indexation au fil de l'eau via un hook après-insertion.
- **Account** (existant, F02) : devient le pivot d'isolation multi-tenant ; toute nouvelle ligne d'index est rattachée à un account via FK avec RLS active.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des conversations en cours survivent à un redémarrage du processus serveur (mesuré via test E2E qui démarre une conversation, redémarre, reprend).
- **SC-002**: Les 15 derniers messages bruts d'une conversation sont systématiquement présents dans le contexte du LLM dès qu'au moins 15 messages existent (mesuré sur 100 % d'un échantillon de 50 conversations test).
- **SC-003**: La recherche sémantique sur l'historique retourne le bon passage dans 90 % des cas où une référence claire à un échange ancien est faite (mesurée sur un jeu de 30 cas test : référence par mot-clé, par projet, par fonds, par date approximative).
- **SC-004**: Aucun chunk d'un account A ne remonte dans une recherche initiée par un utilisateur d'un account B (mesuré sur 100 % de 50 cas test multi-tenant ; tolérance 0).
- **SC-005**: 100 % des motifs sensibles (email, IBAN, carte bancaire valide Luhn, token Bearer) présents dans un message sont masqués dans le chunk indexé (mesuré sur un jeu de 50 cas test couvrant les variations de formatage).
- **SC-006**: La latence d'overhead introduite par la persistance + l'indexation reste sous 100 ms au 99ᵉ percentile (mesurée en production via journaux structurés).
- **SC-007**: Au moins 95 % des messages créés finissent indexés (mesuré sur une fenêtre glissante de 24 h ; en deçà, alerte automatique).
- **SC-008**: La suppression d'un account purge 100 % des artefacts conversationnels associés (vérifié par un test E2E qui crée puis supprime un account et compte les lignes résiduelles dans toutes les tables impactées).
- **SC-009**: La couverture de tests automatisés sur le code introduit par F12 (services mémoire, outils LangChain, hook d'indexation) est ≥ 80 %.
- **SC-010**: Le taux d'invocation de l'outil de recherche d'historique reste sous 30 % des tours de conversation en moyenne (au-delà, signe d'abus du LLM, ajustement de prompt requis).

## Assumptions

- L'infrastructure F02 (multi-tenant + Row-Level Security PostgreSQL) est déjà en place : F12 réutilise le helper de session RLS (`set_rls_context`) et les patterns d'`account_id` FK existants.
- La base PostgreSQL dispose de l'extension `pgvector` activée (déjà installée pour les modules documents et financement).
- Le service d'embedding (`text-embedding-3-small` via OpenRouter) reste disponible et économique (coût négligeable à l'échelle MVP : 1 000 PME × 10 messages / jour ≈ 30 $ / an).
- Les conversations historiques antérieures au déploiement F12 ne sont pas indexées rétroactivement par cette feature — elles le seront opportunistiquement si l'utilisateur les rouvre. Une éventuelle commande de réindexation massive est hors scope (post-MVP).
- Les utilisateurs au sein d'un même account voient les conversations des autres utilisateurs du même account (règle métier Module 7.3 : un account = une PME = une équipe partagée). Pas de cloisonnement intra-account.
- La purge automatique des checkpoints inactifs > 30 jours sera prise en charge par la feature « scheduler & jobs périodiques » à venir (F19). F12 expose la fonction de purge mais ne planifie pas son exécution.
- Les références au profil entreprise, projets, scores ESG/carbone/crédit, candidatures restent rechargées au tour LLM via les tools dédiés F12 → fournit la base, l'enrichissement complet du contexte (tool `get_user_dashboard_summary` étendu) est hors scope strict de cette feature mais peut être amorcé.
- Le frontend n'a pas besoin d'évolution majeure : la mémoire est une responsabilité backend. Une indication visuelle facultative « recherche dans l'historique » peut s'appuyer sur l'événement SSE `tool_call_start` déjà existant pour les autres outils.
- Le masquage des secrets repose sur un ensemble de regex simples (motifs courants : email RFC 5322 simplifié, IBAN, séquences de 13–19 chiffres validées Luhn, tokens type Bearer / API key courants). Les cas exotiques peuvent passer ; la défense en profondeur est combinée avec la consigne explicite à l'utilisateur (« ne partagez jamais de secrets ») prévue par F05.
- Le suivi de la qualité des recommandations « via recall_history » se fait par journaux et observation manuelle pendant les premiers jours ; un tableau de bord dédié peut venir post-MVP.
