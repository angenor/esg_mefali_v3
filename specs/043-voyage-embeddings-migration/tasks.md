---
description: "Task list — F25 Voyage AI Embeddings Migration"
---

# Tasks: F25 — Migration des Embeddings vers Voyage AI

**Input**: Design documents from `/specs/043-voyage-embeddings-migration/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/voyage-embeddings-client.md ✅, quickstart.md ✅

**Tests** : OBLIGATOIRES (Constitution principe IV Test-First, NON-NEGOTIABLE). Pour chaque tâche d'implémentation, le test correspondant DOIT être écrit en RED avant l'implémentation.

**Organization** : tâches groupées par user story pour permettre implémentation et test indépendants. **Périmètre corrigé en Phase 0** : 3 tables vectorielles (`message_chunks`, `document_chunks`, `financing_chunks`), pas 4. Le bug schéma `financing_chunks.embedding TEXT` (mig. 008) est corrigé opportunément par la migration 043.

## Format: `[ID] [P?] [Story?] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance sur tâche incomplète)
- **[Story]** : Rattachement à une user story (US1, US2, US3) — uniquement Phases 3-5
- Chemins absolus relatifs au repo `/Users/mac/Documents/projets/2025/esg_mefali_v3/`

## Path Conventions

Web app monolithique modulaire (cf. `plan.md` Project Structure) :
- Backend Python : `backend/app/`, `backend/tests/`, `backend/alembic/versions/`
- Documentation : `docs/` (racine repo)
- Config env : `.env.example` (racine), `backend/.env.example`
- Doc agent : `CLAUDE.md` (racine)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Préparer l'environnement F25 — dépendances, configuration, marker pytest, fixture de test partagée. Toutes les tâches portent sur des fichiers distincts → exécutables en parallèle.

- [X] T001 [P] Ajouter `langchain-voyageai>=0.1.4` à `backend/requirements.txt` (conserver `langchain-openai>=0.3.0` qui reste utilisé par ChatOpenAI/OpenRouter — FR-014)
- [X] T002 [P] Mettre à jour `.env.example` (racine repo) — ajouter section `VOYAGE_API_KEY=` avec commentaire FR + lien `https://www.voyageai.com/`, retirer la doc `OPENAI_API_KEY`
- [X] T003 [P] Mettre à jour `backend/.env.example` — même contenu que T002 côté backend
- [X] T004 [P] Enregistrer le marker pytest `embeddings` dans `backend/pyproject.toml` (section `[tool.pytest.ini_options]` → `markers = [..., "embeddings: tests touchés par la migration F25"]`)
- [X] T005 [P] Ajouter les champs `voyage_api_key: str = ""`, `voyage_model: Literal["voyage-3.5", "voyage-3-large", "voyage-multilingual-2"] = "voyage-3.5"`, `voyage_embedding_dim: Literal[1024] = 1024` à `backend/app/core/config.py`. Retirer le champ `openai_api_key` orphelin et son commentaire associé. Préserver intégralement le bloc `model_post_init` du mapping `LLM_*` → `openrouter_*`.
- [X] T006 [P] Ajouter la fixture pytest `fake_embeddings` (vecteurs 1024d) à `backend/tests/conftest.py` — classe `FakeEmbeddings` avec `aembed_query`/`aembed_documents` retournant `[0.1] * 1024`, fixture qui monkeypatch `app.lib.embeddings.get_embeddings_client`. Cf. `contracts/voyage-embeddings-client.md` §6.2.

**Checkpoint** : environnement F25 prêt — dépendance Voyage installable, config typée, marker reconnu, fixture partagée disponible.

---

## Phase 2: Foundational (Migration + Helper) — BLOCKING

**Purpose**: Mettre en place les fondations bloquantes : migration de schéma 043 (3 tables), helper centralisé `get_embeddings_client()`, et adaptation des modèles SQLAlchemy. **Aucune user story ne peut démarrer avant ce checkpoint.**

**⚠️ CRITICAL**: cette phase contient l'unique migration de schéma F25 — elle constitue le périmètre du **PR #1 séparé** (cf. spec.md Notes opérationnelles).

### Tests d'abord (RED) — TDD strict

- [X] T007 [P] Écrire le test contractuel de `get_embeddings_client()` dans `backend/tests/memory/test_embeddings_client.py` : asserter que (a) sans `VOYAGE_API_KEY` → retour `None` + warning loggé, (b) avec `VOYAGE_API_KEY` → instance `VoyageAIEmbeddings` avec `model="voyage-3.5"` ; marker `@pytest.mark.embeddings`. Le test échouera en RED tant que `app/lib/embeddings.py` n'existe pas (ImportError attendu).
- [X] T008 [P] Écrire le test round-trip Alembic dans `backend/tests/migrations/test_043_embeddings_voyage_dim.py` : `alembic upgrade head` → vérifier dim 1024 sur les 3 colonnes via `pg_attribute.atttypmod` + présence des 3 index HNSW + RLS préservée + count(*) lignes inchangé ; puis `alembic downgrade -1` → vérifier retour à 1536/TEXT ; puis `alembic upgrade head` → réussite. Marker `@pytest.mark.embeddings`. Skip si dialect != PostgreSQL. Le test échouera en RED tant que la migration 043 n'existe pas.

### Implémentation modèles SQLAlchemy (parallélisable, fichiers distincts)

- [X] T009 [P] Modifier `backend/app/models/message_chunk.py` (ligne ~72) : `Vector(1536) if Vector is not None else Text` → `Vector(1024) if Vector is not None else Text`. Préserver la branche SQLite.
- [X] T010 [P] Modifier `backend/app/models/document.py` (ligne ~140, classe `DocumentChunk`) : même changement `Vector(1536) → Vector(1024)`.
- [X] T011 [P] Modifier `backend/app/models/financing.py` (ligne ~508, classe `FinancingChunk`) : même changement `Vector(1536) → Vector(1024)`. Aligne le modèle avec la nouvelle réalité (la migration 043 promeut la colonne de TEXT à vector(1024)).

### Implémentation helper d'embeddings (FR-001, FR-006, FR-007c)

- [X] T012 [P] Créer `backend/app/lib/embeddings.py` avec la fonction `get_embeddings_client() -> Optional[VoyageAIEmbeddings]` selon le contrat `contracts/voyage-embeddings-client.md` §1 : retour `None` + `logger.warning` si `settings.voyage_api_key` vide ; retour `None` + `logger.error` si import `langchain_voyageai` échoue ; instance configurée avec `model=settings.voyage_model`, `request_timeout=10`, `max_retries=1`, `batch_size=72` sinon.

### Implémentation migration Alembic (PR #1 isolable)

- [X] T013 Créer `backend/alembic/versions/043_embeddings_voyage_dim.py` avec :
  - Header `revision = "043_embeddings_voyage_dim"` ; `down_revision = "042_extension_url_patterns"`.
  - `upgrade()` : `bind = op.get_bind()` ; guard `is_postgres = bind.dialect.name == "postgresql"` (skip total sur SQLite) ; pour chacune des 3 tables, **DROP indexes existants** (`DROP INDEX IF EXISTS`), **`UPDATE … SET embedding = NULL`**, **ALTER COLUMN TYPE** :
    - `message_chunks` : DROP `ix_message_chunks_embedding_hnsw` + `idx_message_chunks_pending_embedding` ; UPDATE NULL ; `ALTER COLUMN embedding TYPE vector(1024)` ; CREATE les 2 indexes (HNSW `m=16 ef_construction=64 vector_cosine_ops` + partial `WHERE embedding IS NULL`).
    - `document_chunks` : DROP `ix_document_chunks_embedding_hnsw` ; UPDATE NULL ; `ALTER COLUMN embedding TYPE vector(1024)` ; CREATE HNSW.
    - `financing_chunks` : pas d'index préexistant à drop ; UPDATE NULL ; `ALTER COLUMN embedding TYPE vector(1024) USING NULL` (conversion forcée TEXT → vector) ; CREATE NEW `ix_financing_chunks_embedding_hnsw` HNSW.
  - `downgrade()` : symétrique — DROP des HNSW (incl. `ix_financing_chunks_embedding_hnsw`), `UPDATE … SET embedding = NULL`, `ALTER COLUMN TYPE vector(1536)` (pour `financing_chunks` retour à `text` via `USING NULL`), recréation des index 1536d.
  - Idempotence : protéger chaque ALTER par lecture `pg_attribute.atttypmod` (skip si déjà dim cible). Cf. `research.md` R4.

### Vérifications (GREEN)

- [X] T014 Exécuter `pytest backend/tests/memory/test_embeddings_client.py -v` — confirme T007 vert.
- [X] T015 Exécuter `pytest backend/tests/migrations/test_043_embeddings_voyage_dim.py -v` sur PostgreSQL local — confirme T008 vert (round-trip up→down→up < 30 s, SC-004).

**Checkpoint** : migration appliquée + helper instantiable + modèles à jour. Les user stories peuvent démarrer.

---

## Phase 3: User Story 1 — Mémoire conversationnelle restaurée (Priority: P1) 🎯 MVP

**Goal** : restaurer la fonction F12 (mémoire pgvector) — l'agent doit pouvoir rappeler le contexte de conversations passées via `recall_history` après ré-embedding lazy.

**Independent Test** : depuis un compte PME neuf, échanger 3-4 messages substantiels (« projet solaire à Dakar »), démarrer une nouvelle conversation, demander un rappel → l'agent cite/résume le contexte antérieur via l'outil `recall_history`. Vérifiable par : `SELECT vector_dims(embedding) FROM message_chunks WHERE embedding IS NOT NULL` retourne 1024.

### Tests d'abord (RED)

- [X] T016 [US1] Mettre à jour `backend/tests/memory/test_service.py` : remplacer toutes occurrences `[0.1] * 1536`, `dim=1536`, mocks renvoyant des vecteurs 1536d par leur équivalent 1024d (utiliser la fixture `fake_embeddings` ou `[0.1] * settings.voyage_embedding_dim`). Apposer `@pytest.mark.embeddings` au niveau module ou par fonction. ~7 tests concernés.
- [X] T017 [P] [US1] Mettre à jour `backend/tests/memory/test_recall_history_tool.py` : même opération mocks 1024d + marker `@pytest.mark.embeddings`.
- [X] T018 [P] [US1] Apposer le marker `@pytest.mark.embeddings` sur les autres tests memory pertinents : `backend/tests/memory/test_chat_context_loader.py`, `test_checkpointer_persistence.py`, `test_purge.py`, `test_observability.py`, `test_hooks.py` (au niveau module). Ne pas modifier la logique des tests, juste le marker.

### Implémentation US1

- [X] T019 [US1] Refactorer `backend/app/modules/memory/service.py` :
  - Remplacer le corps de `_embeddings_model()` (lignes ~260-285) par un appel à `app.lib.embeddings.get_embeddings_client()` ; lever `RuntimeError("Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env.")` si retour `None` (préserve la signature externe attendue par les tests qui monkeypatch).
  - Supprimer l'import `from langchain_openai import OpenAIEmbeddings` dans la fonction.
  - Ligne ~456 : remplacer `if not query_embedding or len(query_embedding) != 1536:` par `if not query_embedding or len(query_embedding) != settings.voyage_embedding_dim:` (ou la constante 1024 directement). Importer `settings` si non déjà fait.

### Vérification (GREEN)

- [X] T020 [US1] Exécuter `pytest backend/tests/memory/ -v` → tous verts (incluant les 7 tests refactorisés et le test contractuel T007). Confirmer absence d'`ImportError` sur `OpenAIEmbeddings`.

**Checkpoint** : US1 fonctionnelle. La mémoire conversationnelle est restaurée. **MVP livrable** : le chat se souvient des conversations passées en mode dégradé propre.

---

## Phase 4: User Story 2 — Recherche sémantique financing/documents (Priority: P2)

**Goal** : recherche sémantique pertinente sur `/financing` (fonds + intermédiaires via `financing_chunks`) et RAG documentaire (`document_chunks`) en français nuancé.

**Independent Test** : seeder le catalogue de fonds via `python -m app.modules.financing.seed`, lancer une requête en français nuancée (« financement pour valoriser les déchets organiques en énergie au Sénégal ») → top 5 résultats incluent les fonds thématiquement pertinents (SUNREF, GCF déchets) au-delà du keyword matching.

### Tests d'abord (RED)

- [X] T021 [P] [US2] Mettre à jour `backend/tests/test_document_embeddings.py` : remplacer mocks 1536d par 1024d + apposer `@pytest.mark.embeddings`.
- [X] T022 [P] [US2] Apposer `@pytest.mark.embeddings` sur les tests financing et document pertinents : `backend/tests/test_financing_node.py`, `backend/tests/test_financing_status.py`, `backend/tests/test_financing_preparation.py`, `backend/tests/test_financing_intermediaries.py`, `backend/tests/test_tools/test_financing_tools.py`, `backend/tests/test_tools/test_document_tools.py`, `backend/tests/test_e2e_documents.py`, `backend/tests/test_document_api.py`, `backend/tests/test_document_node.py`. Ne pas modifier la logique métier ; ajuster mocks à 1024d si applicable.

### Implémentation US2

- [X] T023 [P] [US2] Refactorer `backend/app/modules/financing/service.py` (lignes ~155-185, fonction `search_financing_chunks` ou équivalente) :
  - Remplacer le bloc `from langchain_openai import OpenAIEmbeddings` + instantiation par `from app.lib.embeddings import get_embeddings_client; client = get_embeddings_client()`.
  - Si `client is None` → `return []` (early return mode dégradé).
  - Wrapper l'appel `await client.aembed_query(query_text)` dans un `try/except` → log warning + `return []` sur échec API.
  - Reste de la requête SQL pgvector (`cosine_distance`) inchangé — fonctionne désormais que la colonne soit `vector(1024)` après migration 043.
- [X] T024 [P] [US2] Refactorer `backend/app/modules/financing/seed.py` (lignes ~835-860, fonction `generate_embeddings`) : même pattern que T023 — remplacer instantiation `OpenAIEmbeddings` par `get_embeddings_client()` + early return `0` (zero ré-embeddings effectués) si `None`.
- [X] T025 [P] [US2] Refactorer `backend/app/modules/documents/service.py` (lignes ~490-505, fonction `_get_embeddings`) : remplacer instantiation `OpenAIEmbeddings` par `get_embeddings_client()`. Ajuster les call-sites de `_get_embeddings()` qui supposent un retour non-`None` pour gérer le cas dégradé (early return liste vide ou skip indexation).

### Vérification (GREEN)

- [X] T026 [US2] Exécuter `pytest -m embeddings -v` → tous les tests marqués passent (incluant Phase 3 + Phase 4). Vérifier en particulier que les tests financing et documents touchés par le refactor restent verts.

**Checkpoint** : US2 fonctionnelle. La recherche sémantique financing + documents délivre des résultats pertinents en français.

---

## Phase 5: User Story 3 — Migration deployable + script admin opt-in (Priority: P3)

**Goal** : l'admin peut déployer la migration 043 en production sans interruption, et déclencher un ré-embedding batch via `python -m app.scripts.reembed_all` pour rattraper les lignes `embedding IS NULL`.

**Independent Test** : sur PostgreSQL local avec ~10 messages + 10 fonds + 5 documents seedés, exécuter `alembic upgrade head` → l'app reste opérationnelle ; exécuter `python -m app.scripts.reembed_all --dry-run` → log aperçu sans UPDATE ; exécuter `python -m app.scripts.reembed_all --table all` → les colonnes `embedding` se peuplent en dim 1024 ; `alembic downgrade -1` puis `alembic upgrade head` → succès sans erreur.

### Tests d'abord (RED)

- [X] T027 [US3] Écrire `backend/tests/test_tools/test_reembed_script.py` couvrant 4 cas : (1) `--dry-run` ne fait pas de UPDATE et retourne 0 ; (2) `--table financing` ne touche que `financing_chunks` et pas les 2 autres tables ; (3) `--limit 5` traite ≤ 5 lignes même si plus disponibles ; (4) sans `VOYAGE_API_KEY` → exit code 1 + message stderr `"Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env."`. Marker `@pytest.mark.embeddings`. Mocker `get_embeddings_client()` via la fixture `fake_embeddings`. Le test échouera en RED tant que `app/scripts/reembed_all.py` n'existe pas.

### Implémentation US3

- [X] T028 [US3] Créer `backend/app/scripts/reembed_all.py` selon `data-model.md` §5 :
  - Module `__main__` exécutable via `python -m app.scripts.reembed_all`.
  - `argparse` : `--table {messages,documents,financing,all}` (défaut `all`), `--limit N` (défaut illimité), `--batch-size B` (défaut 72), `--dry-run` (flag).
  - Fonction async `process_table(db, table_name, text_column, batch_size, limit, dry_run)` qui : SELECT `id, <text_column>` WHERE `embedding IS NULL` ORDER BY `created_at` LIMIT N → batch via `client.aembed_documents(...)` → UPDATE par batch (sauf si dry_run).
  - Mapping `text_column` : `message_chunks`→`chunk_text`, `document_chunks`→`content`, `financing_chunks`→`content`.
  - Logger un compteur par table + total + estimation coût Voyage.
  - `asyncio.run(main())`. Pattern aligné sur `app/scripts/fetch_exchange_rates.py` et `seed_admin.py` (cf. `data-model.md` §5).

### Vérification (GREEN)

- [X] T029 [US3] Exécuter `pytest backend/tests/test_tools/test_reembed_script.py -v` → tous verts.
- [ ] T030 [US3] Smoke test manuel quickstart §6-7 : `alembic upgrade head` → `python -m app.scripts.reembed_all --dry-run` → `python -m app.scripts.reembed_all --table all` → vérifier en BDD `SELECT vector_dims(embedding) FROM <table> WHERE embedding IS NOT NULL` retourne 1024 partout.

**Checkpoint** : US3 fonctionnelle. La migration est déployable, le script admin opt-in est livré, le rollback Alembic est validé.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose** : finaliser FR-017 (documentation `docs/embeddings-voyage.md`), FR-018 (mise à jour CLAUDE.md), valider SC-002 (baseline française), et exécuter les revues.

- [X] T031 [P] Créer `docs/embeddings-voyage.md` selon FR-017 — sections obligatoires : (1) Politique de fournisseur retenu (Voyage AI, voyage-3.5, 1024 dim), (2) Procédure de re-embedding (lazy + script `reembed_all`), (3) Estimation de coût (~$0.06/M tokens, cap dev <$1/jour SC-008), (4) Posture vie privée (résidence US, DPA standard, masquage F12 messages, justification absence masquage fonds/documents), (5) Procédure d'eval baseline SC-002 + tableau placeholder pour les résultats des 10 requêtes (à remplir lors de T036), (6) Procédure de rollback Alembic, (7) FAQ « pas de Voyage API key → mode dégradé ».
- [X] T032 Mettre à jour `CLAUDE.md` (4 modifications, fichier unique → tâche séquentielle, pas [P]) :
  - **(a)** Section `Stack Technologique > Backend (FastAPI) > LLM` (ligne ~19) : remplacer `langchain-openai (embeddings text-embedding-3-small)` par `langchain-voyageai (embeddings voyage-3.5, 1024 dim, multilingue) ; langchain-openai conservé pour ChatOpenAI/OpenRouter`.
  - **(b)** Section `Fondations Transverses > F12` (ligne ~114) : remplacer `embedding VECTOR(1536) NULL` par `embedding VECTOR(1024) NULL (passé de 1536 à 1024 par F25, mig. 043)`.
  - **(c)** Section `Module 3 > 008 — Conseiller financement vert` (ligne ~152) : remplacer `Embeddings text-embedding-3-small` par `Embeddings voyage-3.5 (1024 dim, F25 mig. 043)`.
  - **(d)** Ajouter une nouvelle entrée sous `### Module 1 — Conversationnel & UX` (avant F23) :

    > - **F25 — Migration embeddings Voyage AI** (mig. 043) : 3 tables vectorielles `message_chunks`/`document_chunks`/`financing_chunks` `vector(1536) → vector(1024)` ; correction opportuniste du bug schéma `financing_chunks.embedding TEXT` (mig. 008) → `vector(1024)` + nouvel index HNSW `ix_financing_chunks_embedding_hnsw`. Helper centralisé `app/lib/embeddings.py::get_embeddings_client()` retournant `Optional[VoyageAIEmbeddings]` (model `voyage-3.5`, timeout 10 s, max_retries 1, batch_size 72) — utilisé par memory/financing(×2)/documents. Config Pydantic v2 strict : `voyage_api_key: str`, `voyage_model: Literal["voyage-3.5", ...]`, `voyage_embedding_dim: Literal[1024]` ; retrait de `openai_api_key` orphelin (`langchain-openai` reste pour `ChatOpenAI`). Mode dégradé conservé : clé manquante → log warning + chat continue ; erreur API → embedding `NULL` + lazy retry au prochain accès. Script admin opt-in `python -m app.scripts.reembed_all [--table {messages,documents,financing,all}] [--limit N] [--dry-run] [--batch-size B]` pour backfill (non gating). Doc `docs/embeddings-voyage.md` (politique fournisseur + posture vie privée US + baseline 10 requêtes FR SC-002 non-gating). Marker pytest `@pytest.mark.embeddings` ; round-trip Alembic up/down/up validé < 30 s.

- [X] T033 SC-003 verification : `grep -r "OpenAIEmbeddings" backend/app/` doit retourner 0 résultat. Si résultat trouvé → corriger le call-site oublié.
- [X] T034 Cohérence dim verification : `grep -r "1536" backend/app/models/ backend/app/modules/memory/` doit retourner 0 résultat de code (commentaires acceptés s'ils sont historiques). Cf. SC-001.
- [X] T035 Exécuter le pytest gating SC-006 final : `pytest -m embeddings -v` → 100 % vert. Capturer la sortie pour la PR.
- [ ] T036 Exécution manuelle de la **baseline SC-002** (eval francophone non-gating) selon `quickstart.md` §7 + `research.md` R8 : (1) seeder financing + un document PDF + 3-4 messages de chat ; (2) lancer le script `reembed_all --table all` ; (3) jouer les 10 requêtes francophones (financing×5 / memory×3 / RAG documents×2) ; (4) consigner les top-3 retournés dans la section « SC-002 baseline » de `docs/embeddings-voyage.md` ; (5) si > 2 requêtes hors top-3 → ouvrir une issue de re-calibration (non bloquant pour merge).
- [ ] T037 [P] Lancer une revue de code via l'agent **code-reviewer** (Constitution principe IV + checklist code-review.md) sur les 5 fichiers modifiés `backend/app/lib/embeddings.py`, `backend/app/modules/memory/service.py`, `backend/app/modules/financing/service.py`, `backend/app/modules/financing/seed.py`, `backend/app/modules/documents/service.py`, plus la migration `043_embeddings_voyage_dim.py` et le script `reembed_all.py`. Adresser CRITICAL/HIGH avant merge.
- [ ] T038 [P] Lancer une revue de sécurité via l'agent **security-reviewer** (Constitution principe V) — focus sur (a) absence de log de `VOYAGE_API_KEY`, (b) validation Pydantic des champs `voyage_*`, (c) RLS préservée post-migration, (d) absence de fuite cross-tenant pendant le ré-embedding lazy.
- [X] T039 Validation finale : exécuter la checklist d'acceptation `quickstart.md` §10 (10 items) + checklist `specs/043-voyage-embeddings-migration/checklists/requirements.md` (12 items). Cocher tous les `[ ]` une fois validés.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance, démarrage immédiat possible.
- **Foundational (Phase 2)** : dépend de Phase 1 (notamment T005 config + T006 fixture). **Bloque toutes les user stories.**
- **US1 / US2 / US3 (Phases 3-5)** : toutes dépendent de Phase 2 complète. Indépendantes entre elles → parallélisables si plusieurs développeurs.
- **Polish (Phase 6)** : dépend de Phase 2 minimum ; T031-T034 réalisables en parallèle ; T035-T036 nécessitent toutes les user stories implémentées ; T037-T039 finals.

### User Story Dependencies

- **US1 (P1)** : peut démarrer après T015 (checkpoint Phase 2). Aucune dépendance sur US2 ou US3.
- **US2 (P2)** : peut démarrer après T015. Aucune dépendance sur US1 ou US3.
- **US3 (P3)** : peut démarrer après T015. Le script `reembed_all` consomme `get_embeddings_client()` (T012) déjà foundational.

### Within Each User Story (TDD strict)

- Tests RED écrits AVANT impl (Constitution IV NON-NEGOTIABLE).
- Modèles avant services avant endpoints (pas applicable ici, pas de nouveau endpoint).
- Vérification GREEN avant passage à la phase suivante.

### Parallel Opportunities

- **Phase 1** : T001, T002, T003, T004, T005, T006 → tous [P] (6 fichiers distincts).
- **Phase 2 tests** : T007, T008 → [P].
- **Phase 2 modèles** : T009, T010, T011 → [P] (3 fichiers distincts).
- **Phase 2 helper + migration** : T012, T013 → fichiers distincts, peuvent être [P] entre eux et avec T009/T010/T011 (5 tâches d'impl en parallèle au total).
- **Phase 3** : T017, T018 → [P] entre eux ; T016 séquentiel sur le même fichier que T020 indirect.
- **Phase 4** : T021, T022 → [P] ; T023, T024, T025 → [P] (3 fichiers distincts du module financing/documents).
- **Phase 5** : T027 puis T028 séquentiel (test puis impl du même contrat).
- **Phase 6** : T031, T037, T038 → [P] (fichiers distincts) ; T032 séquentiel (4 zones du même `CLAUDE.md`).
- **Inter-stories** : US1, US2, US3 peuvent être travaillées par 3 développeurs en parallèle après le checkpoint Phase 2.

---

## Parallel Example: Phase 2 Foundational

```bash
# Lancer tous les tests RED en parallèle :
Task: "Écrire le test contractuel get_embeddings_client() dans backend/tests/memory/test_embeddings_client.py" (T007)
Task: "Écrire le test round-trip Alembic dans backend/tests/migrations/test_043_embeddings_voyage_dim.py" (T008)

# Une fois les tests écrits (RED confirmé), lancer toutes les implémentations en parallèle :
Task: "Modifier backend/app/models/message_chunk.py Vector(1536) → Vector(1024)" (T009)
Task: "Modifier backend/app/models/document.py DocumentChunk Vector(1536) → Vector(1024)" (T010)
Task: "Modifier backend/app/models/financing.py FinancingChunk Vector(1536) → Vector(1024)" (T011)
Task: "Créer backend/app/lib/embeddings.py avec get_embeddings_client()" (T012)
Task: "Créer backend/alembic/versions/043_embeddings_voyage_dim.py (3-table migration)" (T013)

# Puis vérification séquentielle :
T014 → T015
```

---

## Implementation Strategy

### Découpage en 2 PR (cf. spec.md Notes opérationnelles)

- **PR #1 (migration uniquement)** : T013 + T015 (round-trip test). Permet de rollbacker la migration indépendamment du code applicatif si nécessaire en prod. La migration peut être déployée en avance ; le code applicatif (PR #2) tombera ensuite en mode dégradé propre (clé Voyage absente côté code old-version) jusqu'à son propre déploiement.
- **PR #2 (code applicatif)** : tout le reste (Phases 1, 2 hors migration, 3, 4, 5, 6). Inclut config, helper, models, refactor des 4 call-sites, script `reembed_all`, doc, CLAUDE.md.

> **Ordre de déploiement recommandé** : PR #1 d'abord (migration), puis PR #2 (code). Pendant la fenêtre intermédiaire, les écritures d'embeddings échouent silencieusement (model 1536 vs DB 1024) → embedding NULL → lazy retry après PR #2 deployment. La fenêtre est tolérée par le mode dégradé existant (FR-007).

### MVP First (User Story 1 — Mémoire conversationnelle restaurée)

1. Phase 1 (Setup) — environnement + fixture + config.
2. Phase 2 (Foundational) — migration + helper + models. **PR #1 mergeable ici si on veut isoler la migration.**
3. Phase 3 (US1) — refactor memory + tests à 1024d.
4. **STOP & VALIDATE** : test US1 indépendamment via `quickstart.md` §5.1-5.2 (échange messages → recall_history retrouve le contexte).
5. Deploy/demo MVP : la mémoire conversationnelle est restaurée, le chat fonctionne en mode normal ou dégradé selon présence de `VOYAGE_API_KEY`.

### Incremental Delivery

1. Setup + Foundational + US1 → MVP (mémoire OK, recherche financing/documents en mode dégradé temporaire).
2. + US2 → recherche sémantique financing/documents OK (US1 + US2 indépendamment testables).
3. + US3 → admin tooling complet (script reembed_all + migration validée up/down/up).
4. + Phase 6 → docs + CLAUDE.md + revues + baseline SC-002 archivée → release.

### Parallel Team Strategy (3 développeurs)

Après checkpoint Phase 2 :
- **Dev A** : Phase 3 (US1 — memory) + Phase 6 partielle (T032 CLAUDE.md F12 entry).
- **Dev B** : Phase 4 (US2 — financing/documents) + Phase 6 partielle (T032 CLAUDE.md feature 008 entry).
- **Dev C** : Phase 5 (US3 — script reembed_all) + Phase 6 partielle (T031 docs/embeddings-voyage.md + T035 SC-003 grep).

T032 CLAUDE.md doit être consolidé en un seul commit final (4 modifications du même fichier), donc à coordonner.

---

## Notes

- Marker `@pytest.mark.embeddings` apposé sur **tous** les tests touchés par F25 — la commande gating SC-006 est `pytest -m embeddings -v`.
- `backend/tests/financing/` et `backend/tests/documents/` n'existent **pas** comme dossiers ; les tests sont en flat layout (`tests/test_financing_*.py`, `tests/test_document_*.py`). Ne pas tenter de les créer.
- `documents.embedding` et `funds.embedding` n'existent **pas** dans le schéma — ne pas écrire de tâche les ciblant. Seules `message_chunks`, `document_chunks`, `financing_chunks` ont des colonnes vectorielles.
- Bug schéma pré-existant `financing_chunks.embedding TEXT` (mig. 008) corrigé opportunément par T013 — vérifier post-migration que `\d financing_chunks` montre `embedding | vector(1024)`.
- Coût Voyage en environnement de dev : prévoir < $0.10/jour pour tester (cf. `quickstart.md` Annexe).
- Commit après chaque tâche T-XXX ou logical group (Phase). Convention : `feat(F25): <description>`, `test(F25): <description>`, `refactor(F25): <description>`, etc.
- Vérifier que les tests RED échouent AVANT impl (TDD strict — Constitution IV NON-NEGOTIABLE).
- Avoid : tâches vagues, conflits de fichier dans des tâches [P], dépendances cross-story qui briseraient l'indépendance des user stories.
