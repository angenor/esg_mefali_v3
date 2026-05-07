// Types TypeScript pour les Projets verts (F06)

import type { Money } from './currency'

export type ObjectiveEnvValue =
  | 'mitigation'
  | 'adaptation'
  | 'biodiversity'
  | 'circular_economy'
  | 'water'
  | 'renewable_energy'
  | 'sustainable_agriculture'
  | 'mixed'

export type ProjectMaturity =
  | 'ideation'
  | 'pre_feasibility'
  | 'pilot'
  | 'scale'
  | 'replication'

export type ProjectStatus =
  | 'draft'
  | 'seeking_funding'
  | 'funded'
  | 'in_execution'
  | 'closed'
  | 'cancelled'

export type FinancingStructure =
  | 'subvention'
  | 'pret_concessionnel'
  | 'equity'
  | 'blending'
  | 'mixte'

export type DocType =
  | 'feasibility_study'
  | 'business_plan'
  | 'impact_assessment'
  | 'support_letter'
  | 'other'

// Whitelists exposées pour l'UI
export const OBJECTIVE_ENV_VALUES: ObjectiveEnvValue[] = [
  'mitigation',
  'adaptation',
  'biodiversity',
  'circular_economy',
  'water',
  'renewable_energy',
  'sustainable_agriculture',
  'mixed',
]

export const MATURITY_VALUES: ProjectMaturity[] = [
  'ideation',
  'pre_feasibility',
  'pilot',
  'scale',
  'replication',
]

export const STATUS_VALUES: ProjectStatus[] = [
  'draft',
  'seeking_funding',
  'funded',
  'in_execution',
  'closed',
  'cancelled',
]

export const FINANCING_STRUCTURE_VALUES: FinancingStructure[] = [
  'subvention',
  'pret_concessionnel',
  'equity',
  'blending',
  'mixte',
]

// Libellés français pour l'UI
export const OBJECTIVE_ENV_LABELS: Record<ObjectiveEnvValue, string> = {
  mitigation: 'Atténuation',
  adaptation: 'Adaptation',
  biodiversity: 'Biodiversité',
  circular_economy: 'Économie circulaire',
  water: 'Eau',
  renewable_energy: 'Énergie renouvelable',
  sustainable_agriculture: 'Agriculture durable',
  mixed: 'Mixte',
}

export const MATURITY_LABELS: Record<ProjectMaturity, string> = {
  ideation: 'Idéation',
  pre_feasibility: 'Pré-faisabilité',
  pilot: 'Pilote',
  scale: 'Mise à l\'échelle',
  replication: 'Réplication',
}

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: 'Brouillon',
  seeking_funding: 'En recherche de financement',
  funded: 'Financé',
  in_execution: 'En exécution',
  closed: 'Clôturé',
  cancelled: 'Annulé',
}

export const FINANCING_STRUCTURE_LABELS: Record<FinancingStructure, string> = {
  subvention: 'Subvention',
  pret_concessionnel: 'Prêt concessionnel',
  equity: 'Equity',
  blending: 'Blending',
  mixte: 'Mixte',
}

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  feasibility_study: 'Étude de faisabilité',
  business_plan: 'Plan d\'affaires',
  impact_assessment: 'Étude d\'impact',
  support_letter: 'Lettre de soutien',
  other: 'Autre',
}

export interface ProjectDocumentRead {
  id: string
  project_id: string
  document_id: string
  doc_type: DocType
  created_at: string
}

export interface ProjectSummary {
  id: string
  name: string
  status: ProjectStatus
  maturity: ProjectMaturity | null
  objective_env: ObjectiveEnvValue[]
  target_amount: Money | null
  expected_impact_tco2e: string | null
  auto_generated: boolean
  applications_count: number
  created_at: string
}

export interface ProjectDetail {
  id: string
  account_id: string
  name: string
  description: string | null
  objective_env: ObjectiveEnvValue[]
  maturity: ProjectMaturity | null
  status: ProjectStatus
  target_amount: Money | null
  duration_months: number | null
  financing_structure: FinancingStructure | null
  expected_impact_tco2e: string | null
  expected_jobs_created: number | null
  expected_beneficiaries: number | null
  expected_hectares_restored: string | null
  expected_other_impacts: Record<string, unknown> | null
  location_country: string | null
  location_region: string | null
  auto_generated: boolean
  created_at: string
  updated_at: string
  project_documents: ProjectDocumentRead[]
  applications_count: number
}

export interface ProjectCreatePayload {
  name: string
  description?: string | null
  objective_env?: ObjectiveEnvValue[]
  maturity?: ProjectMaturity | null
  status?: ProjectStatus
  target_amount?: Money | null
  duration_months?: number | null
  financing_structure?: FinancingStructure | null
  expected_impact_tco2e?: string | number | null
  expected_jobs_created?: number | null
  expected_beneficiaries?: number | null
  expected_hectares_restored?: string | number | null
  expected_other_impacts?: Record<string, unknown> | null
  location_country?: string | null
  location_region?: string | null
}

export interface ProjectUpdatePayload {
  name?: string
  description?: string | null
  objective_env?: ObjectiveEnvValue[]
  maturity?: ProjectMaturity | null
  status?: ProjectStatus
  target_amount?: Money | null
  duration_months?: number | null
  financing_structure?: FinancingStructure | null
  expected_impact_tco2e?: string | number | null
  expected_jobs_created?: number | null
  expected_beneficiaries?: number | null
  expected_hectares_restored?: string | number | null
  expected_other_impacts?: Record<string, unknown> | null
  location_country?: string | null
  location_region?: string | null
}

export interface ProjectFilters {
  status?: ProjectStatus
  maturity?: ProjectMaturity
  objective_env?: ObjectiveEnvValue
  auto_generated?: boolean
  page?: number
  limit?: number
}

export interface ProjectListResponse {
  items: ProjectSummary[]
  total: number
  page: number
  limit: number
}

export interface BlockedApplication {
  application_id: string
  fund_name: string
  status: string
}

export interface DeleteResult {
  ok: boolean
  blocked_by: BlockedApplication[]
  hint: string | null
}

export interface ProjectApplicationSummary {
  application_id: string
  fund_id: string
  fund_name: string
  status: string
  intermediary_id: string | null
  intermediary_name: string | null
  target_type: string
  created_at: string
}

export interface DuplicateProjectRequest {
  new_name?: string
}

export interface LinkDocumentRequest {
  document_id: string
  doc_type: DocType
}
