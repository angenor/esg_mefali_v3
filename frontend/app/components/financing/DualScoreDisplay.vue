<script setup lang="ts">
// F045 — DualScoreDisplay : 2 scores cote a cote (project / company) + badge divergence.
//
// Dark mode complet, ARIA region+labelledby.

import { computed } from 'vue'
import DivergenceBadge from '~/components/financing/DivergenceBadge.vue'

interface Props {
  projectScore: number
  companyScore: number
  /** Paragraphe FR gabarit (R6) issu de backend. */
  divergenceExplanation?: string | null
}

const props = defineProps<Props>()

function scoreColorClass(score: number): string {
  if (score >= 75) return 'text-emerald-700 dark:text-emerald-300'
  if (score >= 50) return 'text-amber-700 dark:text-amber-300'
  return 'text-rose-700 dark:text-rose-300'
}

function bgColorClass(score: number): string {
  if (score >= 75) return 'bg-emerald-50 dark:bg-emerald-900/20'
  if (score >= 50) return 'bg-amber-50 dark:bg-amber-900/20'
  return 'bg-rose-50 dark:bg-rose-900/20'
}

const projectColor = computed(() => scoreColorClass(props.projectScore))
const projectBg = computed(() => bgColorClass(props.projectScore))
const companyColor = computed(() => scoreColorClass(props.companyScore))
const companyBg = computed(() => bgColorClass(props.companyScore))
</script>

<template>
  <section
    role="region"
    aria-labelledby="dual-score-title"
    class="rounded-xl border border-gray-200 bg-white p-4
           dark:border-dark-border dark:bg-dark-card"
  >
    <h3
      id="dual-score-title"
      class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3"
    >
      Mon score pour ce projet
    </h3>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
      <div
        :class="['rounded-lg p-3 flex flex-col items-center', projectBg]"
        role="group"
        aria-label="Score projet"
      >
        <span class="text-[11px] uppercase tracking-wide text-gray-600 dark:text-gray-400">
          Match projet
        </span>
        <span
          :class="['text-3xl font-bold', projectColor]"
          aria-label="Score projet en pourcentage"
          :title="`${projectScore}% de compatibilité projet`"
        >
          {{ projectScore }}%
        </span>
      </div>

      <div
        :class="['rounded-lg p-3 flex flex-col items-center', companyBg]"
        role="group"
        aria-label="Score entreprise"
      >
        <span class="text-[11px] uppercase tracking-wide text-gray-600 dark:text-gray-400">
          Match entreprise
        </span>
        <span
          :class="['text-3xl font-bold', companyColor]"
          aria-label="Score entreprise en pourcentage"
          :title="`${companyScore}% de compatibilité entreprise`"
        >
          {{ companyScore }}%
        </span>
      </div>
    </div>

    <div class="mb-3">
      <DivergenceBadge
        :project-score="projectScore"
        :company-score="companyScore"
        :tooltip-text="divergenceExplanation ?? undefined"
      />
    </div>

    <p
      v-if="divergenceExplanation"
      class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed"
    >
      {{ divergenceExplanation }}
    </p>
  </section>
</template>
