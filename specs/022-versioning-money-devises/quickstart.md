# Quickstart — F04 Versioning + Money Type + Multi-devises

**Date** : 2026-05-07
**Feature** : `feat/F04-versioning-money-devises`
**Spec** : [spec.md](./spec.md) | **Plan** : [plan.md](./plan.md) | **Data Model** : [data-model.md](./data-model.md)

Ce document accompagne un développeur qui prend la branche en main pour démarrer l'implémentation ou la valider localement.

---

## 1. Prérequis

- Python 3.12 + `backend/venv/` actif
- PostgreSQL 16 local (via `docker compose up postgres -d`)
- Node.js 20+ pour le frontend Nuxt 4
- Variables d'environnement (`backend/.env`) :
  ```bash
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/esg_mefali
  EXCHANGERATE_API_KEY=  # optionnel pour dev (vide = mode dégradé)
  EXCHANGERATE_API_BASE_URL=https://v6.exchangerate-api.com/v6
  CURRENCY_FETCH_DAILY_QUOTA=50
  ```

---

## 2. Activation venv + migrations

```bash
cd /Users/mac/Documents/projets/2025/esg_mefali_v3
source backend/venv/bin/activate

cd backend
alembic upgrade head     # applique 022_money_and_versioning
```

Vérifier que la migration est bien à jour :

```bash
alembic current
# attendu : 022_money_and_versioning (head)
```

Vérifier les nouvelles colonnes :

```bash
psql -d esg_mefali -c "\d funds" | grep -E "(min_amount|max_amount|version|valid_)"
psql -d esg_mefali -c "\d fund_applications" | grep -E "(snapshot_)"
psql -d esg_mefali -c "\d exchange_rates"
```

---

## 3. Seed initial des taux de change

```bash
cd backend
python -m app.scripts.fetch_exchange_rates --force
```

Note : `--force` bypass le cap 1/jour pour le premier seed.

Vérifier :

```bash
psql -d esg_mefali -c "SELECT base_currency, quote_currency, rate, as_of FROM exchange_rates ORDER BY base_currency, quote_currency;"
```

Attendu : 8 lignes (USD↔{XOF, EUR, GBP, JPY} en direct + inverses).

---

## 4. Test manuel — Conversion FCFA → EUR (peg)

Démarrer le backend :

```bash
cd backend && uvicorn app.main:app --port 8000 --reload &
```

Appeler l'API de conversion :

```bash
curl -X POST http://localhost:8000/api/currency/convert \
  -H "Content-Type: application/json" \
  -d '{"amount": "655957", "source_currency": "XOF", "target_currency": "EUR"}'
```

Réponse attendue :

```json
{
  "source": {"amount": "655957.00", "currency": "XOF"},
  "target": {"amount": "1000.00", "currency": "EUR"},
  "rate_used": "0.001524",
  "method": "peg_fixed",
  "rate_date": null
}
```

---

## 5. Test manuel — Conversion USD → XOF (table)

```bash
curl -X POST http://localhost:8000/api/currency/convert \
  -H "Content-Type: application/json" \
  -d '{"amount": "1000", "source_currency": "USD", "target_currency": "XOF", "date": "2026-04-15"}'
```

Réponse attendue (rate dépend du seed) :

```json
{
  "source": {"amount": "1000.00", "currency": "USD"},
  "target": {"amount": "615200.00", "currency": "XOF"},
  "rate_used": "615.20",
  "method": "table",
  "rate_date": "2026-04-15"
}
```

---

## 6. Test manuel — Snapshot et recompute

### 6.1 Créer une candidature et la soumettre

(Via API backend, requiert auth user JWT — voir tests d'intégration pour exemples).

```python
# backend/tests/test_applications/test_snapshot_creation.py (extrait)
async def test_create_snapshot_on_submission(client, auth_user, fund, referential):
    # Créer candidature
    resp = await client.post("/api/applications", json={"fund_id": str(fund.id), "target_type": "fund_direct"})
    app_id = resp.json()["id"]
    
    # Transitionner vers submitted_to_fund
    resp = await client.post(f"/api/applications/{app_id}/transition", json={"to": "submitted_to_fund"})
    assert resp.status_code == 200
    
    # Vérifier snapshot
    resp = await client.get(f"/api/applications/{app_id}")
    data = resp.json()
    assert data["snapshot_at"] is not None
    assert data["snapshot_data"] is not None
    assert data["snapshot_data"]["referential"]["version"] == referential.version
```

### 6.2 Recompute contre snapshot

```bash
curl -X POST http://localhost:8000/api/applications/{app_id}/recompute-against-snapshot \
  -H "Authorization: Bearer $JWT"
```

Réponse attendue :

```json
{
  "application_id": "...",
  "snapshot_at": "2026-05-07T...",
  "recomputed_at": "2026-05-07T...",
  "score": {"esg_total": 72.5, ...},
  "comparison_with_origin": {"match": true, "delta": 0.0},
  "referential_version_used": "1.2",
  "referential_id_used": "..."
}
```

---

## 7. Démarrage frontend + démo `<MoneyDisplay>`

```bash
cd frontend && npm run dev
```

Ouvrir `http://localhost:3000/financing` : chaque card de fonds doit afficher le montant via `<MoneyDisplay>` avec le mode `both` par défaut (`5 000 000 USD (≈ 3 075 000 000 FCFA)`).

Tester le toggle de mode dans Settings :

- `native` → seul le natif
- `pme` → seul l'équivalent en XOF
- `both` → les deux

Tester le mode dark (icône lune en haut) : `<MoneyDisplay>` et `<ReferentialBadge>` doivent rester lisibles.

---

## 8. Tests automatisés

### Backend

```bash
cd backend && source venv/bin/activate
pytest tests/test_core/test_money.py -v
pytest tests/test_currency/ -v
pytest tests/test_versioning/ -v
pytest tests/test_applications/test_snapshot_creation.py -v
pytest tests/test_applications/test_recompute_against_snapshot.py -v
pytest tests/test_migrations/test_022_money_and_versioning.py -v

# Couverture
pytest tests/ --cov=app --cov-report=term-missing -q
```

Couverture cible : ≥ 80 % sur les nouveaux modules (`app.core.money`, `app.modules.currency`, `app.modules.versioning`, `app.modules.applications.snapshot`, `app.modules.applications.recompute`).

### Frontend

```bash
cd frontend
npm run test -- --coverage
npx playwright test tests/e2e/F04-versioning-money-devises.spec.ts
```

---

## 9. Rollback

Si problème en production, downgrade une révision :

```bash
cd backend && source venv/bin/activate
alembic downgrade -1     # revient à 021_create_audit_log ou 020_sources
```

La migration F04 conserve les colonnes `*_xof` / `*_fcfa` legacy : aucun risque de perte de données. Le downgrade drope uniquement les nouvelles colonnes (versioning + paires Money + snapshot) et la table `exchange_rates`.

---

## 10. Liens utiles

- Spec : [spec.md](./spec.md)
- Plan : [plan.md](./plan.md)
- Research : [research.md](./research.md)
- Data Model : [data-model.md](./data-model.md)
- Contracts : [contracts/currency_api.yaml](./contracts/currency_api.yaml), [contracts/application_recompute.yaml](./contracts/application_recompute.yaml), [contracts/currency_status.yaml](./contracts/currency_status.yaml)
- Tests E2E : `frontend/tests/e2e/F04-versioning-money-devises.spec.ts` (créé en Phase B)
