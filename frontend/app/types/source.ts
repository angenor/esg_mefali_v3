// Types TypeScript pour le module Source (F01)

export type VerificationStatus =
  | 'draft'
  | 'pending'
  | 'verified'
  | 'outdated'

export interface Source {
  id: string
  url: string
  title: string
  publisher: string
  version: string
  date_publi: string
  page: number | null
  section: string | null
  captured_at: string
  captured_by: string
  verified_by: string | null
  verification_status: VerificationStatus
  verified_at: string | null
  outdated_reason: string | null
  created_by_user_id: string
  created_at: string
  updated_at: string
}

export interface SourceListItem {
  id: string
  url: string
  title: string
  publisher: string
  version: string
  date_publi: string
  page: number | null
  section: string | null
  verification_status: VerificationStatus
}

export interface SourceCitation {
  id: string
  title: string
  publisher: string
  version: string
  url: string
  page: number | null
  section: string | null
  date_publi: string
}

export interface PaginatedSources {
  items: SourceListItem[]
  total: number
  page: number
  page_size: number
}
