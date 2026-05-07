// Types TypeScript pour le module Calculateur d'Empreinte Carbone

export type CarbonStatus = 'in_progress' | 'completed'
// F17 — ajout de 'purchases' (achats matieres premieres).
export type EmissionCategory = 'energy' | 'transport' | 'waste' | 'industrial' | 'agriculture' | 'purchases'
export type BenchmarkPosition = 'well_below_average' | 'below_average' | 'average' | 'above_average' | 'well_above_average' | 'unknown'

export interface CarbonEmissionEntry {
  id: string
  category: EmissionCategory
  subcategory: string
  quantity: number
  unit: string
  emission_factor: number
  emissions_tco2e: number
  source_description: string | null
  // F17 — sourcage et snapshot facteur (optionnels pour anciennes entries).
  source_id?: string | null
  factor_id?: string | null
  created_at: string
}

// F17 — Action conforme au schema canonique avec source_id + unsourced.
export interface ReductionPlanActionV2 {
  title: string
  description: string
  estimated_reduction_tco2e: number
  cost_estimate_fcfa: number | null
  timeline: string
  source_id: string | null
  unsourced: boolean
}

// Action legacy (avant F17) — conservee 2 sprints pour retro-compatibilite.
export interface ReductionAction {
  action: string
  reduction_tco2e: number
  savings_fcfa: number
  timeline: string
}

// ReductionPlan accepte les 2 schemas (F17 actions[] OU legacy quick_wins/long_term).
export interface ReductionPlan {
  // Nouveau schema F17.
  actions?: ReductionPlanActionV2[]
  // Schema legacy.
  quick_wins?: ReductionAction[]
  long_term?: ReductionAction[]
}

export interface CarbonAssessment {
  id: string
  user_id: string
  conversation_id: string | null
  year: number
  status: CarbonStatus
  sector: string | null
  total_emissions_tco2e: number | null
  completed_categories: EmissionCategory[]
  reduction_plan: ReductionPlan | null
  entries: CarbonEmissionEntry[]
  created_at: string
  updated_at: string
}

export interface CarbonAssessmentSummary {
  id: string
  year: number
  status: CarbonStatus
  total_emissions_tco2e: number | null
  completed_categories: EmissionCategory[]
  created_at: string
  updated_at: string
}

export interface CarbonAssessmentList {
  items: CarbonAssessmentSummary[]
  total: number
  page: number
  limit: number
}

export interface CategoryBreakdown {
  emissions_tco2e: number
  percentage: number
  entries_count: number
}

export interface Equivalence {
  label: string
  value: number
}

export interface SectorBenchmark {
  sector: string
  sector_average_tco2e: number | null
  position: BenchmarkPosition
  percentile: number | null
}

export interface CarbonSummary {
  assessment_id: string
  year: number
  status: CarbonStatus
  total_emissions_tco2e: number
  by_category: Record<EmissionCategory, CategoryBreakdown>
  equivalences: Equivalence[]
  reduction_plan: ReductionPlan | null
  sector_benchmark: SectorBenchmark | null
}

export interface AddEntriesRequest {
  entries: Omit<CarbonEmissionEntry, 'id' | 'created_at'>[]
  mark_category_complete?: EmissionCategory
}

export interface AddEntriesResponse {
  entries_added: number
  total_emissions_tco2e: number
  completed_categories: EmissionCategory[]
}

export interface BenchmarkResponse {
  sector: string
  average_emissions_tco2e: number
  median_emissions_tco2e: number
  by_category: Record<string, number>
  sample_size: string
  source: string
  fallback_sector?: string
}
