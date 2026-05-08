<script setup lang="ts">
// F09 PRIO 3 — Liste admin des indicateurs.
import { onMounted, ref, watch } from 'vue'
import EntityCRUDTable from '~/components/admin/EntityCRUDTable.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

interface AdminIndicator {
  id: string
  code: string
  pillar: string
  label: string
  publication_status: 'draft' | 'published'
}

const { listEntities } = useAdminCatalog<AdminIndicator>('indicator')
const items = ref<AdminIndicator[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')
const pillarFilter = ref<string>('')

const columns = [
  { key: 'code', label: 'Code' },
  { key: 'pillar', label: 'Pilier' },
  { key: 'label', label: 'Libellé' },
  { key: 'publication_status', label: 'Publication', type: 'status' as const },
]

async function load() {
  loading.value = true
  try {
    const res = await listEntities({
      page: page.value,
      page_size: pageSize,
      q: search.value || undefined,
      pillar: pillarFilter.value || undefined,
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

watch([page, pillarFilter], load)
watch(search, () => {
  page.value = 1
  load()
})

onMounted(load)

const router = useRouter()
function onRowClick(row: AdminIndicator) {
  router.push(`/admin/indicators/${row.id}`)
}
</script>

<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Indicateurs (admin)
      </h1>
      <NuxtLink
        to="/admin/indicators/new"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 text-sm font-medium"
      >
        Nouvel indicateur
      </NuxtLink>
    </header>

    <div class="mb-4 flex items-center gap-2">
      <label class="text-sm text-gray-600 dark:text-gray-400">Pilier :</label>
      <select
        v-model="pillarFilter"
        class="rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-1 text-sm"
      >
        <option value="">Tous</option>
        <option value="environment">Environnement</option>
        <option value="social">Social</option>
        <option value="governance">Gouvernance</option>
      </select>
    </div>

    <EntityCRUDTable
      :columns="columns"
      :rows="items"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      :search-query="search"
      search-placeholder="Rechercher un indicateur…"
      @row-click="onRowClick"
      @page-change="(p) => (page = p)"
      @search="(q) => (search = q)"
    />
  </div>
</template>
