/**
 * F25 — Store Pinia du catalogue admin (`/admin/catalog`).
 *
 * État volatile (aucune persistance). Conserve par onglet : `filters`,
 * `pagination`, `data` et `summary`. Les fetchs réels sont délégués au
 * composable `useAdminCatalog`.
 */
import { defineStore } from 'pinia'
import type {
  CatalogFilters,
  CatalogPublicationStatus,
  CatalogRow,
  CatalogSummary,
  CatalogTab,
  FundIntermediaryStatus,
  PaginatedListResponse,
} from '~/types/adminCatalog'

const DEFAULT_FILTERS: CatalogFilters = {
  q: '',
  publication_status: null,
  status: 'all',
  fund_type: null,
  sort: 'updated_at_desc',
  page: 1,
  page_size: 50,
}

type TabState = {
  data: PaginatedListResponse<CatalogRow> | null
  loading: boolean
  error: string | null
  filters: CatalogFilters
}

function emptyTabState(): TabState {
  return {
    data: null,
    loading: false,
    error: null,
    filters: { ...DEFAULT_FILTERS },
  }
}

interface AdminCatalogState {
  currentTab: CatalogTab
  summary: CatalogSummary | null
  summaryLoading: boolean
  summaryError: string | null
  tabs: Record<CatalogTab, TabState>
}

export const useAdminCatalogStore = defineStore('adminCatalog', {
  state: (): AdminCatalogState => ({
    currentTab: 'funds',
    summary: null,
    summaryLoading: false,
    summaryError: null,
    tabs: {
      funds: emptyTabState(),
      intermediaries: emptyTabState(),
      offers: emptyTabState(),
      fund_intermediaries: emptyTabState(),
    },
  }),

  getters: {
    currentTabState(state): TabState {
      return state.tabs[state.currentTab]
    },
    currentItems(state): CatalogRow[] {
      return state.tabs[state.currentTab].data?.items ?? []
    },
    currentTotal(state): number {
      return state.tabs[state.currentTab].data?.total ?? 0
    },
    currentLoading(state): boolean {
      return state.tabs[state.currentTab].loading
    },
    currentError(state): string | null {
      return state.tabs[state.currentTab].error
    },
    currentFilters(state): CatalogFilters {
      return state.tabs[state.currentTab].filters
    },
    activeFiltersCount(state): number {
      const f = state.tabs[state.currentTab].filters
      let n = 0
      if (f.q.trim().length > 0) n += 1
      if (f.publication_status) n += 1
      if (f.fund_type) n += 1
      if (f.status !== 'all') n += 1
      return n
    },
  },

  actions: {
    setTab(tab: CatalogTab) {
      this.currentTab = tab
    },

    setFilter<K extends keyof CatalogFilters>(key: K, value: CatalogFilters[K]) {
      this.tabs[this.currentTab].filters[key] = value
      // Toute mutation de filtre revient en page 1.
      if (key !== 'page') {
        this.tabs[this.currentTab].filters.page = 1
      }
    },

    resetFilters() {
      this.tabs[this.currentTab].filters = { ...DEFAULT_FILTERS }
    },

    setSummary(summary: CatalogSummary | null) {
      this.summary = summary
    },

    setSummaryLoading(loading: boolean) {
      this.summaryLoading = loading
    },

    setSummaryError(error: string | null) {
      this.summaryError = error
    },

    setTabData(tab: CatalogTab, data: PaginatedListResponse<CatalogRow> | null) {
      this.tabs[tab].data = data
    },

    setTabLoading(tab: CatalogTab, loading: boolean) {
      this.tabs[tab].loading = loading
    },

    setTabError(tab: CatalogTab, error: string | null) {
      this.tabs[tab].error = error
    },

    setPublicationStatus(value: CatalogPublicationStatus | null) {
      this.setFilter('publication_status', value)
    },

    setFundIntermediaryStatus(value: FundIntermediaryStatus) {
      this.setFilter('status', value)
    },
  },
})
