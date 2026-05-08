// F20 — Composable admin Resources (CRUD + workflow draft/published).
import { useAuth } from '~/composables/useAuth'
import type {
  ResourceAdminDetail,
  ResourceCreatePayload,
  ResourceListResponse,
  ResourceUpdatePayload,
} from '~/types/resource'

export interface AdminResourceListFilters {
  type?: string
  status?: string
  language?: string
  q?: string
  page?: number
  limit?: number
}

export function useAdminResources() {
  const { apiFetch } = useAuth()

  async function adminList(
    filters: AdminResourceListFilters = {},
  ): Promise<ResourceListResponse> {
    const params = new URLSearchParams()
    if (filters.type) params.set('type', filters.type)
    if (filters.status) params.set('status', filters.status)
    if (filters.language) params.set('language', filters.language)
    if (filters.q) params.set('q', filters.q)
    params.set('page', String(filters.page ?? 1))
    params.set('limit', String(filters.limit ?? 20))
    return await apiFetch<ResourceListResponse>(
      `/admin/resources?${params.toString()}`,
    )
  }

  async function adminGet(id: string): Promise<ResourceAdminDetail> {
    return await apiFetch<ResourceAdminDetail>(`/admin/resources/${id}`)
  }

  async function adminCreate(
    payload: ResourceCreatePayload,
  ): Promise<ResourceAdminDetail> {
    return await apiFetch<ResourceAdminDetail>('/admin/resources', {
      method: 'POST',
      body: payload,
    })
  }

  async function adminUpdate(
    id: string,
    payload: ResourceUpdatePayload,
  ): Promise<ResourceAdminDetail> {
    return await apiFetch<ResourceAdminDetail>(`/admin/resources/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  }

  async function adminPublish(id: string): Promise<ResourceAdminDetail> {
    return await apiFetch<ResourceAdminDetail>(
      `/admin/resources/${id}/publish`,
      { method: 'POST' },
    )
  }

  async function adminArchive(id: string): Promise<ResourceAdminDetail> {
    return await apiFetch<ResourceAdminDetail>(
      `/admin/resources/${id}/archive`,
      { method: 'POST' },
    )
  }

  async function adminDelete(id: string): Promise<void> {
    await apiFetch<void>(`/admin/resources/${id}`, { method: 'DELETE' })
  }

  return {
    adminList,
    adminGet,
    adminCreate,
    adminUpdate,
    adminPublish,
    adminArchive,
    adminDelete,
  }
}
