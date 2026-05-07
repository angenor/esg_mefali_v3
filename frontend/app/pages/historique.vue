<script setup lang="ts">
// F03 — Page PME : historique d'audit personnel.
import { onMounted, ref, watch } from 'vue'
import AuditFilters from '~/components/audit/AuditFilters.vue'
import AuditTimeline from '~/components/audit/AuditTimeline.vue'
import AuditExportButton from '~/components/audit/AuditExportButton.vue'
import { useAuditLog } from '~/composables/useAuditLog'
import { useAuditStore } from '~/stores/audit'
import type { AuditFilters as AuditFiltersType } from '~/types/audit'

// Le middleware d'authentification est applique globalement via
// `app/middleware/auth.global.ts` ; il ne doit pas etre reference par nom
// dans `definePageMeta` (sinon Nuxt leve "Unknown route middleware: 'auth'"
// car les middlewares globaux ne sont pas exposes au registre nomme).

const auditStore = useAuditStore()
const { fetchMe } = useAuditLog()

const loading = ref(false)
const filters = ref<AuditFiltersType>({
  page: 1,
  limit: 50,
  order: 'desc',
})

async function load() {
  loading.value = true
  try {
    const result = await fetchMe(filters.value)
    if (result) {
      auditStore.setEvents(result.events, result.total)
    }
  } finally {
    loading.value = false
  }
}

watch(filters, () => load(), { deep: true })

onMounted(() => {
  load()
})

function nextPage() {
  filters.value = { ...filters.value, page: (filters.value.page ?? 1) + 1 }
}

function prevPage() {
  if ((filters.value.page ?? 1) > 1) {
    filters.value = { ...filters.value, page: (filters.value.page ?? 1) - 1 }
  }
}
</script>

<template>
  <div class="min-h-screen bg-surface-bg dark:bg-surface-dark-bg">
    <div class="max-w-5xl mx-auto px-4 py-8">
      <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1
            class="text-2xl font-bold text-gray-900 dark:text-surface-dark-text"
            data-testid="historique-title"
          >
            Historique d'activité
          </h1>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Toutes les modifications, créations et consultations admin tracées sur votre compte.
          </p>
        </div>
        <AuditExportButton :filters="filters" />
      </div>

      <div class="mb-6">
        <AuditFilters v-model="filters" />
      </div>

      <div class="mb-3 text-xs text-gray-500 dark:text-gray-400">
        {{ auditStore.total }} événement{{ auditStore.total > 1 ? 's' : '' }} au total
      </div>

      <AuditTimeline :events="auditStore.events" :loading="loading" />

      <div
        v-if="auditStore.total > (filters.limit ?? 50)"
        class="mt-6 flex items-center justify-between text-sm"
      >
        <button
          type="button"
          class="rounded-md border border-gray-300 px-3 py-1.5 dark:border-dark-border dark:text-gray-300"
          :disabled="(filters.page ?? 1) <= 1"
          @click="prevPage"
        >
          Précédent
        </button>
        <span class="text-gray-600 dark:text-gray-400">
          Page {{ filters.page ?? 1 }}
        </span>
        <button
          type="button"
          class="rounded-md border border-gray-300 px-3 py-1.5 dark:border-dark-border dark:text-gray-300"
          :disabled="(filters.page ?? 1) * (filters.limit ?? 50) >= auditStore.total"
          @click="nextPage"
        >
          Suivant
        </button>
      </div>
    </div>
  </div>
</template>
