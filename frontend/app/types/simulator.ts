// F16 — Types TypeScript miroirs des schémas Pydantic du simulateur sourcé.

export type Currency = 'XOF' | 'EUR' | 'USD' | 'GBP' | 'JPY'

export interface Money {
  amount: string
  currency: Currency
}

export type FactorStatus = 'draft' | 'pending' | 'verified' | 'outdated'

export interface MonetaryFigure {
  amount: Money
  amount_pme_equivalent: Money | null
  source_id: string | null
  factor_name: string | null
  factor_status: FactorStatus | null
  degraded_reason: string | null
}

export interface CostBreakdown {
  principal: Money
  doc_fee: MonetaryFigure
  total_fees_over_duration: MonetaryFigure
  guarantee_required: MonetaryFigure
  fx_margin: MonetaryFigure
  total_cost: Money
}

export type InstrumentType =
  | 'subvention'
  | 'pret_concessionnel'
  | 'equity'
  | 'blending'

export interface RoiBreakdown {
  instrument: InstrumentType
  formula_id: string
  gain_estimated: Money | null
  payback_months: number | null
  ratio: string | null
  notes_fr: string
  sources: string[]
}

export interface CarbonImpact {
  tco2e_per_year: string | null
  sector_factor: string | null
  factor_source_id: string | null
  project_estimate_used: string | null
  is_approximate: boolean
  degraded_reason: string | null
}

export type TimelineStepId =
  | 'preparation'
  | 'instruction_intermediaire'
  | 'validation_fonds'
  | 'decaissement'

export interface TimelineStep {
  step_id: TimelineStepId
  label_fr: string
  weeks_min: number | null
  weeks_max: number | null
  source_id: string | null
  degraded_reason: string | null
}

export interface SimulationResult {
  offer_id: string
  project_id: string
  principal: Money
  principal_pme_equivalent: Money | null
  cost_breakdown: CostBreakdown
  roi: RoiBreakdown
  carbon_impact: CarbonImpact
  timeline: TimelineStep[]
  sources_used: string[]
  degraded: boolean
  computed_at: string
  kind: 'ok'
}

export interface DegradedColumn {
  offer_id: string
  reason: string
  computed_at: string
  kind: 'degraded'
}

export type OfferColumn = SimulationResult | DegradedColumn

export interface ComparisonMetadata {
  cheapest_offer_id: string | null
  fastest_offer_id: string | null
  degraded_offers: string[]
  total_offers: number
}

export interface MultiSimulateRequest {
  offer_ids: string[]
}

export interface MultiSimulateResponse {
  project_id: string
  per_offer: Record<string, OfferColumn>
  comparison_metadata: ComparisonMetadata
  factor_snapshot_loaded_at: string
}

// Type guard helper
export function isDegradedColumn(col: OfferColumn): col is DegradedColumn {
  return col.kind === 'degraded'
}

export function isSimulationResult(
  col: OfferColumn,
): col is SimulationResult {
  return col.kind === 'ok'
}
