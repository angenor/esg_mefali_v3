# Data Model — F14 Matching Projet ↔ Offre

## New tables

### `offer_matches`

Persistance d'un match calculé entre un projet (F06) et une offre (F07). UNIQUE `(project_id, offer_id)` → recompute = UPDATE in-place.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID PK | NOT NULL | `gen_random_uuid()` | |
| `account_id` | UUID FK accounts.id ON DELETE RESTRICT | NOT NULL | — | F02 multi-tenant + RLS |
| `project_id` | UUID FK projects.id ON DELETE CASCADE | NOT NULL | — | F06 |
| `offer_id` | UUID FK offers.id ON DELETE RESTRICT | NOT NULL | — | F07 |
| `global_score` | INT | NOT NULL | — | CHECK 0..100, `min(fund_score, intermediary_score)` |
| `fund_score` | INT | NOT NULL | — | CHECK 0..100 |
| `intermediary_score` | INT | NOT NULL | — | CHECK 0..100 |
| `score_breakdown` | JSONB | NOT NULL | `'{}'::jsonb` | `{fund: {...sub_scores, missing_criteria[]}, intermediary: {...}, assessment_missing: bool}` |
| `bottleneck` | VARCHAR(20) | NOT NULL | — | CHECK IN ('fund','intermediary','balanced') |
| `recommended_actions` | JSONB | NOT NULL | `'[]'::jsonb` | top 3 actions FR pour combler les écarts |
| `status` | VARCHAR(20) | NOT NULL | `'suggested'` | CHECK IN ('suggested','viewed','dismissed','converted') |
| `computed_at` | TIMESTAMPTZ | NOT NULL | `now()` | |
| `expires_at` | TIMESTAMPTZ | NOT NULL | `now() + interval '30 days'` | recalcul au-delà |
| `last_notified_at` | TIMESTAMPTZ | NULL | — | idempotence alertes |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | |

**Indexes** :
- `UNIQUE (project_id, offer_id)` → contraint le caractère « courant unique »
- `INDEX (project_id, computed_at DESC)` → liste par projet
- `INDEX (account_id, expires_at)` → cron recompute_stale_matches
- `INDEX (offer_id)` → invalidation event-driven sur Offer
- `INDEX (account_id, global_score DESC)` → liste triée
- `INDEX (last_notified_at) WHERE last_notified_at IS NULL` → cron alertes

**CHECK constraints** :
- `global_score BETWEEN 0 AND 100`
- `fund_score BETWEEN 0 AND 100`
- `intermediary_score BETWEEN 0 AND 100`
- `bottleneck IN ('fund','intermediary','balanced')`
- `status IN ('suggested','viewed','dismissed','converted')`

**RLS** : ENABLE + FORCE. Policies :
- `offer_matches_pme_access_own_account` : `account_id = current_setting('app.current_account_id')::uuid` (USING + WITH CHECK)
- `offer_matches_admin_full_access` : `current_setting('app.current_role') = 'ADMIN'` (USING + WITH CHECK)

**Auditable F03** : `OfferMatch` ajouté à `AUDITABLE_MODELS`.

---

### `match_alerts_subscriptions`

Souscription par projet aux alertes nouvelles offres compatibles.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID PK | NOT NULL | `gen_random_uuid()` | |
| `account_id` | UUID FK accounts.id ON DELETE CASCADE | NOT NULL | — | F02 |
| `project_id` | UUID FK projects.id ON DELETE CASCADE | NOT NULL | — | F06 — UNIQUE |
| `min_global_score` | INT | NOT NULL | `60` | CHECK 0..100 |
| `is_active` | BOOLEAN | NOT NULL | `true` | toggle on/off |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | |

**Indexes** :
- `UNIQUE (project_id)` → 1 souscription / projet
- `INDEX (account_id, is_active)` → cron notify_new_offer_matches

**CHECK** : `min_global_score BETWEEN 0 AND 100`

**RLS** : ENABLE + FORCE. Policies cohérentes F02 (pme_access_own_account + admin_full_access).

**Auditable F03** : `MatchAlertSubscription` ajouté à `AUDITABLE_MODELS`.

---

## Migration Alembic 036

**Revision** : `036_offer_matches_and_alerts`
**Down_revision** : à confirmer en Phase B (au moment de Phase A : `035_admin_publication_status_workflow`)

**Up** :
1. CREATE TABLE `offer_matches` avec colonnes, CHECK, indexes
2. CREATE TABLE `match_alerts_subscriptions` avec colonnes, CHECK, UNIQUE
3. ALTER TABLE `offer_matches` ENABLE ROW LEVEL SECURITY + FORCE + 2 policies (PostgreSQL only via dialect check)
4. ALTER TABLE `match_alerts_subscriptions` ENABLE ROW LEVEL SECURITY + FORCE + 2 policies
5. Backfill `fund_matches` → `offer_matches` (best-effort, ON CONFLICT DO NOTHING) :
   ```sql
   INSERT INTO offer_matches (id, account_id, project_id, offer_id, ...)
   SELECT gen_random_uuid(), fm.account_id,
          (SELECT id FROM projects WHERE account_id = fm.account_id 
           AND status NOT IN ('cancelled','closed') ORDER BY created_at DESC LIMIT 1),
          (SELECT o.id FROM offers o
           JOIN intermediaries i ON i.id = o.intermediary_id
           WHERE o.fund_id = fm.fund_id AND i.code = 'DIRECT'
           AND o.publication_status = 'published'
           ORDER BY o.version DESC LIMIT 1),
          fm.compatibility_score, fm.compatibility_score, fm.compatibility_score,
          '{}'::jsonb, 'balanced', '[]'::jsonb,
          'suggested', now(), now() + interval '30 days', NULL,
          fm.created_at, fm.created_at
   FROM fund_matches fm
   WHERE EXISTS (SELECT 1 FROM projects p WHERE p.account_id = fm.account_id AND p.status NOT IN ('cancelled','closed'))
     AND EXISTS (SELECT 1 FROM offers o JOIN intermediaries i ON i.id=o.intermediary_id
                 WHERE o.fund_id = fm.fund_id AND i.code='DIRECT' AND o.publication_status='published')
   ON CONFLICT (project_id, offer_id) DO NOTHING;
   ```
6. Backfill `match_alerts_subscriptions` pour tous les projets actifs existants (idempotent, ON CONFLICT DO NOTHING).

**Down** :
1. DROP TABLE `match_alerts_subscriptions`
2. DROP TABLE `offer_matches`
(`fund_matches` non touchée)

**Round-trip** `up/down/up` validé sur PostgreSQL.

---

## SQLAlchemy models

### `app/models/offer_match.py`

```python
class OfferMatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "offer_matches"
    __table_args__ = (
        UniqueConstraint("project_id", "offer_id", name="uq_offer_matches_project_offer"),
        CheckConstraint("global_score BETWEEN 0 AND 100", ...),
        # ... 4 autres CHECK
        Index("idx_offer_matches_project_computed", "project_id", "computed_at"),
        Index("idx_offer_matches_account_expires", "account_id", "expires_at"),
        Index("idx_offer_matches_offer", "offer_id"),
        Index("idx_offer_matches_account_score", "account_id", "global_score"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False)
    global_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fund_score: Mapped[int] = mapped_column(Integer, nullable=False)
    intermediary_score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    bottleneck: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_actions: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
        server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(lazy="selectin")
    offer: Mapped["Offer"] = relationship(lazy="selectin")
```

### `app/models/match_alert_subscription.py`

```python
class MatchAlertSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "match_alerts_subscriptions"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_match_alerts_subscription_project"),
        CheckConstraint("min_global_score BETWEEN 0 AND 100", ...),
        Index("idx_match_alerts_account_active", "account_id", "is_active"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    min_global_score: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

---

## Pydantic v2 schemas

`backend/app/modules/financing/matching_schemas.py` :

- `MatchSubBreakdown` (frozen=True) : `sector_match`, `esg_match`, `size_match`, `location_match`, `documents_match`, `instrument_match`, `missing_criteria: list[MissingCriterion]`
- `MissingCriterion` (frozen=True) : `indicator_id: UUID`, `label: str`, `referential_id: UUID`, `source_id: UUID`
- `ScoreBreakdown` (frozen=True) : `fund: MatchSubBreakdown`, `intermediary: MatchSubBreakdown`, `assessment_missing: bool`
- `OfferMatchRead` : sérialisation API complète, `model_config = ConfigDict(from_attributes=True)`
- `OfferMatchListResponse` : `items: list[OfferMatchRead]`, `total`, `page`, `limit`
- `RecomputeMatchesResponse` : `recompute_request_id: UUID`, `total_offers_to_compute: int`
- `ComparisonResult` (réutilisable F11) : `fund_id`, `project_id`, `subjects: list[ComparisonSubject]`, `rows: list[ComparisonRow]`
- `MatchAlertSubscriptionRead` : `id`, `project_id`, `min_global_score`, `is_active`
- `MatchAlertSubscriptionUpdate` : `min_global_score: int | None`, `is_active: bool | None`

Validators :
- `bottleneck` : Literal['fund','intermediary','balanced']
- `status` : Literal['suggested','viewed','dismissed','converted']
- `min_global_score` : `Field(ge=0, le=100)`

---

## Frontend TypeScript types

`frontend/app/types/matching.ts` :

```ts
export interface OfferMatch {
  id: string
  accountId: string
  projectId: string
  offerId: string
  globalScore: number
  fundScore: number
  intermediaryScore: number
  scoreBreakdown: ScoreBreakdown
  bottleneck: 'fund' | 'intermediary' | 'balanced'
  recommendedActions: RecommendedAction[]
  status: 'suggested' | 'viewed' | 'dismissed' | 'converted'
  computedAt: string
  expiresAt: string
  lastNotifiedAt: string | null
}

export interface ScoreBreakdown {
  fund: MatchSubBreakdown
  intermediary: MatchSubBreakdown
  assessmentMissing: boolean
}

export interface MatchSubBreakdown {
  sectorMatch: number
  esgMatch: number
  sizeMatch: number
  locationMatch: number
  documentsMatch: number
  instrumentMatch: number
  missingCriteria: MissingCriterion[]
}

export interface MissingCriterion {
  indicatorId: string
  label: string
  referentialId: string
  sourceId: string
}

export type MatchBottleneck = 'fund' | 'intermediary' | 'balanced'

export interface MatchSubscription {
  id: string
  projectId: string
  minGlobalScore: number
  isActive: boolean
}

export interface RecomputeMatchesResponse {
  recomputeRequestId: string
  totalOffersToCompute: number
}

export interface ComparisonResult {
  fundId: string
  projectId: string
  subjects: Array<{ id: string; label: string; metadata?: Record<string, unknown> }>
  rows: Array<{ key: string; label: string; values: Array<{ subjectId: string; raw: unknown; display: string; sourceId?: string; isWinner?: boolean }> }>
}
```
