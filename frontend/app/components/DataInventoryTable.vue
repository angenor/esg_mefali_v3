<script setup lang="ts">
import { computed } from 'vue'
import type {
  InventoryCounts,
  InventoryLastModified,
} from '~/composables/useDataPrivacy'

interface Props {
  counts: InventoryCounts
  lastModified: InventoryLastModified
}

const props = defineProps<Props>()

interface Row {
  key: keyof InventoryCounts
  label: string
}

const ROWS: Row[] = [
  { key: 'profile', label: 'Profil entreprise' },
  { key: 'projects', label: 'Projets verts' },
  { key: 'applications', label: 'Candidatures financements' },
  { key: 'esg_assessments', label: 'Évaluations ESG' },
  { key: 'carbon_assessments', label: 'Bilans carbone' },
  { key: 'credit_scores', label: 'Scores crédit' },
  { key: 'documents', label: 'Documents uploadés' },
  { key: 'conversations', label: 'Conversations chat' },
  { key: 'messages', label: 'Messages chat' },
  { key: 'attestations', label: 'Attestations crédit' },
  { key: 'consents', label: 'Consentements' },
]

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
</script>

<template>
  <div
    class="overflow-x-auto rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card"
    role="region"
    aria-label="Inventaire de mes données"
  >
    <table class="min-w-full divide-y divide-gray-200 dark:divide-dark-border">
      <thead class="bg-gray-50 dark:bg-dark-hover">
        <tr>
          <th
            scope="col"
            class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300"
          >
            Catégorie
          </th>
          <th
            scope="col"
            class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300"
          >
            Nombre
          </th>
          <th
            scope="col"
            class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300"
          >
            Dernière modification
          </th>
        </tr>
      </thead>
      <tbody
        class="divide-y divide-gray-200 dark:divide-dark-border bg-white dark:bg-dark-card"
      >
        <tr
          v-for="row in ROWS"
          :key="row.key"
          class="hover:bg-gray-50 dark:hover:bg-dark-hover"
        >
          <td
            class="px-4 py-3 text-sm text-surface-text dark:text-surface-dark-text"
          >
            {{ row.label }}
          </td>
          <td
            class="px-4 py-3 text-right text-sm font-medium tabular-nums text-surface-text dark:text-surface-dark-text"
          >
            {{ props.counts[row.key] ?? 0 }}
          </td>
          <td
            class="px-4 py-3 text-right text-sm text-gray-600 dark:text-gray-400"
          >
            {{ formatDate(props.lastModified[row.key]) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
