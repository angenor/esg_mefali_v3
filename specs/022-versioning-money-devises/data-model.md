# Data Model — F04 Versioning + Money Type + Multi-devises

**Date** : 2026-05-06
**Feature** : `feat/F04-versioning-money-devises`
**Migration Alembic** : `022_money_and_versioning` (down_revision : `021_create_audit_log` ou `020_sources` selon état F03)

---

## 1. Nouvelle table : `exchange_rates`

### DDL

```sql
CREATE TABLE exchange_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    rate NUMERIC(20, 10) NOT NULL,
    as_of DATE NOT NULL,
    source VARCHAR(100) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT exchange_rates_currencies_chk CHECK (
        base_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')
        AND quote_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')
    ),
    CONSTRAINT exchange_rates_rate_positive_chk CHECK (rate > 0),
    CONSTRAINT exchange_rates_pair_uniq UNIQUE (base_currency, quote_currency, as_of)
);

CREATE INDEX exchange_rates_lookup_idx ON exchange_rates (
    base_currency, quote_currency, as_of DESC
);
```

### Champs

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `base_currency` | CHAR(3) | Devise source (enum strict) |
| `quote_currency` | CHAR(3) | Devise cible (enum strict) |
| `rate` | NUMERIC(20, 10) | Taux base→quote (1 unité base = `rate` unités quote) |
| `as_of` | DATE | Date du taux (jour) |
| `source` | VARCHAR(100) | « exchangerate-api.com », « ECB », « BCEAO », « manual » |
| `fetched_at` | TIMESTAMPTZ | Horodatage du fetch HTTP |
| `created_at` | TIMESTAMPTZ | Audit insertion |

### Multi-tenant

- **Pas d'`account_id`** : référentiel public global (lecture publique, écriture admin only).

### Tests

- Unique sur `(base, quote, as_of)` — un seul taux par paire et par jour.
- CHECK currencies dans l'enum strict.
- Index pour recherche fallback ascendant `as_of DESC`.

### Seed initial (Phase B)

| base | quote | rate | as_of | source |
|---|---|---|---|---|
| USD | XOF | 615.20 | 2026-04-15 | exchangerate-api.com |
| USD | EUR | 0.92 | 2026-04-15 | exchangerate-api.com |
| USD | GBP | 0.79 | 2026-04-15 | exchangerate-api.com |
| USD | JPY | 152.50 | 2026-04-15 | exchangerate-api.com |
| XOF | USD | 0.001625 | 2026-04-15 | computed (1/USD→XOF) |
| EUR | USD | 1.087 | 2026-04-15 | computed |
| GBP | USD | 1.266 | 2026-04-15 | computed |
| JPY | USD | 0.00656 | 2026-04-15 | computed |

> Note : XOF↔EUR JAMAIS dans `exchange_rates` car peg fixe 655,957 codé en dur via `FCFA_EUR_PEG`.

---

## 2. Modifications de tables existantes — Versioning catalogue

13 tables reçoivent les 4 colonnes `version`, `valid_from`, `valid_to`, `superseded_by` :

| Table | Source feature |
|---|---|
| `sources` | F01 |
| `indicators` | F01 |
| `criteria` | F01 |
| `formulas` | F01 |
| `thresholds` | F01 |
| `referentials` | F01 |
| `referential_indicators` | F01 |
| `emission_factors` | F01 |
| `required_documents` | F01 |
| `simulation_factors` | F01 |
| `funds` | M3 (existant) |
| `intermediaries` | M3 (existant) |
| `fund_intermediaries` | M3 (existant) |

### Pattern DDL appliqué à chaque table

```sql
ALTER TABLE <table> ADD COLUMN version VARCHAR(50) NOT NULL DEFAULT '1.0';
ALTER TABLE <table> ADD CONSTRAINT <table>_version_format_chk CHECK (version ~ '^\d+\.\d+$');
ALTER TABLE <table> ADD COLUMN valid_from DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE <table> ADD COLUMN valid_to DATE NULL;
ALTER TABLE <table> ADD COLUMN superseded_by UUID NULL REFERENCES <table>(id) ON DELETE SET NULL;

CREATE INDEX <table>_valid_to_idx ON <table>(valid_to);
CREATE INDEX <table>_superseded_by_idx ON <table>(superseded_by) WHERE superseded_by IS NOT NULL;

-- Trigger anti-cycle (PostgreSQL only)
CREATE TRIGGER <table>_supersede_cycle_trg
    BEFORE INSERT OR UPDATE OF superseded_by ON <table>
    FOR EACH ROW EXECUTE FUNCTION prevent_supersede_cycle();
```

### Function PL/pgSQL `prevent_supersede_cycle()`

```sql
CREATE OR REPLACE FUNCTION prevent_supersede_cycle() RETURNS trigger AS $$
DECLARE
    cur uuid := NEW.superseded_by;
    seen uuid[] := ARRAY[NEW.id];
    table_name text := TG_TABLE_NAME;
    query text;
    next_cur uuid;
    max_depth int := 100;
    depth int := 0;
BEGIN
    IF NEW.superseded_by IS NULL THEN
        RETURN NEW;
    END IF;
    WHILE cur IS NOT NULL LOOP
        IF cur = ANY(seen) THEN
            RAISE EXCEPTION 'Supersede cycle detected on table % (id=%)', table_name, NEW.id;
        END IF;
        IF depth > max_depth THEN
            RAISE EXCEPTION 'Supersede chain too deep on table % (max % levels)', table_name, max_depth;
        END IF;
        seen := seen || cur;
        depth := depth + 1;
        query := format('SELECT superseded_by FROM %I WHERE id = $1', table_name);
        EXECUTE query INTO next_cur USING cur;
        cur := next_cur;
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Compatibilité SQLite (tests)

- Le trigger PL/pgSQL n'est PAS créé sur SQLite (skip via `if op.get_bind().dialect.name == 'postgresql':`).
- La vérification de cycle est faite côté applicatif dans `app.modules.versioning.service.supersede()`.
- Les tests `test_versioning/test_cycle_trigger.py` testent les deux chemins.

### Lifecycle

- À la création : `version='1.0'`, `valid_from=today`, `valid_to=NULL`, `superseded_by=NULL`.
- À l'édition d'une entité publiée :
  1. Insérer une nouvelle ligne avec `version=bump_version(old)`, `valid_from=today+1`, `valid_to=NULL`.
  2. Mettre à jour l'ancienne : `valid_to=today`, `superseded_by=new.id`.
  3. Conserver les liens FK (ex : `referential_indicators` pointant vers ancien `indicator_id` pointe vers la nouvelle version via `superseded_by` chain — la requête « version active » fait toujours `WHERE valid_to IS NULL`).

---

## 3. Modifications de `fund_applications` — Snapshot

```sql
ALTER TABLE fund_applications ADD COLUMN snapshot_at TIMESTAMPTZ NULL;
ALTER TABLE fund_applications ADD COLUMN snapshot_data JSONB NULL;
```

### Schéma JSON `snapshot_data`

```json
{
  "schema_version": "1.0",
  "captured_at": "2026-05-06T14:30:00Z",
  "referential": {
    "id": "uuid",
    "name": "Référentiel ESG Mefali",
    "version": "1.2",
    "valid_from": "2026-01-01",
    "valid_to": null,
    "indicators": [
      {
        "id": "uuid",
        "code": "E1",
        "name": "Empreinte carbone",
        "weight": 0.15,
        "thresholds": {"low": 100, "med": 50, "high": 10},
        "source_id": "uuid"
      }
    ],
    "documents_requis": [
      {"id": "uuid", "name": "Bilan carbone certifié", "is_mandatory": true}
    ]
  },
  "fund": {
    "id": "uuid",
    "name": "GCF",
    "version": "2.3",
    "min_amount": "5000000.00",
    "min_amount_currency": "USD",
    "max_amount": "10000000.00",
    "max_amount_currency": "USD",
    "esg_requirements": {}
  },
  "intermediary": {
    "id": "uuid",
    "name": "BOAD",
    "version": "1.0",
    "country": "Senegal",
    "fees_typical": "..."
  },
  "offer": {
    "fund_id": "uuid",
    "intermediary_id": "uuid"
  },
  "scores": {
    "esg_total": 72.5,
    "esg_breakdown": {"E": 80, "S": 70, "G": 65},
    "credit_score": null,
    "carbon_total_tco2e": 12.3
  },
  "documents_requis_at_submission": ["..."],
  "source_ids_cited": ["uuid", "uuid"]
}
```

### Triggers / contraintes

- Aucune contrainte BDD : la validation du contenu JSON est faite côté applicatif via Pydantic schema `SnapshotData` (validé à la lecture).
- Immuabilité : aucun service métier n'écrit dans `snapshot_data` après création. Une assertion `validate_immutable()` lève une exception si tentative.

### Multi-tenant

- Hérite de `fund_applications.account_id` (déjà présent depuis F02).
- RLS héritée (déjà active sur `fund_applications`).

---

## 4. Modifications de tables financières — Paires Money

5 tables reçoivent des paires `<field>_amount` + `<field>_currency` :

| Table | Champ legacy | Nouveau champ amount | Nouveau champ currency |
|---|---|---|---|
| `funds` | `min_amount_xof: BIGINT` | `min_amount: NUMERIC(20,2)` | `min_amount_currency: CHAR(3)` |
| `funds` | `max_amount_xof: BIGINT` | `max_amount: NUMERIC(20,2)` | `max_amount_currency: CHAR(3)` |
| `company_profiles` | `annual_revenue_xof: BIGINT` | `annual_revenue_amount: NUMERIC(20,2)` | `annual_revenue_currency: CHAR(3)` |
| `action_items` | `estimated_cost_xof: INT` | `estimated_cost_amount: NUMERIC(20,2)` | `estimated_cost_currency: CHAR(3)` |
| `carbon_assessments` | `savings_fcfa: FLOAT` (si présent) | `savings_amount: NUMERIC(20,2)` | `savings_currency: CHAR(3)` |

> **Note** : `applications.intermediary_fees_xof` est dans le JSON `simulation`, refactor applicatif uniquement (pas de migration BDD pour ce champ).

### Pattern DDL

```sql
ALTER TABLE funds ADD COLUMN min_amount NUMERIC(20, 2) NULL;
ALTER TABLE funds ADD COLUMN min_amount_currency CHAR(3) NULL;
ALTER TABLE funds ADD CONSTRAINT funds_min_amount_currency_chk CHECK (
    min_amount_currency IS NULL
    OR min_amount_currency IN ('XOF', 'EUR', 'USD', 'GBP', 'JPY')
);
ALTER TABLE funds ADD CONSTRAINT funds_min_amount_pair_chk CHECK (
    (min_amount IS NULL AND min_amount_currency IS NULL)
    OR (min_amount IS NOT NULL AND min_amount_currency IS NOT NULL)
);
```

### Backfill (idempotent)

```sql
UPDATE funds SET
    min_amount = COALESCE(min_amount, min_amount_xof),
    min_amount_currency = COALESCE(min_amount_currency, 'XOF')
WHERE min_amount_xof IS NOT NULL;
```

### Cohabitation Python (modèle SQLAlchemy)

```python
class Fund(Base):
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    min_amount_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    min_amount_xof: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # legacy

    @property
    def min_amount_money(self) -> Money | None:
        if self.min_amount is not None and self.min_amount_currency:
            return Money(amount=self.min_amount, currency=self.min_amount_currency)
        if self.min_amount_xof is not None:
            return Money(amount=Decimal(self.min_amount_xof), currency="XOF")
        return None
```

---

## 5. Diagramme de relations (extrait)

```text
+----------------+         +------------------+
|  referentials  |◄────────+ referential_     |
|  +version      |         | indicators       |
|  +valid_from   |         | +version,...     |
|  +valid_to     |         +------------------+
|  +superseded_by|                 │
+----------------+                 ▼
                          +------------------+
                          |   indicators     |
                          |   +version,...   |
                          +------------------+

+--------------------+
| fund_applications  |
|  +snapshot_at      |    snapshot_data (JSONB autoportant) :
|  +snapshot_data    |    {referential, fund, intermediary, scores, ...}
+--------------------+

+----------------+
| exchange_rates |  (référentiel public, pas d'account_id)
|  base, quote   |
|  rate, as_of   |
+----------------+
```

---

## 6. Récapitulatif des changements de schéma

| Type | Quantité |
|---|---|
| Nouvelles tables | 1 (`exchange_rates`) |
| Tables modifiées (versioning columns x4) | 13 |
| Tables modifiées (snapshot fields x2) | 1 (`fund_applications`) |
| Tables modifiées (paires Money) | 5 (avec 2 paires sur `funds`) |
| Total colonnes ajoutées | 13×4 + 2 + (2 + 2 + 2 + 2 + 2) = 64 colonnes |
| Triggers PL/pgSQL créés | 13 (anti-cycle) |
| Functions PL/pgSQL créées | 1 (`prevent_supersede_cycle`) |
| Index ajoutés | 13×2 + 1 = 27 |
| CHECK constraints ajoutées | ~30 (version format + currency enum + pairing) |

---

## 7. Validation Pydantic schemas API (Phase B)

Tous les schemas API exposant des montants doivent utiliser `Money` :

```python
from app.core.money import Money

class FundResponse(BaseModel):
    id: UUID
    name: str
    version: str
    valid_from: date
    valid_to: date | None
    min_amount: Money | None
    max_amount: Money | None
    # ... reste des champs
    
    @model_validator(mode='after')
    def reconstruct_money_from_columns(cls, values):
        # Ou via classmethod from_orm avec Money.from_columns()
        return values
```

```python
class SnapshotData(BaseModel):
    schema_version: str = "1.0"
    captured_at: datetime
    referential: SnapshotReferential
    fund: SnapshotFund
    intermediary: SnapshotIntermediary | None
    offer: SnapshotOffer | None
    scores: SnapshotScores
    documents_requis_at_submission: list[str]
    source_ids_cited: list[UUID]
```
