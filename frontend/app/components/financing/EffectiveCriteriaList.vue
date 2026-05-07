<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  criteria: Record<string, unknown>
}

const props = defineProps<Props>()

const entries = computed<Array<[string, unknown]>>(() => {
  return Object.entries(props.criteria || {}).filter(([, v]) => v !== null && v !== undefined)
})

function formatLabel(key: string): string {
  const labels: Record<string, string> = {
    min_company_age: 'Âge minimum de l\'entreprise',
    max_company_age: 'Âge maximum de l\'entreprise',
    min_revenue: 'Chiffre d\'affaires minimum',
    max_revenue: 'Chiffre d\'affaires maximum',
    max_company_revenue: 'Chiffre d\'affaires maximum',
    sectors: 'Secteurs éligibles',
    countries: 'Pays éligibles',
    min_employees: 'Effectif minimum',
    max_employees: 'Effectif maximum',
    min_esg_score: 'Score ESG minimum',
  }
  return labels[key] ?? key.replace(/_/g, ' ')
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(', ') || '—'
  }
  if (typeof value === 'number') {
    return value.toLocaleString('fr-FR')
  }
  if (value === null || value === undefined) {
    return '—'
  }
  return String(value)
}
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
      Critères effectifs
    </h3>
    <div v-if="entries.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
      Aucun critère spécifique défini.
    </div>
    <ul v-else class="divide-y divide-gray-200 dark:divide-dark-border" role="list">
      <li
        v-for="[key, value] in entries"
        :key="key"
        class="flex items-start justify-between gap-4 py-2.5"
      >
        <span class="text-sm text-gray-600 dark:text-gray-400">
          {{ formatLabel(key) }}
        </span>
        <span class="text-sm font-medium text-gray-900 dark:text-white text-right">
          {{ formatValue(value) }}
        </span>
      </li>
    </ul>
  </div>
</template>
