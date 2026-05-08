// F20 — Composable public Resources (lecture).
import type {
  Resource,
  ResourceFiltersQuery,
  ResourceListResponse,
  ViewCountResponse,
} from '~/types/resource'

interface RuntimeConfigPublic {
  public: { apiBase?: string }
}

function getApiBase(): string {
  const config = useRuntimeConfig() as unknown as RuntimeConfigPublic
  return config.public?.apiBase ?? 'http://localhost:8000/api'
}

function buildQuery(filters: ResourceFiltersQuery): string {
  const params = new URLSearchParams()
  if (filters.type) params.set('type', filters.type)
  if (filters.category) params.set('category', filters.category)
  if (filters.language) params.set('language', filters.language)
  if (filters.intermediary_id) params.set('intermediary_id', filters.intermediary_id)
  if (filters.q) params.set('q', filters.q)
  params.set('page', String(filters.page ?? 1))
  params.set('limit', String(filters.limit ?? 20))
  return params.toString()
}

export function useResources() {
  async function listResources(
    filters: ResourceFiltersQuery = {},
  ): Promise<ResourceListResponse> {
    const url = `${getApiBase()}/resources?${buildQuery(filters)}`
    return await $fetch<ResourceListResponse>(url)
  }

  async function getResource(slug: string): Promise<Resource> {
    return await $fetch<Resource>(`${getApiBase()}/resources/${slug}`)
  }

  async function incrementView(slug: string): Promise<ViewCountResponse> {
    return await $fetch<ViewCountResponse>(
      `${getApiBase()}/resources/${slug}/view`,
      { method: 'POST' },
    )
  }

  async function getIntermediaryGuide(intermediaryId: string): Promise<Resource> {
    return await $fetch<Resource>(
      `${getApiBase()}/intermediaries/${intermediaryId}/guide`,
    )
  }

  return { listResources, getResource, incrementView, getIntermediaryGuide }
}
