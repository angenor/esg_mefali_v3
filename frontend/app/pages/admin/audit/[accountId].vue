<script setup lang="ts">
// F03 — Page admin : log d'un compte PME spécifique.
// Au montage, l'appel `fetchByAccount` déclenche côté backend l'enregistrement
// d'une ligne `view_admin` visible côté PME via `/historique`.
import { onMounted, ref, watch } from 'vue'
import AuditFilters from '~/components/audit/AuditFilters.vue'
import AuditTimeline from '~/components/audit/AuditTimeline.vue'
import { useAuditLog } from '~/composables/useAuditLog'
import type { AuditFilters as AuditFiltersType, AuditEvent } from '~/types/audit'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const route = useRoute()
const accountId = computed(() => String(route.params.accountId))

const { fetchByAccount } = useAuditLog()
const events = ref<AuditEvent[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)

const filters = ref<AuditFiltersType>({
  page: 1,
  limit: 50,
  order: 'desc',
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const result = await fetchByAccount(accountId.value, filters.value)
    if (result) {
      events.value = result.events
      total.value = result.total
    } else {
      error.value = "Impossible de charger l'historique de ce compte."
    }
  } finally {
    loading.value = false
  }
}

watch(filters, () => load(), { deep: true })

onMounted(() => {
  load()
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <h2 class="text-2xl font-bold text-red-900 dark:text-red-100 mb-2">
      Audit du compte
    </h2>
    <p class="text-sm text-red-700 dark:text-red-300 mb-6">
      Compte
      <span class="font-mono text-xs">{{ accountId }}</span>
      — votre consultation est tracée et visible par la PME concernée.
    </p>

    <div v-if="error" class="mb-4 rounded-md bg-red-100 p-3 text-sm text-red-800 dark:bg-red-900/40 dark:text-red-200">
      {{ error }}
    </div>

    <AuditFilters v-model="filters" class="mb-4" />

    <div class="mb-2 text-xs text-red-700 dark:text-red-300">
      {{ total }} événement{{ total > 1 ? 's' : '' }}
    </div>

    <AuditTimeline :events="events" :loading="loading" />
  </div>
</template>
