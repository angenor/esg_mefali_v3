<script setup lang="ts">
// F14 — OffersCompatibleSection : section affichant les offres
// compatibles avec un projet. Liste de cartes match (score décomposé,
// bottleneck, action recommandée), bouton Comparer, empty state.
//
// Réutilise <MatchCardBlock> (F11) pour le rendu visuel quand un
// match enrichi est fourni avec fund_name / intermediary_name.

import { computed, ref } from 'vue'
import BottleneckBadge from '~/components/matching/BottleneckBadge.vue'
import type { OfferMatch } from '~/types/matching'

export interface EnrichedMatch extends OfferMatch {
  fundName: string
  intermediaryName: string
  amountRange?: string | null
  timeline?: string | null
  instruments?: string[] | null
  missingCriteriaCount?: number | null
  ctaLabel?: string
  drilldownUrl?: string
}

interface Props {
  matches: EnrichedMatch[]
  loading?: boolean
  total?: number
  projectId: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  total: 0,
})

const emit = defineEmits<{
  recompute: []
  navigate: [url: string]
  'view-all': [projectId: string]
  'compare-fund': [fundId: string]
}>()

// Top 5 affichés inline ; le reste via "Voir tous les matches"
const displayed = computed(() => props.matches.slice(0, 5))

const showAllLink = computed(() => (props.total ?? props.matches.length) > 5)

function onCompareFund(fundId: string) {
  emit('compare-fund', fundId)
}

function onCardClick(match: EnrichedMatch) {
  if (match.drilldownUrl) {
    emit('navigate', match.drilldownUrl)
  }
}

function scoreColor(score: number): string {
  if (score >= 75) return 'text-emerald-600 dark:text-emerald-400'
  if (score >= 50) return 'text-amber-600 dark:text-amber-400'
  return 'text-rose-600 dark:text-rose-400'
}

const sortedMatches = computed(() =>
  [...displayed.value].sort((a, b) => b.globalScore - a.globalScore),
)
</script>

<template>
  <section
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5"
    aria-labelledby="offers-compatible-heading"
    data-testid="offers-compatible-section"
  >
    <header class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2
          id="offers-compatible-heading"
          class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
        >
          Offres compatibles
        </h2>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Score décomposé fonds × intermédiaire pour ce projet.
        </p>
      </div>
      <button
        type="button"
        class="px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover focus:outline-none focus:ring-2 focus:ring-emerald-500"
        :disabled="loading"
        :aria-busy="loading"
        data-testid="recompute-matches-btn"
        @click="emit('recompute')"
      >
        {{ loading ? 'Recalcul…' : 'Recalculer' }}
      </button>
    </header>

    <div
      v-if="loading && matches.length === 0"
      class="flex items-center justify-center py-10"
      role="status"
      aria-label="Chargement des offres compatibles"
    >
      <div
        class="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"
        aria-hidden="true"
      />
    </div>

    <div
      v-else-if="matches.length === 0"
      class="rounded-md border border-dashed border-gray-300 dark:border-dark-border p-6 text-center"
      data-testid="offers-empty-state"
    >
      <p class="text-sm text-gray-600 dark:text-gray-400">
        Aucune offre compatible identifiée pour le moment.
      </p>
      <p class="mt-1 text-xs text-gray-500 dark:text-gray-500">
        Renseignez votre évaluation ESG et complétez votre projet pour
        améliorer le matching.
      </p>
    </div>

    <ul v-else role="list" class="space-y-3">
      <li
        v-for="match in sortedMatches"
        :key="match.id"
        :data-testid="`match-card-${match.id}`"
        class="rounded-md border border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-input/40 p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <button
              type="button"
              class="text-left text-sm font-semibold text-surface-text dark:text-surface-dark-text hover:text-emerald-700 dark:hover:text-emerald-400 focus:outline-none focus:underline"
              @click="onCardClick(match)"
            >
              {{ match.fundName }}
              <span class="text-gray-500 dark:text-gray-400 font-normal">
                via {{ match.intermediaryName }}
              </span>
            </button>
            <div class="mt-2 flex flex-wrap items-center gap-2 text-xs">
              <span
                :class="['font-bold tabular-nums', scoreColor(match.globalScore)]"
                :aria-label="`Score global ${match.globalScore} sur 100`"
              >
                {{ match.globalScore }}/100
              </span>
              <span class="text-gray-500 dark:text-gray-400">·</span>
              <span class="text-gray-600 dark:text-gray-400">
                Fonds {{ match.fundScore }}/100
              </span>
              <span class="text-gray-500 dark:text-gray-400">·</span>
              <span class="text-gray-600 dark:text-gray-400">
                Intermédiaire {{ match.intermediaryScore }}/100
              </span>
            </div>
          </div>
          <BottleneckBadge
            :bottleneck="match.bottleneck"
            :fund-score="match.fundScore"
            :intermediary-score="match.intermediaryScore"
            size="sm"
          />
        </div>

        <div
          v-if="match.recommendedActions && match.recommendedActions.length > 0"
          class="mt-3 text-xs text-gray-700 dark:text-gray-300"
        >
          <p class="font-medium mb-1">Actions recommandées :</p>
          <ul role="list" class="list-disc pl-4 space-y-0.5">
            <li
              v-for="(action, idx) in match.recommendedActions.slice(0, 3)"
              :key="`${match.id}-action-${idx}`"
            >
              {{ action.label }}
            </li>
          </ul>
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <button
            v-if="match.drilldownUrl"
            type="button"
            class="px-2.5 py-1 text-xs rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover"
            :data-testid="`match-detail-${match.id}`"
            @click="onCardClick(match)"
          >
            Voir le détail
          </button>
          <button
            type="button"
            class="px-2.5 py-1 text-xs rounded border border-emerald-500 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20"
            :data-testid="`compare-fund-${match.id}`"
            @click="onCompareFund(match.offerId)"
          >
            Comparer les intermédiaires
          </button>
        </div>
      </li>
    </ul>

    <div v-if="showAllLink" class="mt-4 text-right">
      <button
        type="button"
        class="text-sm font-medium text-emerald-700 dark:text-emerald-400 hover:underline focus:outline-none"
        data-testid="view-all-matches"
        @click="emit('view-all', projectId)"
      >
        Voir tous les matches ({{ total ?? matches.length }})
      </button>
    </div>
  </section>
</template>
