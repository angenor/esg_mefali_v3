/**
 * F25 — Tests du store Pinia `adminCatalog`.
 * Couvre l'état initial, le switch d'onglet, l'application/réinitialisation
 * des filtres, et la gestion des compteurs de filtres actifs.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAdminCatalogStore } from '~/stores/adminCatalog'

describe('useAdminCatalogStore (F25)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initialise les 4 onglets avec un état vide', () => {
    const store = useAdminCatalogStore()
    expect(store.currentTab).toBe('funds')
    for (const tab of ['funds', 'intermediaries', 'offers', 'fund_intermediaries'] as const) {
      expect(store.tabs[tab].data).toBeNull()
      expect(store.tabs[tab].loading).toBe(false)
      expect(store.tabs[tab].error).toBeNull()
      expect(store.tabs[tab].filters.q).toBe('')
    }
  })

  it('setTab change l\'onglet courant', () => {
    const store = useAdminCatalogStore()
    store.setTab('offers')
    expect(store.currentTab).toBe('offers')
  })

  it('setFilter remet page à 1 sauf pour la clé "page"', () => {
    const store = useAdminCatalogStore()
    store.setFilter('page', 5)
    expect(store.currentFilters.page).toBe(5)
    store.setFilter('q', 'GCF')
    // toute mutation de filtre autre que page => page = 1
    expect(store.currentFilters.page).toBe(1)
    expect(store.currentFilters.q).toBe('GCF')
  })

  it('resetFilters remet l\'onglet courant aux defaults', () => {
    const store = useAdminCatalogStore()
    store.setFilter('q', 'foo')
    store.setFilter('publication_status', 'draft')
    expect(store.activeFiltersCount).toBe(2)
    store.resetFilters()
    expect(store.currentFilters.q).toBe('')
    expect(store.currentFilters.publication_status).toBeNull()
    expect(store.activeFiltersCount).toBe(0)
  })

  it('compte correctement les filtres actifs', () => {
    const store = useAdminCatalogStore()
    expect(store.activeFiltersCount).toBe(0)
    store.setFilter('q', '   ') // espaces seuls => non actif
    expect(store.activeFiltersCount).toBe(0)
    store.setFilter('q', 'GCF')
    expect(store.activeFiltersCount).toBe(1)
    store.setFilter('publication_status', 'published')
    expect(store.activeFiltersCount).toBe(2)
  })

  it('setSummary stocke le résumé', () => {
    const store = useAdminCatalogStore()
    store.setSummary({
      funds: { total: 3, by_status: { published: 2, draft: 1 } },
      intermediaries: { total: 1, by_status: { published: 1 } },
      offers: { total: 0, by_status: {} },
      fund_intermediaries: { total: 2, active: 1, expired: 1 },
    })
    expect(store.summary?.funds.total).toBe(3)
    expect(store.summary?.fund_intermediaries.active).toBe(1)
  })

  it('mutations isolées par onglet', () => {
    const store = useAdminCatalogStore()
    store.setTab('offers')
    store.setFilter('q', 'gcf')
    store.setTab('funds')
    expect(store.currentFilters.q).toBe('')
    store.setTab('offers')
    expect(store.currentFilters.q).toBe('gcf')
  })
})
