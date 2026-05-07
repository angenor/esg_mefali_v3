// F23 — Types Skills (Playbooks Métier).

export type SkillDomain =
  | 'diagnostic_esg'
  | 'scoring_referentiel'
  | 'carbon_calc'
  | 'dossier'
  | 'intermediaire'
  | 'attestation'
  | 'credit_score'

export type SkillStatus = 'draft' | 'published'

export interface ActivationRules {
  page_slugs?: string[]
  intent_keywords?: string[]
  active_module?: string[]
  offer_id?: string | null
  fund_id?: string | null
  intermediary_id?: string | null
}

export interface GoldenContext {
  current_page?: string | null
  active_module?: string | null
  user_profile?: Record<string, unknown> | null
  offer_id?: string | null
  fund_id?: string | null
  intermediary_id?: string | null
}

export interface GoldenExpected {
  tool_called: string | string[]
  payload_contains?: Record<string, unknown> | null
  fallback_acceptable?: boolean
}

export interface GoldenExample {
  id: string
  category: SkillDomain
  context: GoldenContext
  user_message: string
  expected: GoldenExpected
  tags?: string[]
}

export interface SkillRead {
  id: string
  name: string
  domain: SkillDomain | string
  version: string
  prompt_expert: string
  procedure: string
  tool_whitelist: string[]
  sources: string[]
  activation_rules: ActivationRules
  golden_examples: GoldenExample[]
  status: SkillStatus | string
  created_by: string
  verified_by: string | null
  valid_from: string
  valid_to: string | null
  superseded_by: string | null
  created_at: string
  updated_at: string
}

export interface SkillCreate {
  name: string
  domain: SkillDomain
  prompt_expert: string
  procedure: string
  tool_whitelist: string[]
  sources: string[]
  activation_rules: ActivationRules
  golden_examples: GoldenExample[]
}

export interface SkillUpdate {
  domain?: SkillDomain
  prompt_expert?: string
  procedure?: string
  tool_whitelist?: string[]
  sources?: string[]
  activation_rules?: ActivationRules
  golden_examples?: GoldenExample[]
}

export interface SkillListItem {
  id: string
  name: string
  domain: string
  version: string
  status: string
  valid_from: string
  valid_to: string | null
  created_at: string
  updated_at: string
}

export interface SkillListResponse {
  items: SkillListItem[]
  total: number
  page: number
  limit: number
}

export interface FailedCase {
  case_id: string
  expected_tool: string | string[]
  actual_tool: string | null
  payload_diff: Record<string, unknown> | null
  latency_ms: number
  error: string | null
}

export interface SkillEvalReport {
  skill_id: string
  run_id: string
  started_at: string
  completed_at: string
  duration_seconds: number
  total_cases: number
  passed: number
  failed: number
  success_rate: number
  threshold: number
  gate_passed: boolean
  failed_cases: FailedCase[]
}

export interface SkillPublishResponse {
  skill: SkillRead
  eval_report: SkillEvalReport
}

export interface SkillListFilters {
  domain?: string
  status?: SkillStatus
  q?: string
  page?: number
  limit?: number
}
