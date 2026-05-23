/**
 * F047 — Types TypeScript miroir des DTO Pydantic
 * (backend/app/modules/esg/project_schemas.py).
 */

export type ProjectEsgState = 'draft' | 'finalized'

export type ResponseType =
  | 'qcu'
  | 'qcm'
  | 'qcu_justification'
  | 'qcm_justification'
  | 'numeric'
  | 'money'
  | 'free_text'

export interface ProjectEsgAssessmentRead {
  id: string
  account_id: string
  project_id: string
  referential_id: string
  referential_version: string
  state: ProjectEsgState
  score: number | null
  pillar_scores: Record<string, number>
  covered_criteria: string[]
  missing_criteria: string[]
  coverage_rate: string | null // Decimal sérialisé
  snapshot_data: Record<string, unknown> | null
  finalized_at: string | null
  superseded_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface ProjectEsgCriterionResponseRead {
  id: string
  assessment_id: string
  criterion_id: string
  response_type: ResponseType
  response_value: Record<string, unknown>
  normalized_score: string
  source_id: string | null
  unsourced: boolean
  created_at: string
  updated_at: string
}

export interface ProjectEsgAssessmentDetail extends ProjectEsgAssessmentRead {
  responses: ProjectEsgCriterionResponseRead[]
}

export interface ProjectEsgAssessmentCreatePayload {
  referential_id: string
}

export interface ProjectEsgCriterionResponseSavePayload {
  criterion_id: string
  response_type: ResponseType
  response_value: Record<string, unknown>
  source_id?: string | null
  unsourced?: boolean
}

export interface CriterionRef {
  id: string
  code: string
  label: string
}

export interface ProjectEsgAssessmentFinalizeResult {
  assessment: ProjectEsgAssessmentRead
  score: number
  pillar_scores: Record<string, number>
  missing_criteria: CriterionRef[]
  coverage_rate: string
}

export interface EsgReferentialRef {
  id: string
  code: 'ifc_ps' | 'gcf_ess' | 'boad_ess' | string
  label: string
  description: string
}
