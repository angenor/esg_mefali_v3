<script setup lang="ts">
// Carte résumé financement vert pour le dashboard
import SourceLink from '~/components/sources/SourceLink.vue'
import type { FinancingSummary } from '~/types/dashboard'

interface Props {
  financing: FinancingSummary | null
  sourceId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  sourceId: null,
})

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

// Couleur badge statut candidature
function statusColor(status: string): string {
  switch (status) {
    case 'accepted': return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
    case 'submitted_to_fund':
    case 'submitted_to_intermediary': return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
    case 'under_review':
    case 'review': return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
    case 'rejected': return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
    default: return 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
  }
}

// Libellé français d'un statut
function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'Brouillon',
    preparing_documents: 'Préparation',
    in_progress: 'En cours',
    review: 'Relecture',
    ready_for_intermediary: 'Prêt (intermédiaire)',
    ready_for_fund: 'Prêt (fonds)',
    submitted_to_intermediary: 'Soumis (intermédiaire)',
    submitted_to_fund: 'Soumis (fonds)',
    under_review: 'En examen',
    accepted: 'Accepté',
    rejected: 'Refusé',
  }
  return labels[status] ?? status
}
</script>

<template>
  <div
    class="bg-white dark:bg-dark-card rounded-xl shadow-sm border border-gray-200 dark:border-dark-border p-5 flex flex-col gap-3"
  >
    <!-- En-tête -->
    <div class="flex items-center gap-2">
      <span class="text-xl">💰</span>
      <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Financement vert</span>
    </div>

    <!-- Contenu si données disponibles -->
    <template v-if="financing">
      <!-- Compteurs -->
      <div class="flex gap-4">
        <div class="flex flex-col">
          <span class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
            {{ financing.recommended_funds_count }}
            <!-- F01 picto source cliquable sur les chiffres financement -->
            <SourceLink
              v-if="sourceId"
              :source-id="sourceId"
              aria-label="Voir la source des donnees financement"
              @open="(id) => emit('open-source', id)"
            />
          </span>
          <span class="text-xs text-gray-500 dark:text-gray-500">Fonds recommandés</span>
        </div>
        <div class="flex flex-col">
          <span class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
            {{ financing.active_applications_count }}
          </span>
          <span class="text-xs text-gray-500 dark:text-gray-500">Candidatures actives</span>
        </div>
      </div>

      <!-- Statuts des candidatures -->
      <div
        v-if="Object.keys(financing.application_statuses).length > 0"
        class="flex flex-wrap gap-1"
      >
        <span
          v-for="(count, status) in financing.application_statuses"
          :key="status"
          :class="['text-xs px-2 py-0.5 rounded-full font-medium', statusColor(status)]"
        >
          {{ statusLabel(status) }} ({{ count }})
        </span>
      </div>

      <!-- Prochaine action intermédiaire -->
      <div
        v-if="financing.next_intermediary_action"
        class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 border border-blue-100 dark:border-blue-800"
      >
        <div class="flex items-start gap-2">
          <span class="text-base mt-0.5">🏦</span>
          <div>
            <p class="text-xs font-semibold text-blue-700 dark:text-blue-300">
              {{ financing.next_intermediary_action.title }}
            </p>
            <p
              v-if="financing.next_intermediary_action.intermediary_name"
              class="text-xs text-blue-600 dark:text-blue-400 mt-0.5"
            >
              {{ financing.next_intermediary_action.intermediary_name }}
            </p>
          </div>
        </div>
      </div>

      <!-- Chemins via intermédiaires -->
      <div v-if="financing.has_intermediary_paths" class="flex items-center gap-1">
        <span class="text-green-500 text-xs">✓</span>
        <span class="text-xs text-gray-500 dark:text-gray-500">Chemins d'accès identifiés</span>
      </div>
    </template>

    <!-- État vide -->
    <template v-else>
      <p class="text-sm text-gray-400 dark:text-gray-600">
        Aucune donnée de financement disponible.
      </p>
      <NuxtLink
        to="/financing"
        class="text-xs text-green-600 dark:text-green-400 hover:underline"
      >
        Découvrir les fonds →
      </NuxtLink>
    </template>
  </div>
</template>
