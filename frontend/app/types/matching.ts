// F14 — Types TypeScript miroir des schemas Pydantic

export type MatchBottleneck = 'fund' | 'intermediary' | 'balanced'
export type MatchStatus = 'suggested' | 'viewed' | 'dismissed' | 'converted'

export interface MissingCriterion {
  indicatorId?: string | null
  indicatorCode?: string | null
  label: string
  referentialId?: string | null
  sourceId?: string | null
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

export interface ScoreBreakdown {
  fund: MatchSubBreakdown
  intermediary: MatchSubBreakdown
  assessmentMissing: boolean
  sizeMatchCurrencyMismatch?: boolean
}

export interface RecommendedAction {
  label: string
  indicatorId?: string | null
  referentialId?: string | null
  sourceId?: string | null
}

export interface OfferMatch {
  id: string
  accountId: string
  projectId: string
  offerId: string
  globalScore: number
  fundScore: number
  intermediaryScore: number
  scoreBreakdown: Record<string, unknown>
  bottleneck: MatchBottleneck
  recommendedActions: RecommendedAction[]
  status: MatchStatus
  computedAt: string
  expiresAt: string
  lastNotifiedAt: string | null
}

export interface OfferMatchListResponse {
  items: OfferMatch[]
  total: number
  page: number
  limit: number
}

export interface RecomputeMatchesResponse {
  recomputeRequestId: string
  totalOffersToCompute: number
}

export interface ComparisonValue {
  subjectId: string
  raw: unknown
  display: string
  sourceId?: string | null
  isWinner: boolean
}

export interface ComparisonRow {
  key: string
  label: string
  type: string
  values: ComparisonValue[]
}

export interface ComparisonSubject {
  id: string
  label: string
  metadata?: Record<string, unknown>
}

export interface ComparisonResult {
  fundId: string
  projectId: string
  subjects: ComparisonSubject[]
  rows: ComparisonRow[]
}

export interface MatchAlertSubscription {
  id: string
  projectId: string
  minGlobalScore: number
  isActive: boolean
}

export interface MatchAlertSubscriptionUpdate {
  minGlobalScore?: number
  isActive?: boolean
}
