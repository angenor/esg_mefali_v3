# F25 — Embeddings Voyage AI (voyage-3.5)

> Migration des embeddings pgvector du backend ESG Mefali de
> `text-embedding-3-small` (OpenAI, 1536 dims) vers `voyage-3.5` (Voyage AI,
> 1024 dims, multilingue). Migration de schéma : `043_embeddings_voyage_dim`.

## 1. Politique de fournisseur

### 1.1 Choix retenu

- **Fournisseur** : Voyage AI ([https://www.voyageai.com/](https://www.voyageai.com/))
- **Modèle** : `voyage-3.5` (1024 dimensions, multilingue)
- **Tarif** : ~ $0.06 / 1 M tokens (cf. [pricing](https://www.voyageai.com/pricing/))
- **Justification** : qualité française nuancée supérieure aux modèles
  généralistes (vocabulaire UEMOA/CEDEAO, terminologie ESG en français,
  finance verte africaine), tarif compétitif, compatibilité native via
  `langchain-voyageai>=0.1.3`.

### 1.2 Modèles autorisés (Pydantic Literal)

```python
voyage_model: Literal[
    "voyage-3.5",            # 1024 dims — défaut MVP
    "voyage-3-large",        # alternative haute qualité (non utilisé)
    "voyage-multilingual-2", # alternative legacy (non utilisé)
]
```

Le passage à `voyage-3-large` ou `voyage-multilingual-2` requiert :
1. Vérifier la dim native du modèle.
2. Adapter `voyage_embedding_dim: Literal[1024]` en conséquence.
3. Migrer les colonnes pgvector vers la nouvelle dim (nouveau migration
   Alembic, mêmes étapes que F25).

### 1.3 Conservation `langchain-openai`

`langchain-openai>=0.3.0` reste dans `requirements.txt` car il fournit
`ChatOpenAI`, utilisé par `app/graph/llm.py` pour piloter le LLM via
OpenRouter (claude-sonnet-4-x). Seul le sous-module `OpenAIEmbeddings`
disparaît du backend.

## 2. Architecture — helper centralisé

Tous les call sites du backend utilisent l'unique helper :

```python
from app.lib.embeddings import get_embeddings_client

client = get_embeddings_client()
if client is None:
    return []  # mode degrade — voir §4
vector = await client.aembed_query(text)
```

Call sites :
- `app/modules/memory/service.py::_embeddings_model()` (F12)
- `app/modules/financing/service.py::search_financing_chunks()` (F08 RAG)
- `app/modules/financing/seed.py::generate_embeddings()` (F08 seed)
- `app/modules/documents/service.py::_get_embeddings()` (RAG documents)
- `app/scripts/reembed_all.py::main()` (script admin opt-in)

### 2.1 Paramètres SDK (FR-007c)

```python
VoyageAIEmbeddings(
    voyage_api_key=settings.voyage_api_key,
    model=settings.voyage_model,        # "voyage-3.5"
    batch_size=72,                       # max recommande
)
# + override _client/_aclient avec timeout=10s, max_retries=1
```

> **Note** : `langchain-voyageai 0.1.3` ne supporte pas
> `request_timeout` / `max_retries` au constructeur (`ConfigDict
> extra="forbid"`). Le helper override `_client` / `_aclient` après
> instantiation pour appliquer FR-007c.

## 3. Procédure de re-embedding

### 3.1 Lazy (automatique)

Toute ligne avec `embedding IS NULL` est ré-embeddée à la demande :
- **Messages** : à l'insertion via hook `after_insert` (best-effort,
  `asyncio.create_task`).
- **Documents** : au moment de l'indexation initiale (`store_embeddings`).
- **Financing** : aucun ré-embedding lazy automatique — soit lors du
  seed, soit via le script admin (cf. §3.2).

### 3.2 Backfill batch (admin opt-in)

```bash
# Dry-run d'abord (no-op, observation seule)
python -m app.scripts.reembed_all --dry-run

# Cible une seule table avec limite
python -m app.scripts.reembed_all --table financing --limit 50

# Execution reelle complete
python -m app.scripts.reembed_all --table all
```

CLI complète :

```
python -m app.scripts.reembed_all [OPTIONS]

  --table {messages,documents,financing,all}   Defaut: all
  --limit N                                    Limite par table
  --batch-size B                               Taille batch (defaut 72)
  --dry-run                                    Aperçu sans UPDATE
```

Codes de sortie : `0` succès partiel ou complet ; `1` cle Voyage absente
ou erreur fatale ; `2` argument invalide.

## 4. Mode dégradé

### 4.1 Sans `VOYAGE_API_KEY`

L'application démarre normalement, le chat fonctionne, **aucun
embedding n'est créé**.

Logs attendus :
```
WARNING - Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env.
```

Comportements :
- `recall_history` retourne `[]` (mode mémoire désactivé).
- `search_financing_chunks` retourne `[]` (recherche sémantique
  désactivée — keyword matching toujours actif).
- `_get_embeddings` (documents) retourne `None` ; chunks insérés avec
  `embedding=NULL`.
- Aucune erreur 5xx, aucune interruption du chat.

### 4.2 Erreurs API transitoires

Le SDK Voyage retry **1× automatiquement** (FR-007c). Si l'échec
persiste :
- L'embedding échoue silencieusement (best-effort, log warning).
- La ligne est insérée avec `embedding=NULL`.
- Au prochain accès via lazy re-embedding ou backfill, la ligne sera
  retentée.

## 5. Estimation des coûts (SC-008)

### 5.1 Tarif

`voyage-3.5` : ~ $0.06 / 1 M tokens (input + output combinés).

### 5.2 Estimation dev/staging

| Scenario | Volume | Coût |
|----------|--------|------|
| Re-embedding initial (post-migration) | 1000 chunks × 500 tokens ≈ 500k tokens | ~$0.03 |
| Conversations actives quotidiennes | 100 messages × 200 tokens × 5 chunks/msg ≈ 100k tokens/jour | ~$0.006/jour |
| **Cap journalier dev** | < 0.10 USD/jour | **conforme SC-008** |

### 5.3 Estimation production (10 PME × 50 messages/jour)

| Scenario | Volume | Coût |
|----------|--------|------|
| Volume total quotidien | 500 messages × 200 tokens × 5 chunks ≈ 500k tokens/jour | ~$0.03/jour |
| **Cap journalier prod estimé** | < 1 USD/jour | **conforme SC-008** |

Suivi recommandé : alerte si la consommation Voyage > $1/jour pendant
7 jours consécutifs (à mettre en place hors scope F25).

## 6. Posture vie privée

### 6.1 Résidence des données

- **Voyage AI** est une société américaine. Les requêtes d'embedding
  transitent par leurs serveurs aux États-Unis.
- **DPA standard** : Voyage propose un Data Processing Agreement (DPA)
  conforme RGPD. Disponible sur demande à `enterprise@voyageai.com`.
- **Pas de stockage des inputs** : Voyage déclare ne pas conserver les
  textes envoyés à l'API embeddings (cf.
  [Voyage AI Privacy Policy](https://www.voyageai.com/privacy)).

### 6.2 Masquage F12 (messages)

Avant embedding, les messages sont masqués par
`app/modules/memory/service.py::mask_secrets()` :
- Tokens (Bearer, JWT) → `[TOKEN]`
- Emails → `[EMAIL]`
- Numéros bancaires (IBAN, RIB) → `[BANK]`
- Cartes (Luhn) → `[CARD]`

Cette posture est **strictement préservée** par F25 (aucune modification
du masquage).

### 6.3 Pas de masquage sur fonds / documents

Justification :
- Les **catalogues de fonds** (`financing_chunks`) sont publics par
  nature (fiches descriptives GCF/BOAD/AFD/etc.) — aucune PII.
- Les **documents PME** (`document_chunks`) contiennent des données
  métier (rapports ESG, factures, contrats) qui ne sont pas masquées
  car le masquage casserait la pertinence du RAG. Le contrôle d'accès
  RLS F02 (filtrage par `account_id`) garantit qu'aucun tenant ne voit
  les documents d'un autre tenant.

## 7. Procédure de rollback Alembic

```bash
# Rollback de la migration 043 :
alembic downgrade -1
# Resultat : les 3 tables vectorielles repassent en vector(1536)
# (financing_chunks repasse en TEXT, etat anterieur bug mig. 008).
# Toutes les valeurs `embedding` sont remises a NULL.
# Re-application :
alembic upgrade head
```

Round-trip up → down → up validé en < 30 secondes (SC-004).

## 8. Procédure d'eval baseline SC-002 (non-gating)

> **Eval manuelle one-shot** consignée dans ce document. Si > 2 requêtes
> hors top-3 → ouvrir une issue de re-calibration (non bloquant pour
> merge).

### 8.1 Setup

1. Configurer `VOYAGE_API_KEY` valide.
2. `alembic upgrade head` (applique 043).
3. `python -m app.modules.financing.seed` (catalogue fonds).
4. Importer un PDF carbone et 3-4 messages de chat substantiels.
5. `python -m app.scripts.reembed_all --table all`.

### 8.2 Requêtes de baseline (10 requêtes francophones)

| # | Requête | Table cible | Top-3 attendu |
|---|---------|-------------|---------------|
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

### 8.3 Résultats baseline (smoke test 2026-05-08)

| # | Top-3 retourné | Conforme attendu ? |
|---|----------------|---------------------|
| 1 | _non testé (besoin seed financing)_ | ☐ |
| 2 | _non testé_ | ☐ |
| 3 | **`recall_history` — ✅ valide** : agent rappelle « déchets organiques au Sénégal » + le QCU compostage/biogaz précédent (variante de la requête #3) | ☑ |
| 4 | _non testé_ | ☐ |
| 5 | _non testé_ | ☐ |
| 6 | _non testé_ | ☐ |
| 7 | _non testé_ | ☐ |
| 8 | _non testé_ | ☐ |
| 9 | _non testé_ | ☐ |
| 10 | _non testé_ | ☐ |

**Validation E2E 2026-05-08 sur compte NeloTech (PME, account c9969300)** :
- Migration 043 appliquée : `message_chunks` / `document_chunks` / `financing_chunks` en `vector(1024)` ✅
- 4 indexes HNSW présents (incl. nouveau `ix_financing_chunks_embedding_hnsw` corrigeant bug mig. 008) ✅
- `python -m app.scripts.reembed_all --table messages` → 20 lignes mises à jour, dim=1024 ✅
- Hook lazy F12 : 22 message_chunks au total, 0 NULL après nouvelle conversation ✅
- US1 (recall_history) : l'agent IA cite correctement le contexte de conversations passées via similarité cosine sur embeddings voyage-3.5 ✅

**Critère de réussite** : 8/10 requêtes avec top-3 conforme aux attentes.
Si < 8 → ouvrir une issue de re-calibration.

## 9. FAQ

### 9.1 « Pas de Voyage API key — que se passe-t-il ? »

→ Mode dégradé propre. Le chat continue, le warning est loggé une fois
par appel à `get_embeddings_client()`. Les nouveaux messages/documents
sont insérés avec `embedding=NULL`. Aucune erreur 5xx, aucune
interruption.

Pour réactiver les embeddings : ajouter `VOYAGE_API_KEY=...` dans `.env`,
redémarrer l'app, puis (optionnel) lancer
`python -m app.scripts.reembed_all` pour rattraper les lignes en
attente.

### 9.2 « Comment vérifier que les embeddings sont bien en 1024 dims ? »

```sql
SELECT vector_dims(embedding) AS dim, COUNT(*)
FROM message_chunks WHERE embedding IS NOT NULL
GROUP BY dim;
-- Attendu : dim=1024
```

### 9.3 « Le SDK propose-t-il un modèle français spécifique ? »

`voyage-3.5` est multilingue avec excellent support français. Pas
besoin d'un modèle dédié.

### 9.4 « Quel est l'impact de la migration sur les conversations en
cours ? »

Aucun. La migration vide les colonnes `embedding` (toutes les valeurs
deviennent `NULL`), mais ne supprime aucune ligne métier (messages,
chunks textuels). Au prochain accès :
- `recall_history` retourne `[]` jusqu'au ré-embedding (lazy ou batch).
- `search_financing_chunks` retourne `[]` jusqu'au ré-embedding.
- Le chat continue de fonctionner normalement (réponses LLM toujours
  pertinentes).

## 10. Références

- Spec F25 : [`specs/043-voyage-embeddings-migration/spec.md`](../specs/043-voyage-embeddings-migration/spec.md)
- Plan F25 : [`specs/043-voyage-embeddings-migration/plan.md`](../specs/043-voyage-embeddings-migration/plan.md)
- Data model : [`specs/043-voyage-embeddings-migration/data-model.md`](../specs/043-voyage-embeddings-migration/data-model.md)
- Contrat helper : [`specs/043-voyage-embeddings-migration/contracts/voyage-embeddings-client.md`](../specs/043-voyage-embeddings-migration/contracts/voyage-embeddings-client.md)
- Quickstart : [`specs/043-voyage-embeddings-migration/quickstart.md`](../specs/043-voyage-embeddings-migration/quickstart.md)
- Migration Alembic : [`backend/alembic/versions/043_embeddings_voyage_dim.py`](../backend/alembic/versions/043_embeddings_voyage_dim.py)
- Script CLI : [`backend/app/scripts/reembed_all.py`](../backend/app/scripts/reembed_all.py)
- Helper centralisé : [`backend/app/lib/embeddings.py`](../backend/app/lib/embeddings.py)
- F12 (mémoire pgvector) : [`docs/auth-and-multitenant.md`](./auth-and-multitenant.md) (RLS multi-tenant héritée).
