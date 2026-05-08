// F09 PRIO 3 — Composable admin /companies (read + actions).
import { useAuth } from '~/composables/useAuth'

export interface AdminAccountSummary {
  id: string
  name: string
  is_active: boolean
  plan: string
  created_at: string
  deletion_scheduled_at: string | null
}

export interface AdminCompanyOverview {
  account: AdminAccountSummary & {
    deleted_at: string | null
  }
  company_profile: Record<string, unknown> | null
  users: Array<Record<string, unknown>>
  projects: Array<Record<string, unknown>>
  applications: Array<Record<string, unknown>>
  scores: {
    esg_assessments_count: number
    carbon_assessments_count: number
    credit_scores_count: number
  }
  attestations: Array<Record<string, unknown>>
}

export interface ListAccountsFilters {
  is_active?: boolean
  q?: string
  page?: number
  page_size?: number
}

function toQueryString(params: ListAccountsFilters): string {
  const usp = new URLSearchParams()
  if (params.is_active !== undefined) usp.set('is_active', String(params.is_active))
  if (params.q) usp.set('q', params.q)
  if (params.page) usp.set('page', String(params.page))
  if (params.page_size) usp.set('page_size', String(params.page_size))
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export function useAdminCompanies() {
  const { apiFetch } = useAuth()

  async function listCompanies(
    filters: ListAccountsFilters = {},
  ): Promise<{
    items: AdminAccountSummary[]
    total: number
    page: number
    limit: number
  }> {
    return await apiFetch(`/admin/companies${toQueryString(filters)}`)
  }

  async function getCompanyOverview(
    accountId: string,
  ): Promise<AdminCompanyOverview> {
    return await apiFetch<AdminCompanyOverview>(`/admin/companies/${accountId}`)
  }

  return { listCompanies, getCompanyOverview }
}
