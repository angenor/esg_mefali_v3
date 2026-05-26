# Feature Specification: F25 — Migration des Embeddings vers Voyage AI

**Feature Branch**: `043-voyage-embeddings-migration`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "F25 — Migration embeddings : OpenAIEmbeddings → VoyageAIEmbeddings (modèle voyage-3.5, 1024 dim, multilingue)"

## Clarifications

### Session 2026-05-08

- Q: Posture vie privée vis-à-vis de Voyage AI (fournisseur US, documents PME confidentiels) → A: Accepter Voyage AI tel quel et documenter la posture (DPA standard + masquage F12 existant) dans `docs/embeddings-voyage.md`. Pas de gating supplémentaire (consentement, masquage étendu, revue DPO).
- Q: Stratégie de ré-embedding des données existantes après migration → A: Lazy auto sur les 4 tables (déclenchement au prochain accès lecture/recherche pour `embedding IS NULL`) + script admin opt-in `python -m app.scripts.reembed_all` documenté dans `docs/embeddings-voyage.md`. Aucun cron ni worker background introduit dans cette feature.
- Q: Comportement face aux pannes ou rate limits Voyage AI (retries, timeout, circuit breaker) → A: 1 retry avec backoff exponentiel (défauts du SDK) + timeout 10 s par requête, puis embedding `NULL` si échec, log warning. Pas de circuit breaker applicatif, pas de queue de retry persistante. Le ré-embedding lazy joue le rôle de retry long-terme.
- Q: Vérification empirique de la qualité multilingue voyage-3.5 (SC-002 gating ou non) → A: Eval manuelle smoke test **non-gating**. 10 requêtes francophones jouées une fois avant déclaration de done, résultat consigné dans `docs/embeddings-voyage.md`. Un échec >2/10 doit déclencher un suivi (issue de re-calibration) mais ne bloque pas le merge.

### Corrections issues de la phase Plan (2026-05-08)

Lors de la phase `/speckit.plan` (research.md R1 + R10 + R11), une vérification du code source a révélé que la liste des tables vectorielles dans la spec initiale était **inexacte**. Corrections appliquées ci-dessous (FR-007a, FR-008, FR-010, Edge Cases, Key Entities, SC-001, SC-006, SC-007, Assumptions) :

- Tables vectorielles **réelles** : `message_chunks`, `document_chunks`, `financing_chunks` (3 tables, pas 4).
- `documents.embedding` et `funds.embedding` n'existent pas dans le schéma — c'étaient des références incorrectes aux tables `document_chunks` et `financing_chunks` respectivement.
- Bug schéma pré-existant identifié : `financing_chunks.embedding` était déclarée `TEXT` en migration 008 alors que le modèle SQLAlchemy déclare `Vector(1536)`. F25 corrige opportunément cette incohérence en promouvant la colonne à `vector(1024)` + création de l'index HNSW manquant.
- SC-006 reformulé pour utiliser un marker pytest `@pytest.mark.embeddings` plutôt que des chemins de dossier qui n'existaient pas (`backend/tests/financing/`, `backend/tests/documents/`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Mémoire conversationnelle restaurée pour la PME (Priority: P1)

Une PME utilisatrice du chat ESG Mefali revient sur la plateforme après plusieurs jours et pose une question relative à un échange précédent (par exemple : « rappelle-moi ce que tu m'avais conseillé sur mon bilan carbone »). L'agent doit récupérer le contexte sémantique des conversations passées et y faire référence dans sa réponse, comme prévu par la fondation F12 (mémoire contextuelle pgvector).

**Why this priority** : la mémoire conversationnelle est aujourd'hui silencieusement dégradée (clé OpenRouter passée à un endpoint OpenAI ou OpenRouter sans embeddings). C'est le défaut le plus visible côté utilisateur, et le seul scénario où la valeur métier promise par F12 est totalement absente. Le restaurer débloque toute la promesse « conseiller qui se souvient ».

**Independent Test** : depuis un compte PME neuf, échanger 3-4 messages substantiels sur un sujet (ex : projet solaire), démarrer une nouvelle conversation, demander un rappel sémantique du sujet — l'agent doit citer ou résumer correctement le contexte antérieur via l'outil `recall_history`.

**Acceptance Scenarios** :

1. **Given** une PME a échangé des messages avec embeddings actifs, **When** elle pose une question sémantiquement liée dans une nouvelle conversation, **Then** l'outil `recall_history` retourne au moins un extrait pertinent et l'agent l'intègre à sa réponse.
2. **Given** l'environnement n'a aucune clé d'embedding configurée, **When** un utilisateur envoie un message, **Then** le chat continue de fonctionner (mode dégradé), aucun message d'erreur n'est exposé à l'utilisateur, et un avertissement clair est journalisé côté serveur.
3. **Given** un message contenant des secrets (token, IBAN, carte), **When** il est indexé, **Then** les secrets sont masqués avant embedding et stockage (continuité du comportement F12 existant).

---

### User Story 2 — Recherche sémantique pertinente en français pour fonds et documents (Priority: P2)

Un utilisateur explore la page `/financing` ou pose une question RAG sur ses documents uploadés. La recherche sémantique des fonds (12 fonds GCF/FEM/BOAD/BAD/SUNREF/FNDE/…) et des chunks de documents doit retourner des résultats correctement classés selon la pertinence sémantique en français, langue principale du public PME UEMOA/CEDEAO.

**Why this priority** : la recherche sémantique est un différenciateur produit (matching projet-financement, RAG documentaire). Sans embeddings fonctionnels, le ranking se rabat sur du keyword matching basique, qui dégrade fortement la pertinence pour des requêtes nuancées. Priorité P2 car le matching de fonds dispose de filtres structurés (pays/secteur/montant) qui amortissent partiellement la perte.

**Independent Test** : seeder le catalogue de fonds, lancer une recherche en français nuancée (ex : « financement pour valoriser les déchets organiques en énergie au Sénégal »), vérifier que les fonds les plus pertinents (ex : SUNREF, GCF déchets) sont retournés en tête de classement.

**Acceptance Scenarios** :

1. **Given** le catalogue de fonds est seedé avec embeddings 1024d, **When** un utilisateur soumet une requête sémantique en français, **Then** les top 5 résultats incluent les fonds dont la thématique correspond au-delà de simples mots-clés.
2. **Given** un document PDF a été uploadé et chunké, **When** l'utilisateur pose une question RAG, **Then** les chunks sémantiquement les plus proches sont récupérés et intégrés à la réponse de l'agent.

---

### User Story 3 — Migration idempotente avec opération continue pour l'admin (Priority: P3)

Un administrateur déploie la migration en production. Il exécute la migration Alembic, observe les logs, vérifie que l'application reste opérationnelle pendant que les nouvelles données se ré-embeddent paresseusement (lazy), et peut rejouer la migration sans effet secondaire si elle échoue à mi-chemin.

**Why this priority** : permet un déploiement maîtrisé, mais ne bloque pas la valeur utilisateur si la migration n'est pas idéalement orchestrée. Le rollback Alembic est un filet de sécurité utilisé en exception, pas en routine.

**Independent Test** : sur PostgreSQL local avec données factices (~10 messages, ~10 fonds, ~5 documents), exécuter `alembic upgrade head`, puis `alembic downgrade -1`, puis `alembic upgrade head` — chaque étape doit réussir sans erreur, et l'application doit répondre normalement après chaque transition.

**Acceptance Scenarios** :

1. **Given** une base contient des embeddings 1536d existants, **When** la migration `up` s'exécute, **Then** les colonnes `embedding` des **3 tables** (`message_chunks`, `document_chunks`, `financing_chunks`) passent à 1024d, leurs valeurs sont vidées (TRUNCATE des colonnes, pas des lignes), les index HNSW sont recréés (et nouvellement créé pour `financing_chunks` qui n'en avait pas — bug schéma migration 008 corrigé), et aucune ligne métier n'est perdue.
2. **Given** la migration `up` a été appliquée, **When** un appel sémantique sur une donnée non encore ré-embeddée a lieu, **Then** soit le ré-embedding est déclenché paresseusement, soit le résultat retourne une liste vide proprement (pas d'erreur 500).
3. **Given** la migration a été déployée, **When** l'admin lance `alembic downgrade`, **Then** les colonnes reviennent à 1536d (avec TRUNCATE symétrique) et l'application revient à l'état antérieur sans perte de lignes.

---

### Edge Cases

- **Clé `VOYAGE_API_KEY` absente ou vide** : le système log un avertissement clair (« Aucune clé d'embedding configurée. Définir VOYAGE_API_KEY dans .env. ») et continue à servir le chat sans embeddings (mode dégradé), sans `AttributeError` ni 500.
- **Clé `VOYAGE_API_KEY` présente mais invalide / Voyage AI temporairement indisponible** : l'erreur est capturée best-effort, l'embedding échoue silencieusement pour ce message, le chat poursuit, la ligne `message_chunks` est créée avec `embedding NULL` (pour ré-essai ultérieur via index partiel `pending_embedding`).
- **Tests SQLite in-memory** : les colonnes `embedding` sont représentées en `Text` (et non `Vector`) pour la compatibilité SQLite — la migration Alembic et les modèles ne doivent pas casser cette branche.
- **Données 1536d existantes au moment du déploiement** : les valeurs sont vidées (TRUNCATE de la colonne uniquement) sans suppression de lignes ; les utilisateurs ne perdent aucune conversation, document ou fonds, seulement leur capacité de recherche sémantique sur ces lignes jusqu'au ré-embedding lazy ou batch.
- **Re-embedding lazy partiel** : un utilisateur peut interagir avec une partie de ses données déjà ré-embeddées et une autre qui ne l'est pas — la fonction de recherche doit gérer les `embedding IS NULL` sans planter.
- **Conflit de dimension à l'insertion** : si du code legacy tente d'écrire un vecteur 1536d dans une colonne 1024d post-migration, pgvector lève une erreur — celle-ci doit être capturée et journalisée comme bug à corriger, pas masquer un échec silencieux.
- **RLS multi-tenant F02** : les nouvelles colonnes embedding héritent des policies existantes ; aucune fuite cross-tenant ne doit être possible pendant ou après la migration.

## Requirements *(mandatory)*

### Functional Requirements

#### Capacités d'embedding et de recherche sémantique

- **FR-001** : Le système DOIT générer les embeddings de tous les contenus indexés (messages chat, chunks de documents, fonds de financement) via un fournisseur unique d'embeddings dédié, distinct du fournisseur LLM principal.
- **FR-002** : Le système DOIT stocker chaque embedding dans une colonne vectorielle de dimension uniforme et compatible avec le fournisseur retenu.
- **FR-003** : Le système DOIT permettre la recherche sémantique multilingue (au minimum français + anglais), avec un niveau de pertinence acceptable pour des requêtes en français nuancées émises par des PME UEMOA/CEDEAO.
- **FR-004** : Lorsqu'un nouveau message utilisateur est créé, le système DOIT déclencher l'indexation sémantique (chunking + embedding) en best-effort sans bloquer la réponse du chat.
- **FR-005** : L'outil global `recall_history` DOIT retourner les extraits de conversations passées sémantiquement les plus proches d'une requête, restreints au compte de l'utilisateur appelant.

#### Comportement en mode dégradé

- **FR-006** : Si la clé d'embedding n'est pas configurée, le système DOIT continuer à servir le chat et toutes les fonctionnalités non sémantiques sans exposer d'erreur à l'utilisateur final, et DOIT journaliser un avertissement clair côté serveur identifiant la variable d'environnement à définir.
- **FR-007** : Si l'API d'embedding renvoie une erreur transitoire pour un contenu donné, le système DOIT enregistrer la ligne avec un embedding `NULL` (statut « en attente ») et permettre un nouvel essai ultérieur, sans interrompre la session utilisateur.
- **FR-007c** : Le système DOIT exécuter au plus **1 retry** avec backoff exponentiel via les défauts du SDK fournisseur, et appliquer un **timeout de 10 secondes** par requête d'embedding. Au-delà → `embedding NULL` + warning log. Aucun circuit breaker applicatif, aucune queue de retry persistante n'est introduite par cette feature ; le ré-embedding lazy (FR-007a) couvre la reprise long-terme.
- **FR-007a** : Le système DOIT déclencher le ré-embedding paresseux (lazy) sur les 3 tables vectorielles réelles (`message_chunks`, `document_chunks`, `financing_chunks`) lors du prochain accès en lecture ou recherche d'une ligne dont l'embedding est `NULL`, sans nécessiter d'intervention admin pour les utilisateurs actifs.
- **FR-007b** : Le projet DOIT fournir un script administratif opt-in `python -m app.scripts.reembed_all` permettant de forcer le ré-embedding batch de toutes les lignes `embedding IS NULL` post-migration. Son exécution n'est pas gating ; elle est documentée dans `docs/embeddings-voyage.md`. Aucun cron périodique ni worker background n'est introduit par cette feature.

#### Migration de schéma

- **FR-008** : Le système DOIT fournir une migration de schéma idempotente qui ajuste les 3 tables vectorielles existantes (`message_chunks`, `document_chunks`, `financing_chunks`) à la nouvelle dimension d'embedding sans suppression de lignes métier. Pour `financing_chunks`, la colonne `embedding` est promue de `TEXT` (état réel migration 008) à `vector(1024)` — corrigeant un bug schéma pré-existant.
- **FR-009** : La migration DOIT préserver l'intégralité des données métier (lignes, FK, RLS, autres colonnes) ; seules les valeurs de la colonne d'embedding sont vidées.
- **FR-010** : La migration DOIT recréer les index de recherche vectorielle (HNSW cosinus) pour la nouvelle dimension, sans dégrader la sémantique de RLS multi-tenant existante. Un nouvel index HNSW `ix_financing_chunks_embedding_hnsw` DOIT être créé pour `financing_chunks` (qui n'en avait pas en production).
- **FR-011** : La migration DOIT exposer un chemin de rollback (downgrade) symétrique ramenant les colonnes à leur dimension antérieure (avec TRUNCATE équivalent) sans perte de lignes.

#### Configuration & secrets

- **FR-012** : La configuration applicative DOIT exposer trois paramètres typés et validés pour le nouveau fournisseur d'embedding : la clé API, le nom du modèle (limité à un ensemble fini de valeurs supportées), et la dimension du vecteur (constante du modèle retenu).
- **FR-013** : Le système DOIT charger la clé d'embedding depuis l'environnement (et non du code source), et la documentation `.env.example` (racine et backend) DOIT refléter la nouvelle variable et son lien fournisseur.

#### Compatibilité

- **FR-014** : Le mapping de configuration LLM principal (passerelle OpenRouter) DOIT rester strictement inchangé : seul le pipeline embeddings est concerné par cette feature.
- **FR-015** : Le code de la branche tests SQLite in-memory DOIT continuer à passer sans nécessiter de service vectoriel externe.
- **FR-016** : Le système NE DOIT plus contenir aucune dépendance d'exécution sur l'ancien SDK d'embedding ; les imports correspondants doivent disparaître du code applicatif et la dépendance peut être retirée du gestionnaire de paquets.

#### Documentation et opérations

- **FR-017** : Le projet DOIT publier un document opérationnel `docs/embeddings-voyage.md` décrivant : politique de fournisseur retenu, dimension cible, procédure de re-embedding (lazy + script `reembed_all`), estimation de coût, posture vie privée vis-à-vis du fournisseur (résidence US des données, DPA standard, masquage F12 actif sur les messages, justification absence de masquage pour fonds/documents), ET le jeu de 10 requêtes francophones de baseline avec leurs résultats top-3 (matériel SC-002).
- **FR-018** : Les fondations transverses pertinentes (CLAUDE.md, F12) DOIVENT être mises à jour pour refléter la nouvelle dimension et le nouveau fournisseur.

### Key Entities *(include if feature involves data)*

- **Embedding de message** (`message_chunks.embedding`) : représentation vectorielle d'un chunk de message conversationnel (≤ 6000 caractères, overlap 200), masqué pour secrets, scopé par compte (RLS) et par conversation. Sert l'outil `recall_history` (mémoire F12).
- **Embedding de chunk de document** (`document_chunks.embedding`) : représentation vectorielle d'un fragment de document uploadé. Sert le RAG documentaire (F04 ESG, financing, etc.).
- **Embedding de chunk financing** (`financing_chunks.embedding`) : représentation vectorielle d'un chunk descriptif d'un fonds OU d'un intermédiaire (discriminator `source_type`). Sert la recherche sémantique sur la page `/financing` et le matching projet-financement. ⚠️ Cette colonne était stockée en `TEXT` en production suite à un défaut de la migration 008 ; F25 la promeut à `vector(1024)` et crée l'index HNSW manquant.
- **Configuration fournisseur d'embedding** : triplet (clé API, modèle, dimension), expose le contrat avec le fournisseur retenu — accessible à tous les services applicatifs qui produisent ou consomment des vecteurs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : 100 % des nouvelles conversations utilisateur déclenchent la création d'embeddings de dimension 1024 dans `message_chunks` ; idem pour les nouveaux chunks de documents (`document_chunks`) et les chunks financing ré-embeddés (`financing_chunks`). Vérifiable par `SELECT vector_dims(embedding) FROM <table> WHERE embedding IS NOT NULL` sur les 3 tables — toutes valeurs DOIVENT retourner 1024.
- **SC-002** : Sur un échantillon de 10 requêtes de rappel sémantique en français issues du parcours PME, l'outil `recall_history` retrouve l'extrait pertinent dans le top 3 dans au moins 8 cas sur 10. **Vérification non-gating** : eval manuelle exécutée une fois avant déclaration de done par l'équipe, jeu de requêtes + résultats consignés dans `docs/embeddings-voyage.md` à titre de baseline. Un échec >2/10 déclenche une issue de re-calibration mais ne bloque pas le merge de cette feature.
- **SC-003** : 0 import résiduel de l'ancien SDK d'embedding dans le code applicatif (`grep` ciblé doit retourner 0 résultat dans `backend/app/`).
- **SC-004** : Le scénario `up` → `down` → `up` de la migration Alembic réussit sans erreur sur PostgreSQL local en moins de 30 secondes pour une base de test (~100 lignes par table vectorielle).
- **SC-005** : Avec la clé d'embedding non configurée, 100 % des messages utilisateur reçoivent une réponse du chat (mode dégradé) ; aucune erreur HTTP 5xx n'est levée et l'avertissement attendu apparaît dans les logs du backend.
- **SC-006** : La suite de tests marquée `@pytest.mark.embeddings` passe à 100 % via `pytest -m embeddings -v`. Le marker est apposé sur tous les tests touchés par F25 dans `backend/tests/memory/` (test_service, test_recall_history_tool, nouveaux test_embeddings_client) ainsi que sur les tests `tests/test_financing_*.py`, `tests/test_document_embeddings.py`, `tests/test_tools/test_financing_tools.py`, `tests/test_tools/test_document_tools.py`, et le nouveau `tests/migrations/test_043_embeddings_voyage_dim.py`. Tests préexistants flagués comme bugs séparés (cf. `test_hook_no_op_without_event_loop`) sont exclus du périmètre F25.
- **SC-007** : La migration ne supprime aucune ligne dans les 3 tables vectorielles concernées (`message_chunks`, `document_chunks`, `financing_chunks`) ; vérifiable par comparaison de `COUNT(*)` avant/après migration sur PostgreSQL local.
- **SC-008** : Les coûts d'embedding journaliers en dev/staging restent en dessous de 1 USD pour un usage normal, conformément au tarif du modèle retenu.

## Out of Scope

- Migration des modèles LLM (génération de texte) : le LLM continue de passer par OpenRouter, seul le pipeline embeddings change.
- Re-calibration du seuil de similarité (actuellement 0.6 dans `search_history`) : laissé pour une feature ultérieure.
- Re-embedding rétroactif batch des données historiques : le lazy (au prochain accès) est suffisant pour le MVP, un script optionnel `python -m app.scripts.reembed_all` est documenté mais son exécution n'est pas gating.
- Fallback automatique multi-fournisseurs (Voyage → OpenAI → OpenRouter) : politique KISS, un seul fournisseur d'embedding.
- Adoption d'un modèle Voyage de plus grande dimension (variante 2048d) : voyage-3.5 (1024d) suffit pour la cible.
- Refactoring du code F12 hors de la fonction `_embeddings_model` (le bug 01 a déjà été corrigé séparément).
- Correction d'un bug isolé sur un test de hook (`test_hook_no_op_without_event_loop`) qui relève d'un autre périmètre (bug 04).

## Assumptions

- **Clé API déjà provisionnée** : `VOYAGE_API_KEY` est déjà présente dans le `.env` du projet (vérification : commentaire utilisateur). Le déploiement production présuppose qu'un secret équivalent est ou sera fourni au runtime.
- **Qualité multilingue voyage-3.5** : le modèle `voyage-3.5` (1024 dims) supporte nativement le français, l'anglais, l'espagnol, l'allemand et autres langues européennes ; sa qualité pour le public UEMOA/CEDEAO francophone est jugée suffisante pour le MVP, à valider empiriquement post-déploiement (SC-002).
- **Volumétrie actuelle limitée** : la fonctionnalité F12 étant cassée silencieusement depuis sa mise en production, peu d'embeddings 1536d exploitables existent en base. La perte par TRUNCATE est donc considérée comme négligeable.
- **Coût Voyage maîtrisé** : tarif estimé ~ 0,06 USD pour 1 M tokens sur voyage-3.5, le coût en environnement de développement reste de l'ordre du centime, et la consommation de production restera faible tant que la base utilisateur n'a pas explosé.
- **Re-embedding lazy acceptable** : le ré-embedding paresseux (au prochain accès lecture/recherche) couvre les 4 tables vectorielles. Le script admin opt-in `python -m app.scripts.reembed_all` est livré pour donner un levier de backfill complet à l'admin, mais son exécution n'est ni gating ni programmée (pas de cron). Aucun batch synchrone pré-déploiement n'est requis.
- **Compatibilité pgvector** : la base PostgreSQL 16 production supporte déjà pgvector ; la migration de dimension est une opération `ALTER COLUMN ... TYPE vector(1024)` standard avec recréation d'index HNSW, sans installation supplémentaire.
- **RLS et audit log inchangés** : les fondations F02 (multi-tenant + RLS) et F03 (audit log append-only) ne sont pas affectées : les colonnes d'embedding héritent des policies et triggers existants.
- **Pas d'impact sur F01 sourçage** : les outils `cite_source` / `search_source` / `flag_unsourced` continuent de fonctionner ; `search_source` consomme indirectement les embeddings et bénéficie de la migration sans modification de son interface.
- **PR séparé pour la migration Alembic** : le déploiement opérationnel privilégie un PR distinct pour la migration de schéma afin de pouvoir la rollbacker indépendamment du code applicatif si nécessaire.
- **Posture vie privée Voyage AI assumée** : les contenus indexés (messages chat masqués via F12, fragments de documents PME, descriptions de fonds) transitent vers un fournisseur d'embeddings tiers basé aux États-Unis. La posture retenue s'appuie exclusivement sur (1) le masquage F12 existant côté messages, (2) le DPA commercial standard du fournisseur et (3) la documentation explicite de cette posture dans `docs/embeddings-voyage.md`. Aucun consentement utilisateur supplémentaire ni revue DPO formelle n'est requis pour cette feature.
- **Correction opportuniste du bug schéma `financing_chunks`** : la migration 008 a créé `financing_chunks.embedding` en `TEXT` alors que le modèle SQLAlchemy déclare `Vector(1536)`. F25 promeut cette colonne à `vector(1024)` et crée l'index HNSW manquant. Cette correction est embarquée dans la migration 043 plutôt que traitée séparément, car elle est nécessaire pour que US2 (recherche sémantique fonds) soit satisfaite et qu'aucun comportement utilisateur ne reste incohérent.
