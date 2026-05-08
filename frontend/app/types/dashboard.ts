// Types TypeScript pour le module Dashboard

// F21 — Référence Source F01 attachée à un score (US4).
export interface ScoreSourceRef {
  source_id: string
  title: string
  publisher: string | null
  version: string | null
  url: string | null
}

export interface EsgSummary {
  score: number
  grade: string
  trend: string | null
  last_assessment_date: string | null
  pillar_scores: Record<string, number>
  // F21 — Sources F01 cliquables.
  sources?: ScoreSourceRef[]
}

export interface CarbonSummary {
  total_tco2e: number
  year: number
  variation_percent: number | null
  top_category: string | null
  categories: Record<string, number>
  sources?: ScoreSourceRef[]
}

export interface CreditSummary {
  score: number
  grade: string
  last_calculated: string | null
  sources?: ScoreSourceRef[]
}

// F21 (US1) — Card de candidature par Offre.
export interface ApplicationCard {
  application_id: string
  offer_id: string | null
  fund_name: string
  intermediary_name: string  // « Accès direct » si direct
  fund_logo_url: string | null
  intermediary_logo_url: string | null
  status: string
  current_step: string  // libellé FR pour humains
  next_deadline: string | null
  next_reminder: string | null
  last_activity_at: string
}

// F21 (US3) — Intermédiaire actif sur la carte UEMOA.
export interface ActiveIntermediary {
  intermediary_id: string
  name: string
  type: string  // gov_agency / dfi / commercial_bank / mfi / ngo / consulting
  country: string
  lat: number
  lon: number
  is_fallback_capital: boolean
  accreditations: string[]
  applications_count: number
}

export interface FinancingSummary {
  recommended_funds_count: number
  active_applications_count: number
  application_statuses: Record<string, number>
  next_intermediary_action: {
    title: string
    due_date: string
    intermediary_name: string
  } | null
  has_intermediary_paths: boolean
  // F21
  applications_by_offer?: ApplicationCard[]
  active_intermediaries?: ActiveIntermediary[]
}

export interface NextAction {
  id: string
  title: string
  category: string
  due_date: string | null
  status: string
  intermediary_name: string | null
  intermediary_address: string | null
}

export interface ActivityEvent {
  type: string
  title: string
  description: string | null
  timestamp: string
  related_entity_type: string | null
  related_entity_id: string | null
}

export interface BadgeSummary {
  badge_type: string
  unlocked_at: string
}

export interface DashboardSummary {
  esg: EsgSummary | null
  carbon: CarbonSummary | null
  credit: CreditSummary | null
  financing: FinancingSummary
  next_actions: NextAction[]
  recent_activity: ActivityEvent[]
  badges: BadgeSummary[]
}
