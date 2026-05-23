/**
 * F045 - Types TypeScript miroir des schemas Pydantic backend.
 *
 * Source de verite : backend/app/modules/financing/matching_schemas.py +
 * data-model.md §9 de specs/045-matching-projet-centric/.
 */

/** Cles des 8 sub-scores projet (research.md R5). */
export type SubScoreKey =
  | 'sector'
  | 'taxonomy'
  | 'gcf_themes'
  | 'co2_impact'
  | 'beneficiaries'
  | 'gender'
  | 'vulnerable'
  | 'project_esg'

export type FactorStatus = 'ok' | 'sources_pending' | 'unsourced_fallback'

export type MissingCriterionKind = 'below_threshold' | 'missing' | 'wrong_value'

export interface SubScores {
  sector: number
  taxonomy: number
  gcf_themes: number
  co2_impact: number
  beneficiaries: number
  gender: number
  vulnerable: number
  project_esg: number
}

export interface SourceUsed {
  sub_score: SubScoreKey
  source_id: string
  source_name: string
  url?: string | null
}

export interface MissingCriterion {
  key: string
  label_fr: string
  source_id?: string | null
  kind: MissingCriterionKind
  current_value?: number | string | null
  target_value?: number | string | null
}

export interface BoostApplied {
  rule_triggered: boolean
  rule_name?: string | null
}

export type ProjectEsgSourceKind = 'calculated' | 'manual_f045' | 'unsourced'

export interface ReferentialRef {
  id: string
  code: string
  label: string
  version: string
}

/** F047 — Sub-score project_esg détaillé (transparence UI + CTA). */
export interface ProjectEsgSubScore {
  score: number
  weight: number
  is_fallback: boolean
  referential_used: ReferentialRef | null
  assessment_id: string | null
  source_kind: ProjectEsgSourceKind
  unsourced: boolean
  cta_hint: string | null
}

export interface ProjectScoreBreakdown {
  weights_version: string
  sub_scores: SubScores
  sources_used: SourceUsed[]
  missing_criteria: MissingCriterion[]
  boost_applied: BoostApplied
  computed_at: string
  factor_status: FactorStatus
  /** F047 — meta du sub-score project_esg. Optionnel (rétrocompat). */
  project_esg_subscore?: ProjectEsgSubScore | null
}

export interface MatchFundsItem {
  offer_id: string
  fund_id: string
  fund_name: string
  intermediary_id?: string | null
  intermediary_name?: string | null
  project_score: number
  company_score: number
  project_score_breakdown: ProjectScoreBreakdown | Record<string, unknown>
  divergence_explanation?: string | null
  computed_at: string
  expires_at: string
}

export interface MatchFundsResponse {
  project_id: string
  project_name: string
  matches_count: number
  top_matches: MatchFundsItem[]
  no_match_reason?: string | null
  recompute_request_id?: string | null
}

export type DivergenceCategory =
  | 'convergent'
  | 'projet_fort'
  | 'entreprise_forte'
  | 'moyen'

export interface DivergenceExplanation {
  category: DivergenceCategory
  long_text: string
  short_text: string
}

/** Payload emis par le tool match_funds_for_project comme block visualisation F11. */
export interface ProjectMatchCardBlockPayload {
  title: string
  fund_name: string
  intermediary_name?: string | null
  project_score: number
  company_score: number
  divergence: string
  fund_url: string
  offer_id: string
  project_id: string
  sources: Array<{ source_id?: string | null; source_name: string; url?: string | null }>
  missing_criteria_top_3: Array<{
    key: string
    label_fr: string
    current_value?: number | string | null
    target_value?: number | string | null
  }>
  factor_status: FactorStatus
}

export interface MatchFundsRequestOptions {
  minScore?: number
  limit?: number
  forceRecompute?: boolean
}
