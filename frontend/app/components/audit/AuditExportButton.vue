<script setup lang="ts">
// F03 — Bouton d'export CSV / JSON pour le log d'audit.
import { ref } from 'vue'
import type { AuditFilters } from '~/types/audit'
import { useAuditLog } from '~/composables/useAuditLog'

interface Props {
  filters: AuditFilters
}

const props = defineProps<Props>()
const { exportCsv, exportJson } = useAuditLog()

const open = ref(false)
const exporting = ref(false)
const error = ref<string | null>(null)

async function doExport(format: 'csv' | 'json') {
  exporting.value = true
  error.value = null
  try {
    if (format === 'csv') {
      await exportCsv(props.filters)
    } else {
      await exportJson(props.filters)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Erreur d'export"
  } finally {
    exporting.value = false
    open.value = false
  }
}
</script>

<template>
  <div class="relative inline-block">
    <button
      type="button"
      class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-dark-border dark:bg-dark-card dark:text-surface-dark-text dark:hover:bg-dark-hover"
      :disabled="exporting"
      :aria-expanded="open"
      aria-haspopup="menu"
      data-testid="export-button"
      @click="open = !open"
    >
      {{ exporting ? 'Export en cours...' : 'Exporter' }}
    </button>

    <div
      v-if="open"
      role="menu"
      class="absolute right-0 z-10 mt-1 w-40 rounded-md border border-gray-200 bg-white shadow-lg dark:border-dark-border dark:bg-dark-card"
    >
      <button
        type="button"
        role="menuitem"
        data-testid="export-csv"
        class="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-surface-dark-text dark:hover:bg-dark-hover"
        @click="doExport('csv')"
      >
        Format CSV (Excel)
      </button>
      <button
        type="button"
        role="menuitem"
        data-testid="export-json"
        class="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-surface-dark-text dark:hover:bg-dark-hover"
        @click="doExport('json')"
      >
        Format JSON
      </button>
    </div>

    <p
      v-if="error"
      class="mt-2 text-xs text-red-700 dark:text-red-400"
      role="alert"
    >
      {{ error }}
    </p>
  </div>
</template>
