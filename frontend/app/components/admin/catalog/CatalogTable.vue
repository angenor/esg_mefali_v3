<script setup lang="ts">
// F25 — Tableau générique du catalogue admin.
// Les colonnes sont configurées via la prop `columns`. Pagination affichée
// uniquement quand `paginated=true` (FR-013a). Badge d'incohérence rendu
// pour chaque ligne avec `has_incoherence=true`.
import CatalogIncoherenceBadge from './CatalogIncoherenceBadge.vue'
import type { CatalogRow, PaginatedListResponse } from '~/types/adminCatalog'

interface Column {
  key: string
  label: string
  format?: (row: CatalogRow) => string | null | undefined
  ariaSort?: 'ascending' | 'descending' | 'none' | 'other'
}

interface Props {
  rows: CatalogRow[]
  columns: Column[]
  data: PaginatedListResponse<CatalogRow> | null
  rowLink?: (row: CatalogRow) => string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), { loading: false })

const emit = defineEmits<{
  (event: 'change-page', page: number): void
}>()

function valueOf(row: CatalogRow, col: Column): string {
  if (col.format) return col.format(row) ?? '—'
  const v = (row as unknown as Record<string, unknown>)[col.key]
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}

function statusLabel(value: string | null): string {
  switch (value) {
    case 'published':
      return 'Publié'
    case 'draft':
      return 'Brouillon'
    case 'deprecated':
      return 'Déprécié'
    default:
      return value ?? '—'
  }
}

function statusClasses(value: string | null): string {
  switch (value) {
    case 'published':
      return 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 ring-emerald-300 dark:ring-emerald-700'
    case 'draft':
      return 'bg-gray-100 dark:bg-dark-hover text-gray-700 dark:text-gray-300 ring-gray-300 dark:ring-gray-600'
    case 'deprecated':
      return 'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-200 ring-rose-300 dark:ring-rose-700'
    default:
      return 'bg-gray-100 dark:bg-dark-hover text-gray-700 dark:text-gray-300 ring-gray-300 dark:ring-gray-600'
  }
}
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card">
    <table class="min-w-full divide-y divide-gray-200 dark:divide-dark-border">
      <thead class="bg-gray-50 dark:bg-dark-hover">
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            scope="col"
            class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300"
          >
            {{ col.label }}
          </th>
          <th scope="col" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
            Action
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-200 dark:divide-dark-border">
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
            Chargement…
          </td>
        </tr>
        <tr
          v-for="row in rows"
          v-else
          :key="row.id"
          class="hover:bg-gray-50 dark:hover:bg-dark-hover focus-within:bg-gray-50 dark:focus-within:bg-dark-hover"
        >
          <td v-for="col in columns" :key="col.key" class="px-4 py-3 text-sm text-surface-text dark:text-surface-dark-text">
            <template v-if="col.key === 'publication_status'">
              <span
                class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1"
                :class="statusClasses((row as unknown as Record<string, string | null>)['publication_status'])"
              >
                {{ statusLabel((row as unknown as Record<string, string | null>)['publication_status']) }}
              </span>
            </template>
            <template v-else-if="col.key === 'has_incoherence'">
              <CatalogIncoherenceBadge v-if="(row as { has_incoherence?: boolean }).has_incoherence" />
              <span v-else class="text-xs text-gray-400 dark:text-gray-500">—</span>
            </template>
            <template v-else>
              {{ valueOf(row, col) }}
            </template>
          </td>
          <td class="px-4 py-3 text-right text-sm">
            <NuxtLink
              v-if="rowLink"
              :to="rowLink(row)"
              class="inline-flex items-center text-red-700 dark:text-red-300 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              :aria-label="`Ouvrir ${row.name ?? row.id}`"
            >
              Ouvrir
            </NuxtLink>
          </td>
        </tr>
      </tbody>
    </table>

    <div
      v-if="data?.paginated"
      class="flex items-center justify-between border-t border-gray-200 dark:border-dark-border px-4 py-3 text-sm text-gray-600 dark:text-gray-400"
    >
      <span>Page {{ data.page }} ({{ data.page_size }} par page)</span>
      <div class="flex items-center gap-2">
        <button
          type="button"
          :disabled="data.page <= 1"
          class="rounded border border-gray-300 dark:border-dark-border px-2 py-1 disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-dark-hover"
          @click="emit('change-page', data.page - 1)"
        >
          Précédente
        </button>
        <button
          type="button"
          :disabled="data.items.length < data.page_size"
          class="rounded border border-gray-300 dark:border-dark-border px-2 py-1 disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-dark-hover"
          @click="emit('change-page', data.page + 1)"
        >
          Suivante
        </button>
      </div>
    </div>
  </div>
</template>
