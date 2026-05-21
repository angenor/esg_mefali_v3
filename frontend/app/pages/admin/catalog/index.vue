<script setup lang="ts">
// F25 — Page shell `/admin/catalog`.
// Orchestration : store Pinia `adminCatalog` + composable `useAdminCatalog`.
// 4 onglets, recherche, filtres, table générique avec lignes cliquables.
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter, useRuntimeConfig } from '#app'
import { useAdminCatalog } from '~/composables/useAdminCatalog'
import { useAuth } from '~/composables/useAuth'
import type {
  CatalogPublicationStatus,
  CatalogRow,
  CatalogTab,
  FundIntermediaryStatus,
} from '~/types/adminCatalog'

definePageMeta({
  layout: 'admin',
  middleware: 'admin',
})

useHead({ title: 'Catalogue admin — ESG Mefali' })

const {
  store,
  fetchSummary,
  fetchTab,
  setSearch,
  setTab,
  resetFilters,
  buildQueryString,
} = useAdminCatalog()
const { apiFetchBlob } = useAuth()
const route = useRoute()
const router = useRouter()

const TAB_KEYS: CatalogTab[] = ['funds', 'intermediaries', 'offers', 'fund_intermediaries']

function readTabFromQuery(): CatalogTab {
  const t = route.query.tab
  if (typeof t === 'string' && (TAB_KEYS as string[]).includes(t)) {
    return t as CatalogTab
  }
  return 'funds'
}

function onTabChange(tab: CatalogTab) {
  setTab(tab)
  router.replace({ query: { ...route.query, tab } })
}

onMounted(() => {
  store.setTab(readTabFromQuery())
  fetchSummary()
  fetchTab(store.currentTab)
})

watch(
  () => route.query.tab,
  (newTab) => {
    if (typeof newTab === 'string' && (TAB_KEYS as string[]).includes(newTab)) {
      const tab = newTab as CatalogTab
      if (tab !== store.currentTab) {
        store.setTab(tab)
        fetchTab(tab)
      }
    }
  },
)

const columns = computed(() => {
  switch (store.currentTab) {
    case 'funds':
      return [
        { key: 'name', label: 'Nom' },
        { key: 'fund_type', label: 'Type' },
        { key: 'organization', label: 'Organisme' },
        { key: 'publication_status', label: 'Statut' },
        { key: 'version', label: 'Version' },
        { key: 'has_incoherence', label: 'Alertes' },
      ]
    case 'intermediaries':
      return [
        { key: 'name', label: 'Nom' },
        { key: 'country', label: 'Pays' },
        { key: 'publication_status', label: 'Statut' },
        { key: 'version', label: 'Version' },
        { key: 'has_incoherence', label: 'Alertes' },
      ]
    case 'offers':
      return [
        {
          key: 'name',
          label: 'Offre',
          format: (row: CatalogRow) =>
            (row as { name?: string }).name ??
            `${(row as { fund_id?: string }).fund_id} × ${(row as { intermediary_id?: string }).intermediary_id}`,
        },
        { key: 'publication_status', label: 'Statut' },
        { key: 'version', label: 'Version' },
        { key: 'has_incoherence', label: 'Alertes' },
      ]
    case 'fund_intermediaries':
      return [
        { key: 'fund_name', label: 'Fonds' },
        { key: 'intermediary_name', label: 'Intermédiaire' },
        { key: 'accredited_from', label: 'Accréditation' },
        {
          key: 'is_active',
          label: 'État',
          format: (row: CatalogRow) =>
            (row as { is_active?: boolean }).is_active ? 'Active' : 'Expirée',
        },
        { key: 'has_incoherence', label: 'Alertes' },
      ]
  }
  return []
})

function rowLink(row: CatalogRow): string {
  switch (store.currentTab) {
    case 'funds':
      return `/admin/catalog/funds/${row.id}`
    case 'intermediaries':
      return `/admin/catalog/intermediaries/${row.id}`
    case 'offers':
      return `/admin/catalog/offers/${row.id}`
    case 'fund_intermediaries':
      return `/admin/catalog/fund-intermediaries/${encodeURIComponent(row.id)}`
  }
  return '#'
}

const filteredCount = computed(() => store.currentTabState.data?.items.length ?? 0)

const isEmpty = computed(
  () => !store.currentLoading && filteredCount.value === 0,
)
const isEmptyDueToFilters = computed(
  () => isEmpty.value && store.activeFiltersCount > 0,
)

function onChangePage(page: number) {
  store.setFilter('page', page)
  fetchTab(store.currentTab)
}

function onSearch(value: string) {
  setSearch(value)
}

function onPublicationStatus(value: CatalogPublicationStatus | null) {
  store.setFilter('publication_status', value)
  fetchTab(store.currentTab)
}

function onStatusChange(value: FundIntermediaryStatus) {
  store.setFilter('status', value)
  fetchTab(store.currentTab)
}

function onSortChange(value: string) {
  store.setFilter('sort', value)
  fetchTab(store.currentTab)
}

async function onExport() {
  // Téléchargement authentifié : on récupère le CSV en blob via apiFetchBlob
  // (Bearer auth + intercepteur 401 → refresh) puis on crée un lien
  // programmatique. window.open ne propage pas le token JWT.
  const filters = store.currentFilters
  const qs = buildQueryString(store.currentTab, filters)
  const url = `/admin/catalog/export?tab=${store.currentTab}${qs ? '&' + qs : ''}`
  try {
    const blob = await apiFetchBlob(url)
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    link.download = `catalog-${store.currentTab}-${date}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
  } catch (err) {
    store.setTabError(
      store.currentTab,
      err instanceof Error ? err.message : 'Erreur lors de l\'export CSV',
    )
  }
}
</script>

<template>
  <div class="space-y-6">
    <header class="space-y-1">
      <h1 class="text-xl font-semibold text-surface-text dark:text-surface-dark-text">Catalogue admin</h1>
      <p class="text-sm text-gray-600 dark:text-gray-400">
        Vue unifiée des fonds, intermédiaires, offres et liaisons publiés ou non sur
        <code>/financing</code>. Lecture seule.
      </p>
    </header>

    <CatalogTabs
      :model-value="store.currentTab"
      :summary="store.summary"
      :loading="store.summaryLoading"
      @update:model-value="onTabChange"
    />

    <CatalogToolbar
      :tab="store.currentTab"
      :query="store.currentFilters.q"
      :publication-status="store.currentFilters.publication_status"
      :status="store.currentFilters.status"
      :sort="store.currentFilters.sort"
      :total="store.currentTotal"
      :filtered-count="filteredCount"
      @update:query="onSearch"
      @update:publication-status="onPublicationStatus"
      @update:status="onStatusChange"
      @update:sort="onSortChange"
      @reset="resetFilters"
      @export="onExport"
    />

    <div
      v-if="store.currentError"
      class="rounded-md border border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-900/40 px-4 py-3 text-sm text-rose-800 dark:text-rose-200"
      role="alert"
    >
      {{ store.currentError }}
    </div>

    <CatalogEmptyState
      v-if="isEmpty"
      :mode="isEmptyDueToFilters ? 'no-match' : 'empty'"
      :query="store.currentFilters.q"
      label="élément"
      @reset="resetFilters"
    />

    <CatalogTable
      v-else
      :rows="store.currentItems"
      :columns="columns"
      :data="store.currentTabState.data"
      :loading="store.currentLoading"
      :row-link="rowLink"
      @change-page="onChangePage"
    />
  </div>
</template>
