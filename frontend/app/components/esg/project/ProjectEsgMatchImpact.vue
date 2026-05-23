<script setup lang="ts">
/**
 * F047 (US4 — étape 7) — Bloc « Impact sur le matching » affiché après la
 * finalisation d'une évaluation ESG-projet. Réutilise <DualScoreDisplay>
 * en sous-composant pour afficher les 2 scores avant/après.
 *
 * Dark mode + ARIA region.
 */
import DualScoreDisplay from '~/components/financing/DualScoreDisplay.vue'
import type { ProjectEsgSubScore } from '~/types/projectMatching'

interface MatchSnapshot {
  fund_name: string
  project_score: number
  company_score: number
  divergence_explanation?: string | null
  project_esg_subscore?: ProjectEsgSubScore | null
}

interface Props {
  before: MatchSnapshot | null
  after: MatchSnapshot
}

defineProps<Props>()
</script>

<template>
  <section
    role="region"
    aria-labelledby="match-impact-title"
    class="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4
           dark:border-emerald-800 dark:bg-emerald-900/10"
    data-testid="project-esg-match-impact"
  >
    <h3
      id="match-impact-title"
      class="mb-3 text-sm font-semibold text-emerald-900 dark:text-emerald-200"
    >
      Impact sur le matching — {{ after.fund_name }}
    </h3>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div v-if="before">
        <p class="mb-1 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Avant finalisation
        </p>
        <DualScoreDisplay
          :project-score="before.project_score"
          :company-score="before.company_score"
          :divergence-explanation="before.divergence_explanation"
          :project-esg-subscore="before.project_esg_subscore"
        />
      </div>
      <div v-else class="text-xs italic text-gray-500 dark:text-gray-400">
        Aucun matching pré-évaluation à comparer.
      </div>

      <div>
        <p class="mb-1 text-xs uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
          Après finalisation
        </p>
        <DualScoreDisplay
          :project-score="after.project_score"
          :company-score="after.company_score"
          :divergence-explanation="after.divergence_explanation"
          :project-esg-subscore="after.project_esg_subscore"
        />
      </div>
    </div>
  </section>
</template>
