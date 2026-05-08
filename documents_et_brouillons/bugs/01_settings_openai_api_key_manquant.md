# Bug 01 — `Settings` n'a pas l'attribut `openai_api_key`

## Symptôme

Dans les logs uvicorn, à chaque insertion de `Message`, on voit :

```
Embedding API a échoué pour message <uuid> : 'Settings' object has no attribute 'openai_api_key' — chunks insérés sans embedding
```

Conséquence : la fonctionnalité **F12 — Mémoire contextuelle pgvector** est cassée. Tous les `message_chunks` sont insérés avec `embedding=NULL` ; le tool global `recall_history` ne peut plus retrouver de contexte sémantique.

## Cause racine

Fichier `backend/app/modules/memory/service.py`, ligne 272 :

```python
api_key=settings.openai_api_key or settings.openrouter_api_key,
```

La classe `Settings` (`backend/app/core/config.py`) ne déclare **pas** d'attribut `openai_api_key`. Pydantic-Settings n'injecte que les champs déclarés. L'accès `settings.openai_api_key` lève donc `AttributeError`, qui est attrapé en aval par le `try/except Exception` autour de `await model.aembed_documents(chunks)` → tous les chunks sont marqués `failed`.

Le `.env` racine (`/Users/mac/Documents/projets/2025/esg_mefali_v3/.env`) contient :
- `LLM_API_KEY=sk-or-v1-...` → mappé vers `openrouter_api_key`
- `VOYAGE_API_KEY=pa-...` → embeddings Voyage AI (non utilisé actuellement)
- **Pas** de `OPENAI_API_KEY`

Le code utilise `langchain_openai.OpenAIEmbeddings` (modèle `text-embedding-3-small`), donc il faut une clé OpenAI réelle. OpenRouter ne sert PAS d'embeddings OpenAI directement — fallback `openrouter_api_key` ne marche pas pour le SDK OpenAI Embeddings (404 sur l'endpoint `/embeddings`).

## Fichiers concernés

- `backend/app/core/config.py` — classe `Settings` (ajouter le champ)
- `backend/app/modules/memory/service.py:260-275` — fonction `_embeddings_model`
- `backend/.env` ou `/Users/mac/Documents/projets/2025/esg_mefali_v3/.env` — ajouter la variable
- Tests : `backend/tests/modules/memory/` (vérifier les tests existants)

## Tâche

1. **Ajouter le champ `openai_api_key` dans `Settings`** :

```python
# Embeddings F12 (text-embedding-3-small via OpenAI direct)
openai_api_key: str = ""
```

2. **Corriger l'accès dans `_embeddings_model`** : éviter l'AttributeError et logger un message clair quand aucune clé n'est disponible :

```python
def _embeddings_model() -> Any:
    from langchain_openai import OpenAIEmbeddings

    api_key = settings.openai_api_key or settings.openrouter_api_key
    if not api_key:
        raise RuntimeError(
            "Aucune clé d'embedding configurée. Définir OPENAI_API_KEY dans .env."
        )
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key,
    )
```

3. **Documenter la variable d'env** : ajouter une ligne dans `/Users/mac/Documents/projets/2025/esg_mefali_v3/.env.example` (ou créer le fichier si absent) :

```
# Embeddings F12 (mémoire pgvector). Requiert un compte OpenAI direct.
# Si vide, F12 fonctionne en mode dégradé (chunks insérés sans embedding).
OPENAI_API_KEY=
```

4. **Optionnel (à proposer) — Migration vers Voyage AI** : la clé `VOYAGE_API_KEY` est déjà dans `.env` mais inutilisée. Évaluer le coût du portage `OpenAIEmbeddings` → `VoyageAIEmbeddings` (modèle `voyage-3` ou `voyage-3-lite`). Si retenu, créer un ticket séparé — ne PAS l'inclure dans ce fix.

## Critères d'acceptation

- [ ] `from app.core.config import settings; settings.openai_api_key` retourne une string (vide ou non), jamais `AttributeError`.
- [ ] Avec `OPENAI_API_KEY` valide : insérer un message déclenche un embedding réel et un row `message_chunks` avec `embedding IS NOT NULL` (vérifier en BDD).
- [ ] Avec `OPENAI_API_KEY` vide : log clair `"Aucune clé d'embedding configurée"`, aucun `AttributeError`, le chat continue de fonctionner (best-effort F12).
- [ ] Tests existants passent : `pytest backend/tests/modules/memory/ -v`.
- [ ] `git diff` minimal : pas de refactor large, juste les 2-3 lignes nécessaires.

## Notes

- Ne PAS corriger en parallèle le bug 02 (race condition `message_chunks`) — il est traité séparément.
- Ne PAS toucher au modèle `MessageChunk` ni à la migration 023.
