<script setup lang="ts">
/**
 * F047 — Affichage du score 0..100 + breakdown par standard.
 */
import { computed } from 'vue'
import type { ProjectEsgAssessmentRead } from '~/types/projectEsg'

interface Props {
  assessment: ProjectEsgAssessmentRead
  compact?: boolean
}
const props = defineProps<Props>()

const score = computed(() => props.assessment.score ?? 0)
const ringColor = computed(() => {
  if (score.value >= 75) return 'ring-emerald-500'
  if (score.value >= 50) return 'ring-amber-500'
  return 'ring-red-500'
})

const pillars = computed(() =>
  Object.entries(props.assessment.pillar_scores || {}).sort(([a], [b]) =>
    a.localeCompare(b),
  ),
)

const coveragePercent = computed(() => {
  const r = props.assessment.coverage_rate
  return r ? Math.round(parseFloat(r) * 100) : 0
})
</script>

<template>
  <div
    role="region"
    aria-label="Score ESG-projet"
    class="rounded-lg ring-1 ring-gray-200 dark:ring-dark-border bg-white dark:bg-dark-card p-4"
  >
    <div :class="['flex items-center gap-4', compact ? 'flex-row' : 'flex-col md:flex-row']">
      <div
        :class="[
          'flex items-center justify-center rounded-full ring-4',
          ringColor,
          compact ? 'w-16 h-16 text-xl' : 'w-24 h-24 text-3xl',
          'font-bold text-surface-text dark:text-surface-dark-text',
        ]"
      >
        {{ score }}
      </div>
      <div class="flex-1">
        <h3 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text">
          Score ESG-projet
        </h3>
        <p class="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
          Couverture : {{ coveragePercent }}%
          ({{ assessment.covered_criteria.length }} critères couverts,
          {{ assessment.missing_criteria.length }} manquants)
        </p>
        <p
          v-if="assessment.finalized_at"
          class="text-[10px] text-gray-500 mt-0.5"
        >
          Finalisée le {{ new Date(assessment.finalized_at).toLocaleDateString('fr-FR') }}
        </p>
      </div>
    </div>

    <div v-if="!compact && pillars.length" class="mt-4 pt-3 border-t border-gray-100 dark:border-dark-border">
      <h4 class="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
        Détail par standard
      </h4>
      <ul class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <li
          v-for="[key, val] in pillars"
          :key="key"
          class="text-center p-2 rounded bg-gray-50 dark:bg-dark-hover"
        >
          <div class="text-[10px] uppercase tracking-wide text-gray-500">
            {{ key }}
          </div>
          <div class="text-sm font-semibold text-surface-text dark:text-surface-dark-text">
            {{ val }}
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
