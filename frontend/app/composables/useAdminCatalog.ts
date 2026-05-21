/**
 * F25 — Composable orchestrant les fetchs du catalogue admin
 * (`/admin/catalog`). Délègue l'état au store Pinia
 * `useAdminCatalogStore` et applique :
 *
 *   - debounce 300 ms sur la recherche plein-texte `q`,
 *   - redirection vers `/dashboard` si l'API renvoie 403,
 *   - construction des querystrings cohérents avec les contrats backend.
 */
import { getCurrentScope, onScopeDispose } from 'vue'
import { useAdminCatalogStore } from '~/stores/adminCatalog'
import { useAuth } from '~/composables/useAuth'
import type {
  CatalogFilters,
  CatalogRow,
  CatalogSummary,
  CatalogTab,
  FundIntermediaryDetail,
  PaginatedListResponse,
} from '~/types/adminCatalog'

// Conventions Mefali (cf. useAdminSources.ts) : `apiBase` inclut déjà `/api`,
// donc tous les paths commencent ici par `/admin/...` (sans préfixe `/api/`).
const TAB_TO_PATH: Record<CatalogTab, string> = {
  funds: '/admin/funds',
  intermediaries: '/admin/intermediaries',
  offers: '/admin/offers',
  fund_intermediaries: '/admin/catalog/fund-intermediaries',
}

function buildQueryString(tab: CatalogTab, filters: CatalogFilters): string {
  const params = new URLSearchParams()

  if (filters.q.trim().length > 0) params.set('q', filters.q.trim())

  // `publication_status` n'est pas applicable à l'onglet liaisons.
  if (tab !== 'fund_intermediaries' && filters.publication_status) {
    params.set('publication_status', filters.publication_status)
  }

  if (tab === 'funds' && filters.fund_type) {
    params.set('fund_type', filters.fund_type)
  }

  if (tab === 'fund_intermediaries' && filters.status !== 'all') {
    params.set('status', filters.status)
  }

  // Tri.
  if (filters.sort) params.set('sort', filters.sort)

  params.set('page', String(filters.page))
  params.set('page_size', String(filters.page_size))

  return params.toString()
}

function isForbiddenError(err: unknown): boolean {
  return (
    err !== null &&
    typeof err === 'object' &&
    'status' in err &&
    (err as { status: number }).status === 403
  )
}

function extractMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message
  return fallback
}

export function useAdminCatalog() {
  const store = useAdminCatalogStore()
  const { apiFetch } = useAuth()
  const router = useRouter()

  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  // Cleanup automatique : si le composant consommateur est démonté pendant
  // la fenêtre de debounce, on annule le timer pour éviter une requête
  // fantôme + accès au store détruit (Nuxt 4 SSR + navigation rapide).
  // `getCurrentScope` retourne null hors EffectScope (ex. tests Vitest),
  // auquel cas le hook est simplement ignoré.
  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (debounceTimer) {
        clearTimeout(debounceTimer)
        debounceTimer = null
      }
    })
  }

  function handleAuthError(err: unknown) {
    if (isForbiddenError(err)) {
      router.push('/dashboard')
    }
  }

  async function fetchSummary(): Promise<void> {
    store.setSummaryLoading(true)
    store.setSummaryError(null)
    try {
      const data = await apiFetch<CatalogSummary>('/admin/catalog/summary')
      store.setSummary(data)
    } catch (err) {
      handleAuthError(err)
      store.setSummaryError(extractMessage(err, 'Erreur lors du chargement du résumé'))
    } finally {
      store.setSummaryLoading(false)
    }
  }

  async function fetchTab(tab: CatalogTab = store.currentTab): Promise<void> {
    store.setTabLoading(tab, true)
    store.setTabError(tab, null)
    const filters = store.tabs[tab].filters
    const qs = buildQueryString(tab, filters)
    const url = `${TAB_TO_PATH[tab]}${qs ? '?' + qs : ''}`
    try {
      const raw = await apiFetch<unknown>(url)
      // Les 3 routers F09 (`funds`/`intermediaries`/`offers`) renvoient
      // `{items, total, page, limit}` (limit au lieu de page_size, jamais
      // de `paginated`). On normalise vers `PaginatedListResponse<T>`.
      const normalized = normalizeResponse(raw)
      store.setTabData(tab, normalized)
    } catch (err) {
      handleAuthError(err)
      store.setTabError(tab, extractMessage(err, "Erreur lors du chargement de l'onglet"))
    } finally {
      store.setTabLoading(tab, false)
    }
  }

  function normalizeResponse(raw: unknown): PaginatedListResponse<CatalogRow> {
    if (raw === null || typeof raw !== 'object') {
      return {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        paginated: false,
      }
    }
    const obj = raw as {
      items?: CatalogRow[]
      total?: number
      page?: number
      page_size?: number
      limit?: number
      paginated?: boolean
    }
    const total = obj.total ?? 0
    return {
      items: obj.items ?? [],
      total,
      page: obj.page ?? 1,
      page_size: obj.page_size ?? obj.limit ?? Math.max(total, 1),
      paginated: obj.paginated ?? false,
    }
  }

  function setSearch(value: string, debounce = true) {
    store.setFilter('q', value)
    if (debounceTimer) clearTimeout(debounceTimer)
    if (debounce) {
      debounceTimer = setTimeout(() => {
        fetchTab(store.currentTab)
      }, 300)
    } else {
      fetchTab(store.currentTab)
    }
  }

  function setTab(tab: CatalogTab) {
    store.setTab(tab)
    fetchTab(tab)
  }

  function resetFilters() {
    store.resetFilters()
    fetchTab(store.currentTab)
  }

  async function fetchFundIntermediaryDetail(
    compositeId: string,
  ): Promise<FundIntermediaryDetail> {
    return apiFetch<FundIntermediaryDetail>(
      `/admin/catalog/fund-intermediaries/${encodeURIComponent(compositeId)}`,
    )
  }

  return {
    store,
    fetchSummary,
    fetchTab,
    setSearch,
    setTab,
    resetFilters,
    fetchFundIntermediaryDetail,
    buildQueryString,
  }
}
