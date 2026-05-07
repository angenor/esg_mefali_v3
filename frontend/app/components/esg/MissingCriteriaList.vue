<script setup lang="ts">
/**
 * F13 — Liste des critères manquants pour un référentiel.
 *
 * Chaque critère est cliquable et ouvre une modale avec définition,
 * <SourceLink> F01 et suggestion d'indicateur Mefali à renseigner.
 */
import { ref } from 'vue'
import type { MissingCriterion } from '~/types/esg'

interface Props {
  criteria: MissingCriterion[]
  referentialName: string
}

defineProps<Props>()

const selectedCriterion = ref<MissingCriterion | null>(null)

function openDetail(criterion: MissingCriterion) {
  selectedCriterion.value = criterion
}

function closeDetail() {
  selectedCriterion.value = null
}

function reasonLabel(reason: string): string {
  switch (reason) {
    case 'non_renseigne':
      return 'Non renseigné'
    case 'invalide':
      return 'Donnée invalide'
    case 'hors_scope':
      return 'Hors scope'
    default:
      return reason
  }
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4">
    <h3 class="mb-3 text-base font-semibold text-surface-text dark:text-surface-dark-text">
      Critères manquants ({{ criteria.length }})
    </h3>

    <ul v-if="criteria.length > 0" role="list" class="space-y-2">
      <li
        v-for="criterion in criteria"
        :key="criterion.indicator_code"
        class="rounded-md border border-gray-100 dark:border-dark-border bg-gray-50 dark:bg-dark-input p-3"
      >
        <button
          type="button"
          class="w-full text-left flex flex-col gap-1 hover:opacity-80 transition focus:outline-none focus:ring-2 focus:ring-primary rounded-md"
          @click="openDetail(criterion)"
          :aria-label="`Voir le détail du critère ${criterion.indicator_code}`"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium text-surface-text dark:text-surface-dark-text">
              {{ criterion.indicator_code }}
            </span>
            <span class="rounded-full bg-orange-100 dark:bg-orange-900/40 px-2 py-0.5 text-xs text-orange-700 dark:text-orange-300">
              {{ reasonLabel(criterion.reason) }}
            </span>
          </div>
          <p
            v-if="criterion.suggestion"
            class="text-xs text-gray-600 dark:text-gray-400"
          >
            {{ criterion.suggestion }}
          </p>
        </button>
      </li>
    </ul>

    <p v-else class="text-sm text-gray-500 dark:text-gray-400">
      Aucun critère manquant pour {{ referentialName }}.
    </p>

    <!-- Modale détail critère -->
    <div
      v-if="selectedCriterion"
      role="dialog"
      aria-modal="true"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="closeDetail"
    >
      <div class="max-w-lg w-full rounded-lg bg-white dark:bg-dark-card p-6 shadow-xl">
        <h4 class="mb-2 text-lg font-semibold text-surface-text dark:text-surface-dark-text">
          {{ selectedCriterion.indicator_code }}
        </h4>
        <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">
          {{ reasonLabel(selectedCriterion.reason) }} — {{ referentialName }}
        </p>
        <p
          v-if="selectedCriterion.suggestion"
          class="mb-4 text-sm text-surface-text dark:text-surface-dark-text"
        >
          {{ selectedCriterion.suggestion }}
        </p>

        <div
          v-if="selectedCriterion.source_id"
          class="mb-4 rounded-md bg-gray-50 dark:bg-dark-input p-3 text-sm"
        >
          <p class="font-medium text-surface-text dark:text-surface-dark-text">
            Source officielle
          </p>
          <p class="text-xs text-gray-600 dark:text-gray-400">
            ID : {{ selectedCriterion.source_id }}
          </p>
        </div>

        <button
          type="button"
          class="w-full rounded-md bg-primary text-white px-3 py-2 text-sm font-medium hover:bg-primary/90 transition"
          @click="closeDetail"
        >
          Fermer
        </button>
      </div>
    </div>
  </div>
</template>
