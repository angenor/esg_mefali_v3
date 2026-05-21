<script setup lang="ts">
// F045 — ProjectFundsSection : section « Fonds compatibles avec ce projet »
// pour /profile/projects/[id]. Top 5 matches projet-centric.
//
// Inclut bouton « Recalculer les matches » (T080b) qui appelle
// useProjectMatching().recomputeMatches(projectId) + toast FR.

import { computed, onMounted, ref } from 'vue'
import { useProjectMatchingStore } from '~/stores/projectMatching'
import { useProjectMatching } from '~/composables/useProjectMatching'
import { useToast } from '~/composables/useToast'
import ProjectMatchCardBlock from '~/components/financing/ProjectMatchCardBlock.vue'
import type {
  MatchFundsItem,
  ProjectMatchCardBlockPayload,
  ProjectScoreBreakdown,
} from '~/types/projectMatching'

interface Props {
  projectId: string
}

const props = defineProps<Props>()
const router = useRouter()

const store = useProjectMatchingStore()
const { matchFunds, error: matchingError } = useProjectMatching()
const { success: showSuccess, error: showError } = useToast()

const recomputing = ref(false)

const response = computed(() => store.getMatches(props.projectId))
const loading = computed(() => store.isLoading(props.projectId))

const top5 = computed<MatchFundsItem[]>(() => {
  const r = response.value
  if (!r) return []
  return r.top_matches.slice(0, 5)
})

const emptyState = computed(() => {
  const r = response.value
  if (!r) return null
  if (r.matches_count > 0) return null
  return r.no_match_reason ??
    "Aucun fonds compatible n'a été trouvé pour ce projet."
})

function toBlockPayload(item: MatchFundsItem): ProjectMatchCardBlockPayload {
  const bd = item.project_score_breakdown as ProjectScoreBreakdown | undefined
  return {
    title: item.intermediary_name
      ? `${item.fund_name} via ${item.intermediary_name}`
      : item.fund_name,
    fund_name: item.fund_name,
    intermediary_name: item.intermediary_name ?? null,
    project_score: item.project_score,
    company_score: item.company_score,
    divergence: item.divergence_explanation ?? '',
    fund_url: `/financing/offers/${item.offer_id}?project_id=${item.fund_id ? props.projectId : props.projectId}`,
    offer_id: item.offer_id,
    project_id: props.projectId,
    sources: [],
    missing_criteria_top_3:
      bd?.missing_criteria?.slice(0, 3).map((m) => ({
        key: m.key,
        label_fr: m.label_fr,
        current_value: m.current_value ?? null,
        target_value: m.target_value ?? null,
      })) ?? [],
    factor_status: bd?.factor_status ?? 'ok',
  }
}

async function load(): Promise<void> {
  await store.loadMatches(props.projectId, { minScore: 0, limit: 10 })
  if (matchingError.value) {
    showError(matchingError.value.messageFr)
  }
}

async function onRecompute(): Promise<void> {
  recomputing.value = true
  try {
    const r = await matchFunds(props.projectId, { forceRecompute: true })
    if (r) {
      store.matchesByProject = { ...store.matchesByProject, [props.projectId]: r }
      showSuccess('Matching recalculé avec succès.')
    } else if (matchingError.value) {
      showError(matchingError.value.messageFr)
    }
  } finally {
    recomputing.value = false
  }
}

function onNavigate(url: string): void {
  router.push(url)
}

function onSeeAll(): void {
  router.push(`/profile/projects/${props.projectId}/matches`)
}

onMounted(load)
</script>

<template>
  <section
    aria-labelledby="project-funds-title"
    class="rounded-xl border border-gray-200 bg-white p-4
           dark:border-dark-border dark:bg-dark-card"
  >
    <header class="flex items-start justify-between gap-3 mb-4">
      <div>
        <h2
          id="project-funds-title"
          class="text-base font-semibold text-surface-text dark:text-surface-dark-text"
        >
          Fonds compatibles avec ce projet
        </h2>
        <p class="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
          Top 5 fonds triés par score projet décroissant.
        </p>
      </div>
      <button
        type="button"
        :disabled="recomputing || loading"
        class="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white
               px-3 py-1.5 text-sm font-medium text-gray-700 transition
               hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50
               focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2
               dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text
               dark:hover:bg-dark-hover dark:focus:ring-offset-dark-card"
        aria-label="Recalculer les fonds compatibles avec ce projet"
        @click="onRecompute"
      >
        <span aria-hidden="true">{{ recomputing ? '⏳' : '↻' }}</span>
        {{ recomputing ? 'Recalcul…' : 'Recalculer' }}
      </button>
    </header>

    <div
      v-if="loading && !response"
      class="py-8 text-center text-sm text-gray-500 dark:text-gray-400"
    >
      Chargement des fonds compatibles…
    </div>

    <div
      v-else-if="emptyState"
      class="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center
             dark:border-dark-border dark:bg-dark-input"
    >
      <p class="text-sm text-gray-700 dark:text-gray-300 mb-2">
        {{ emptyState }}
      </p>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        Renforcez les critères verts (taxonomie UEMOA, thèmes GCF, impact CO2)
        pour augmenter votre éligibilité.
      </p>
    </div>

    <div v-else class="space-y-3">
      <ProjectMatchCardBlock
        v-for="item in top5"
        :key="item.offer_id"
        :payload="toBlockPayload(item)"
        @navigate="onNavigate"
      />

      <button
        v-if="response && response.matches_count > 5"
        type="button"
        class="w-full mt-2 rounded-md border border-emerald-200 bg-emerald-50
               px-3 py-2 text-sm font-medium text-emerald-700
               transition hover:bg-emerald-100
               dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-300
               dark:hover:bg-emerald-900/40"
        @click="onSeeAll"
      >
        Voir tous les matches ({{ response.matches_count }})
      </button>
    </div>
  </section>
</template>
