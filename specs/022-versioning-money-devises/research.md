# Research — F04 Versioning + Money Type + Multi-devises

**Date** : 2026-05-06
**Feature** : `feat/F04-versioning-money-devises`

Document Phase 0 du plan. Consigne les décisions techniques, leurs alternatives et leur rationale avant d'attaquer Phase 1 (design / contracts).

---

## R-01 : Représentation BDD du type `Money`

- **Décision** : 2 colonnes `<field>_amount: NUMERIC(20,2)` + `<field>_currency: CHAR(3)` par champ Money. Reconstruction `Money` côté schéma Pydantic.
- **Rationale** :
  - Compatible PostgreSQL ET SQLite (pas de type composé portable).
  - Indexable sur `currency` si besoin (ex : agrégation par devise).
  - Évite la complexité d'un `TypeDecorator` SQLAlchemy custom et d'un type composé PostgreSQL `(amount, currency)`.
  - Cohérent avec la convention F01 / F02 (colonnes simples + helpers Python).
- **Alternatives évaluées** :
  - **Type composé PostgreSQL** `CREATE TYPE money_t AS (amount NUMERIC, currency CHAR(3))` : refusé pour incompatibilité SQLite et complexité Alembic.
  - **JSONB unique** `{amount, currency}` par champ : refusé pour perte d'index, requêtes plus lourdes, sérialisation Decimal en string non standard.
  - **TypeDecorator SQLAlchemy custom** : refusé pour MVP (complexité, edge cases sur `__composite_values__`).

---

## R-02 : Type JSONB pour `snapshot_data`

- **Décision** : `JSONB` natif PostgreSQL via `sqlalchemy.dialects.postgresql.JSONB`, avec variant `JSON` pour SQLite (cf. helper `JSONType` déjà utilisé par F01 dans `app/models/source.py`).
- **Rationale** :
  - JSONB indexable, supporte les opérateurs `->`, `->>`, `@>` pour extraction et requêtage.
  - Variant SQLite préserve la cohérence de tests in-memory.
  - Stockage typique attendu < 100 KB (10-30 indicateurs + fund + intermediary + scores).
- **Alternatives évaluées** :
  - **Table satellite** `application_snapshots` (1:1) : refusé car snapshot toujours lu en même temps que la candidature, jointure inutile.
  - **JSON (non binaire)** : refusé car perte d'opérateurs et perf de parsing à la lecture.
  - **gzip + bytea** : reporté post-MVP (mesure d'abord la taille moyenne).

---

## R-03 : Trigger anti-cycle PostgreSQL

- **Décision** : fonction PL/pgSQL `prevent_supersede_cycle()` + trigger `BEFORE INSERT OR UPDATE OF superseded_by` par table catalogue. Sur SQLite (tests), skip ; fallback applicatif via `versioning.supersede(entity, new_id)` qui fait une recherche en chaîne.
- **Rationale** :
  - Garantit l'invariant en BDD (défense en profondeur), même si un service oublie de valider.
  - PL/pgSQL est performant pour parcourir une chaîne courte (< 10 niveaux typiquement).
- **Implémentation** (PostgreSQL) :
  ```sql
  CREATE OR REPLACE FUNCTION prevent_supersede_cycle() RETURNS trigger AS $$
  DECLARE
      cur uuid := NEW.superseded_by;
      seen uuid[] := ARRAY[NEW.id];
      table_name text := TG_TABLE_NAME;
      query text;
  BEGIN
      IF NEW.superseded_by IS NULL THEN
          RETURN NEW;
      END IF;
      WHILE cur IS NOT NULL LOOP
          IF cur = ANY(seen) THEN
              RAISE EXCEPTION 'Supersede cycle detected on table % (id=%)', table_name, NEW.id;
          END IF;
          seen := seen || cur;
          query := format('SELECT superseded_by FROM %I WHERE id = $1', table_name);
          EXECUTE query INTO cur USING cur;
      END LOOP;
      RETURN NEW;
  END;
  $$ LANGUAGE plpgsql;
  ```
- **Alternatives évaluées** :
  - **Vérification applicative uniquement** : refusée — un bug applicatif ou un bypass admin pourrait introduire un cycle.
  - **Contrainte CHECK simple** : impossible (CHECK ne peut pas faire de récursion).

---

## R-04 : Cap fetch quotidien exchangerate-api.com

- **Décision** : vérification applicative simple : `SELECT MAX(fetched_at) FROM exchange_rates` ; si delta < 24h, skip silencieux. Pas de table de quota séparée.
- **Rationale** :
  - Tier gratuit : 1500 req/mois → 50 req/jour. Notre usage : 1 fetch/jour (un appel HTTP retourne toutes les paires USD→XYZ). Marge confortable.
  - Pas de source de vérité externe (pas de Redis/Memcached pour quota), `exchange_rates` suffit.
- **Implémentation** :
  ```python
  async def should_fetch(session: AsyncSession) -> bool:
      result = await session.execute(select(func.max(ExchangeRate.fetched_at)))
      last = result.scalar_one_or_none()
      if last is None:
          return True
      return (datetime.now(timezone.utc) - last) > timedelta(hours=24)
  ```
- **Alternatives évaluées** :
  - **Compteur Redis** : refusé (pas de Redis dans le MVP).
  - **APScheduler** : reporté à F19 (scheduler dédié).

---

## R-05 : API exchangerate-api.com

- **Décision** : endpoint `https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD`. Parsing JSON `conversion_rates` qui contient toutes les paires `USD→XYZ`. Insertion par paire dans la table `exchange_rates`.
- **Rationale** :
  - 1 seul appel HTTP suffit pour récupérer les 4-5 paires nécessaires (USD→XOF, USD→EUR, USD→GBP, USD→JPY) — économie de quota.
  - Format JSON simple, parsing direct.
  - Mode dégradé : si `EXCHANGERATE_API_KEY` vide, le service skip silencieusement (utile pour dev sans clé).
- **Dérivation des paires inverses** :
  - `XOF→USD = 1 / (USD→XOF)` calculé à l'insertion et inséré comme entrée séparée.
- **Alternatives évaluées** :
  - **fixer.io** : tier gratuit limité à EUR base, refusé.
  - **ECB / openexchangerates.org** : tier gratuit moins permissif.
  - **BCEAO scraping** : refusé (pas d'API officielle, fragile).

---

## R-06 : Pivot USD pour conversion non-peggée

- **Décision** : si pas de paire directe `(base, quote)` en table, le service tente le pivot USD : `convert(EUR, JPY) = convert(USD, JPY) * convert(EUR, USD)`. Si l'un des deux taux est manquant, exception `ConversionPathUnavailableError`.
- **Rationale** :
  - USD est la devise pivot universelle de exchangerate-api.com (toutes les paires partent de USD).
  - Évite la combinatoire N² de stockage de paires.
  - Comportement déterministe et testable.
- **Algorithme** :
  ```python
  def convert_with_pivot(money: Money, target: Currency) -> Money:
      if (money.currency, target) in PEG_PAIRS:
          return _convert_peg(money, target)
      direct = _try_direct(money.currency, target)
      if direct is not None:
          return Money(amount=money.amount * direct, currency=target)
      # Pivot USD
      to_usd = _try_direct(money.currency, "USD")
      from_usd = _try_direct("USD", target)
      if to_usd is None or from_usd is None:
          raise ConversionPathUnavailableError(money.currency, target)
      return Money(amount=money.amount * to_usd * from_usd, currency=target)
  ```
- **Alternatives évaluées** :
  - **Pivot EUR** : refusé car volume des paires EUR↔X plus faible que USD↔X.
  - **Multi-pivot avec graphe** : reporté post-MVP (overkill pour 5 devises).

---

## R-07 : Validation Pydantic v2 strict pour `Money`

- **Décision** : Pydantic v2 `BaseModel` avec :
  - `amount: Decimal = Field(..., ge=0, decimal_places=2)` (utilisation de `Annotated` + `condecimal`)
  - `currency: Currency` (`Literal["XOF", "EUR", "USD", "GBP", "JPY"]`)
  - `model_config = ConfigDict(frozen=True, strict=True)` pour immuabilité
- **Rationale** :
  - `frozen=True` rend l'instance immuable (cohérent avec principle de coding-style).
  - `strict=True` empêche les coercions silencieuses (pas de `Money(amount="1000.00", ...)` autorisé sans cast explicite).
  - `decimal_places=2` aligne sur la précision BDD `NUMERIC(20,2)`.
- **Sérialisation JSON** : `model_dump(mode='json')` → `{"amount": "655.957", "currency": "XOF"}` (Decimal en string pour préserver précision).
- **Alternatives évaluées** :
  - **NamedTuple** : refusé car pas de validation Pydantic au runtime.
  - **dataclass(frozen=True)** : refusé pour la même raison + manque d'intégration FastAPI.

---

## R-08 : Stratégie migration en 2 phases

- **Décision Phase 1 (F04)** : ajout colonnes `<field>_amount` + `<field>_currency` SANS dropper les anciennes `*_xof` / `*_fcfa`. Backfill systématique.
- **Décision Phase 2 (HORS-SCOPE F04)** : drop des anciennes colonnes après refactor exhaustif des services consommateurs (planifiée comme migration séparée 02X).
- **Rationale** :
  - Permet déploiement incrémental : la phase 1 peut sortir en prod sans casser les services qui utilisent encore `*_xof`.
  - Refactor des services peut être étalé sur plusieurs PR.
  - Drop séparé minimise le rollback risk.
- **Cohabitation** : property Python sur les modèles SQLAlchemy
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

## R-09 : Bump version semver-like

- **Décision** : format `MAJOR.MINOR` à 2 composantes (regex `^\d+\.\d+$`). Bump minor par défaut, bump major via flag explicite.
- **Rationale** :
  - 2 composantes suffisent pour le MVP : MAJOR = changement structurel, MINOR = ajustement non rupteur.
  - Pas de PATCH (les hotfixes catalogue sont rares ; bump minor suffit).
- **Implémentation** :
  ```python
  def bump_version(current: str, force_major: bool = False) -> str:
      m = re.match(r"^(\d+)\.(\d+)$", current)
      if not m:
          raise VersioningError(f"invalid version format: {current}")
      major, minor = int(m.group(1)), int(m.group(2))
      if force_major:
          return f"{major + 1}.0"
      return f"{major}.{minor + 1}"
  ```

---

## R-10 : Format `snapshot_data`

- **Décision** : structure JSON standardisée auto-portante.
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
      "esg_requirements": {...}
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
    "source_ids_cited": ["uuid", "uuid", ...]
  }
  ```
- **Rationale** :
  - `schema_version` permet d'évoluer le format de snapshot dans le futur sans casser les anciens.
  - `referential.indicators` contient tout ce qu'il faut pour le `recompute` (poids, seuils, source_id).
  - `source_ids_cited` permet de retrouver les sources F01 mobilisées.
  - Auto-portant : aucune FK externe ; les UUIDs sont indicatifs uniquement.

---

## R-11 : Persistance Pydantic Money en BDD via SQLAlchemy

- **Décision** : pas de `TypeDecorator` SQLAlchemy custom pour le MVP. Les modèles exposent les colonnes `_amount` + `_currency` ; les schemas Pydantic API exposent `Money` reconstruit via une factory `Money.from_columns(amount, currency)` ou `Money(**{"amount": x.min_amount, "currency": x.min_amount_currency})`.
- **Rationale** :
  - Évite la complexité d'un type SQLAlchemy custom.
  - Cohérent avec le paradigme « modèle SQLAlchemy minimal, schémas Pydantic riches » du projet.
- **Helper** :
  ```python
  class Money(BaseModel):
      ...
      @classmethod
      def from_columns(cls, amount: Decimal | None, currency: str | None) -> "Money | None":
          if amount is None or currency is None:
              return None
          return cls(amount=amount, currency=currency)
  ```

---

## R-12 : Compatibilité SQLite pour les tests

- **Décision** : `Numeric(20,2)` et `String(3)` portables. `JSONType` (variant `JSONB`/`JSON`) déjà en place. Triggers PL/pgSQL skip en SQLite (vérification cycle applicative).
- **Rationale** :
  - Maintient le pattern de tests in-memory rapide (pas de docker postgres requis pour tests unitaires).
  - Tests d'intégration `test_022_money_and_versioning.py` utilisent PostgreSQL pour valider les triggers.

---

## R-13 : Endpoint `recompute-against-snapshot`

- **Décision** : `POST /api/applications/{id}/recompute-against-snapshot` (auth user, vérifie `account_id`). Retourne `{score: float, breakdown: dict, snapshot_at: datetime, comparison_with_origin: {match: bool, delta: float}}`.
- **Rationale** :
  - POST (et non GET) car opération idempotente mais pouvant être chère et journalisée (audit log F03).
  - Comparaison avec score d'origine pour démontrer l'immuabilité.
- **Sécurité** : 403 si `account_id` ne match pas, 409 si `snapshot_at IS NULL`.

---

## R-14 : Endpoint admin `fetch-status`

- **Décision** : `GET /api/admin/currency/fetch-status` (auth admin via `get_current_admin`). Réponse :
  ```json
  {
    "last_success_at": "2026-05-06T08:00:00Z",
    "last_failure_at": null,
    "last_error_message": null,
    "daily_quota_used": 1,
    "daily_quota_max": 50
  }
  ```
- **Rationale** : permet à l'admin de monitorer sans loguer. Source de données : `MAX(fetched_at)` + table `currency_fetch_log` (envisagée mais finalement les infos peuvent être dérivées de `exchange_rates` directement, pas de table dédiée nécessaire pour MVP).
- **Implémentation simplifiée** (sans table fetch_log dédiée) :
  - `last_success_at = MAX(fetched_at)` depuis `exchange_rates`.
  - `last_failure_at`, `last_error_message` : stockés en mémoire process (non persistant) pour le MVP, ou journalisé via log structuré seulement.
  - `daily_quota_used = COUNT(DISTINCT (base_currency, quote_currency)) WHERE fetched_at >= today`.
  - `daily_quota_max = 50` (constante config).

---

## Récapitulatif

Toutes les questions techniques ouvertes ont été tranchées. Aucune NEEDS CLARIFICATION ne demeure. La Phase 1 (data-model.md, contracts/, quickstart.md) peut démarrer.
