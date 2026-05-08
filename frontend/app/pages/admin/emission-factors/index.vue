<script setup lang="ts">
// F09 PRIO 3 — Liste admin des facteurs d'émission.
import { onMounted, ref, watch } from 'vue'
import EntityCRUDTable from '~/components/admin/EntityCRUDTable.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

interface AdminEmissionFactor {
  id: string
  code: string
  label: string
  category: string
  country: string
  year: number
  value: number
  unit: string
  publication_status: 'draft' | 'published'
}

const { listEntities } = useAdminCatalog<AdminEmissionFactor>('emission_factor')
const items = ref<AdminEmissionFactor[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')
const countryFilter = ref('')
const router = useRouter()

const columns = [
  { key: 'code', label: 'Code' },
  { key: 'label', label: 'Libellé' },
  { key: 'category', label: 'Catégorie' },
  { key: 'country', label: 'Pays' },
  { key: 'year', label: 'Année' },
  {
    key: 'value',
    label: 'Valeur',
    formatter: (v: unknown, row: AdminEmissionFactor) => `${v} ${row.unit}`,
  },
  { key: 'publication_status', label: 'Publication', type: 'status' as const },
]

async function load() {
  loading.value = true
  try {
    const res = await listEntities({
      page: page.value,
      page_size: pageSize,
      q: search.value || undefined,
      country: countryFilter.value || undefined,
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

watch([page, countryFilter], load)
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
        Facteurs d'émission (admin)
      </h1>
      <NuxtLink
        to="/admin/emission-factors/new"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 text-sm font-medium"
      >
        Nouveau facteur
      </NuxtLink>
    </header>

    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      Sources ADEME, IPCC, IEA. Seedés par F17 pour 8 pays UEMOA.
    </p>

    <div class="mb-4 flex items-center gap-2">
      <label class="text-sm text-gray-600 dark:text-gray-400">Pays :</label>
      <select
        v-model="countryFilter"
        class="rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-1 text-sm"
      >
        <option value="">Tous</option>
        <option value="CI">Côte d'Ivoire</option>
        <option value="SN">Sénégal</option>
        <option value="BF">Burkina Faso</option>
        <option value="ML">Mali</option>
        <option value="NE">Niger</option>
        <option value="BJ">Bénin</option>
        <option value="TG">Togo</option>
        <option value="GW">Guinée-Bissau</option>
        <option value="global">Global</option>
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
      search-placeholder="Rechercher un facteur…"
      @row-click="(row) => router.push(`/admin/emission-factors/${row.id}`)"
      @page-change="(p) => (page = p)"
      @search="(q) => (search = q)"
    />
  </div>
</template>
