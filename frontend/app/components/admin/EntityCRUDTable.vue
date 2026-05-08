<script setup lang="ts" generic="T extends Record<string, unknown>">
// F09 PRIO 3 — Tableau CRUD générique pour le catalogue admin.
//
// Réutilisé par les 8 sections catalogue (funds, intermediaries, offers,
// referentials, indicators, criteria, emission_factors, simulation_factors).
//
// Props :
// - columns : définition des colonnes (key, label, formatter optionnel)
// - rows : données déjà chargées (le parent gère le fetch)
// - total : nombre total (pagination)
// - page / pageSize : état pagination courant
// - loading : état de chargement
// - searchQuery / searchPlaceholder : binding recherche
// - emptyMessage : libellé si aucune ligne
//
// Émets :
// - row-click(row) : double-clic pour naviguer vers la fiche
// - page-change(newPage) : pagination
// - search(query) : recherche
import { computed } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'

interface Column<T> {
  key: keyof T | string
  label: string
  formatter?: (value: unknown, row: T) => string
  type?: 'text' | 'status' | 'date' | 'badge'
}

interface Props {
  columns: Column<T>[]
  rows: T[]
  total: number
  page: number
  pageSize: number
  loading?: boolean
  searchQuery?: string
  searchPlaceholder?: string
  emptyMessage?: string
  showSearch?: boolean
  rowKeyField?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  searchQuery: '',
  searchPlaceholder: 'Rechercher…',
  emptyMessage: 'Aucun élément.',
  showSearch: true,
  rowKeyField: 'id',
})

const emit = defineEmits<{
  (e: 'row-click', row: T): void
  (e: 'page-change', page: number): void
  (e: 'search', query: string): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

function formatCell(col: Column<T>, row: T): string {
  const raw = row[col.key as keyof T]
  if (col.formatter) return col.formatter(raw, row)
  if (raw === null || raw === undefined || raw === '') return '—'
  if (col.type === 'date' && typeof raw === 'string') {
    try {
      return new Date(raw).toLocaleDateString('fr-FR')
    } catch {
      return String(raw)
    }
  }
  return String(raw)
}

function onSearchInput(event: Event) {
  const value = (event.target as HTMLInputElement).value
  emit('search', value)
}

function onPrev() {
  if (props.page > 1) emit('page-change', props.page - 1)
}

function onNext() {
  if (props.page < totalPages.value) emit('page-change', props.page + 1)
}
</script>

<template>
  <div class="space-y-4">
    <!-- Barre de recherche -->
    <div v-if="showSearch" class="flex items-center gap-2">
      <input
        type="search"
        :value="searchQuery"
        :placeholder="searchPlaceholder"
        class="flex-1 rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-4 py-2 text-sm text-surface-text dark:text-surface-dark-text placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:focus:ring-emerald-400"
        :aria-label="searchPlaceholder"
        data-testid="admin-crud-search"
        @input="onSearchInput"
      />
      <span class="text-xs text-gray-500 dark:text-gray-400">
        {{ total }} {{ total > 1 ? 'éléments' : 'élément' }}
      </span>
    </div>

    <!-- Tableau -->
    <div
      class="overflow-hidden rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card"
    >
      <table class="w-full text-sm">
        <thead class="bg-gray-50 dark:bg-gray-800/40 text-left">
          <tr>
            <th
              v-for="col in columns"
              :key="String(col.key)"
              class="px-4 py-2 font-semibold text-surface-text dark:text-surface-dark-text"
              scope="col"
            >
              {{ col.label }}
            </th>
            <th class="px-4 py-2 sr-only">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td
              :colspan="columns.length + 1"
              class="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
            >
              Chargement…
            </td>
          </tr>
          <tr
            v-else-if="rows.length === 0"
            data-testid="admin-crud-empty"
          >
            <td
              :colspan="columns.length + 1"
              class="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
            >
              {{ emptyMessage }}
            </td>
          </tr>
          <tr
            v-for="row in rows"
            v-else
            :key="String(row[rowKeyField as keyof T])"
            class="border-t border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover cursor-pointer"
            data-testid="admin-crud-row"
            @click="emit('row-click', row)"
          >
            <td
              v-for="col in columns"
              :key="String(col.key)"
              class="px-4 py-2 text-surface-text dark:text-surface-dark-text"
            >
              <StatusBadge
                v-if="col.type === 'status' && typeof row[col.key as keyof T] === 'string'"
                :variant="String(row[col.key as keyof T]) as 'draft' | 'published'"
              />
              <slot
                v-else
                :name="`cell-${String(col.key)}`"
                :row="row"
                :value="row[col.key as keyof T]"
              >
                {{ formatCell(col, row) }}
              </slot>
            </td>
            <td class="px-4 py-2 text-right">
              <slot name="row-actions" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div
      v-if="total > pageSize"
      class="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400"
    >
      <span>
        Page {{ page }} sur {{ totalPages }}
      </span>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="rounded-lg border border-gray-300 dark:border-dark-border px-3 py-1 hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="page <= 1"
          data-testid="admin-crud-prev"
          @click="onPrev"
        >
          Précédent
        </button>
        <button
          type="button"
          class="rounded-lg border border-gray-300 dark:border-dark-border px-3 py-1 hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="page >= totalPages"
          data-testid="admin-crud-next"
          @click="onNext"
        >
          Suivant
        </button>
      </div>
    </div>
  </div>
</template>
