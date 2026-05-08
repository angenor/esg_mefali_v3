<script setup lang="ts">
// F09 PRIO 3 — Liste admin des constantes simulateur.
import { onMounted, ref, watch } from 'vue'
import EntityCRUDTable from '~/components/admin/EntityCRUDTable.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

interface AdminSimFactor {
  id: string
  code: string
  label: string
  value: number
  unit: string
  scope: string
  status: 'verified' | 'pending'
  publication_status: 'draft' | 'published'
}

const { listEntities } = useAdminCatalog<AdminSimFactor>('simulation_factor')
const items = ref<AdminSimFactor[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')
const router = useRouter()

const columns = [
  { key: 'code', label: 'Code' },
  { key: 'label', label: 'Libellé' },
  { key: 'scope', label: 'Scope' },
  {
    key: 'value',
    label: 'Valeur',
    formatter: (v: unknown, row: AdminSimFactor) => `${v} ${row.unit}`,
  },
  { key: 'status', label: 'Statut métier' },
  { key: 'publication_status', label: 'Publication', type: 'status' as const },
]

async function load() {
  loading.value = true
  try {
    const res = await listEntities({
      page: page.value,
      page_size: pageSize,
      q: search.value || undefined,
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

watch(page, load)
watch(search, () => {
  page.value = 1
  load()
})
onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Constantes simulateur (admin)
      </h1>
      <NuxtLink
        to="/admin/simulation-factors/new"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 text-sm font-medium"
      >
        Nouvelle constante
      </NuxtLink>
    </header>

    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      Constantes utilisées par les simulateurs (taux, ratios). Statut
      <em>pending</em> permis sans source.
    </p>

    <EntityCRUDTable
      :columns="columns"
      :rows="items"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      :search-query="search"
      search-placeholder="Rechercher une constante…"
      @row-click="(row) => router.push(`/admin/simulation-factors/${row.id}`)"
      @page-change="(p) => (page = p)"
      @search="(q) => (search = q)"
    />
  </div>
</template>
