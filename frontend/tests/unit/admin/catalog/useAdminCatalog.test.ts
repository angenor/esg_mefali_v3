/**
 * F25 — Tests du composable `useAdminCatalog`.
 *
 * Couvre :
 * - `buildQueryString` (paramètres conformes aux contrats backend),
 * - `fetchSummary` (succès + erreur 403),
 * - `fetchTab` (normalisation des deux formats backend),
 * - debounce 300 ms sur `setSearch`,
 * - redirection sur 403.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ─── Mocks Nuxt / store auth ───
const mockRouterPush = vi.fn()
vi.stubGlobal('useRouter', () => ({ push: mockRouterPush }))
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://localhost:8000' },
}))

const mockApiFetch = vi.fn()
vi.mock('~/composables/useAuth', () => ({
  useAuth: () => ({ apiFetch: mockApiFetch }),
}))

// Import dynamique pour respecter le hoisting des mocks.
async function importComposable() {
  const mod = await import('~/composables/useAdminCatalog')
  return mod.useAdminCatalog()
}

describe('useAdminCatalog (F25)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockApiFetch.mockReset()
    mockRouterPush.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('buildQueryString', () => {
    it("construit le QS sans `publication_status` pour l'onglet liaisons", async () => {
      const { buildQueryString, store } = await importComposable()
      store.setFilter('publication_status', 'draft')
      store.setFilter('status', 'expired')
      const qs = buildQueryString('fund_intermediaries', store.currentFilters)
      expect(qs).toContain('status=expired')
      expect(qs).not.toContain('publication_status=draft')
    })

    it('respecte `q.trim()` (ignore espaces)', async () => {
      const { buildQueryString, store } = await importComposable()
      store.setFilter('q', '   ')
      const qs = buildQueryString('funds', store.currentFilters)
      expect(qs).not.toContain('q=')
    })
  })

  describe('fetchSummary', () => {
    it('expose le résumé renvoyé par /admin/catalog/summary', async () => {
      mockApiFetch.mockResolvedValueOnce({
        funds: { total: 1, by_status: { published: 1 } },
        intermediaries: { total: 0, by_status: {} },
        offers: { total: 0, by_status: {} },
        fund_intermediaries: { total: 0, active: 0, expired: 0 },
      })
      const { fetchSummary, store } = await importComposable()
      await fetchSummary()
      expect(store.summary?.funds.total).toBe(1)
      expect(store.summaryLoading).toBe(false)
      expect(store.summaryError).toBeNull()
    })

    it('redirige sur /dashboard si le backend renvoie 403', async () => {
      const err = Object.assign(new Error('Forbidden'), { status: 403 })
      mockApiFetch.mockRejectedValueOnce(err)
      const { fetchSummary } = await importComposable()
      await fetchSummary()
      expect(mockRouterPush).toHaveBeenCalledWith('/dashboard')
    })
  })

  describe('fetchTab', () => {
    it('normalise un payload F09 (`limit` au lieu de `page_size`)', async () => {
      mockApiFetch.mockResolvedValueOnce({
        items: [{ id: 'a' }],
        total: 1,
        page: 1,
        limit: 50,
      })
      const { fetchTab, store } = await importComposable()
      await fetchTab('funds')
      expect(store.tabs.funds.data?.page_size).toBe(50)
      expect(store.tabs.funds.data?.paginated).toBe(false)
      expect(store.tabs.funds.data?.items).toHaveLength(1)
    })

    it('normalise un payload `paginated=true`', async () => {
      mockApiFetch.mockResolvedValueOnce({
        items: [{ id: 'a' }],
        total: 5000,
        page: 2,
        page_size: 50,
        paginated: true,
      })
      const { fetchTab, store } = await importComposable()
      await fetchTab('fund_intermediaries')
      expect(store.tabs.fund_intermediaries.data?.paginated).toBe(true)
      expect(store.tabs.fund_intermediaries.data?.page).toBe(2)
    })
  })

  describe('setSearch (debounce 300 ms)', () => {
    it('attend 300 ms avant de fetcher', async () => {
      mockApiFetch.mockResolvedValue({ items: [], total: 0, page: 1, limit: 50 })
      const { setSearch } = await importComposable()
      setSearch('GCF')
      expect(mockApiFetch).not.toHaveBeenCalled()
      vi.advanceTimersByTime(299)
      expect(mockApiFetch).not.toHaveBeenCalled()
      vi.advanceTimersByTime(1)
      // Les promises continuent à se résoudre — basta on a déclenché le fetch.
      expect(mockApiFetch).toHaveBeenCalledTimes(1)
    })
  })
})
