// F09 PRIO 3 — Composable CRUD générique pour les sections catalogue admin.
//
// Factory typed qui produit les méthodes CRUD pour toute entité catalogue
// (fund, intermediary, offer, referential, indicator, criterion,
// emission_factor, simulation_factor).
//
// Les segments REST suivent la convention plurielle de l'API admin
// (`/admin/funds`, `/admin/emission-factors`, etc).
import { useAuth } from '~/composables/useAuth'

export type AdminCatalogEntity =
  | 'fund'
  | 'intermediary'
  | 'offer'
  | 'referential'
  | 'indicator'
  | 'criterion'
  | 'emission_factor'
  | 'simulation_factor'

const SEGMENT_MAP: Record<AdminCatalogEntity, string> = {
  fund: 'funds',
  intermediary: 'intermediaries',
  offer: 'offers',
  referential: 'referentials',
  indicator: 'indicators',
  criterion: 'criteria',
  emission_factor: 'emission-factors',
  simulation_factor: 'simulation-factors',
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

export interface ListFilters {
  publication_status?: 'draft' | 'published'
  q?: string
  page?: number
  page_size?: number
  [key: string]: unknown
}

function buildQuery(filters: ListFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    params.append(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function useAdminCatalog<T = Record<string, unknown>>(
  entity: AdminCatalogEntity,
) {
  const { apiFetch } = useAuth()
  const segment = SEGMENT_MAP[entity]

  async function listEntities(
    filters: ListFilters = {},
  ): Promise<PaginatedResult<T>> {
    return await apiFetch<PaginatedResult<T>>(
      `/admin/${segment}${buildQuery(filters)}`,
    )
  }

  async function getEntity(id: string): Promise<T> {
    return await apiFetch<T>(`/admin/${segment}/${id}`)
  }

  async function createEntity(payload: Partial<T>): Promise<T> {
    return await apiFetch<T>(`/admin/${segment}`, {
      method: 'POST',
      body: payload as Record<string, unknown>,
    })
  }

  async function updateEntity(id: string, payload: Partial<T>): Promise<T> {
    return await apiFetch<T>(`/admin/${segment}/${id}`, {
      method: 'PATCH',
      body: payload as Record<string, unknown>,
    })
  }

  async function deleteEntity(id: string): Promise<{ deleted: boolean }> {
    return await apiFetch<{ deleted: boolean }>(`/admin/${segment}/${id}`, {
      method: 'DELETE',
    })
  }

  return {
    listEntities,
    getEntity,
    createEntity,
    updateEntity,
    deleteEntity,
  }
}
