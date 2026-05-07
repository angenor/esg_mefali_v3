<script setup lang="ts">
// F09 — Liste admin des sources (filtre par statut).
import { computed, onMounted, ref, watch } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import {
  useAdminSources,
  type AdminSource,
  type VerificationStatus,
} from '~/composables/useAdminSources'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const { listSources } = useAdminSources()

const items = ref<AdminSource[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const filter = ref<VerificationStatus | undefined>(undefined)
const search = ref('')
const page = ref(1)

async function fetchAll() {
  loading.value = true
  error.value = ''
  try {
    const result = await listSources({
      verification_status: filter.value,
      q: search.value || undefined,
      page: page.value,
      page_size: 50,
    })
    items.value = result.items
    total.value = result.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)
watch([filter, page], fetchAll)
</script>

<template>
  <div class="px-6 py-8">
    <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
          Sources réglementaires
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {{ total }} source(s) au total
        </p>
      </div>
      <NuxtLink
        to="/admin/sources/new"
        class="rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 text-sm font-medium"
      >
        + Nouvelle source
      </NuxtLink>
    </div>

    <div class="mb-4 flex flex-wrap gap-2">
      <button
        type="button"
        class="px-3 py-1 text-sm rounded-full border"
        :class="
          filter === undefined
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white dark:bg-dark-card border-gray-300 dark:border-dark-border text-gray-700 dark:text-gray-300'
        "
        @click="filter = undefined"
      >
        Toutes
      </button>
      <button
        v-for="s in ['draft', 'pending', 'verified', 'outdated'] as VerificationStatus[]"
        :key="s"
        type="button"
        class="px-3 py-1 text-sm rounded-full border capitalize"
        :class="
          filter === s
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white dark:bg-dark-card border-gray-300 dark:border-dark-border text-gray-700 dark:text-gray-300'
        "
        @click="filter = s"
      >
        {{ s }}
      </button>
    </div>

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
        <thead class="bg-gray-50 dark:bg-gray-800/40">
          <tr class="text-left text-gray-700 dark:text-gray-300">
            <th class="px-4 py-2">Titre</th>
            <th class="px-4 py-2">Publisher</th>
            <th class="px-4 py-2">Statut</th>
            <th class="px-4 py-2">Date publi</th>
            <th class="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="src in items"
            :key="src.id"
            class="border-t border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover"
          >
            <td class="px-4 py-2 text-surface-text dark:text-surface-dark-text">
              {{ src.title }}
            </td>
            <td class="px-4 py-2 text-gray-600 dark:text-gray-400">
              {{ src.publisher }}
            </td>
            <td class="px-4 py-2">
              <StatusBadge :variant="src.verification_status" />
            </td>
            <td class="px-4 py-2 text-gray-600 dark:text-gray-400">
              {{ src.date_publi }}
            </td>
            <td class="px-4 py-2">
              <NuxtLink
                :to="`/admin/sources/${src.id}`"
                class="text-blue-600 hover:underline"
              >
                Voir
              </NuxtLink>
            </td>
          </tr>
          <tr v-if="!loading && items.length === 0">
            <td
              colspan="5"
              class="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
            >
              Aucune source.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
