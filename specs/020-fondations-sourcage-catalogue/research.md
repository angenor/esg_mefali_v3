# Phase 0 — Research : Fondations Sourçage et Catalogue Source

**Feature** : F01 — `feat/F01-fondations-sourcage-catalogue` / `020-fondations-sourcage-catalogue`
**Date** : 2026-05-06
**Statut** : Décisions techniques actées (autonomie totale, utilisateur absent)

> Ce document consolide les décisions techniques prises avant Phase 1, avec rationale et alternatives évaluées. Toute décision est cohérente avec les invariants ESG Mefali (cf. `.cc-orchestrator.md`) et la stack imposée.

## R-001 — Workflow 4-yeux : invariant `verified_by != captured_by`

**Décision** : implémenter une **CHECK constraint PostgreSQL** au niveau de la table `sources` :

```sql
CONSTRAINT sources_four_eyes_chk
    CHECK (verified_by IS NULL OR verified_by != captured_by)
```

…doublée d'une validation applicative dans `SourceService.verify_source(...)` (defense-in-depth).

**Rationale** :
- La CHECK constraint garantit l'invariant même en cas de bug applicatif ou de raw SQL.
- La validation applicative renvoie un message d'erreur lisible en français à l'API plutôt qu'une `IntegrityError` brute.
- La double couche est coûteuse à 0 ligne supplémentaire et conforme à l'invariant ESG Mefali « plus sûr que strictement nécessaire ».

**Alternatives évaluées** :
- *Validation applicative seule* : rejetée. Un script de seed ou un raw SQL pourrait contourner.
- *Trigger BEFORE UPDATE* : rejeté. Plus complexe à maintenir et à tester ; CHECK suffit puisque la condition est purement structurelle.

## R-002 — Détection des chiffres dans la réponse LLM

**Décision** : regex Python compilée unique :

```python
NUMERIC_CLAIM_RE = re.compile(
    r"\b(\d{1,3}(?:[\s ]?\d{3})*(?:[.,]\d+)?)\s*"
    r"(%|tCO2e|kgCO2e|FCFA|XOF|EUR|USD|/100|/10|kWh|km|tonne|MW)\b",
    re.IGNORECASE,
)
```

…doublée d'une **liste blanche `IGNORED_NUMERIC_PATTERNS`** (constante Python) :

```python
IGNORED_NUMERIC_PATTERNS = [
    r"\bISO\s?(?:9001|14001|14064|14067|26000|27001|50001)\b",
    r"\barticle\s+\d+\.\d+\b",
    r"\b802\.1[A-Z]?\b",
    r"\bPCI[-\s]?DSS\s?\d+\.\d+\b",
    r"\bIFRS\s?\d+\b",
    r"\bGRI\s?\d+\b",
    # extensible itérativement sur le golden set
]
```

L'algorithme du validator :
1. Strip toutes les sous-chaînes matching `IGNORED_NUMERIC_PATTERNS`.
2. Appliquer `NUMERIC_CLAIM_RE.finditer(stripped_text)`.
3. Pour chaque match : grouper en grappes selon FR-014 (proximité ≤ 200 caractères dans le même paragraphe).
4. Pour chaque grappe : exiger ≥ 1 `cite_source` ou ≥ 1 `flag_unsourced` dans les `tool_calls` du tour.

**Rationale** :
- Regex unique et liste blanche extensible = simple, testable, déterministe.
- Compatible avec la cible ≤ 5 % d'erreur sur 50 réponses annotées (FR-018).
- La liste est versionnée dans le code, pas dans une table BDD : pas de surface administrateur à construire pour F01 (YAGNI).

**Alternatives évaluées** :
- *Parser AST markdown* : rejeté. Les LLMs produisent du texte en partie non-markdown, le parser AST manquerait des chiffres dans les listes ou phrases en clair.
- *Validation par un second LLM* : rejeté. Coût latence + coût tokens, déterminisme faible, contradictoire avec le principe « validation rapide post-tour ≤ 50 ms ».
- *Liste de tokens « ignorés » dans une table BDD* : rejeté pour F01 (YAGNI). À considérer F09 back-office admin si le besoin émerge.

## R-003 — Indexation pgvector pour `search_source`

**Décision** : index **HNSW** sur la colonne `embedding vector(1536)` de `sources` :

```sql
CREATE INDEX sources_embedding_hnsw_idx
    ON sources USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Rationale** :
- HNSW scale gracieusement de 30 à 10 000 sources sans re-tuning.
- La feature 008 (financing matching) utilise déjà HNSW sur `funds.embedding` avec ces mêmes paramètres → cohérence de stack.
- Recherche cosine (`<=>` opérateur pgvector) car les embeddings OpenAI sont normalisés pour cette distance.

**Alternatives évaluées** :
- *IVFFlat* : rejeté. Nécessite un `lists` à tuner selon le volume → lourd pour un catalogue qui démarre à 30 entrées.
- *Pas d'index, full scan* : viable jusqu'à ~1000 sources, mais ne respecte pas SC-009 (≤ 1 s p95 modal détail) si la modal préfetche les sources liées via search.

## R-004 — Modèle d'embedding utilisé

**Décision** : **`text-embedding-3-small` OpenAI** (dimension 1536).

**Rationale** :
- Déjà adopté dans la feature 008 (financing) : cohérence de pipeline et coût mutualisé.
- Dimension 1536 + HNSW = empreinte ~6 KB par source, négligeable.
- Texte indexé : `{title} | {publisher} | {section} | {url}` → suffisant pour la pertinence sémantique demandée par `search_source`.

**Alternatives évaluées** :
- *`text-embedding-3-large` (3072 dim)* : rejeté. Coût × 6, gain marginal sur catalogue 30-200 sources.
- *Embeddings locaux (sentence-transformers)* : rejeté. Pas de GPU local en MVP, latence CPU élevée, complexité opérationnelle.

## R-005 — Annexe PDF : collecte des sources mobilisées

**Décision** : **reconstruction post-hoc** depuis la table `tool_call_logs` (déjà existante depuis la feature 012).

**Rationale** :
- `tool_call_logs` journalise déjà chaque appel de tool LangChain avec `(conversation_id, tool_name, arguments, result, timestamp)`.
- Lors de la génération du rapport, le service `report_service.generate_esg_report(report_id)` fait :
  ```python
  cite_calls = await tool_call_logs_repo.list_by_conversation_and_tool(
      conversation_id=report.conversation_id,
      tool_name="cite_source",
      since=report.generation_started_at,
  )
  source_ids = [UUID(call.arguments["source_id"]) for call in cite_calls]
  sources = await source_service.list_by_ids(source_ids)
  ```
- Les sources sont injectées dans le contexte Jinja2 du template HTML/PDF.

**Rationale (suite)** :
- Déterministe : 100 % des `cite_source` invoqués par l'agent pendant la génération sont capturés.
- Pas de fuite de `contextvars.ContextVar` en cas d'exception en cours de génération.
- Réutilise une table existante, pas de schéma additionnel.

**Alternatives évaluées** :
- *Capture in-process via `contextvars.ContextVar`* : rejeté. Risque de fuite si exception non rattrapée, complexe à tester en multi-coroutine.
- *Champ JSON `mobilized_sources` ajouté à `reports`* : rejeté. Duplication de données, risque d'incohérence si le rapport est régénéré sans purger le champ.

## R-006 — Validator middleware : point d'injection LangGraph

**Décision** : **hook sur la fonction `stream_graph_events`** (`backend/app/api/chat.py`) qui collecte la réponse finale + tool_calls et invoque `source_required.validate()` avant d'émettre l'event SSE final.

**Rationale** :
- `stream_graph_events` est déjà le point central de production du flux SSE depuis la feature 012.
- Injection en post-traitement = zéro modification du graphe LangGraph (`backend/app/graph/graph.py` zone interdite).
- Streaming token-by-token utilisateur préservé : la dernière chunk peut être ré-écrite si rejet (pattern « buffer-and-rewrite »).
- Retry max 1 implémenté en relançant un sous-graphe ciblé avec le contexte déjà calculé (pas un nouveau tour complet).

**Alternatives évaluées** :
- *Nœud LangGraph `validation_node` ajouté au graphe* : rejeté. Modifie `graph.py` (zone interdite cf. `.cc-orchestrator.md`).
- *Décorateur sur chaque nœud spécialiste* : rejeté. Multiplie les points d'injection (7 nœuds), risque de dérive entre nœuds.
- *Middleware FastAPI sur l'endpoint chat* : rejeté. Trop tardif (le streaming est déjà émis).

## R-007 — Stratégie de seed des 30+ sources `verified`

**Décision** : seed via **fonction `seed_sources()`** appelée depuis la migration `020_create_sources_catalog.py` dans une fonction `data_upgrade()` séparée, après `op.create_table(...)`.

Le seed crée d'abord un user système `system@esg-mefali.local` (rôle `admin`) si absent, puis insère 30+ sources avec `captured_by = system_user.id` et `verified_by = system_user.id` (workflow 4-yeux bypass justifié par la procédure éditoriale documentée hors-app, cf. edge case spec.md).

**Pour respecter l'invariant CHECK `verified_by != captured_by`** : le seed crée **deux** users système distincts (`system-curator@esg-mefali.local` et `system-validator@esg-mefali.local`) avec rôle `admin` ; les sources seedées ont `captured_by = curator.id`, `verified_by = validator.id`.

**Rationale** :
- L'application est utilisable dès la première mise en production sans intervention humaine de seed.
- L'invariant 4-yeux n'est pas contourné (deux identités distinctes) → CHECK constraint respectée.
- Idempotent : ré-exécution de la migration ne duplique pas les sources (vérification `WHERE NOT EXISTS` ou ON CONFLICT DO NOTHING).
- Migration des `EMISSION_FACTORS`, `ESGCriterion`, `SECTOR_WEIGHTS`, constantes simulateur s'appuie sur les sources seedées (FK valides immédiatement).

**Alternatives évaluées** :
- *Seed manuel via script Python séparé* : rejeté. Ajoute une étape humaine au déploiement, casse la promesse « migration unique ».
- *Pas de seed initial, attendre que les admins saisissent* : rejeté. Bloque la migration des `EMISSION_FACTORS` car il n'y a pas de `source_id` à pointer.

## R-008 — Migration des constantes simulateur

**Décision** : table `simulation_factors(id UUID, code VARCHAR, label TEXT, value NUMERIC, unit VARCHAR, scope VARCHAR, source_id UUID FK NULL → sources.id, status VARCHAR ENUM('verified','pending'), created_by_user_id UUID FK users.id, created_at TIMESTAMPTZ)`.

`source_id NULL` autorisé **uniquement** quand `status = 'pending'` (CHECK constraint). Les constantes du simulateur (`_SAVINGS_RATE`, `_CARBON_IMPACT_PER_MXOF`) migrent en `status = 'pending'` puisqu'aucune source officielle ne les couvre aujourd'hui.

```sql
CONSTRAINT simulation_factors_source_required_chk
    CHECK (
        (status = 'verified' AND source_id IS NOT NULL)
        OR
        (status = 'pending' AND source_id IS NULL)
    )
```

**Rationale** :
- Honnêteté éditoriale : les constantes inventées sont marquées `pending` plutôt que cachées.
- Le tool `cite_source` rejette toute citation sur une `simulation_factors` `pending` car son `source_id IS NULL` (rien à citer).
- Liste de suivi administrative naturelle : `SELECT * FROM simulation_factors WHERE status = 'pending'`.

**Alternatives évaluées** :
- *Forcer `source_id NOT NULL` et créer une source bidon « ESG Mefali estimations internes »* : rejeté. Auto-référence non vérifiable, contraire à la promesse.
- *Stocker les constantes dans une table générique `app_settings`* : rejeté. Perd la traçabilité par source et la possibilité de migrer vers `verified` quand une vraie source officielle est trouvée.

## R-009 — Composants frontend : réutilisation et accessibilité

**Décision** :
- `SourceLink.vue` : nouveau composant atomique (icône `i-heroicons-link` + `<button>` avec `aria-label="Voir la source de cette donnée"`).
- `SourceModal.vue` : réutilise `composables/useFocusTrap.ts` existant (déjà utilisé par `chat/InteractiveQuestionHost.vue` en feature 018).
- `SourceBadge.vue` : nouveau composant générique paramétrable par status `verified/pending/outdated` + raison.
- `SourcesList.vue` : composant liste, paramétrable par `sourceIds: UUID[]`.

**Rationale** :
- Réutilise `useFocusTrap` (invariant ESG Mefali #9 « réutilisabilité composants »).
- Tous les composants supportent dark mode (variantes `dark:` Tailwind).
- ARIA roles présents : `role="dialog"`, `aria-modal="true"`, `aria-labelledby="source-modal-title"`, `aria-describedby` sur le badge avec la raison.

**Alternatives évaluées** :
- *Tout en 1 composant `SourceWidget.vue`* : rejeté. Composants atomiques réutilisables, plus testables.
- *Bibliothèque tierce (HeadlessUI Vue)* : rejeté. Pas dans la stack imposée, dépendance supplémentaire injustifiée.

## R-010 — Cache Pinia frontend

**Décision** : store `sources.ts` avec map `Record<UUID, Source>` + invalidation TTL 5 min.

**Rationale** :
- La même source est souvent citée plusieurs fois sur la même page (ex: 10 critères ESG citent la Taxonomie verte UEMOA).
- 5 min de TTL = trade-off entre fraîcheur (statut `outdated` doit apparaître rapidement) et économie réseau.
- Pinia déjà adopté pour `auth`, `dashboard`, `esg`, etc. : cohérence.

**Alternatives évaluées** :
- *Cache HTTP browser (`Cache-Control: max-age=300`)* : rejeté. Moins de contrôle programmatique, gestion des badges `outdated` plus complexe.
- *Pas de cache* : rejeté. SC-009 (modal ≤ 1 s p95) impossible à atteindre si chaque clic refait un GET.

## R-011 — Conventions Alembic et numérotation

**Décision** : migration `backend/alembic/versions/020_create_sources_catalog.py`.

`down_revision` = dernière migration en place sur `main` (à confirmer au moment de l'écriture, candidat : `5b7f090f1dcc` ou la dernière de la chaîne F00). **Le numéro 020** est cohérent avec la chaîne séquentielle (018 = interactive widgets, 019 = F02 multitenant en parallèle).

> Note : F02 (en cours sur une autre branche) crée également une migration. Le sous-agent F01 NE DOIT PAS toucher aux migrations F02 (zone interdite). Si conflit Alembic émerge à l'intégration, l'orchestrateur sérialise les merges.

**Rationale** :
- Numérotation séquentielle 020 explicite, lisible.
- `down_revision` unique pour éviter les têtes Alembic multiples.
- Migration **additive uniquement** (pas de DROP, pas de ALTER destructif). Rollback `downgrade` possible et testé.

**Alternatives évaluées** :
- *Numérotation hash auto-générée par `alembic revision`* : rejeté. Le hash 12 caractères perd la lisibilité des numéros séquentiels pour la sérialisation des migrations.
- *Plusieurs migrations atomiques (1 par table)* : rejeté pour F01. Toutes les tables sont conceptuellement liées au catalogue ; une migration unique simplifie le up/down/up.

## R-012 — Tests E2E Playwright : architecture

**Décision** : nouveau fichier `frontend/tests/e2e/F01-fondations-sourcage-catalogue.spec.ts` couvrant 3 parcours critiques :

1. **Parcours PME catalogue** : ouvre `/sources`, recherche « ADEME », filtre par publisher « ADEME », clique sur une entrée, vérifie modal détail + lien officiel.
2. **Parcours fund officer score ESG** : crée une PME mockée (via fixtures Playwright), navigue vers `/esg`, clique sur le picto à côté du score global, vérifie modal détail + statut « vérifiée ».
3. **Parcours validator backend rejette chiffre sans citation** : envoie via API mockée une réponse LLM contenant un chiffre sans `cite_source`, vérifie que le SSE final remplace par le fallback texte.

**Rationale** :
- 3 scénarios = couvre les 3 personas critiques (PME, fund officer simulé, agent IA).
- Scénario 3 testable via une couche d'API mockée (pas besoin de vrai LLM en E2E, conformément au principe « LLM mock par défaut »).
- Réutilise les fixtures Playwright existantes (`frontend/tests/e2e/fixtures/`) introduites en feature 011.

**Alternatives évaluées** :
- *Tests E2E uniquement sur le parcours PME* : rejeté. Couvrirait insuffisamment l'invariant de sourçage côté agent.
- *Tests d'intégration backend uniquement* : rejeté. L'orchestrateur exige des E2E Playwright exécutables (cf. `.cc-orchestrator.md` invariant #11).

---

**Sortie Phase 0** : toutes les décisions sont actées, aucun `NEEDS CLARIFICATION` résiduel. Phase 1 peut démarrer.
