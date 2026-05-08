<script setup lang="ts">
// F09 PRIO 3 — Liste admin des intermédiaires.
import { onMounted, ref, watch } from 'vue'
import EntityCRUDTable from '~/components/admin/EntityCRUDTable.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

interface AdminIntermediary {
  id: string
  name: string
  publication_status: 'draft' | 'published'
  country?: string | null
  type?: string | null
}

const { listEntities } = useAdminCatalog<AdminIntermediary>('intermediary')
const items = ref<AdminIntermediary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')

const columns = [
  { key: 'name', label: 'Nom' },
  { key: 'type', label: 'Type' },
  { key: 'country', label: 'Pays' },
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
function onRowClick(row: AdminIntermediary) {
  router.push(`/admin/intermediaries/${row.id}`)
}
</script>

<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Intermédiaires (admin)
      </h1>
      <NuxtLink
        to="/admin/intermediaries/new"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 text-sm font-medium"
      >
        Nouvel intermédiaire
      </NuxtLink>
    </header>

    <EntityCRUDTable
      :columns="columns"
      :rows="items"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      :search-query="search"
      search-placeholder="Rechercher un intermédiaire…"
      @row-click="onRowClick"
      @page-change="(p) => (page = p)"
      @search="(q) => (search = q)"
    >
      <template #row-actions="{ row }">
        <NuxtLink
          :to="`/admin/intermediaries/${row.id}`"
          class="text-blue-600 dark:text-blue-400 hover:underline text-xs"
        >
          Voir
        </NuxtLink>
      </template>
    </EntityCRUDTable>
  </div>
</template>
