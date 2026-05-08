/**
 * F15 — Types TypeScript miroirs des schémas Pydantic ``TemplateDossier``.
 */

export type TemplateLanguage = 'fr' | 'en'

export type TemplateInstrumentType =
  | 'subvention'
  | 'prêt_concessionnel'
  | 'equity'
  | 'blending'
  | 'mixte'

export type TemplateStatus = 'draft' | 'published'

export interface TemplateSection {
  key: string
  title: string
  instructions: string
  target_length: number
  tone?: string | null
  required: boolean
}

export interface TemplateRequiredDocument {
  title: string
  mandatory: boolean
  source_id?: string | null
  origin: 'fund' | 'intermediary' | 'both' | 'template'
}

export interface TemplateRead {
  id: string
  name: string
  offer_id: string | null
  instrument_type: TemplateInstrumentType
  language: TemplateLanguage
  sections: TemplateSection[]
  required_documents: TemplateRequiredDocument[]
  tone: string
  vocabulary_hints: Record<string, unknown> | null
  anti_patterns: unknown[] | null
  skill_id: string
  source_id: string
  version: string
  valid_from: string
  valid_to: string | null
  superseded_by: string | null
  status: TemplateStatus
  captured_by: string
  verified_by: string | null
  created_at: string
  updated_at: string
}

export interface TemplateListResponse {
  items: TemplateRead[]
  total: number
}

/** Labels FR/EN pour les selects UI. */
export const INSTRUMENT_LABELS: Record<TemplateInstrumentType, string> = {
  subvention: 'Subvention',
  'prêt_concessionnel': 'Prêt concessionnel',
  equity: 'Equity',
  blending: 'Blending',
  mixte: 'Mixte',
}

export const LANGUAGE_LABELS: Record<TemplateLanguage, string> = {
  fr: 'Français',
  en: 'Anglais',
}
