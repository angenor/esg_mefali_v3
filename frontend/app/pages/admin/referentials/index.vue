<script setup lang="ts">
// F09 PRIO 3 — Liste admin des référentiels (ESG Mefali, GCF, IFC, BOAD, GRI).
import { onMounted, ref, watch } from 'vue'
import EntityCRUDTable from '~/components/admin/EntityCRUDTable.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

interface AdminReferential {
  id: string
  code: string
  label: string
  description: string
  publication_status: 'draft' | 'published'
  version?: string | null
  source_id: string
}

const { listEntities } = useAdminCatalog<AdminReferential>('referential')
const items = ref<AdminReferential[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')

const columns = [
  { key: 'code', label: 'Code' },
  { key: 'label', label: 'Libellé' },
  { key: 'version', label: 'Version' },
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

const router = useRouter()
function onRowClick(row: AdminReferential) {
  router.push(`/admin/referentials/${row.id}`)
}
</script>

<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Référentiels (admin)
      </h1>
      <NuxtLink
        to="/admin/referentials/new"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 text-sm font-medium"
      >
        Nouveau référentiel
      </NuxtLink>
    </header>

    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      Référentiels ESG Mefali, GCF, IFC, BOAD, GRI, ODD avec versioning F04 et
      sources F01.
    </p>

    <EntityCRUDTable
      :columns="columns"
      :rows="items"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      :search-query="search"
      search-placeholder="Rechercher un référentiel…"
      @row-click="onRowClick"
      @page-change="(p) => (page = p)"
      @search="(q) => (search = q)"
    />
  </div>
</template>
