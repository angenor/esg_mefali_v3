// F09 — Composable admin /sources (CRUD + workflow 4-yeux + dependents).
import { useAuth } from '~/composables/useAuth'

export type VerificationStatus =
  | 'draft'
  | 'pending'
  | 'verified'
  | 'outdated'

export interface AdminSource {
  id: string
  url: string
  title: string
  publisher: string
  version: string
  date_publi: string
  page: number | null
  section: string | null
  verification_status: VerificationStatus
  captured_by: string
  verified_by: string | null
  verified_at: string | null
  outdated_reason: string | null
  created_at: string
  updated_at: string
}

export interface SourceListFilters {
  verification_status?: VerificationStatus
  publisher?: string
  q?: string
  page?: number
  page_size?: number
}

export interface PaginatedSources {
  items: AdminSource[]
  total: number
  page: number
  limit: number
}

export interface SourceCreatePayload {
  url: string
  title: string
  publisher: string
  version: string
  date_publi: string
  page?: number | null
  section?: string | null
}

export interface SourceUpdatePayload {
  url?: string
  title?: string
  publisher?: string
  version?: string
  date_publi?: string
  page?: number | null
  section?: string | null
  verification_status?: VerificationStatus
  outdated_reason?: string
}

export interface DependentsReport {
  indicators: string[]
  criteria: string[]
  formulas: string[]
  emission_factors: string[]
  simulation_factors: string[]
  skills: string[]
  total: number
}

export function useAdminSources() {
  const { apiFetch } = useAuth()

  async function listSources(
    filters: SourceListFilters = {},
  ): Promise<PaginatedSources> {
    const params = new URLSearchParams()
    if (filters.verification_status) {
      params.set('verification_status', filters.verification_status)
    }
    if (filters.publisher) params.set('publisher', filters.publisher)
    if (filters.q) params.set('q', filters.q)
    params.set('page', String(filters.page ?? 1))
    params.set('page_size', String(filters.page_size ?? 50))
    return await apiFetch<PaginatedSources>(
      `/admin/sources?${params.toString()}`,
    )
  }

  async function getSource(id: string): Promise<AdminSource> {
    return await apiFetch<AdminSource>(`/admin/sources/${id}`)
  }

  async function createSource(
    payload: SourceCreatePayload,
  ): Promise<AdminSource> {
    return await apiFetch<AdminSource>('/admin/sources', {
      method: 'POST',
      body: payload,
    })
  }

  async function updateSource(
    id: string,
    payload: SourceUpdatePayload,
  ): Promise<AdminSource> {
    return await apiFetch<AdminSource>(`/admin/sources/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  }

  async function verifySource(id: string): Promise<AdminSource> {
    return await updateSource(id, { verification_status: 'verified' })
  }

  async function markOutdated(
    id: string,
    reason: string,
  ): Promise<AdminSource> {
    return await updateSource(id, {
      verification_status: 'outdated',
      outdated_reason: reason,
    })
  }

  async function getDependents(id: string): Promise<DependentsReport> {
    return await apiFetch<DependentsReport>(`/admin/sources/${id}/dependents`)
  }

  async function deleteSource(
    id: string,
    force = false,
  ): Promise<{ deleted: boolean; force: boolean; blockers: string[] }> {
    return await apiFetch(
      `/admin/sources/${id}?force=${force ? 'true' : 'false'}`,
      { method: 'DELETE' },
    )
  }

  return {
    listSources,
    getSource,
    createSource,
    updateSource,
    verifySource,
    markOutdated,
    getDependents,
    deleteSource,
  }
}
