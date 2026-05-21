<script setup lang="ts">
// F25 — Toolbar du catalogue admin : recherche, filtres, tri, export.
// Émet `update:query`, `update:publicationStatus`, `update:status`, `update:sort`,
// `export`, `reset`. La page parente est responsable du store et des fetchs.
import { computed } from 'vue'
import type {
  CatalogPublicationStatus,
  CatalogTab,
  FundIntermediaryStatus,
} from '~/types/adminCatalog'

interface Props {
  tab: CatalogTab
  query: string
  publicationStatus: CatalogPublicationStatus | null
  status: FundIntermediaryStatus
  sort: string
  total: number
  filteredCount: number
  exportEnabled?: boolean
}

const props = withDefaults(defineProps<Props>(), { exportEnabled: true })

const emit = defineEmits<{
  (event: 'update:query', value: string): void
  (event: 'update:publicationStatus', value: CatalogPublicationStatus | null): void
  (event: 'update:status', value: FundIntermediaryStatus): void
  (event: 'update:sort', value: string): void
  (event: 'export'): void
  (event: 'reset'): void
}>()

const isFundIntermediariesTab = computed(() => props.tab === 'fund_intermediaries')

const sortOptions = computed(() => {
  if (isFundIntermediariesTab.value) {
    return [
      { value: 'accredited_from_desc', label: 'Accréditation (récente d\'abord)' },
      { value: 'accredited_from_asc', label: 'Accréditation (ancienne d\'abord)' },
      { value: 'updated_at_desc', label: 'Mise à jour (récente d\'abord)' },
      { value: 'updated_at_asc', label: 'Mise à jour (ancienne d\'abord)' },
    ]
  }
  return [
    { value: 'updated_at_desc', label: 'Mise à jour (récente d\'abord)' },
    { value: 'updated_at_asc', label: 'Mise à jour (ancienne d\'abord)' },
    { value: 'version_desc', label: 'Version (récente d\'abord)' },
    { value: 'version_asc', label: 'Version (ancienne d\'abord)' },
  ]
})

function onQueryInput(event: Event) {
  emit('update:query', (event.target as HTMLInputElement).value)
}

function onPublicationStatusChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  emit('update:publicationStatus', value === '' ? null : (value as CatalogPublicationStatus))
}

function onStatusChange(event: Event) {
  emit('update:status', (event.target as HTMLSelectElement).value as FundIntermediaryStatus)
}

function onSortChange(event: Event) {
  emit('update:sort', (event.target as HTMLSelectElement).value)
}
</script>

<template>
  <div
    class="flex flex-col gap-3 rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4"
  >
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:flex-wrap">
      <label class="flex-1 min-w-[14rem]">
        <span class="sr-only">Recherche</span>
        <input
          type="search"
          :value="query"
          placeholder="Rechercher par nom, code ou mot-clé…"
          class="w-full rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          @input="onQueryInput"
        />
      </label>

      <label v-if="!isFundIntermediariesTab" class="md:w-48">
        <span class="sr-only">Filtre statut</span>
        <select
          :value="publicationStatus ?? ''"
          class="w-full rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          aria-label="Filtre statut de publication"
          @change="onPublicationStatusChange"
        >
          <option value="">Tous les statuts</option>
          <option value="published">Publié</option>
          <option value="draft">Brouillon</option>
          <option value="deprecated">Déprécié</option>
        </select>
      </label>

      <label v-if="isFundIntermediariesTab" class="md:w-48">
        <span class="sr-only">Filtre état</span>
        <select
          :value="status"
          class="w-full rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          aria-label="Filtre état d'accréditation"
          @change="onStatusChange"
        >
          <option value="all">Tous les états</option>
          <option value="active">Actives</option>
          <option value="expired">Expirées</option>
        </select>
      </label>

      <label class="md:w-56">
        <span class="sr-only">Tri</span>
        <select
          :value="sort"
          class="w-full rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          aria-label="Tri"
          @change="onSortChange"
        >
          <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <div class="flex items-center gap-2">
        <button
          type="button"
          class="rounded-md border border-gray-300 dark:border-dark-border px-3 py-2 text-sm font-medium text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          @click="emit('reset')"
        >
          Réinitialiser
        </button>
        <button
          type="button"
          :disabled="!exportEnabled"
          class="rounded-md bg-red-700 px-3 py-2 text-sm font-semibold text-white hover:bg-red-800 dark:bg-red-800 dark:hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          @click="emit('export')"
        >
          Exporter CSV
        </button>
      </div>
    </div>

    <p class="text-xs text-gray-600 dark:text-gray-400" aria-live="polite">
      <span class="font-semibold text-surface-text dark:text-surface-dark-text">{{ filteredCount }}</span>
      résultat{{ filteredCount > 1 ? 's' : '' }} sur {{ total }} élément{{ total > 1 ? 's' : '' }}.
    </p>
  </div>
</template>
