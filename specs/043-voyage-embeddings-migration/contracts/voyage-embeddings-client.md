# Contract: Voyage AI Embeddings Client (`app/lib/embeddings.py`)

**Branch**: `043-voyage-embeddings-migration` | **Date**: 2026-05-08

Ce document décrit le contrat exposé par le helper `get_embeddings_client()` introduit par F25. Il s'agit de l'interface unique qu'utilisent **tous** les call sites du backend pour produire ou consommer des embeddings (FR-001).

---

## 1. Surface API publique

```python
# Module: app/lib/embeddings.py

def get_embeddings_client() -> Optional[VoyageAIEmbeddings]:
    """Retourne un client Voyage configure prêt à l'emploi, ou None.

    Comportement déterministe :
    - Si VOYAGE_API_KEY est non-vide → retourne une instance VoyageAIEmbeddings
      configurée avec le modèle settings.voyage_model et timeout/retry FR-007c.
    - Si VOYAGE_API_KEY est vide ou absent → retourne None ET émet un
      logger.warning explicite (« Aucune cle d'embedding configuree. ... »).
    - Si import langchain_voyageai échoue (package manquant) → retourne None
      ET émet un logger.error.

    Cette fonction NE PROPAGE JAMAIS d'exception pour ces cas attendus.
    Les callers doivent gérer le retour None comme un signal de mode dégradé.
    """
```

### Signatures connexes consommées par le helper

```python
# La librairie SDK fournit (>= 0.1.4) :
class VoyageAIEmbeddings:
    voyage_api_key: str
    model: str             # 'voyage-3.5' par défaut F25
    request_timeout: int   # secondes
    max_retries: int
    batch_size: int

    async def aembed_query(self, text: str) -> list[float]: ...
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
```

---

## 2. Préconditions

| Précondition | Source | Vérification |
|--------------|--------|--------------|
| `settings.voyage_api_key` est défini OU vide (jamais `None`) | Pydantic v2 `str = ""` | typage `Settings.voyage_api_key: str` (default `""`) |
| `settings.voyage_model` ∈ `{"voyage-3.5", "voyage-3-large", "voyage-multilingual-2"}` | Pydantic `Literal[...]` | échec démarrage si valeur invalide en env |
| `settings.voyage_embedding_dim` == `1024` | Pydantic `Literal[1024]` | constante MVP |
| `langchain-voyageai>=0.1.4` est installé | `requirements.txt` | échec import capturé en `logger.error` + return `None` |

---

## 3. Postconditions

### Cas 1 — Clé valide

- Retour : instance `VoyageAIEmbeddings` configurée.
- Effets de bord : aucun (pas de log).
- Invariants : l'instance est réutilisable thread-safe (le SDK gère son propre pool HTTP).

### Cas 2 — Clé absente / vide

- Retour : `None`.
- Effets de bord : `logger.warning("Aucune cle d'embedding configuree. ...")` émis exactement une fois par appel.
- Invariants : aucun appel HTTP n'est tenté.

### Cas 3 — Package manquant

- Retour : `None`.
- Effets de bord : `logger.error("Module langchain_voyageai indisponible. ...")` émis exactement une fois.
- Invariants : aucune exception ne traverse la frontière du helper.

---

## 4. Comportement runtime du client retourné (Cas 1)

| Scénario | Méthode | Comportement attendu |
|----------|---------|----------------------|
| Texte court FR (≤ 6000 c) | `aembed_query` | Retourne un `list[float]` de longueur **exactement 1024**. Latence typique < 1 s. |
| Liste de 5–72 textes | `aembed_documents` | Retourne une liste de listes (cardinalité = input). Toutes les listes internes ont longueur 1024. |
| Texte vide | `aembed_query` | Comportement SDK par défaut — vraisemblablement vecteur de zéros ou erreur 400. **Caller MUST guard**. |
| Texte > 32k tokens | `aembed_query` | SDK truncate par défaut (paramètre `truncation=True` implicite). |
| API Voyage indisponible / 5xx | toute méthode | SDK retry 1× avec backoff (`max_retries=1`). Si échec persiste → exception `voyageai.error.VoyageError` à capturer best-effort par le caller. |
| Timeout 10 s dépassé | toute méthode | `httpx.TimeoutException` → caller doit traiter comme « embedding NULL », FR-007c. |
| Rate limit (429) | toute méthode | SDK retry 1× ; si encore 429 → exception. Caller traite comme NULL + lazy retry plus tard. |
| Quota épuisé / 401 | toute méthode | Exception. Caller log warning et fonctionne en mode dégradé. |

---

## 5. Contrats des call sites

### 5.1 `memory/service.py::_embeddings_model()` (refactor)

```python
def _embeddings_model() -> Any:
    """Construire le client d'embeddings F25 (voyage-3.5).

    Conserve la signature publique pour preserver les ~7 tests qui mockent
    cette fonction via monkeypatch."""
    from app.lib.embeddings import get_embeddings_client
    client = get_embeddings_client()
    if client is None:
        raise RuntimeError(
            "Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env."
        )
    return client
```

> **Note** : `_embeddings_model()` lève une exception (pour préserver le contrat existant des callers F12 qui le capturent), tandis que `get_embeddings_client()` retourne `None`. Cela respecte la rétrocompatibilité côté memory tout en exposant une API plus simple aux nouveaux callers (financing, documents).

### 5.2 `financing/service.py::search_financing_chunks()` (refactor)

```python
async def search_financing_chunks(
    db: AsyncSession,
    query_text: str,
    source_type: str | None = None,
    limit: int = 5,
) -> list[FinancingChunk]:
    from app.lib.embeddings import get_embeddings_client

    client = get_embeddings_client()
    if client is None:
        return []  # mode degrade : pas d'embeddings dispo

    try:
        query_vector = await client.aembed_query(query_text)
    except Exception:
        logger.warning("Echec embedding requete financing.", exc_info=True)
        return []

    query = (
        select(FinancingChunk)
        .where(FinancingChunk.embedding.is_not(None))
        .order_by(FinancingChunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    if source_type:
        query = query.where(FinancingChunk.source_type == source_type)

    result = await db.execute(query)
    return list(result.scalars().all())
```

### 5.3 `documents/service.py::_get_embeddings()` (refactor)

```python
def _get_embeddings() -> Any:
    """Construire le client d'embeddings pour le RAG documentaire."""
    from app.lib.embeddings import get_embeddings_client
    return get_embeddings_client()  # peut retourner None
```

Callers de `_get_embeddings()` : ajouter early-return `if client is None: return ...` partout où l'instance est utilisée.

### 5.4 `financing/seed.py::generate_embeddings()` (refactor)

Même pattern que 5.2 : early-return si `client is None`. Le seed peut s'exécuter sans embeddings (les chunks sont créés avec `embedding NULL`, le `reembed_all` ou le lazy comblera).

---

## 6. Compatibilité tests (mocks)

### 6.1 Pattern monkeypatch existant

```python
# Pattern actuellement utilise par tests/memory/test_service.py
monkeypatch.setattr(
    "app.modules.memory.service._embeddings_model",
    lambda: FakeEmbeddings(dim=1536),
)
```

Doit devenir :

```python
monkeypatch.setattr(
    "app.modules.memory.service._embeddings_model",
    lambda: FakeEmbeddings(dim=1024),
)
```

### 6.2 Helper de test partagé

`tests/conftest.py` (ou nouveau `tests/_helpers/embeddings_fixtures.py`) :

```python
class FakeEmbeddings:
    def __init__(self, dim: int = 1024):
        self.dim = dim

    async def aembed_query(self, text: str) -> list[float]:
        return [0.1] * self.dim

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dim for _ in texts]


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Fixture pytest reutilisable pour mocker get_embeddings_client()."""
    fake = FakeEmbeddings(dim=1024)
    monkeypatch.setattr(
        "app.lib.embeddings.get_embeddings_client",
        lambda: fake,
    )
    return fake
```

---

## 7. Invariants de sécurité

- **VOYAGE_API_KEY n'apparaît jamais en log**. Le SDK injecte la clé dans les headers HTTP, pas dans les logs.
- **Aucun secret n'est exposé via le client retourné**. `client.voyage_api_key` est lisible programmatiquement (pour les tests d'introspection) mais doit être référencé sans logging.
- **Le helper ne fait aucun appel réseau** ; seul l'appel `await client.aembed_*` déclenche du trafic. Cela permet aux tests d'instancier le client en CI sans clé pour vérifier des invariants statiques.

---

## 8. Versioning et évolution

- Le helper est un point d'extension futur : si un fournisseur alternatif est introduit (ex. Cohere Embeddings), il devra être ajouté **dans ce helper uniquement**, sans toucher les call sites.
- Le `Literal` sur `voyage_model` peut s'étendre en ajoutant une nouvelle valeur — `voyage_embedding_dim` doit alors être adapté dynamiquement (passer de `Literal[1024]` à `dict[str, int]` keyed by model). Hors scope F25.

---

## 9. Conformité spec

| Exigence | Couverte ? |
|----------|------------|
| FR-001 (fournisseur unique d'embeddings dédié) | ✅ helper unique |
| FR-006 (mode dégradé clair) | ✅ `None` + `logger.warning` |
| FR-007 (NULL si erreur transitoire) | ✅ caller-side (l'helper ne décide pas, caller decide) |
| FR-007c (1 retry + 10 s timeout) | ✅ paramètres SDK |
| FR-012 (config typée Pydantic) | ✅ `voyage_api_key`, `voyage_model: Literal[...]`, `voyage_embedding_dim: Literal[1024]` |
| FR-013 (clé en env, pas en code) | ✅ `settings.voyage_api_key` lu depuis env |
| FR-014 (LLM mapping inchangé) | ✅ aucune modification des champs `openrouter_*` ou `llm_*` |
| FR-015 (SQLite tests) | ✅ helper retourne `None` si CI sans clé, branche `Vector → Text` côté modèle préservée |
| FR-016 (0 import résiduel OpenAIEmbeddings) | ✅ helper Voyage uniquement ; vérifié par grep SC-003 |
