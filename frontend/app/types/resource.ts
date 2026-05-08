// F20 — Types miroir des schemas Pydantic Resource.

export type ResourceType =
  | 'guide'
  | 'template_doc'
  | 'video'
  | 'faq'
  | 'intermediary_guide'

export type ResourceLanguage = 'fr' | 'en'

export type ResourcePublicationStatus = 'draft' | 'published' | 'archived'

export type ResourceTargetAudience = 'pme_micro' | 'pme_small' | 'pme_medium'

export interface ResourceListItem {
  id: string
  type: ResourceType
  title: string
  slug: string
  description: string
  category: string[]
  target_audience: ResourceTargetAudience[]
  language: ResourceLanguage
  duration_seconds: number | null
  intermediary_id: string | null
  version: string
  publication_status: ResourcePublicationStatus
  view_count: number
  updated_at: string
}

export interface Resource extends ResourceListItem {
  content_md: string | null
  file_url: string | null
  video_url: string | null
  source_id: string
  valid_from: string | null
  valid_to: string | null
  created_at: string
}

export interface ResourceAdminDetail extends Resource {
  created_by: string
  verified_by: string | null
  superseded_by: string | null
}

export interface ResourceListResponse {
  items: ResourceListItem[]
  total: number
  page: number
  limit: number
}

export interface ResourceFiltersQuery {
  type?: ResourceType
  category?: string
  language?: ResourceLanguage
  intermediary_id?: string
  q?: string
  page?: number
  limit?: number
}

export interface ResourceCreatePayload {
  type: ResourceType
  title: string
  slug: string
  description: string
  content_md?: string | null
  file_url?: string | null
  video_url?: string | null
  duration_seconds?: number | null
  category: string[]
  target_audience: ResourceTargetAudience[]
  language: ResourceLanguage
  source_id: string
  intermediary_id?: string | null
}

export type ResourceUpdatePayload = Partial<
  Omit<ResourceCreatePayload, 'type' | 'slug' | 'intermediary_id'>
>

export interface ViewCountResponse {
  slug: string
  view_count: number
}

export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  guide: 'Guide',
  template_doc: 'Modèle',
  video: 'Vidéo',
  faq: 'FAQ',
  intermediary_guide: 'Fiche intermédiaire',
}

export const RESOURCE_TYPE_COLORS: Record<ResourceType, string> = {
  guide: 'emerald',
  template_doc: 'violet',
  video: 'rose',
  faq: 'amber',
  intermediary_guide: 'blue',
}
