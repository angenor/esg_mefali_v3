<script setup lang="ts">
/**
 * 050 — Rappel du projet vert auquel un dossier de candidature se rapporte
 * (lien 1:1, F06). Réutilisé dans l'en-tête de la page détail
 * (``variant="header"`` : encart cliquable vers ``/profile/projects/[id]``) et
 * sur la carte de la liste des dossiers (``variant="compact"`` : rappel discret
 * du nom, sans lien imbriqué car la carte est elle-même cliquable).
 */
import { computed } from 'vue'
import {
  OBJECTIVE_ENV_LABELS,
  STATUS_LABELS,
} from '~/types/project'
import type { ApplicationProjectInfo } from '~/stores/applications'

interface Props {
  project: ApplicationProjectInfo
  variant?: 'header' | 'compact'
}

const props = withDefaults(defineProps<Props>(), { variant: 'header' })

const statusLabel = computed(
  () => STATUS_LABELS[props.project.status] ?? props.project.status,
)

const objectiveLabels = computed(() =>
  props.project.objective_env
    .map(o => OBJECTIVE_ENV_LABELS[o] ?? o)
    .join(', '),
)

const statusColorClass = computed(() => {
  switch (props.project.status) {
    case 'draft':
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800/50 dark:text-gray-300'
    case 'seeking_funding':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
    case 'funded':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
    case 'in_execution':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
    case 'closed':
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
    case 'cancelled':
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800/50 dark:text-gray-300'
  }
})
</script>

<template>
  <!-- Mode compact : rappel discret sur une carte déjà cliquable (pas de lien
       imbriqué pour éviter un <a> dans un <a>). -->
  <span
    v-if="variant === 'compact'"
    class="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 min-w-0"
  >
    <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
    <span class="truncate">Projet : {{ project.name }}</span>
  </span>

  <!-- Mode header : encart projet avec lien vers la fiche détaillée. -->
  <div
    v-else
    class="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h3 class="text-sm font-semibold text-emerald-700 dark:text-emerald-300 mb-1">
          Projet
        </h3>
        <NuxtLink
          :to="`/profile/projects/${project.id}`"
          class="inline-flex items-center gap-1 text-base font-semibold text-emerald-800 dark:text-emerald-200 hover:underline"
        >
          {{ project.name }}
          <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </NuxtLink>
        <p
          v-if="objectiveLabels"
          class="text-xs text-emerald-600 dark:text-emerald-400 mt-1"
        >
          {{ objectiveLabels }}
        </p>
      </div>
      <span
        class="shrink-0 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
        :class="statusColorClass"
      >
        {{ statusLabel }}
      </span>
    </div>
  </div>
</template>
