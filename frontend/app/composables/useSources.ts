import { useSourcesStore } from '~/stores/sources'
import { useAuth, SessionExpiredError } from '~/composables/useAuth'
import type { Source, SourceListItem, PaginatedSources } from '~/types/source'

export function useSources() {
  const store = useSourcesStore()
  const { apiFetch, handleAuthFailure } = useAuth()

  async function fetchSource(id: string, options?: { skipCache?: boolean }): Promise<Source | null> {
    if (!options?.skipCache) {
      const cached = store.getById(id)
      if (cached) return cached
    }
    store.setLoading(true)
    store.setError('')
    try {
      const data = await apiFetch<Source>(`/sources/${id}`)
      store.setSource(data)
      return data
    } catch (e) {
      if (e instanceof SessionExpiredError) {
        await handleAuthFailure()
        return null
      }
      const msg = e instanceof Error ? e.message : 'Erreur lors du chargement de la source'
      store.setError(msg)
      return null
    } finally {
      store.setLoading(false)
    }
  }

  async function searchSources(
    query: string,
    opts?: { publisher?: string; page?: number; pageSize?: number },
  ): Promise<PaginatedSources | null> {
    store.setLoading(true)
    store.setError('')
    try {
      const params = new URLSearchParams()
      if (query) params.set('search', query)
      if (opts?.publisher) params.set('publisher', opts.publisher)
      if (opts?.page) params.set('page', String(opts.page))
      if (opts?.pageSize) params.set('page_size', String(opts.pageSize))
      const qs = params.toString()
      const url = qs ? `/sources?${qs}` : '/sources'
      const data = await apiFetch<PaginatedSources>(url)
      return data
    } catch (e) {
      if (e instanceof SessionExpiredError) {
        await handleAuthFailure()
        return null
      }
      const msg = e instanceof Error ? e.message : 'Erreur lors de la recherche de sources'
      store.setError(msg)
      return null
    } finally {
      store.setLoading(false)
    }
  }

  function cacheSource(source: Source): void {
    store.setSource(source)
  }

  return {
    store,
    fetchSource,
    searchSources,
    cacheSource,
  }
}
