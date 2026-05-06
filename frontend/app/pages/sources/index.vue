<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useSources } from '~/composables/useSources'
import SourcesList from '~/components/sources/SourcesList.vue'
import SourceModal from '~/components/sources/SourceModal.vue'
import type { PaginatedSources, SourceListItem } from '~/types/source'

// Le middleware d'authentification est applique globalement via
// `app/middleware/auth.global.ts` ; il ne doit pas etre reference par nom
// dans `definePageMeta` (sinon Nuxt leve "Unknown route middleware: 'auth'"
// car les middlewares globaux ne sont pas exposes au registre nomme).

const { searchSources } = useSources()

const items = ref<SourceListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const error = ref('')
const search = ref('')
const publisher = ref<string>('')

const PUBLISHERS = [
  'ADEME', 'IPCC', 'IEA', 'UEMOA', 'BCEAO', 'GCF', 'IFC',
  'BOAD', 'Gold Standard', 'Verra', 'ODD ONU', 'GRI', 'ISO',
]

const selectedSourceId = ref<string | null>(null)
const modalVisible = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch([search, publisher], () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    void load()
  }, 300)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result: PaginatedSources | null = await searchSources(search.value, {
      publisher: publisher.value || undefined,
      page: page.value,
      pageSize,
    })
    if (result) {
      items.value = result.items
      total.value = result.total
    } else {
      items.value = []
      total.value = 0
      error.value = 'Erreur lors du chargement des sources'
    }
  } finally {
    loading.value = false
  }
}

function changePage(newPage: number) {
  if (newPage < 1) return
  if ((newPage - 1) * pageSize >= total.value) return
  page.value = newPage
  void load()
}

function handleSelect(id: string) {
  selectedSourceId.value = id
  modalVisible.value = true
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="min-h-screen bg-surface-bg dark:bg-surface-dark-bg p-6">
    <div class="max-w-5xl mx-auto space-y-6">
      <header>
        <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
          Catalogue de sources
        </h1>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
          Toutes les references officielles utilisees par la plateforme.
          Seules les sources verifiees sont affichees.
        </p>
      </header>

      <div class="flex flex-col sm:flex-row gap-3">
        <input
          v-model="search"
          type="search"
          placeholder="Rechercher (titre, editeur, section)..."
          aria-label="Recherche dans les sources"
          class="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
        <select
          v-model="publisher"
          aria-label="Filtre par editeur"
          class="px-4 py-2 rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Tous les editeurs</option>
          <option v-for="p in PUBLISHERS" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <div v-if="error" class="text-center text-red-600 dark:text-red-400 py-4">
        {{ error }}
      </div>

      <SourcesList :sources="items" :loading="loading" @select="handleSelect" />

      <div
        v-if="total > pageSize"
        class="flex items-center justify-between mt-6"
      >
        <button
          type="button"
          :disabled="page <= 1"
          class="px-4 py-2 rounded-lg bg-white dark:bg-dark-card border border-gray-300 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50 disabled:cursor-not-allowed text-surface-text dark:text-surface-dark-text"
          @click="changePage(page - 1)"
        >
          Precedent
        </button>
        <span class="text-sm text-gray-600 dark:text-gray-400">
          Page {{ page }} - {{ total }} sources au total
        </span>
        <button
          type="button"
          :disabled="page * pageSize >= total"
          class="px-4 py-2 rounded-lg bg-white dark:bg-dark-card border border-gray-300 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50 disabled:cursor-not-allowed text-surface-text dark:text-surface-dark-text"
          @click="changePage(page + 1)"
        >
          Suivant
        </button>
      </div>

      <SourceModal
        :source-id="selectedSourceId"
        :visible="modalVisible"
        @close="modalVisible = false"
      />
    </div>
  </div>
</template>
