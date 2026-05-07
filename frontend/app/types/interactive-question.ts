// Types pour les widgets interactifs F18 (QCU/QCM) + F10 (9 nouveaux widgets)

// ─── Enum élargi (4 F18 + 9 F10) ────────────────────────────────────────

export type InteractiveQuestionType =
  // F18 — widgets QCU/QCM
  | 'qcu'
  | 'qcm'
  | 'qcu_justification'
  | 'qcm_justification'
  // F10 — 9 nouveaux widgets bottom sheet
  | 'yes_no'
  | 'select'
  | 'number'
  | 'date'
  | 'date_range'
  | 'rating'
  | 'file_upload'
  | 'form'
  | 'summary_card'

export type InteractiveQuestionState =
  | 'pending'
  | 'answered'
  | 'abandoned'
  | 'expired'

// Devise supportée par ask_number et show_form (champ money)
export type SupportedCurrency = 'XOF' | 'EUR' | 'USD' | 'CDF'

// ─── F18 — Option d'un QCU/QCM ─────────────────────────────────────────

export interface InteractiveOption {
  id: string
  label: string
  emoji?: string
  description?: string
}

// ─── F10 — Payloads par variante ───────────────────────────────────────

export interface YesNoPayload {
  question_type: 'yes_no'
  confirm_label: string
  deny_label: string
  destructive: boolean
}

export interface SelectOption {
  id: string
  label: string
  sublabel?: string | null
  group?: string | null
}

export interface SelectPayload {
  question_type: 'select'
  options: SelectOption[]
  min_selections: number
  max_selections: number
  allow_other: boolean
}

export interface NumberPayload {
  question_type: 'number'
  unit: string
  min?: number | null
  max?: number | null
  step: number
  currency?: SupportedCurrency | null
  default?: number | null
}

export interface DatePayload {
  question_type: 'date'
  min?: string | null
  max?: string | null
  default?: string | null
}

export interface DateRangePayload {
  question_type: 'date_range'
  min?: string | null
  max?: string | null
}

export interface RatingPayload {
  question_type: 'rating'
  scale: number
  labels?: string[] | null
}

export interface FileUploadPayload {
  question_type: 'file_upload'
  accept: string[]
  max_size_mb: number
  multi: boolean
  doc_type_hint?: string | null
}

export type FormFieldType =
  | 'text'
  | 'number'
  | 'select'
  | 'date'
  | 'textarea'
  | 'money'

export interface FormFieldValidation {
  min_length?: number | null
  max_length?: number | null
  min?: number | null
  max?: number | null
  pattern?: string | null
  options?: SelectOption[] | null
}

export interface FormField {
  name: string
  label: string
  type: FormFieldType
  required: boolean
  placeholder?: string | null
  default?: string | number | boolean | null
  validation?: FormFieldValidation | null
}

export interface FormPayload {
  question_type: 'form'
  title: string
  fields: FormField[]
  submit_label: string
}

export interface SummaryCardItem {
  label: string
  value: string | number | boolean | null
  editable: boolean
}

export interface SummaryCardPayload {
  question_type: 'summary_card'
  title: string
  items: SummaryCardItem[]
  confirm_label: string
  correct_label: string
}

export type InteractiveQuestionPayload =
  | YesNoPayload
  | SelectPayload
  | NumberPayload
  | DatePayload
  | DateRangePayload
  | RatingPayload
  | FileUploadPayload
  | FormPayload
  | SummaryCardPayload

// ─── F10 — Réponses structurées par variante ───────────────────────────

export interface YesNoResponse {
  question_type: 'yes_no'
  value: boolean
  label: string
}

export interface SelectResponse {
  question_type: 'select'
  selected: SelectOption[]
  other_value?: string | null
}

export interface NumberResponse {
  question_type: 'number'
  value: number
  currency?: SupportedCurrency | null
  formatted: string
}

export interface DateResponse {
  question_type: 'date'
  value: string
  label: string
}

export interface DateRangeResponse {
  question_type: 'date_range'
  from: string
  to: string
  label: string
}

export interface RatingResponse {
  question_type: 'rating'
  value: number
  scale: number
  label?: string | null
}

export interface UploadedDocument {
  document_id: string
  filename: string
  size: number
  mime_type: string
}

export interface FileUploadResponse {
  question_type: 'file_upload'
  documents: UploadedDocument[]
}

export interface FormResponse {
  question_type: 'form'
  values: Record<string, string | number | boolean | null>
  summary_label: string
}

export interface SummaryCardModification {
  field: string
  before: string | number | boolean | null
  after: string | number | boolean | null
}

export interface SummaryCardResponse {
  question_type: 'summary_card'
  validated: boolean
  modifications: SummaryCardModification[]
}

export type InteractiveQuestionResponsePayload =
  | YesNoResponse
  | SelectResponse
  | NumberResponse
  | DateResponse
  | DateRangeResponse
  | RatingResponse
  | FileUploadResponse
  | FormResponse
  | SummaryCardResponse

// ─── Évènements SSE backend → frontend ────────────────────────────────

export interface InteractiveQuestionEvent {
  type: 'interactive_question'
  id: string
  conversation_id: string
  question_type: InteractiveQuestionType
  prompt: string
  module: string
  created_at: string
  // F18 — champs racine pour les 4 widgets QCU/QCM
  options?: InteractiveOption[]
  min_selections?: number
  max_selections?: number
  requires_justification?: boolean
  justification_prompt?: string | null
  // F10 — payload variante-spécifique pour les 9 nouveaux widgets
  payload?: InteractiveQuestionPayload
}

export interface InteractiveQuestionResolvedEvent {
  type: 'interactive_question_resolved'
  id: string
  state: InteractiveQuestionState
  response_values: string[] | null
  response_justification: string | null
  answered_at: string
  // F10 — payload structuré (au-delà de response_values)
  response_payload?: InteractiveQuestionResponsePayload | null
}

// ─── État d'une question dans le frontend ─────────────────────────────

export interface InteractiveQuestion extends Omit<InteractiveQuestionEvent, 'type'> {
  state: InteractiveQuestionState
  response_values: string[] | null
  response_justification: string | null
  response_payload?: InteractiveQuestionResponsePayload | null
  answered_at: string | null
}

// Réponse F18 (legacy QCU/QCM)
export interface InteractiveQuestionAnswer {
  values: string[]
  justification?: string
}

// F10 — Réponse étendue avec payload structuré
export interface InteractiveQuestionAnswerExt {
  values: string[]
  justification?: string
  response_payload?: InteractiveQuestionResponsePayload
  /** Message texte canonique à afficher dans le fil utilisateur (« ✓ Oui », etc.). */
  display_text?: string
}
