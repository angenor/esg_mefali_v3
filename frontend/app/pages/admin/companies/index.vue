<script setup lang="ts">
// F09 PRIO 3 — Liste admin des comptes PME.
import { onMounted, ref, watch } from 'vue'
import EntityCRUDTable from '~/components/admin/EntityCRUDTable.vue'
import { useAdminCompanies, type AdminAccountSummary } from '~/composables/useAdminCompanies'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const { listCompanies } = useAdminCompanies()
const items = ref<AdminAccountSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const search = ref('')
const activeFilter = ref<'' | 'true' | 'false'>('')
const router = useRouter()

const columns = [
  { key: 'name', label: 'Nom du compte' },
  { key: 'plan', label: 'Plan' },
  {
    key: 'is_active',
    label: 'Actif',
    formatter: (v: unknown) => (v ? 'Oui' : 'Non'),
  },
  { key: 'created_at', label: 'Créé le', type: 'date' as const },
]

async function load() {
  loading.value = true
  try {
    const res = await listCompanies({
      page: page.value,
      page_size: pageSize,
      q: search.value || undefined,
      is_active:
        activeFilter.value === '' ? undefined : activeFilter.value === 'true',
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

watch([page, activeFilter], load)
watch(search, () => {
  page.value = 1
  load()
})
onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <header class="mb-6">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Comptes PME (admin)
      </h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
        Vue cross-tenant. Chaque consultation déclenche un audit log
        <code>view_admin</code> visible côté PME (dédup quotidienne).
      </p>
    </header>

    <div class="mb-4 flex items-center gap-3">
      <label class="text-sm text-gray-600 dark:text-gray-400">Statut :</label>
      <select
        v-model="activeFilter"
        class="rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-1 text-sm"
      >
        <option value="">Tous</option>
        <option value="true">Actifs</option>
        <option value="false">Désactivés</option>
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
      search-placeholder="Rechercher un compte…"
      empty-message="Aucun compte PME."
      @row-click="(row) => router.push(`/admin/companies/${row.id}`)"
      @page-change="(p) => (page = p)"
      @search="(q) => (search = q)"
    />
  </div>
</template>
