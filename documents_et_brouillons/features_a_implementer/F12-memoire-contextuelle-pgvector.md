# F12 — Mémoire Contextuelle Conforme : 15 Messages + pgvector + recall_history

**Module(s) source(s)** : Module 1.4 (Mémoire Contextuelle MVP simplifié)
**Priorité** : P1 — important pour la qualité et la continuité conversationnelle
**Dépendances** : F02 (multi-tenant)
**Estimation** : 1 sprint

## Contexte & motivation

Module 1.4 spécifie : « **15 derniers messages** conservés en clair dans le contexte. **Historique ancien** indexé via pgvector (RAG basique), récupéré à la demande via le tool `recall_history(query)`. »

**État actuel** :
- Le checkpointer LangGraph utilise `MemorySaver` (`backend/app/graph/graph.py:172-173`) — **en mémoire RAM** uniquement → toutes les conversations en cours **perdues au redémarrage** du serveur
- `_load_context_memory` (`backend/app/api/chat.py:383-396`) charge **uniquement les 3 derniers résumés** de conversations (via `chains/summarization`), pas les 15 derniers messages bruts
- pgvector existe pour `document_chunks` (Module 2) et `financing_chunks` (Module 3) mais **aucun embedding sur les `messages`**
- Aucun tool `recall_history(query)` (`grep "recall_history"` → 0 résultats)
- Synchronisation bidirectionnelle entre éditions manuelles et contexte LLM : OK partiellement (profil entreprise SSE temps réel), mais pas pour ESG/carbone/finance/credit

**Conséquences** :
- Reboot serveur = perte des contextes en cours (toutes conversations actives du jour)
- Perte de qualité conversationnelle : le LLM ne se souvient pas des 15 derniers échanges, juste 3 résumés synthétiques (perte de nuances)
- Conversations anciennes inutilisables : impossible pour le LLM de retrouver "tu m'avais dit il y a 2 mois que tu avais 50 employés"
- Pas de RAG sur les messages → contexte conversationnel limité

## User stories

- **PME** : « Quand je reprends une conversation après 3 jours, le LLM doit se souvenir des 15 derniers échanges en détail (pas juste un résumé), pour ne pas me reposer les mêmes questions. »
- **PME** : « Quand je dis "tu te souviens de mon projet X dont on parlait il y a 2 semaines ?", le LLM doit pouvoir invoquer `recall_history` pour retrouver les passages pertinents. »
- **PME** : « Quand je modifie manuellement mon profil entreprise, le LLM doit voir la nouvelle valeur dès le prochain message, pas continuer sur l'ancienne. »
- **Architecte plateforme** : « Le serveur peut redémarrer (deploy, crash, scale) sans perdre les conversations en cours des utilisateurs. »

## Périmètre fonctionnel

### Checkpointer persistant : `AsyncPostgresSaver`

Remplacer `MemorySaver` par `AsyncPostgresSaver` (déjà importé dans `backend/app/graph/checkpointer.py` mais non utilisé en prod).

Configuration :
- Connect string PostgreSQL (réutilise `DATABASE_URL`)
- Tables auto-créées par `langgraph` : `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`
- TTL : 30 jours (purge automatique des checkpoints inactifs > 30j via cron)

### Chargement des 15 derniers messages bruts

Dans `backend/app/api/chat.py:_load_context_memory` :
- Garder les 3 résumés de conversations précédentes (utile)
- **Ajouter** : les 15 derniers messages bruts de la conversation courante (charger depuis `messages` table) injectés dans le state LangGraph
- Format : alternance user/assistant en clair, avec timestamps relatifs ("il y a 2 minutes")

Si la conversation a moins de 15 messages, utiliser tous les messages disponibles.

### Embedding des messages anciens (RAG)

Pour chaque message créé (`Message.create`), déclencher async :
- Embed via `text-embedding-3-small` (déjà utilisé pour documents)
- Stocker dans nouvelle table `message_chunks` :
  - `id: UUID`
  - `account_id: UUID FK accounts.id` (multi-tenant F02)
  - `conversation_id: UUID`
  - `message_id: UUID FK messages.id`
  - `chunk_text: text` (le contenu du message, ou un chunk si très long)
  - `embedding: vector(1536)` (pgvector)
  - `created_at: datetime`
  - `role: enum('user', 'assistant')`

Index HNSW pour recherche rapide.

### Tool `recall_history(query)`

`backend/app/graph/tools/memory_tools.py` (nouveau fichier) :

```python
@tool(args_schema=RecallHistoryArgs)
async def recall_history(query: str, max_results: int = 5, since: date | None = None) -> list[MessageRecall]:
    """
    Récupère des messages anciens pertinents pour la query courante.
    
    Use when: l'utilisateur fait référence à un échange ancien ("tu te souviens", "il y a X temps")
    OU quand le contexte récent est insuffisant pour répondre à une question.
    
    Don't use when: l'info est dans les 15 derniers messages OU dans le profil entreprise/projets injectés.
    
    Exemple: user demande "tu te souviens du nom du fonds qu'on évoquait pour mon projet panneaux solaires ?"
    → recall_history("fonds panneaux solaires") retourne les messages pertinents.
    """
```

Implémentation :
- Embed `query` via `text-embedding-3-small`
- SELECT cosine similarity sur `message_chunks` filtré par `account_id` (RLS F02), `conversation_id` exclu (déjà dans contexte) ou inclus selon paramètre, `since >= since`
- LIMIT `max_results`, similarity threshold > 0.6
- Retourne liste `[{message_id, role, chunk_text, created_at, conversation_title, similarity}]`

### Synchronisation bidirectionnelle des éditions manuelles

Pour chaque entité métier (Project F06, ESG, Carbon, Credit, Application) :
- Quand mutée via API REST manuelle (UI directe, pas LLM), émettre un event SSE `entity_update` avec `{entity_type, entity_id, account_id, source: 'manual'}`
- Le frontend chat met à jour le state contextuel
- Le prochain message LLM rechargera l'entité depuis la DB (ce qui est déjà le cas pour le profil entreprise)

Étendre `_load_profile_for_state` en `_load_full_context_for_state` :
- Charge profil entreprise
- Charge projets actifs (F06)
- Charge derniers scores ESG/carbon/credit (résumés)
- Charge candidatures actives (F07)
- Tout est ré-injecté à chaque tour LLM

### Suppression des conversations sur deletion compte (F05)

Quand un account est purgé (F05 J+30) :
- Supprimer en cascade `conversations`, `messages`, `message_chunks`, `interactive_questions`
- Supprimer les checkpoints LangGraph (`AsyncPostgresSaver` checkpoints) liés à `thread_id` du compte

## Hors-scope (post-MVP)

- Digest périodique automatique des conversations (résumé hebdomadaire)
- Snapshot mensuel du profil avec versioning
- Apprentissage en ligne (fine-tuning sur les corrections utilisateur)
- Mémoire émotionnelle / personnalité utilisateur (post-MVP)
- Pruning intelligent des chunks vieux et peu consultés
- Cross-account memory (jamais — interdit par RLS)

## Exigences techniques

### Backend

- Migration Alembic `028_memory_persistence.py` :
  - Table `message_chunks` (UUID, account_id, conversation_id, message_id, chunk_text, embedding vector(1536), created_at, role)
  - Index HNSW : `CREATE INDEX ON message_chunks USING hnsw (embedding vector_cosine_ops)`
  - Index : `(account_id, conversation_id, created_at DESC)`
  - RLS policies F02 sur cette table
- Refactor `backend/app/graph/graph.py` : remplacer `MemorySaver` par `AsyncPostgresSaver`
  - Configuration via `backend/app/graph/checkpointer.py` (déjà préparé)
  - Test : un reboot ne perd pas les conversations
- Module `app/modules/memory/` :
  - `service.py` : `embed_message`, `search_history`
  - Hooks SQLAlchemy : `event.listens_for(Message, "after_insert")` → embed async + insert dans `message_chunks`
- Tools `app/graph/tools/memory_tools.py` :
  - `recall_history` (cf. ci-dessus)
  - `summarize_conversation(conversation_id)` (post-MVP, déjà partiellement existant via `chains/summarization`)
- Mise à jour `app/api/chat.py:_load_context_memory` :
  - Charger les 15 derniers messages bruts en plus des 3 résumés
  - Charger projets actifs, derniers scores
- Mise à jour `tool_selector_config.py` : `recall_history` visible sur tous les nœuds (transverse)
- Tests :
  - Test reboot : crée conversation, restart serveur, reprend → contexte persistant
  - Test embed : message créé → row dans `message_chunks` avec embedding non-null
  - Test recall : query similaire → retourne le message correspondant
  - Test RLS : recall_history dans account A ne retourne pas messages account B
  - Test purge : delete account → cascade supprime messages, message_chunks, checkpoints
  - Test 15 derniers messages : 16+ messages en DB → contexte LLM contient les 15 derniers

### Frontend

- Pas de changement majeur côté frontend (la mémoire est backend)
- (optionnel) Indicateur visuel "🧠 Recherche dans l'historique..." quand `recall_history` est invoqué (via SSE tool_call_start)

### Base de données

- Tables : `message_chunks`
- Tables auto-créées par `langgraph` : `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` (gérées par `AsyncPostgresSaver`)
- Index HNSW sur `message_chunks(embedding)`
- RLS F02

## Critères d'acceptation

- [ ] `MemorySaver` remplacé par `AsyncPostgresSaver` en prod
- [ ] Test reboot : restart serveur ne perd pas les conversations en cours
- [ ] Table `message_chunks` créée avec embedding pgvector
- [ ] Hook après-insert messages déclenche embedding async (sans bloquer la réponse user)
- [ ] Tool `recall_history` implémenté et fonctionnel
- [ ] `_load_context_memory` charge bien 15 derniers messages bruts + 3 résumés
- [ ] `_load_full_context_for_state` charge profil + projets + scores derniers
- [ ] Test recall : "tu te souviens de mon projet X" → retourne les messages mentionnant X
- [ ] Test multi-tenant : recall_history filtré par account_id (RLS)
- [ ] Performance : embedding async ne bloque pas la latence du chat (mesurer p99 < 100 ms overhead)
- [ ] Couverture tests ≥ 80 % sur `memory/service.py`, `memory_tools.py`, hooks SQLAlchemy
- [ ] Documentation `docs/memory-architecture.md` : decision tree (15 derniers / résumé / recall)

## Risques & garde-fous

- **Risque** : explosion volume `message_chunks` (1 row par message × 1000 PME × 10 msg/jour = 3 M rows/an). **Garde-fou** : pas de problème en pgvector + HNSW jusqu'à 10 M rows ; partitionnement par mois post-MVP si besoin.
- **Risque** : embedding API coûteux (1 call par message). **Garde-fou** : `text-embedding-3-small` est très bon marché ($0.02/M tokens) ; batch les embeddings pendant des fenêtres de 5 sec.
- **Risque** : embedding async échoue silencieusement → message non indexé → recall manqué. **Garde-fou** : retry 3x, log d'erreurs, monitoring "% messages embedded" ; cron quotidien qui re-traite les messages sans embedding.
- **Risque** : `AsyncPostgresSaver` charge trop de checkpoints en mémoire et dégrade les perfs. **Garde-fou** : TTL 30 jours, cron de purge nocturne ; benchmark p95 latency avant/après migration.
- **Risque** : un message contient un secret (mot de passe, token) qui se retrouve indexé. **Garde-fou** : rapprocher F05 RGPD — politique de "ne jamais demander de secrets dans le chat", masquage server-side avant embedding (regex emails / tokens / numéros bancaires).
- **Risque** : `recall_history` invoqué trop souvent → coût LLM explose et latence dégradée. **Garde-fou** : décrire dans le tool docstring "Don't use when info is in recent context" + monitoring du taux d'invocation, ajustement du prompt si abus.
- **Risque** : un user d'un même account A peut voir les conversations d'autres users de A. **Comportement attendu** : OUI, car les utilisateurs d'un même account ont les mêmes droits (Module 7.3). Documenter ce point.
