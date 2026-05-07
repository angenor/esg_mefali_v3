<script setup lang="ts">
// F03 — Page admin : log global d'audit (filtrable par compte/utilisateur).
import { onMounted, ref, watch } from 'vue'
import AuditFilters from '~/components/audit/AuditFilters.vue'
import AuditTimeline from '~/components/audit/AuditTimeline.vue'
import { useAuditLog } from '~/composables/useAuditLog'
import type { AuditFilters as AuditFiltersType, AuditEvent } from '~/types/audit'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const { fetchGlobal } = useAuditLog()
const events = ref<AuditEvent[]>([])
const total = ref(0)
const loading = ref(false)

const filters = ref<AuditFiltersType>({
  page: 1,
  limit: 50,
  order: 'desc',
  account_id: null,
  user_id: null,
})

const accountFilter = ref('')
const userFilter = ref('')

async function load() {
  loading.value = true
  try {
    const merged: AuditFiltersType = {
      ...filters.value,
      account_id: accountFilter.value || null,
      user_id: userFilter.value || null,
    }
    const result = await fetchGlobal(merged)
    if (result) {
      events.value = result.events
      total.value = result.total
    }
  } finally {
    loading.value = false
  }
}

watch([filters, accountFilter, userFilter], () => load(), { deep: true })

onMounted(() => {
  load()
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <h2 class="text-2xl font-bold text-red-900 dark:text-red-100 mb-2">
      Journal d'audit global
    </h2>
    <p class="text-sm text-red-700 dark:text-red-300 mb-6">
      Toutes les mutations métier de la plateforme. Filtre par compte ou utilisateur.
    </p>

    <div class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1 text-xs">
        <span class="text-red-700 dark:text-red-300">UUID compte</span>
        <input
          v-model="accountFilter"
          type="text"
          placeholder="ex: 00000000-0000-0000-..."
          class="rounded-md border border-red-300 bg-white px-2 py-1.5 font-mono text-sm dark:border-red-700 dark:bg-red-950/30 dark:text-red-100"
        />
      </label>
      <label class="flex flex-col gap-1 text-xs">
        <span class="text-red-700 dark:text-red-300">UUID utilisateur</span>
        <input
          v-model="userFilter"
          type="text"
          placeholder="ex: 00000000-0000-0000-..."
          class="rounded-md border border-red-300 bg-white px-2 py-1.5 font-mono text-sm dark:border-red-700 dark:bg-red-950/30 dark:text-red-100"
        />
      </label>
    </div>

    <AuditFilters v-model="filters" class="mb-4" />

    <div class="mb-2 text-xs text-red-700 dark:text-red-300">
      {{ total }} événement{{ total > 1 ? 's' : '' }} au total
    </div>

    <AuditTimeline :events="events" :loading="loading" />
  </div>
</template>
