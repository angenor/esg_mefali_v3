# Quickstart — F03 Audit Log Append-Only

## Prérequis

- F02 mergé (multi-tenant + RLS + roles + `get_current_admin`).
- F01 mergé (catalogue Source) — pas de dépendance fonctionnelle directe mais cohabitation respectée.
- Docker Compose démarré (`postgres` service).
- venv backend activé : `cd backend && source venv/bin/activate`.

## Mise en route

### 1. Appliquer la migration

```bash
cd backend && source venv/bin/activate
alembic upgrade head
# Doit appliquer 021_create_audit_log après 020_sources
```

### 2. Vérifier la migration

```bash
psql $DATABASE_URL -c "\dt audit_log"
psql $DATABASE_URL -c "\d audit_log"
psql $DATABASE_URL -c "\di audit_log*"
psql $DATABASE_URL -c "SELECT typname, oid FROM pg_type WHERE typname IN ('audit_action', 'audit_source')"
psql $DATABASE_URL -c "SELECT tgname FROM pg_trigger WHERE tgrelid = 'audit_log'::regclass"
```

Sortie attendue :
- Table `audit_log` présente avec 12 colonnes.
- 4 indexes (`idx_audit_log_account_timestamp`, etc.).
- 2 ENUMs `audit_action`, `audit_source`.
- 2 triggers `audit_log_no_update`, `audit_log_no_delete`.

### 3. Vérifier les triggers append-only

```bash
psql $DATABASE_URL <<'EOF'
-- Insérer une ligne test (manuelle, sans passer par l'app)
INSERT INTO audit_log (id, user_id, account_id, timestamp, entity_type, entity_id,
                       action, source_of_change)
SELECT gen_random_uuid(), id, account_id, now(), 'test', gen_random_uuid(),
       'create', 'manual'
FROM users LIMIT 1
RETURNING id;

-- Tenter UPDATE → DOIT échouer
UPDATE audit_log SET source_of_change='manual' WHERE entity_type='test';
-- ERROR:  audit_log is append-only ; UPDATE is forbidden

-- Tenter DELETE → DOIT échouer
DELETE FROM audit_log WHERE entity_type='test';
-- ERROR:  audit_log is append-only ; DELETE is forbidden
EOF
```

### 4. Démarrer backend et frontend

```bash
# Terminal 1 — backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

## Scénarios fonctionnels

### Scénario 1 — PME édite manuellement son profil

1. Se connecter en PME (Alice, account_id `<pme_a>`).
2. Aller sur `/profile`, modifier le champ `sector` de `agriculture` à `energie`, sauvegarder.
3. Aller sur `/historique`.
4. **Attendu** : voir une entrée :
   - Action : « Modification »
   - Acteur : « Vous »
   - Entité : « Profil entreprise »
   - Diff : `sector : agriculture → energie`
   - Source : « Manuel »
   - Horodatage : « il y a quelques secondes »

### Scénario 2 — PME crée une candidature via le LLM

1. Toujours connecté en PME Alice.
2. Aller sur `/chat`, démarrer une conversation : « Je veux candidater au fonds GCF via la BOAD pour mon projet d'agriculture solaire ».
3. L'assistant pose des questions et appelle le tool `create_fund_application`.
4. Aller sur `/historique`.
5. **Attendu** : voir une entrée :
   - Action : « Création »
   - Acteur : « L'assistant IA »
   - Entité : « Dossier de candidature »
   - Source : « LLM »
   - `actor_metadata.tool_name = "create_fund_application"`
   - `actor_metadata.conversation_id = <id>`

### Scénario 3 — Admin consulte le compte PME (transparence)

1. Se connecter en Admin (Bob, account_id `NULL`, role `ADMIN`).
2. Aller sur `/admin/audit/<pme_a_account_id>` (page admin de consultation).
3. La page affiche tous les événements d'audit de la PME Alice.
4. **Effet de bord backend** : une ligne `audit_log` est créée avec `action=view_admin, source_of_change=admin, account_id=<pme_a>, user_id=<admin_id>`.
5. Se déconnecter, se reconnecter en PME Alice.
6. Aller sur `/historique`.
7. **Attendu** : voir une entrée :
   - Action : « Consultation Admin »
   - Acteur : « Un admin Mefali »
   - Entité : « Compte »
   - Source : « Admin »
   - `actor_metadata.endpoint = "/api/admin/audit/<pme_a>"`

### Scénario 4 — Export CSV de l'historique

1. Connecté en PME Alice avec ≥ 50 événements.
2. Aller sur `/historique`.
3. Cliquer sur le bouton « Exporter » → choisir « CSV ».
4. **Attendu** :
   - Téléchargement d'un fichier `audit-log-<account_id>-20260506.csv`.
   - Encodage UTF-8 BOM (s'ouvre dans Excel sans corruption des accents).
   - Toutes les lignes filtrées (si filtre actif) ou toutes les lignes (sinon).
   - Colonnes : `id, timestamp, user_email, user_id, account_id, entity_type, entity_id, action, field, old_value, new_value, source_of_change, actor_metadata`.

### Scénario 5 — Filtrage et pagination

1. Connecté en PME Alice avec ≥ 200 événements.
2. Aller sur `/historique`.
3. Filtrer par `source = LLM` et `entité = Dossier de candidature`.
4. **Attendu** : seules les entrées correspondant aux deux filtres sont affichées, paginées par 50.
5. Cliquer sur « Page suivante ».
6. **Attendu** : les query params de l'URL sont mis à jour (`?source=llm&entity_type=fund_application&page=2`).

## Tests automatisés

### Tests backend (unit + intégration)

```bash
cd backend && source venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing -k "audit"
```

Cible : couverture ≥ 85 % sur `app/core/auditable.py`, `app/core/audit_context.py`, `app/modules/audit/*`, `app/models/audit_log.py`.

### Tests frontend (unit Vitest)

```bash
cd frontend && npm run test -- --coverage components/audit/ composables/useAuditLog
```

### Tests E2E (Playwright)

```bash
cd frontend && npx playwright test tests/e2e/F03-audit-log.spec.ts --reporter=html
```

4 scénarios E2E :
1. `pme_edits_profile_creates_manual_audit` — édition manuelle → audit `manual` visible.
2. `llm_creates_application_creates_llm_audit` — chat LLM → audit `llm` avec diff complet.
3. `admin_views_pme_account_creates_view_admin_audit` — admin consulte → audit `view_admin` côté PME.
4. `pme_exports_audit_log_csv_with_french_accents` — export CSV → fichier téléchargé, accents corrects.

## Dépannage

### La migration échoue : `permission denied to drop type audit_action`

Cause probable : le rôle utilisé n'est pas owner du type. Vérifier que la migration s'exécute avec le rôle owner du schéma (typiquement le rôle utilisé par `database_url`).

### Les triggers ne s'appliquent pas (UPDATE/DELETE passe)

Vérifier :
1. Le rôle applicatif n'est pas SUPERUSER.
2. Les triggers existent : `SELECT * FROM pg_trigger WHERE tgrelid = 'audit_log'::regclass`.
3. Si SUPERUSER, c'est attendu — cf. limites MVP documentées.

### Aucune ligne `audit_log` n'est créée après une mutation

Vérifier :
1. Le modèle muté hérite bien de `Auditable` (ex. `class CompanyProfile(Auditable, UUIDMixin, TimestampMixin, Base)`).
2. Le listener `before_flush` est enregistré au démarrage de l'app (import `app.core.auditable` exécuté dans `app/main.py`).
3. La mutation passe bien par la `Session` (et non un `INSERT` SQL brut hors ORM).
4. Les variables RLS sont positionnées (`SET LOCAL app.current_account_id = ...`).

### `source_of_change=manual` au lieu de `llm` dans une mutation par chat

Vérifier que le nœud LangGraph appelle bien :
```text
with source_of_change_scope("llm"):
    await service.do_something()
```

Sans le context manager, la valeur par défaut `manual` est utilisée.

### Export CSV : caractères français cassés dans Excel

Vérifier que la première ligne du fichier contient bien le BOM UTF-8 (`EF BB BF` en hexa). Sans BOM, Excel suppose CP-1252 et corrompt les accents.

## Limites MVP documentées

- **Pas de Merkle / hash chaîné** : la défense repose sur trigger + REVOKE. Évolution post-MVP.
- **Pas de PDF signé** : F08 introduira la signature Ed25519.
- **Pas de diff visuel side-by-side** : MVP affiche les valeurs textuelles `old → new`.
- **Pas de partitionnement** : les indexes suffisent jusqu'à ~100 000 lignes par compte. Au-delà, partitionnement par mois recommandé (post-MVP).
- **RGPD Art. 17 (droit à l'oubli)** : conflit avec append-only. Mécanisme DPO (anonymisation tombstone) reporté post-MVP. La limite est documentée dans `docs/audit-log.md`.
- **Pas de rôle PostgreSQL séparé `application_user`** : cohérent avec décision F02. Le REVOKE peut être no-op si le rôle est superuser/owner ; le trigger reste la défense effective.
