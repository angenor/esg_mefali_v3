// Types TypeScript pour le module ESG

export type ESGPillar = 'environment' | 'social' | 'governance'
export type ESGStatus = 'draft' | 'in_progress' | 'completed'
export type ImpactLevel = 'high' | 'medium' | 'low'
export type BenchmarkPosition = 'above_average' | 'average' | 'below_average'

export interface CriteriaScoreDetail {
  score: number
  justification: string
  sources: string[]
}

export interface PillarWeights {
  [criterionCode: string]: number
}

export interface PillarDetail {
  raw_score: number
  weighted_score: number
  weights_applied: PillarWeights
}

export interface AssessmentData {
  criteria_scores: Record<string, CriteriaScoreDetail>
  pillar_details: Record<ESGPillar, PillarDetail>
}

export interface ESGRecommendation {
  priority: number
  criteria_code: string
  pillar: ESGPillar
  title: string
  description: string
  impact: ImpactLevel
  effort: ImpactLevel
  timeline: string
}

export interface ESGStrength {
  criteria_code: string
  pillar: ESGPillar
  title: string
  description: string
  score: number
}

export interface ESGGap {
  criteria_code: string
  pillar: ESGPillar
  title: string
  score: number
}

export interface SectorBenchmark {
  sector: string
  averages: {
    environment: number
    social: number
    governance: number
    overall: number
  }
  position: BenchmarkPosition
  percentile: number
}

export interface ESGAssessment {
  id: string
  user_id: string
  conversation_id: string | null
  version: number
  status: ESGStatus
  sector: string
  overall_score: number | null
  environment_score: number | null
  social_score: number | null
  governance_score: number | null
  assessment_data: AssessmentData | null
  recommendations: ESGRecommendation[] | null
  strengths: ESGStrength[] | null
  gaps: ESGGap[] | null
  sector_benchmark: SectorBenchmark | null
  current_pillar: ESGPillar | null
  evaluated_criteria: string[]
  created_at: string
  updated_at: string
}

export interface ESGAssessmentSummary {
  id: string
  version: number
  status: ESGStatus
  sector: string
  overall_score: number | null
  environment_score: number | null
  social_score: number | null
  governance_score: number | null
  created_at: string
}

export interface ESGAssessmentList {
  data: ESGAssessmentSummary[]
  total: number
  page: number
  limit: number
}

export interface CriteriaScoreResponse {
  code: string
  label: string
  score: number
  max: number
  weight: number
}

export interface PillarScoreResponse {
  score: number
  criteria: CriteriaScoreResponse[]
}

export interface ScoreResponse {
  assessment_id: string
  status: ESGStatus
  overall_score: number
  color: string
  pillars: Record<ESGPillar, PillarScoreResponse>
  strengths_count: number
  gaps_count: number
  recommendations_count: number
}

export interface BenchmarkResponse {
  sector: string
  sector_label: string
  sample_size: string
  averages: {
    environment: number
    social: number
    governance: number
    overall: number
  }
  top_criteria: string[]
  weak_criteria: string[]
}

export interface EvaluateResponse {
  assessment_id: string
  status: ESGStatus
  current_pillar: ESGPillar | null
  evaluated_criteria: string[]
  progress_percent: number
  total_criteria: number
}

// ----------------------------------------------------------------------
// F13 — Scoring multi-référentiels
// ----------------------------------------------------------------------

export type ComputedBy = 'manual' | 'llm' | 'auto'
export type MissingReason = 'non_renseigne' | 'invalide' | 'hors_scope'

export interface PillarScore {
  score: number
  weight: number
  criteria_count: number
  /** Nombre de critères renseignés (clé JSON encode UTF-8 conservée). */
  criteria_renseignés?: number
  criteria_renseignes?: number
}

export interface CoveredCriterion {
  indicator_id: string
  indicator_code: string
  score: number
  weight: number
  source_id: string | null
}

export interface MissingCriterion {
  indicator_id: string
  indicator_code: string
  reason: MissingReason
  source_id: string | null
  suggestion: string | null
}

export interface ReferentialScore {
  id: string
  assessment_id: string
  referential_id: string
  referential_code: string
  referential_name: string
  referential_version: string
  overall_score: number | null
  pillar_scores: Record<string, PillarScore>
  coverage_rate: number
  covered_criteria: CoveredCriterion[]
  missing_criteria: MissingCriterion[]
  gap_to_threshold: number | null
  eligibility: boolean | null
  computed_at: string
  computed_by: ComputedBy
  computed_request_id: string | null
  is_fallback: boolean
}

export interface ComparisonResult {
  scores: ReferentialScore[]
  gaps: Record<string, number>
  divergent_criteria: Record<string, CoveredCriterion[]>
  summary_text: string | null
}

export interface RecomputeRequestResponse {
  status: string
  recompute_request_id: string
  referentials_to_recompute: string[]
  estimated_duration_seconds: number
}

export interface BottleneckInfo {
  bottleneck_referential_code: string
  bottleneck_referential_name: string
  bottleneck_score: number
  other_referential_code: string
  other_referential_score: number
  gap: number
  eligibility_min: boolean
  top_3_critical_indicators: string[]
}

export interface DualReferentialResponse {
  fund_score: ReferentialScore
  intermediary_score: ReferentialScore | null
  bottleneck: BottleneckInfo | null
  is_dual_view: boolean
}

export interface ReferentialOption {
  code: string
  name: string
  version: string
}

export interface GenerateReportRequest {
  referentials?: string[]
  include_appendix_sources?: boolean
  format?: 'pdf'
}
