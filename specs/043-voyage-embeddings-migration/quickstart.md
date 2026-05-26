# Quickstart: F25 Voyage AI Embeddings Migration

**Branch**: `043-voyage-embeddings-migration` | **Date**: 2026-05-08

Ce guide condensé permet à un développeur ou à un admin de **valider F25 en local** en moins de 30 minutes : installation du package, exécution de la migration, vérification des comportements clés, exécution du smoke test SC-002.

---

## Prérequis

- PostgreSQL 16 + extension `vector` activée (déjà le cas dans l'environnement de dev existant).
- Python 3.12 + venv backend activé : `source backend/venv/bin/activate`.
- Une clé `VOYAGE_API_KEY` valide (lien : https://www.voyageai.com/ → API keys).
- Cette branche `043-voyage-embeddings-migration` checkée out.

---

## 1. Installation des dépendances

```bash
cd backend
pip install -r requirements.txt        # ajoute langchain-voyageai>=0.1.4
pip list | grep -i voyageai            # vérification : doit afficher langchain-voyageai 0.1.x
```

Vérification grep "anti-régression" (SC-003) :

```bash
grep -r "OpenAIEmbeddings" backend/app/    # attendu : 0 résultat
grep -r "from langchain_openai import" backend/app/    # attendu : uniquement ChatOpenAI
```

---

## 2. Configuration de l'environnement

### `.env` (racine repo)

```ini
# ── Embeddings (F25 — Voyage AI) ────────────────────────────────
# Cle API Voyage : https://www.voyageai.com/
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxxxxxx

# (la variable OPENAI_API_KEY n'est plus utilisee — peut etre retiree)
```

### `backend/.env` (idem)

```ini
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Sans clé** : l'application démarre, le chat fonctionne, mais aucun embedding n'est créé. Logs : `WARNING - Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env.`

---

## 3. Migration de schéma (PR #1, indépendant)

```bash
cd backend
source venv/bin/activate
alembic current               # devrait afficher 042_extension_url_patterns
alembic upgrade head          # applique 043_embeddings_voyage_dim
alembic current               # devrait afficher 043_embeddings_voyage_dim
```

**Attendu** : la migration s'exécute en < 30 secondes sur une base locale (~100 lignes par table).

### Vérifications post-`up`

```bash
psql $DATABASE_URL -c "
  SELECT c.relname, a.atttypmod AS dim
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  WHERE c.relname IN ('message_chunks','document_chunks','financing_chunks')
    AND a.attname = 'embedding' AND NOT a.attisdropped
  ORDER BY c.relname;
"
```

Sortie attendue :
```
     relname     | dim
-----------------+------
 document_chunks | 1024
 financing_chunks| 1024
 message_chunks  | 1024
```

```bash
psql $DATABASE_URL -c "
  SELECT indexname FROM pg_indexes
  WHERE indexname LIKE '%embedding_hnsw%' OR indexname = 'idx_message_chunks_pending_embedding'
  ORDER BY indexname;
"
```

Sortie attendue : 4 lignes.

### Round-trip rollback (SC-004)

```bash
alembic downgrade -1          # retour à 042
# Vérifier que les colonnes sont à nouveau VECTOR(1536) (financing_chunks repasse en TEXT)
psql $DATABASE_URL -c "SELECT atttypmod FROM pg_attribute WHERE attname='embedding'..."
alembic upgrade head          # remonte à 043
```

Toute l'opération (up → down → up) doit se terminer en < 30 secondes (SC-004).

---

## 4. Démarrage de l'application (PR #2, code applicatif)

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

À l'écran :
- Pas d'erreur d'import `langchain_voyageai`.
- Aucune référence à `text-embedding-3-small` dans les logs.

---

## 5. Smoke tests fonctionnels

### 5.1 Mémoire conversationnelle (US1)

```bash
# Depuis le frontend Nuxt (ou via curl) :
# 1. Se connecter en tant que PME (compte test).
# 2. Echanger 3 messages substantiels sur "projet solaire Dakar".
# 3. Verifier en BDD :
psql $DATABASE_URL -c "
  SELECT vector_dims(embedding) AS dim, COUNT(*)
  FROM message_chunks WHERE embedding IS NOT NULL
  GROUP BY dim;
"
# attendu : dim=1024, count > 0
```

### 5.2 `recall_history` (US1, SC-002)

```bash
# 4. Demarrer une nouvelle conversation, demander :
#    "Rappelle-moi nos discussions sur le projet solaire"
# 5. L'agent doit repondre en citant les messages precedents.
# 6. Inspecter les logs : un appel a recall_history doit etre journalise.
```

### 5.3 Ré-embedding lazy (FR-007a)

```bash
# 7. Forcer une ligne en NULL :
psql $DATABASE_URL -c "
  UPDATE message_chunks SET embedding = NULL
  WHERE id = (SELECT id FROM message_chunks ORDER BY created_at DESC LIMIT 1);
"
# 8. Lancer une recherche recall_history qui devrait toucher cette ligne.
# 9. Verifier que l'embedding a ete rempli :
psql $DATABASE_URL -c "
  SELECT id, vector_dims(embedding)
  FROM message_chunks ORDER BY created_at DESC LIMIT 1;
"
# attendu : dim=1024 (la ligne a ete re-embeddee paresseusement)
```

### 5.4 Mode dégradé (FR-006, SC-005)

```bash
# 10. Stopper l'app, retirer VOYAGE_API_KEY du .env.
# 11. Redemarrer : uvicorn app.main:app
# 12. Echanger un message via le chat. Doit recevoir une reponse normale.
# 13. Verifier les logs : warning "Aucune cle d'embedding configuree." present.
# 14. Verifier en BDD : message_chunks recents ont embedding=NULL.
```

---

## 6. Script admin opt-in (FR-007b)

```bash
# Dry-run d'abord (no-op, observation uniquement)
python -m app.scripts.reembed_all --dry-run

# Cible une seule table avec limite
python -m app.scripts.reembed_all --table financing --limit 50 --dry-run

# Execution reelle (apres validation du dry-run)
python -m app.scripts.reembed_all --table all
```

Sortie attendue (run reel) :
```
[reembed_all] message_chunks: 12 candidats, 12 succes
[reembed_all] document_chunks: 8 candidats, 8 succes
[reembed_all] financing_chunks: 50 candidats, 50 succes
[reembed_all] Total: 70 succes / 70 candidats. Coût estimé Voyage : ~0.001 USD.
```

---

## 7. Smoke test SC-002 — baseline française non-gating

> **Procédure d'eval manuelle** documentée dans `docs/embeddings-voyage.md`.

1. S'assurer que les 3 tables sont peuplées (seed financing + au moins quelques messages + un document PDF chunké).
2. Pour chaque requête de la baseline (10 requêtes — voir `research.md` R8), exécuter le parcours produit correspondant :
   - Queries 1, 2, 7, 8, 10 → page `/financing` ou tool `search_financing_chunks`.
   - Queries 3, 4, 9 → tool `recall_history`.
   - Queries 5, 6 → RAG documentaire via chat.
3. Consigner le top-3 retourné par requête dans `docs/embeddings-voyage.md` sous la section « SC-002 baseline ».
4. Si > 2 requêtes hors top-3 : ouvrir une issue de re-calibration (non bloquant pour merge).

---

## 8. Tests automatiques

```bash
cd backend
pytest -m embeddings -v
```

Sortie attendue : tous les tests marqués `@pytest.mark.embeddings` passent (SC-006).

```bash
# Tests de migration spécifiques (PostgreSQL container requis)
pytest tests/migrations/test_043_embeddings_voyage_dim.py -v
```

---

## 9. Cleanup environnement de dev

```bash
# Si la migration locale a degenere et qu'on veut repartir propre :
alembic downgrade 042_extension_url_patterns
# Verifier l'etat puis remonter :
alembic upgrade head
```

---

## 10. Checklist de done F25

- [ ] `pip list | grep voyageai` retourne `langchain-voyageai 0.1.x`
- [ ] `grep -r "OpenAIEmbeddings" backend/app/` → 0 résultat (SC-003)
- [ ] `alembic upgrade head` puis `alembic downgrade -1` puis `alembic upgrade head` réussit en < 30 s (SC-004)
- [ ] `pytest -m embeddings -v` → 100 % vert (SC-006)
- [ ] Avec `VOYAGE_API_KEY` valide : new conversation → ligne `message_chunks` avec embedding 1024d (SC-001)
- [ ] Sans `VOYAGE_API_KEY` : chat continue, warning visible en logs, pas de 5xx (SC-005)
- [ ] `recall_history` retrouve un message indexé après ré-embedding lazy (US1)
- [ ] Baseline 10 requêtes FR consignée dans `docs/embeddings-voyage.md` (SC-002, non-gating)
- [ ] CLAUDE.md mis à jour (Stack > LLM ; F12 ; nouvelle entrée F25)
- [ ] `.env.example` (racine + backend) mis à jour
- [ ] `docs/embeddings-voyage.md` créé (politique fournisseur, posture vie privée, procédure re-embedding, baseline)
- [ ] Code review terminée (Constitution principe IV — code-reviewer agent)
- [ ] Security review terminée (Constitution principe V — security-reviewer agent)

---

## Annexe — Estimation des coûts Voyage AI (cf. SC-008)

- Tarif voyage-3.5 : ~ $0.06 / 1 M tokens.
- Estimation dev/staging :
  - Re-embedding initial : ~ 1000 chunks × 500 tokens / chunk ≈ 500k tokens → ~ $0.03.
  - Conversations actives quotidiennes : ~ 100 messages × 200 tokens ≈ 20k tokens / jour → ~ $0.001 / jour.
  - **Cap journalier dev** : < 0.10 USD (largement sous le seuil SC-008 de 1 USD).
- Estimation production (10 PME actives × 50 messages / jour) :
  - 500 messages × 200 tokens × ~ 5 chunks moyen ≈ 500k tokens / jour → ~ $0.03 / jour.
  - **Cap journalier prod actuel** : < 1 USD (conforme).

Suivi recommandé : alerte simple si la consommation Voyage dépasse $1 / jour pendant 7 jours consécutifs (à mettre en place dans la feature ops dédiée, hors scope F25).
