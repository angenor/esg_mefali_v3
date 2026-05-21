/**
 * Types miroirs (TypeScript strict) des schemas Pydantic de
 * `backend/app/schemas/admin_catalog.py`. Toute modification côté backend
 * doit être propagée ici sans dérive de structure.
 */

import type { Money } from './currency'

export type CatalogTab = 'funds' | 'intermediaries' | 'offers' | 'fund_intermediaries'

export type CatalogPublicationStatus = 'draft' | 'published' | 'deprecated'

export type FundIntermediaryStatus = 'active' | 'expired' | 'all'

export type SourceVerificationStatus = 'draft' | 'pending' | 'verified' | 'outdated'

export interface CatalogTabCounts {
  total: number
  by_status: Record<string, number>
}

export interface CatalogFundIntermediariesCounts {
  total: number
  active: number
  expired: number
}

export interface CatalogSummary {
  funds: CatalogTabCounts
  intermediaries: CatalogTabCounts
  offers: CatalogTabCounts
  fund_intermediaries: CatalogFundIntermediariesCounts
}

export interface SourceRef {
  id: string
  title: string | null
  url: string | null
  status: SourceVerificationStatus
}

export interface CatalogRowBase {
  id: string
  name: string
  publication_status: string | null
  version: string | null
  updated_at: string
  has_incoherence: boolean
}

export interface FundRow extends CatalogRowBase {
  fund_type: string | null
  organization: string | null
  superseded_by: string | null
}

export interface IntermediaryRow extends CatalogRowBase {
  intermediary_type: string | null
  organization_type: string | null
  country: string | null
  superseded_by: string | null
}

export interface OfferRow extends CatalogRowBase {
  fund_id: string
  intermediary_id: string
  fund_name: string | null
  intermediary_name: string | null
  superseded_by: string | null
}

export interface FundIntermediaryRow {
  id: string
  fund_id: string
  fund_name: string
  intermediary_id: string
  intermediary_name: string
  accredited_from: string | null
  accredited_to: string | null
  is_active: boolean
  max_amount_per_fund_money: Money | null
  has_source: boolean
  has_incoherence: boolean
  updated_at: string
}

export interface FundIntermediaryDetail extends FundIntermediaryRow {
  accreditation_source: SourceRef | null
  fund_link: string
  intermediary_link: string
  created_at: string
  version?: string | null
  superseded_by?: string | null
}

export interface PaginatedListResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  paginated: boolean
}

export type CatalogRow = FundRow | IntermediaryRow | OfferRow | FundIntermediaryRow

export interface CatalogFilters {
  q: string
  publication_status: CatalogPublicationStatus | null
  status: FundIntermediaryStatus
  fund_type: string | null
  sort: string
  page: number
  page_size: number
}
