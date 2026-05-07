<script setup lang="ts">
import { computed } from 'vue'
import {
  MATURITY_LABELS,
  STATUS_LABELS,
  type ProjectSummary,
} from '~/types/project'

interface Props {
  project: ProjectSummary
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'view-applications': [id: string]
  'view-detail': [id: string]
}>()

const statusLabel = computed(() => STATUS_LABELS[props.project.status])
const maturityLabel = computed(() =>
  props.project.maturity ? MATURITY_LABELS[props.project.maturity] : null,
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

function onViewApplications() {
  emit('view-applications', props.project.id)
}

function onViewDetail() {
  emit('view-detail', props.project.id)
}
</script>

<template>
  <article
    role="article"
    :aria-label="`Projet ${project.name}`"
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5 hover:shadow-md transition-shadow"
  >
    <!-- Header -->
    <div class="flex items-start justify-between gap-3 mb-3">
      <h3
        class="text-base font-semibold text-surface-text dark:text-surface-dark-text line-clamp-2 cursor-pointer hover:text-brand-green dark:hover:text-emerald-400"
        @click="onViewDetail"
      >
        {{ project.name }}
      </h3>
      <span
        class="shrink-0 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
        :class="statusColorClass"
      >
        {{ statusLabel }}
      </span>
    </div>

    <!-- Auto-generated badge -->
    <div v-if="project.auto_generated" class="mb-2">
      <span
        class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400 border border-amber-200 dark:border-amber-800/40"
      >
        Projet généré automatiquement — à compléter
      </span>
    </div>

    <!-- Maturity -->
    <div v-if="maturityLabel" class="mb-3">
      <span class="text-xs text-gray-500 dark:text-gray-400">
        Maturité :
      </span>
      <span class="text-sm font-medium text-surface-text dark:text-surface-dark-text">
        {{ maturityLabel }}
      </span>
    </div>

    <!-- Target amount -->
    <div v-if="project.target_amount" class="mb-3">
      <span class="text-xs text-gray-500 dark:text-gray-400 block">
        Montant cible
      </span>
      <MoneyDisplay :money="project.target_amount" />
    </div>

    <!-- Impact badges -->
    <div class="mb-4">
      <ProjectImpactBadges :project="project" />
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-dark-border">
      <button
        type="button"
        :disabled="project.applications_count === 0"
        class="text-sm font-medium text-brand-green dark:text-emerald-400 hover:underline disabled:opacity-50 disabled:cursor-not-allowed disabled:no-underline"
        @click="onViewApplications"
      >
        Voir candidatures
        <span
          v-if="project.applications_count > 0"
          class="ml-1 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-bold bg-brand-green text-white"
        >
          {{ project.applications_count }}
        </span>
      </button>
      <button
        type="button"
        class="text-sm text-gray-500 dark:text-gray-400 hover:text-brand-green dark:hover:text-emerald-400"
        @click="onViewDetail"
      >
        Détails →
      </button>
    </div>
  </article>
</template>
