# Quickstart : F07 Entité Offre = Couple Fonds × Intermédiaire

**Branch** : `feat/F07-entite-offre-fonds-intermediaire`
**Pour qui** : développeur reprenant le code après livraison de F07.

## Prérequis

- Stack ESG Mefali installée : `backend/venv`, frontend Nuxt 4, PostgreSQL 16 via Docker.
- Migrations 020 (F01), 019 (F02), 022 (F04), 025 (F06), 027 (F05) appliquées.
- `cd backend && source venv/bin/activate && alembic current` doit afficher `027_consents_and_account_deletion`.

## 1. Appliquer la migration 028

```bash
cd backend
source venv/bin/activate
alembic upgrade head  # passe à 028_offers_and_enrich_fund_intermediary
```

Vérifications attendues :
```bash
psql -d esg_mefali_dev -c "SELECT COUNT(*) FROM offers"
# doit retourner ≥ 50 (toutes les paires fund_intermediaries + fonds direct)

psql -d esg_mefali_dev -c "SELECT code FROM intermediaries WHERE code = 'DIRECT'"
# doit retourner 'DIRECT' (singleton seedé)

psql -d esg_mefali_dev -c "SELECT COUNT(*) FROM fund_applications WHERE offer_id IS NULL"
# doit retourner 0
```

## 2. Tester la réversibilité

```bash
alembic downgrade -1
psql -d esg_mefali_dev -c "\d offers"
# doit retourner "Did not find any relation named 'offers'"

alembic upgrade head
# revient à l'état post-028
```

## 3. Tester le calculator `compute_effective_offer`

```bash
cd backend
source venv/bin/activate
pytest tests/unit/test_offer_calculator.py -v
```

Test manuel via Python :
```python
from app.modules.offers.calculator import compute_effective_offer
from app.db.session import async_session_maker

async def main():
    async with async_session_maker() as session:
        # Récupérer fund + intermediary depuis seed
        result = await compute_effective_offer(session, fund_id=GCF_UUID, intermediary_id=BOAD_UUID)
        print(result.model_dump_json(indent=2))

import asyncio; asyncio.run(main())
```

## 4. Appeler les endpoints REST

### Endpoints publics

```bash
# Liste paginée (filtre langue FR)
curl http://localhost:8000/api/offers?language=FR&limit=20

# Détail d'une offre
curl http://localhost:8000/api/offers/<offer_id>

# Comparateur pour un fonds
curl http://localhost:8000/api/offers/comparator?fund_id=<gcf_uuid>
```

### Endpoints admin (token JWT admin requis)

```bash
ADMIN_TOKEN="<jwt-admin>"

# Preview du calcul auto (sans persister)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -X POST "http://localhost:8000/api/admin/offers/compute?fund_id=<gcf>&intermediary_id=<bad>"

# Création d'une offre depuis draft édité
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST http://localhost:8000/api/admin/offers \
     -d '{
       "fund_id": "<gcf>",
       "intermediary_id": "<bad>",
       "name": "GCF via BAD - Mitigation Sahel",
       "accepted_languages": ["FR"],
       "effective_criteria": {...},
       "effective_required_documents": [...],
       "effective_fees": {...},
       "source_id": "<source-accreditation>",
       "publication_status": "draft"
     }'

# Liste complète admin (incluant drafts)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     "http://localhost:8000/api/admin/offers?include_drafts=true"

# Bascule en published
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -X PATCH http://localhost:8000/api/admin/offers/<offer_id> \
     -d '{"publication_status": "published", "is_active": true}'
```

## 5. Activer la vue Offres côté frontend

### Option A : env var

```bash
# Dans frontend/.env (ou .env.local)
USE_OFFER_VIEW=true
```

Puis redémarrer le frontend :
```bash
cd frontend && npm run dev
```

Naviguer sur http://localhost:3000/financing → la home affiche maintenant des Cards Offres (au lieu des Cards Fonds legacy).

### Option B : runtimeConfig override (build-time)

Modifier `frontend/nuxt.config.ts` :
```ts
runtimeConfig: {
  public: {
    useOfferView: true,  // était false par défaut
  },
},
```

## 6. Exécuter le cron d'expiration des accréditations

```bash
cd backend
source venv/bin/activate
python scripts/check_expired_accreditations.py
```

Output attendu (avec une accréditation expirée) :
```
[INFO] Found 1 fund_intermediary with accredited_to < today
[INFO] Deactivating offer <uuid> (fund=GCF, intermediary=BOAD)
[INFO] Audit log entry created: action='auto_unpublished_accreditation_expired'
[INFO] Done. 1 offer deactivated.
```

Output attendu (run consécutif, idempotent) :
```
[INFO] Found 0 fund_intermediary with accredited_to < today
[INFO] Done. 0 offer deactivated.
```

## 7. Lancer les tests E2E Playwright

```bash
cd frontend
npx playwright test tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts --reporter=html
```

Les 4 scénarios testés :
1. Admin crée une offre → calcul auto → publication → visible côté PME
2. PME consulte 2 offres GCF (BOAD + UNDP) et les compare côte-à-côte
3. PME tente d'accéder à `/api/admin/offers?include_drafts=true` → 403
4. Cron expiration désactive offre → invisible côté PME (re-fetch après cron)

## 8. Tester les tools LangChain dans le chat

```bash
# Lancer backend + frontend
make dev

# Dans le chat, demander :
"Quelles offres de financement pour mon projet d'agriculture durable ?"
```

Vérifier dans les logs backend que le tool `list_offers` est appelé avec les filtres déduits par le LLM.

## Troubleshooting

- **Migration 028 échoue** : vérifier que `027_consents_and_account_deletion` est appliquée. Inspecter le log Alembic pour identifier l'étape qui a échoué.
- **`offers.source_id` NOT NULL violation au backfill** : vérifier que la source `system://mefali/direct-singleton` existe avant le seed singleton DIRECT.
- **`compute_effective_offer` retourne dict vide** : vérifier que `fund.eligibility_criteria` et `intermediary.eligibility_for_sme` ne sont pas `{}` (cas seed initial).
- **Frontend Cards Offres ne s'affichent pas** : vérifier `useRuntimeConfig().public.useOfferView === true` dans la console DevTools.
- **Cron `check_expired_accreditations.py` ne désactive aucune offre** : vérifier `SELECT * FROM fund_intermediaries WHERE accredited_to < CURRENT_DATE` (peut être vide si aucune accréditation n'a expiré).

## Schémas BDD références

Voir [data-model.md](./data-model.md) pour le DDL complet.

## Schémas API références

Voir [contracts/openapi-offers.yaml](./contracts/openapi-offers.yaml) et [contracts/openapi-admin-offers.yaml](./contracts/openapi-admin-offers.yaml).

## Schémas tools LangChain

Voir [contracts/tools-langchain.md](./contracts/tools-langchain.md).
