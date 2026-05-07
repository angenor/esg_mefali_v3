# Quickstart F12 — Mémoire Contextuelle Conforme

Guide pas à pas pour valider F12 en local après implémentation. Cible : développeurs et reviewers.

---

## Pré-requis

- Branche `feat/F12-memoire-contextuelle-pgvector` checkout, code F12 implémenté.
- PostgreSQL 16 démarré localement avec extension pgvector activée.
- `backend/venv/` activé : `source backend/venv/bin/activate`.

## 1. Migration Alembic

```bash
cd backend && source venv/bin/activate
alembic upgrade head
```

Vérifier qu'il existe désormais la table `message_chunks` :

```bash
psql -h localhost -U esg_mefali -d esg_mefali_dev -c "\d message_chunks"
```

Vérifier la présence de l'index HNSW :

```bash
psql -h localhost -U esg_mefali -d esg_mefali_dev -c "SELECT indexname FROM pg_indexes WHERE tablename = 'message_chunks';"
# Devrait retourner: idx_message_chunks_account_conv_created, ix_message_chunks_embedding_hnsw, idx_message_chunks_pending_embedding
```

Vérifier RLS active :

```bash
psql -h localhost -U esg_mefali -d esg_mefali_dev -c "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'message_chunks';"
# relrowsecurity = t, relforcerowsecurity = t
```

## 2. Lancer le backend

```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

À la première exécution, observer les logs : `AsyncPostgresSaver setup completed.` (le checkpointer crée ses 3 tables).

```bash
psql -h localhost -U esg_mefali -d esg_mefali_dev -c "\dt"
# Devrait inclure: checkpoints, checkpoint_writes, checkpoint_blobs (en plus des tables métier).
```

## 3. Lancer le frontend

```bash
cd frontend && npm run dev
```

## 4. Test E2E US1 : Reprise après redémarrage

1. Ouvrir `http://localhost:3000` et se connecter (compte test PME).
2. Démarrer une conversation : « Bonjour, je suis Sarah, dirigeante d'une PME agroalimentaire à Dakar. Je veux faire mon bilan ESG. »
3. L'assistant entame le module ESG, demande quelques critères. Répondre à 3-4 questions.
4. **CTRL+C** sur le processus uvicorn pour simuler un crash.
5. Relancer `uvicorn app.main:app --reload --port 8000`.
6. Sur le frontend, envoyer le message suivant dans la même conversation : « On reprend ? ».
7. **Vérification** : l'assistant doit citer un critère ESG déjà répondu ou continuer la séquence là où elle en était (pas de retour au critère 1).

## 5. Test E2E US2 : 15 derniers messages bruts en contexte

1. Dans une nouvelle conversation, envoyer 18 messages utilisateur (poser 18 questions ESG distinctes).
2. Au 19e message, demander : « Rappelle-moi ce que je t'ai dit dans mon 4e message ».
3. **Vérification** : l'assistant ne doit PAS pouvoir répondre précisément (le 4e message est hors fenêtre de 15 → seuls les messages 5-19 sont en contexte clair). C'est conforme au design.
4. Poser une question référant un détail du 7e message (ex. « Quel était le secteur que je t'ai indiqué ? »).
5. **Vérification** : l'assistant doit répondre avec le secteur correct (présent dans la fenêtre des 15 derniers).

## 6. Test E2E US3 : recall_history

1. Dans la conversation, envoyer un message qui force la référence au passé : « Tu te souviens du fonds qu'on évoquait il y a 2 mois ? ».
2. **Vérification frontend** : le composant `ToolCallIndicator.vue` affiche brièvement « Recherche dans l'historique de conversation… » (texte du toolcall recall_history).
3. **Vérification backend** : dans les logs, observer une ligne `tool_call_start: recall_history` puis `tool_call_end: recall_history` avec un nombre de résultats.

> Préalable : avoir effectivement parlé d'un fonds dans une conversation antérieure pour que la recherche retourne quelque chose. Sinon le résultat sera vide et l'assistant répondra honnêtement « Je ne retrouve pas ce détail ».

## 7. Test multi-tenant (manuel)

1. Créer un 2e compte de test sur un autre account (script `python -m app.scripts.seed_admin` ou registration UI).
2. Avoir des messages indexés des deux côtés contenant un mot commun (ex. « solaire »).
3. Depuis l'account A, déclencher un recall_history sur « solaire ».
4. **Vérification SQL directe** : 
   ```sql
   -- En tant que role PME avec account_id de A :
   SET app.current_role = 'PME';
   SET app.current_account_id = '<UUID_A>';
   SELECT account_id, chunk_text FROM message_chunks WHERE chunk_text LIKE '%solaire%';
   -- Doit retourner UNIQUEMENT les chunks de l'account A.
   ```

## 8. Tests automatisés

```bash
cd backend && source venv/bin/activate
pytest tests/memory/ -v --cov=app.modules.memory --cov=app.graph.tools.memory_tools --cov=app.graph.checkpointer --cov-report=term-missing
```

Cibles :
- Tous les tests doivent passer.
- Coverage ≥ 80 % sur le module `memory/` et le tool `recall_history`.

```bash
cd frontend && npm run test
```

Tests Vitest : extension `ToolCallIndicator.vue` doit être verte (cas `recall_history`).

```bash
cd frontend && npx playwright test tests/e2e/F12-memoire-contextuelle-pgvector.spec.ts
```

Doit valider les 4 scénarios E2E (cf. tasks.md).

## 9. Rollback (si nécessaire)

```bash
cd backend && source venv/bin/activate
alembic downgrade -1
```

Drop manuel des tables checkpoint LangGraph (créées hors Alembic) :

```bash
psql -h localhost -U esg_mefali -d esg_mefali_dev -c "DROP TABLE IF EXISTS checkpoint_blobs, checkpoint_writes, checkpoints CASCADE;"
```

Reverter la branche : `git revert HEAD~N` ou `git checkout main`.

---

## Critères de validation finale

- [ ] Migration 023 applique et rollback proprement (`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`).
- [ ] Logs montrent `AsyncPostgresSaver setup completed` au premier démarrage.
- [ ] Une conversation survit à un redémarrage uvicorn.
- [ ] Les 15 derniers messages sont visibles dans le state LangGraph (vérifiable via debug log dans `_load_context_memory`).
- [ ] L'index HNSW est créé et utilisé (vérifier via `EXPLAIN ANALYZE` sur la requête de search_history).
- [ ] RLS bloque effectivement les fuites inter-account (test SQL direct).
- [ ] Masquage des secrets : un message contenant email + IBAN + carte est correctement masqué dans `message_chunks.chunk_text` (vérification SQL).
- [ ] `purge_account_chunks(account_id)` supprime chunks ET checkpoints sans casser les autres accounts.
- [ ] Coverage backend `memory/` ≥ 80 %.
- [ ] E2E Playwright : 4 scénarios verts.
- [ ] Documentation `docs/memory-architecture.md` à jour.
