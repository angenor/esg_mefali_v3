/**
 * F18 — Types Mobile Money + Photos IA + Données publiques.
 *
 * Miroir des schémas Pydantic backend (`app/modules/credit/alternative/schemas.py`).
 */

export type Provider = 'wave' | 'orange_money' | 'mtn_momo' | 'moov_money'
export type ImportStatus = 'pending' | 'completed' | 'failed'
export type Direction = 'incoming' | 'outgoing'

export interface MobileMoneyImportRead {
  id: string
  provider: Provider
  file_path: string
  imported_rows: number
  rejected_rows: number
  status: ImportStatus
  error_summary?: Record<string, unknown> | null
  created_at: string
}

export interface TopCounterparty {
  counterparty_hash: string
  total_amount: string
  transaction_count: number
}

export interface MobileMoneyKpis {
  monthly_volume_avg: string
  monthly_volume_stddev: string
  regularity_30d: number
  avg_balance_estimate: string
  growth_12m: number
  top_counterparties: TopCounterparty[]
  transaction_count: number
  period_start?: string | null
  period_end?: string | null
}

export interface MobileMoneyAnalysisRead {
  id: string
  methodology_version: string
  kpis: MobileMoneyKpis
  consent_active: boolean
  computed_at: string
}

export interface MobileMoneyUploadResponse {
  import_id: string
  imported_rows: number
  rejected_rows: number
  status: ImportStatus
  error_summary?: Record<string, unknown> | null
  analysis: MobileMoneyAnalysisRead | null
}

export type PhotoQualityStatus = 'pending' | 'ok' | 'low_quality' | 'failed'

export interface PhotoAnalysisScores {
  material: number
  organization: number
  hygiene: number
  env_practices: number
  activity: number
}

export interface PhotoAnalysisResult {
  scores: PhotoAnalysisScores
  observations: string[]
  red_flags: string[]
  green_signals: string[]
}

export interface CreditPhotoRead {
  id: string
  file_path: string
  captured_at?: string | null
  analyzed_at?: string | null
  analysis_result?: PhotoAnalysisResult | null
  quality_status: PhotoQualityStatus
  methodology_version?: string | null
  created_at: string
}

export type SourceType =
  | 'google_my_business'
  | 'facebook_page'
  | 'google_reviews'
  | 'trustpilot'
  | 'green_program'
  | 'other'

export type PublicDataStatus = 'declared' | 'evidence_attached' | 'pending_review'

export interface PublicDataSourceCreate {
  source_type: SourceType
  url: string
  declared_rating?: number | null
  declared_reviews_count?: number | null
  program_label?: string | null
}

export interface PublicDataSourceRead {
  id: string
  source_type: SourceType
  url: string
  declared_rating?: string | null
  declared_reviews_count?: number | null
  program_label?: string | null
  evidence_path?: string | null
  status: PublicDataStatus
  created_at: string
}

export interface MethodologyFactor {
  id: string
  version: string
  name: string
  category: string
  weight: string
  description: string
  source_id: string
  publication_status: 'draft' | 'published'
}

export interface MethodologyResponse {
  version: string
  factors: MethodologyFactor[]
  total_weight: string
}

export type AlternativeConsentType =
  | 'mobile_money_analysis'
  | 'photos_ia_analysis'
  | 'public_data_analysis'
