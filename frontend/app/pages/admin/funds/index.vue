<script setup lang="ts">
// F09 — Liste admin des fonds (avec publication_status).
import { onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import { useAuth } from '~/composables/useAuth'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

interface AdminFund {
  id: string
  name: string
  publication_status: 'draft' | 'published'
  status: string
  fund_type?: string | null
}

const { apiFetch } = useAuth()
const items = ref<AdminFund[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await apiFetch<{ items: AdminFund[]; total: number }>(
      '/admin/funds?page=1&page_size=50',
    )
    items.value = res.items
    total.value = res.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8">
    <h1 class="text-2xl font-bold mb-4">Fonds (admin)</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-6">
      {{ total }} fonds en BDD
    </p>

    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>

    <div
      class="overflow-hidden rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card"
    >
      <table class="w-full text-sm">
        <thead class="bg-gray-50 dark:bg-gray-800/40 text-left">
          <tr>
            <th class="px-4 py-2">Nom</th>
            <th class="px-4 py-2">Type</th>
            <th class="px-4 py-2">Publication</th>
            <th class="px-4 py-2">Statut métier</th>
            <th class="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="f in items"
            :key="f.id"
            class="border-t border-gray-200 dark:border-dark-border"
          >
            <td class="px-4 py-2">{{ f.name }}</td>
            <td class="px-4 py-2 text-gray-600 dark:text-gray-400">
              {{ f.fund_type ?? '—' }}
            </td>
            <td class="px-4 py-2">
              <StatusBadge :variant="f.publication_status" />
            </td>
            <td class="px-4 py-2 text-gray-600 dark:text-gray-400">{{ f.status }}</td>
            <td class="px-4 py-2">
              <NuxtLink
                :to="`/admin/funds/${f.id}`"
                class="text-blue-600 hover:underline"
                >Voir</NuxtLink
              >
            </td>
          </tr>
          <tr v-if="!loading && items.length === 0">
            <td
              colspan="5"
              class="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
            >
              Aucun fonds.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
