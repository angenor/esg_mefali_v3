# Phase 0 — Research: F25 Voyage AI Embeddings Migration

**Branch**: `043-voyage-embeddings-migration` | **Date**: 2026-05-08

Ce document consolide les recherches techniques préalables à la phase Design (Phase 1). Chaque section se termine par **Decision / Rationale / Alternatives considered**.

---

## R1 — Inventaire RÉEL des colonnes pgvector existantes (CRITIQUE)

### Findings

La spec listait 4 tables (`message_chunks`, `document_chunks`, `documents`, `funds`). **Vérification du code source révèle un écart majeur** :

| Table déclarée par la spec | Existe avec embedding ? | Type réel en production |
|----------------------------|-------------------------|------------------------|
| `message_chunks.embedding` | ✅ Oui | `VECTOR(1536)` (mig. 023) |
| `document_chunks.embedding` | ✅ Oui | `VECTOR(1536)` (mig. 163318558259) |
| `documents.embedding` | ❌ **N'existe pas** | Le modèle `Document` (`app/models/document.py:50`) n'a aucune colonne `embedding`. Seul `DocumentChunk` (line 126) en a une. |
| `funds.embedding` | ❌ **N'existe pas** | Le modèle `Fund` (`app/models/financing.py:121`) n'a aucune colonne `embedding`. Seul `FinancingChunk` (line 490) en a une. |

**Tables ayant réellement un usage d'embeddings** (déduit de `app/models/`) :

| Table | Modèle | Type production | Type modèle SQLAlchemy | Source migration |
|-------|--------|-----------------|------------------------|------------------|
| `message_chunks.embedding` | `MessageChunk` (memory F12) | `VECTOR(1536)` | `Vector(1536) if Vector is not None else Text` | mig. 023 |
| `document_chunks.embedding` | `DocumentChunk` (RAG documents) | `VECTOR(1536)` | `Vector(1536) if Vector is not None else Text` | mig. 163318558259 |
| `financing_chunks.embedding` | `FinancingChunk` (RAG fonds + intermédiaires via `source_type`) | **`TEXT`** ⚠️ | `Vector(1536) if Vector is not None else Text` | mig. 008 |
| `sources.embedding` | `Source` (F01) | `JSONType` | `JSONType` | mig. 020 (hors scope F25) |

### ⚠️ Bug pré-existant identifié dans `financing_chunks.embedding`

- La migration `008_add_financing_tables.py:162` crée la colonne avec `sa.Column('embedding', sa.Text(), nullable=True)`.
- Aucune migration ultérieure ne fait d'`ALTER COLUMN ... TYPE vector(...)`.
- Le modèle SQLAlchemy `app/models/financing.py:507-509` déclare pourtant `Vector(1536)` pour PostgreSQL.
- Le service `app/modules/financing/service.py` utilise `FinancingChunk.embedding.cosine_distance(query_vector)` — ce qui échouerait en production car `text <=> vector` n'est pas un opérateur défini.
- Conclusion : la recherche sémantique financing est **doublement cassée** : (1) appel `OpenAIEmbeddings` sur OpenRouter (404), (2) colonne TEXT au lieu de pgvector.

### Decision

**Ramener le périmètre à 3 tables réelles** : `message_chunks`, `document_chunks`, `financing_chunks`. La migration `043_embeddings_voyage_dim.py` :

- Pour `message_chunks` et `document_chunks` : `ALTER COLUMN embedding TYPE vector(1024)` après `UPDATE ... SET embedding = NULL` (TRUNCATE des valeurs).
- Pour `financing_chunks` : double action — (a) `UPDATE ... SET embedding = NULL` puis (b) `ALTER COLUMN embedding TYPE vector(1024) USING NULL`. La conversion `TEXT → vector(1024)` est forcée via `USING NULL` (les valeurs textuelles éventuellement présentes étant invalides ou tout aussi cassées que les autres).

### Rationale

- Aligné sur l'intention exprimée dans la description initiale (« Migrer tous les usages d'embeddings ») et sur la réalité du code.
- Inclure `financing_chunks` corrige opportunément un bug pré-existant qui aurait sinon empêché US2 (recherche sémantique fonds) d'être satisfaite.
- Exclure `documents.embedding` et `funds.embedding` qui n'existent pas évite des `ALTER COLUMN` voués à échouer.

### Alternatives considered

- **A** : Conserver le périmètre spec (4 tables) → tomberait à l'exécution Alembic (`column "embedding" of relation "documents" does not exist`).
- **B** : Périmètre 3 tables + ne rien faire pour `financing_chunks.embedding TEXT` → US2 resterait cassée même après F25 ; SC-002 inatteignable pour les fonds.
- **C** (retenu) : Périmètre 3 tables avec correction `financing_chunks` au passage.

### Action sur la spec

Mettre à jour `spec.md` pour remplacer les références aux 4 tables erronées par les 3 tables réelles dans : Acceptance Scenarios US3, Edge Cases, Key Entities, FR-008, FR-010, SC-001, SC-007.

---

## R2 — Tail-end audit log F03 et RLS F02

### Findings

- Constantes `AUDITABLE_MODELS` / `EXEMPT_MODELS` introduites par F03 (mig. 021).
- `MessageChunk`, `DocumentChunk`, `FinancingChunk` ne font partie ni de `AUDITABLE_MODELS` (qui liste 7 modèles métier core : CompanyProfile, FundApplication, ESGAssessment, CarbonAssessment, CreditScore, ActionPlan, ActionItem) ni explicitement de `EXEMPT_MODELS` (catalogue F01, infra, AuditLog, Skill, ExchangeRate). Ces modèles sont des **représentations dérivées** (chunks d'autres entités) — pas suivis par audit, c'est sain.
- RLS `message_chunks` : 2 policies `admin_full_access`, `pme_access_own_account` créées en mig. 023. RLS `document_chunks` et `financing_chunks` : à vérifier (probable absence pour `financing_chunks` au vu du bug schéma).

### Decision

- La migration 043 ne touche ni les policies RLS ni l'audit. Les `ALTER COLUMN ... TYPE vector(1024)` n'invalident pas les policies existantes (PostgreSQL conserve les policies sur les changements de type colonne).
- L'audit log F03 ne déclenche aucun `audit_log` row pour les inserts/updates de chunks (modèles non audité), donc le ré-embedding lazy ne pollue pas l'audit. ✅

### Rationale

Préserve les invariants F02 et F03 sans intervention explicite — la migration est strictement orientée schéma.

### Alternatives considered

Aucune — mécaniquement il n'y a rien à faire côté audit/RLS.

---

## R3 — API langchain-voyageai (constructor + dimensions)

### Findings

Pattern d'utilisation standard de `langchain-voyageai` (>= 0.1.4) :

```python
from langchain_voyageai import VoyageAIEmbeddings

embeddings = VoyageAIEmbeddings(
    voyage_api_key=settings.voyage_api_key,  # ou via env VOYAGE_API_KEY (lookup auto)
    model="voyage-3.5",
    # voyage-3.5 retourne 1024 dims par défaut
    # batch_size paramétrable (défaut: dépendant du modèle, typiquement 7..72)
    # truncation par défaut = True (texte trop long tronqué côté serveur)
)

# API async (utilisée dans memory/financing/documents)
vector: list[float] = await embeddings.aembed_query("texte requête")
vectors: list[list[float]] = await embeddings.aembed_documents(["t1", "t2"])
```

- `voyage-3.5` : modèle à 1024 dims, multilingue (FR/EN/ES/DE/IT/JA/ZH/KO/AR…), tarif ~ $0.06/M tokens (cf. https://www.voyageai.com/pricing/).
- Embeddings normalisés : par défaut, voyage-3.5 retourne des vecteurs unit-norm, ce qui rend `cosine_distance` ↔ `inner_product` équivalents et stables.
- Timeouts : configurables via paramètres SDK (cf. `httpx` underlying client). Default ~ 30 s — à clamper à 10 s par FR-007c.

### Decision

Utiliser le SDK comme suit dans tous les call sites :

```python
from langchain_voyageai import VoyageAIEmbeddings
from app.core.config import settings

embeddings = VoyageAIEmbeddings(
    voyage_api_key=settings.voyage_api_key,
    model=settings.voyage_model,  # "voyage-3.5"
    request_timeout=10,           # FR-007c — 10s timeout
    max_retries=1,                # FR-007c — 1 retry max
    batch_size=72,                # par défaut Voyage pour voyage-3.5
)
```

- Helper centralisé `app/modules/memory/service.py::_embeddings_model()` reste le point d'instantiation pour memory.
- Pour cohérence et DRY, créer un helper réutilisable `app/lib/embeddings.py::get_embeddings_client()` qui retourne le même client → utilisé par memory, financing/service, financing/seed, documents/service. **Cela évite 4 instantiations dupliquées** et centralise la gestion `voyage_api_key vide` (mode dégradé via `RuntimeError` capturé).

### Rationale

- Conforme au principe VII Simplicité : un seul point d'instantiation.
- FR-001 « fournisseur unique d'embeddings dédié » est mieux servi par un helper centralisé.
- Facilite les tests (mock unique).

### Alternatives considered

- **A** : Garder 4 instantiations dispersées (statu quo) → augmente la surface de mock, viole DRY.
- **B** (retenu) : Helper `get_embeddings_client()` dans `app/lib/embeddings.py`.

### Note sur `voyage_embedding_dim`

- Typer `Literal[1024]` côté Pydantic v2.
- Cette constante est utilisée pour : (a) la validation du retour SDK, (b) le check de dim dans `memory/service.py:456`, (c) le seed des fixtures de tests SQLite (longueur du vecteur stub).
- Elle n'est **pas** envoyée au SDK Voyage (qui détermine la dim depuis `model`).

---

## R4 — Pattern ALTER COLUMN pgvector + recréation HNSW

### Findings

Pour modifier la dimension d'une colonne pgvector, deux approches existent :

**Approche A (en place avec NULL forcé)** :
```sql
DROP INDEX IF EXISTS ix_message_chunks_embedding_hnsw;
DROP INDEX IF EXISTS idx_message_chunks_pending_embedding;  -- partiel WHERE embedding IS NULL
UPDATE message_chunks SET embedding = NULL;
ALTER TABLE message_chunks ALTER COLUMN embedding TYPE vector(1024);
CREATE INDEX ix_message_chunks_embedding_hnsw
  ON message_chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_message_chunks_pending_embedding
  ON message_chunks (created_at) WHERE embedding IS NULL;
```

**Approche B (cast USING)** :
```sql
ALTER TABLE message_chunks ALTER COLUMN embedding TYPE vector(1024) USING NULL;
```
plus DROP/CREATE indexes.

### Decision

Approche A. Plus explicite, traçabilité claire dans les logs migration (le `UPDATE ... SET NULL` est visible et compté), et cohérente avec FR-009 « les valeurs de la colonne d'embedding sont vidées ».

Pour `financing_chunks.embedding TEXT → VECTOR(1024)`, on doit utiliser une variante :
```sql
ALTER TABLE financing_chunks ALTER COLUMN embedding TYPE vector(1024) USING NULL;
```
Pas besoin de DROP de l'index HNSW ici — il n'existe **pas** côté production (jamais créé en migration), il faut au contraire le **créer**. Module-level `Index(...)` dans `app/models/financing.py:518-526` est une déclaration ORM jamais propagée.

Actions concrètes pour la migration 043 :

| Table | Avant | Migration | Après |
|-------|-------|-----------|-------|
| `message_chunks.embedding` | `VECTOR(1536)` + HNSW + partial idx | DROP both idx → SET NULL → ALTER → CREATE both idx (dim 1024) | `VECTOR(1024)` + HNSW(1024) + partial idx |
| `document_chunks.embedding` | `VECTOR(1536)` + HNSW | DROP idx → SET NULL → ALTER → CREATE idx | `VECTOR(1024)` + HNSW(1024) |
| `financing_chunks.embedding` | `TEXT` (pas d'idx HNSW) | ALTER ... USING NULL → CREATE HNSW idx | `VECTOR(1024)` + HNSW(1024) (nouveau) |

### Rationale

- Préserve la sémantique RLS (PostgreSQL conserve les policies sur ALTER COLUMN TYPE).
- Recréation des index HNSW indispensable car ils sont sémantiquement liés à la dim de la colonne.
- Pour `financing_chunks`, la création de l'index HNSW est un **bonus** corrigeant le bug pré-existant.

### Alternatives considered

- **A** : `DROP TABLE ... CREATE TABLE` → perd les lignes métier (violation FR-009).
- **B** : Créer une nouvelle colonne `embedding_v2 vector(1024)`, copier, drop ancienne, rename → lourd, double migration, risque de FK orphans.
- **C** (retenu) : `ALTER COLUMN TYPE` en place avec TRUNCATE explicite des valeurs.

### Idempotence

- `DROP INDEX IF EXISTS` rend chaque drop idempotent.
- `ALTER COLUMN TYPE` n'est pas idempotent natif Alembic, mais on peut wrapper avec une vérification `pg_catalog` :

```python
def _column_dim(bind, table: str, column: str) -> int | None:
    """Retourne la dimension actuelle d'une colonne vector, ou None si pas vector."""
    result = bind.execute(sa.text(f"""
        SELECT a.atttypmod
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = :t AND a.attname = :col AND NOT a.attisdropped
    """), {"t": table, "col": column}).scalar()
    # atttypmod pour vector(N) = N (cf. doc pgvector)
    return result if result and result > 0 else None
```

Applicable pour rendre la migration ré-exécutable (skip si déjà 1024).

---

## R5 — Coexistence langchain-openai (LLM) et langchain-voyageai (embeddings)

### Findings

- `langchain-openai>=0.3.0` est dans `requirements.txt`. Il est utilisé pour **deux** usages distincts :
  1. `OpenAIEmbeddings` → utilisé dans 4 fichiers (memory, financing×2, documents). **À retirer.**
  2. `ChatOpenAI` (modèle LLM via OpenRouter) → utilisé dans `app/graph/llm.py`, etc. **À CONSERVER** (FR-014).

- Vérification : retirer le sous-module `OpenAIEmbeddings` ne nécessite PAS de retirer le package `langchain-openai` (on en garde le besoin pour `ChatOpenAI`).

### Decision

- Conserver `langchain-openai>=0.3.0` dans `requirements.txt`.
- Ajouter `langchain-voyageai>=0.1.4`.
- Retirer uniquement les imports `from langchain_openai import OpenAIEmbeddings`.
- Vérifier post-implémentation par grep que `langchain_openai` est encore importé pour `ChatOpenAI` mais plus jamais pour `OpenAIEmbeddings` (cf. SC-003 : grep ciblé `OpenAIEmbeddings` dans `backend/app/` doit retourner 0).

### Rationale

FR-014 est explicite : « Le mapping de configuration LLM principal (passerelle OpenRouter) DOIT rester strictement inchangé ». Retirer `langchain-openai` casserait ChatOpenAI.

### Alternatives considered

- **A** : Migrer aussi le LLM vers un autre SDK pour pouvoir retirer `langchain-openai` → hors scope F25 (cf. spec « Hors Scope »).
- **B** (retenu) : Coexistence des deux packages.

### Action sur config.py

- Le champ `openai_api_key` (`app/core/config.py`) était utilisé exclusivement pour `OpenAIEmbeddings`. Après migration, il **devient orphelin**.
- Décision : le **conserver** marqué `Deprecated` dans le commentaire en attendant un cleanup ultérieur, OU le supprimer maintenant. Compte tenu du principe VII (Simplicité — pas de code mort), **le supprimer** est la bonne décision.
- Mise à jour `.env.example` : retirer `OPENAI_API_KEY=`, ajouter `VOYAGE_API_KEY=` avec lien `https://www.voyageai.com/`.

---

## R6 — Compatibilité tests SQLite in-memory

### Findings

- Le pattern `Vector(1536) if Vector is not None else Text` dans les modèles préserve la branche SQLite (où `pgvector` import lève ImportError → `Vector is None`).
- Migration 023 utilise `bind.dialect.name == "postgresql"` pour sauter HNSW + RLS sur SQLite.
- La nouvelle migration 043 doit suivre le même pattern : skip ALTER COLUMN si dialect SQLite (la colonne est déjà `Text`, pas besoin de la « migrer »).
- Tests `backend/tests/memory/test_service.py` mockent `_embeddings_model()` via `monkeypatch` → leurs vecteurs de retour passent à 1024 floats au lieu de 1536.
- `backend/tests/conftest.py` configure SQLite in-memory pour les tests unitaires ; PostgreSQL est utilisé uniquement pour les tests `tests/migrations/` et certains intégration.

### Decision

- Migration 043 : guard `if is_postgres:` autour de tout le bloc `ALTER COLUMN` + DROP/CREATE INDEX.
- Modèles : préserver le pattern `Vector(N) if Vector is not None else Text`, juste passer `1536 → 1024`.
- Tests `test_service.py` et `test_recall_history_tool.py` : remplacer toutes occurrences de `[0.1] * 1536` par `[0.1] * 1024` (helper `_make_test_vector(dim: int = 1024)`).
- Nouveau test contractuel `tests/memory/test_embeddings_client.py` : assert que `_embeddings_model()` (avec `VOYAGE_API_KEY` set) retourne une instance `VoyageAIEmbeddings`. Test skipé si la clé n'est pas en env CI.

### Rationale

Préserve FR-015 (« branche tests SQLite in-memory DOIT continuer à passer ») et la TDD strict (Constitution principe IV).

---

## R7 — Script `reembed_all.py` : contrat & comportement

### Findings

- `app/scripts/` contient déjà 2 scripts (`fetch_exchange_rates.py`, `seed_admin.py`) avec pattern :
  - Module `__main__.py`-style (`python -m app.scripts.NAME`)
  - Loader async via `asyncio.run(main())`
  - Configuration via `argparse`
  - Idempotent (SELECT-before-INSERT pattern)

- Pour `reembed_all.py`, le contrat est : **scanner les 3 tables vectorielles à la recherche de `embedding IS NULL`, ré-embedder par batch, persister.**

### Decision

CLI :
```
python -m app.scripts.reembed_all [--table {messages,documents,financing,all}] [--limit N] [--dry-run] [--batch-size B]
```

Defaults : `--table all`, pas de limit, `--dry-run` désactivé, `--batch-size 72` (max Voyage pour voyage-3.5).

Comportement :
- Pour chaque table cible, `SELECT id, chunk_text/content WHERE embedding IS NULL ORDER BY created_at LIMIT N`.
- Batcher les contenus, appeler `aembed_documents(batch)`, persister via `UPDATE table SET embedding = :v WHERE id = :id`.
- Logger un compteur (`{X} ré-embeddings réussis, {Y} échecs sur {Z} candidats`).
- `--dry-run` : tout sauf le `UPDATE` final.
- Échec API → retry SDK comme en runtime, sinon log warning et passage au batch suivant.
- Sortie code : 0 si tout traité (même partiellement), 1 si erreur fatale (clé manquante, DB indisponible).

### Rationale

- Aligné sur le pattern existant `app/scripts/`.
- `--dry-run` essentiel pour valider en pré-prod sans coût Voyage.
- `--batch-size` permet à l'admin de calibrer en fonction du quota Voyage.

### Alternatives considered

- **A** : Script bash + curl direct vers Voyage → réinvente la roue, perd la consistance Pydantic v2.
- **B** : Scinder en 3 scripts (un par table) → DRY violé.
- **C** (retenu) : Script unique avec `--table` discriminator.

---

## R8 — Eval baseline française pour SC-002 (smoke test non-gating)

### Findings

- SC-002 vise top-3 sur 8/10 requêtes en français.
- Q4 (clarification) : eval manuelle, non-gating, baseline à consigner dans `docs/embeddings-voyage.md`.

### Decision

10 requêtes francophones de baseline, balayant les 3 tables vectorielles et les parcours PME UEMOA :

| # | Requête | Table cible | Résultat attendu (top-3) |
|---|---------|-------------|--------------------------|
| 1 | « financement pour valoriser les déchets organiques en énergie au Sénégal » | `financing_chunks` (fonds) | SUNREF, GCF déchets, BOAD ESS |
| 2 | « lignes de crédit BCEAO pour PME agricoles » | `financing_chunks` | BOAD agriculture, FNDE, BCEAO refinancement |
| 3 | « rappelle-moi nos discussions sur le projet solaire à Dakar » | `message_chunks` | extraits messages projet solaire |
| 4 | « mes notes sur la conformité GRI 2021 » | `message_chunks` | extraits messages GRI |
| 5 | « bilan carbone secteur transport en zone UEMOA » | `document_chunks` | chunks PDF carbone transport |
| 6 | « critères ESG pour entreprise de recyclage » | `document_chunks` | chunks Mefali / IFC PS recyclage |
| 7 | « accréditation BOAD pour fonds verts » | `financing_chunks` (intermédiaires) | intermédiaires BOAD GCF/FEM |
| 8 | « fonds bilatéraux français pour PME africaines » | `financing_chunks` | AFD, Proparco, Sunref AFD |
| 9 | « plan d'action ESG sur 12 mois pour PME informelle » | `message_chunks` ou `document_chunks` | extraits action plan informel |
| 10 | « subvention non remboursable pour énergie renouvelable » | `financing_chunks` | GCF readiness, FNDE subvention |

Procédure :
1. Démarrer un environnement local avec `VOYAGE_API_KEY` valide.
2. Seeder le catalogue de fonds (`python -m app.modules.financing.seed`) puis lancer `reembed_all`.
3. Pour chaque requête : exécuter via `recall_history` (queries 3, 4, 9) ou via le service de matching financing (queries 1, 2, 7, 8, 10) ou via le RAG documents (queries 5, 6).
4. Consigner le top-3 dans `docs/embeddings-voyage.md` sous une section « SC-002 baseline ».
5. Si > 2 requêtes hors top-3 : ouvrir une issue de re-calibration (non bloquant pour merge).

### Rationale

- Couvre les 3 tables et les 3 parcours produit (financing, memory, RAG).
- Mélange spécifique sectoriel africain (Sénégal, UEMOA, BOAD) et générique (subvention, énergie renouvelable).
- Reproductibilité : queries figées + résultats archivés.

### Alternatives considered

- **A** : Eval automatisée via pytest avec API Voyage réelle → coût + flakiness.
- **B** (retenu) : Eval manuelle one-shot + archivage doc.

---

## R9 — Mode dégradé : implémentation harmonisée

### Findings

- Pattern actuel `memory/service.py:_embeddings_model()` lève `RuntimeError("Aucune cle d'embedding configuree")` si la clé est absente, capturée dans le caller best-effort.
- `financing/service.py` retourne `[]` (liste vide) si `settings.openrouter_api_key` est vide.
- `documents/service.py` : à vérifier (probablement même pattern que financing).

### Decision

Helper centralisé `app/lib/embeddings.py::get_embeddings_client()` :
```python
def get_embeddings_client() -> "VoyageAIEmbeddings | None":
    """Retourne un client Voyage configuré, ou None si VOYAGE_API_KEY vide.

    Convention : un retour None déclenche le mode dégradé (caller log + skip).
    L'absence de clé est attendue (dev local, CI sans secret) ; les exceptions
    sont des bugs."""
    if not settings.voyage_api_key:
        logger.warning(
            "Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env."
        )
        return None

    from langchain_voyageai import VoyageAIEmbeddings
    return VoyageAIEmbeddings(
        voyage_api_key=settings.voyage_api_key,
        model=settings.voyage_model,
        request_timeout=10,
        max_retries=1,
        batch_size=72,
    )
```

Tous les call sites (memory, financing×2, documents) appellent ce helper et early-return si `None`.

### Rationale

- DRY (un seul endroit pour le warning + la construction).
- Plus simple à mocker.
- Aligne sur FR-006 (mode dégradé + log clair) et FR-001 (fournisseur unique).

### Alternatives considered

- **A** : Lever une exception et capturer 4× → bruit, viole DRY.
- **B** (retenu) : Helper retournant `Optional`.

---

## R10 — Discrepancies à corriger dans `spec.md`

### Liste des corrections nécessaires

Suite à R1, mettre à jour `spec.md` :

1. **Edge Cases** : remplacer « les colonnes `embedding` des 4 tables » par « des 3 tables vectorielles (`message_chunks`, `document_chunks`, `financing_chunks`) ».
2. **FR-007a** : remplacer « 4 tables vectorielles (`message_chunks`, `document_chunks`, `documents`, `funds`) » par « 3 tables vectorielles (`message_chunks`, `document_chunks`, `financing_chunks`) ».
3. **FR-008** : « ajuste les 4 tables vectorielles existantes (chunks de messages, chunks de documents, documents, fonds) » → « ajuste les 3 tables vectorielles existantes (chunks de messages, chunks de documents, chunks financing) ».
4. **FR-010** : « les index de recherche vectorielle (HNSW cosinus) » → ajouter « (création d'un nouvel index HNSW pour `financing_chunks` qui n'en avait pas — corrige un bug pré-existant migration 008 où la colonne était `Text` au lieu de `vector`) ».
5. **Key Entities** :
   - Supprimer « Embedding de document complet (`documents.embedding`) ».
   - Supprimer « Embedding de fonds (`funds.embedding`) ».
   - Ajouter « Embedding de chunk financing (`financing_chunks.embedding`) : représentation vectorielle d'un chunk descriptif d'un fonds OU d'un intermédiaire (discriminator `source_type`). Sert la recherche sémantique sur la page `/financing` et le matching projet-financement. ⚠️ Cette colonne était `TEXT` en production (bug schéma migration 008) ; F25 la promeut à `vector(1024)` avec création d'un index HNSW. »
6. **SC-001** : `SELECT vector_dims(embedding) FROM message_chunks` reste valide (table existante) ; ajouter une note pour `document_chunks` et `financing_chunks`.
7. **SC-007** : préciser « 3 tables vectorielles concernées (message_chunks, document_chunks, financing_chunks) ».
8. **Assumptions** : ajouter une nouvelle assumption explicitant la correction de bug schéma `financing_chunks` au passage.

Ces corrections seront appliquées immédiatement après la rédaction de research.md (avant data-model.md).

---

## R11 — Test paths discrepancy (SC-006)

### Findings

- Spec mentionne `backend/tests/financing/` et `backend/tests/documents/` mais ces dossiers n'existent pas.
- Tests réels en flat layout :
  - `backend/tests/test_financing_*.py` (7 fichiers : node, status, preparation, intermediaries, etc.) + `tests/test_tools/test_financing_tools.py` + `tests/test_offers/test_financing_tools_offers.py` + `tests/test_prompts/test_financing_prompt.py`.
  - `backend/tests/test_document_*.py` (8 fichiers) + `tests/test_tools/test_document_tools.py`.
  - `backend/tests/memory/` ✅ (dossier existant).

### Decision

Reformuler SC-006 :
```
SC-006: pytest backend/tests/memory/ backend/tests/test_financing_*.py
        backend/tests/test_document_*.py backend/tests/test_tools/test_document_tools.py
        backend/tests/test_tools/test_financing_tools.py -v passe à 100%.
```

OU plus simplement, créer un marker pytest `@pytest.mark.embeddings` apposé sur tous les tests touchés par F25, et exécuter `pytest -m embeddings -v` comme commande gating de SC-006.

### Rationale

Marker pytest = solution canonique (Constitution python/testing.md « Use pytest.mark for test categorization »). Permet aussi à des tests futurs de s'inscrire automatiquement dans le périmètre F25.

### Action sur la spec

Mettre à jour SC-006 pour utiliser le marker `@pytest.mark.embeddings`. Lister les tests à marquer dans data-model.md / tasks.md.

---

## Synthèse des décisions

| # | Domaine | Décision |
|---|---------|----------|
| R1 | Tables réelles | 3 tables : `message_chunks`, `document_chunks`, `financing_chunks` (corrige spec). |
| R2 | Audit / RLS | Aucune intervention nécessaire. |
| R3 | SDK Voyage | Helper centralisé `app/lib/embeddings.py::get_embeddings_client()` ; `voyage_embedding_dim: Literal[1024]`. |
| R4 | Pattern Alembic | DROP idx → SET NULL → ALTER COLUMN TYPE → CREATE idx ; idempotent via `pg_attribute.atttypmod` check. |
| R5 | Coexistence packages | Conserver `langchain-openai` (pour ChatOpenAI/OpenRouter) ; ajouter `langchain-voyageai`. Retirer `openai_api_key` orphelin du config + `.env.example`. |
| R6 | Tests SQLite | Préserver pattern `Vector(N) if Vector is not None else Text` ; mocker `_embeddings_model()` à 1024d. |
| R7 | Script reembed_all | CLI `[--table {messages,documents,financing,all}] [--limit N] [--dry-run] [--batch-size B]`. |
| R8 | Eval baseline FR | 10 requêtes définies, archivées dans `docs/embeddings-voyage.md`, non-gating. |
| R9 | Mode dégradé | Helper centralisé retournant `Optional[VoyageAIEmbeddings]` ; tous les callers early-return. |
| R10 | Corrections spec | 8 endroits à mettre à jour suite à R1. |
| R11 | Marker pytest | `@pytest.mark.embeddings` pour SC-006. |

**Toutes les NEEDS CLARIFICATION sont résolues.** Phase 1 peut démarrer.
