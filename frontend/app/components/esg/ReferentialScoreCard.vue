<script setup lang="ts">
/**
 * F13 — Carte de score d'un référentiel ESG.
 *
 * Affiche le score global, le radar par pilier, le badge coverage, le
 * bouton « Inclure dans rapport PDF » (désactivé si coverage < 50%).
 */
import { computed } from 'vue'
import type { ReferentialScore } from '~/types/esg'
import ScoreCircle from './ScoreCircle.vue'

interface Props {
  score: ReferentialScore
  /** Affiche le bouton « Inclure dans rapport PDF » (false par défaut). */
  showIncludeInReport?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showIncludeInReport: false,
})

const emit = defineEmits<{
  'include-in-report': [referentialCode: string]
}>()

const coveragePercent = computed(() =>
  Math.round((props.score.coverage_rate ?? 0) * 100),
)

const coverageInsufficient = computed(() => coveragePercent.value < 50)

const displayedScore = computed(() => props.score.overall_score ?? 0)

const eligibilityBadge = computed(() => {
  if (props.score.eligibility === null) return null
  return props.score.eligibility ? 'eligible' : 'non-eligible'
})

const visibleCard = computed(() => props.score.overall_score !== null)

function handleIncludeInReport() {
  emit('include-in-report', props.score.referential_code)
}
</script>

<template>
  <div
    v-if="visibleCard"
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 shadow-sm"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1">
        <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text">
          {{ score.referential_name }}
        </h3>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Version {{ score.referential_version }}
        </p>
        <p
          v-if="score.is_fallback"
          class="mt-2 inline-block rounded-md bg-blue-50 dark:bg-blue-900/30 px-2 py-1 text-xs text-blue-700 dark:text-blue-300"
        >
          Référentiel Mefali — fallback
        </p>
      </div>

      <ScoreCircle :score="displayedScore" :max="100" :size="100" />
    </div>

    <!-- Badge coverage si < 50% -->
    <div
      v-if="coverageInsufficient"
      role="alert"
      class="mt-4 rounded-md border border-orange-200 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/30 px-3 py-2 text-sm text-orange-700 dark:text-orange-300"
    >
      Couverture indicateurs : {{ coveragePercent }} % — score indicatif
    </div>

    <!-- Pilier scores -->
    <div v-if="score.pillar_scores" class="mt-4 space-y-2">
      <div
        v-for="(pillar, key) in score.pillar_scores"
        :key="key"
        class="flex items-center justify-between text-sm"
      >
        <span class="text-surface-text dark:text-surface-dark-text capitalize">
          {{ key }}
        </span>
        <span class="font-medium text-surface-text dark:text-surface-dark-text">
          {{ Math.round(pillar.score) }} / 100
        </span>
      </div>
    </div>

    <!-- Critères couverts/manquants -->
    <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
      <div class="rounded-md bg-green-50 dark:bg-green-900/30 p-2 text-green-700 dark:text-green-300">
        <span class="font-medium">{{ score.covered_criteria.length }}</span> critère(s) couvert(s)
      </div>
      <div class="rounded-md bg-red-50 dark:bg-red-900/30 p-2 text-red-700 dark:text-red-300">
        <span class="font-medium">{{ score.missing_criteria.length }}</span> critère(s) manquant(s)
      </div>
    </div>

    <!-- Eligibilité -->
    <div v-if="eligibilityBadge" class="mt-3">
      <span
        v-if="eligibilityBadge === 'eligible'"
        class="inline-block rounded-full bg-green-100 dark:bg-green-900/40 px-3 py-1 text-xs font-medium text-green-700 dark:text-green-300"
      >
        Éligible
      </span>
      <span
        v-else
        class="inline-block rounded-full bg-red-100 dark:bg-red-900/40 px-3 py-1 text-xs font-medium text-red-700 dark:text-red-300"
      >
        Non éligible actuellement
      </span>
    </div>

    <!-- Bouton inclure dans rapport PDF -->
    <button
      v-if="showIncludeInReport"
      type="button"
      :disabled="coverageInsufficient"
      :title="coverageInsufficient ? 'Couverture insuffisante (< 50 %). Renseignez plus d\'indicateurs.' : ''"
      @click="handleIncludeInReport"
      class="mt-4 w-full rounded-md border border-primary bg-primary text-white px-3 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition"
    >
      Inclure dans rapport PDF
    </button>
  </div>

  <div
    v-else
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-card p-6 text-center text-sm text-gray-500 dark:text-gray-400"
  >
    Score non calculable pour {{ score.referential_name }} (couverture insuffisante).
  </div>
</template>
