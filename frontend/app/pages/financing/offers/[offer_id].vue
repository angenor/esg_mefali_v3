<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useFinancing } from '~/composables/useFinancing'
import { useProjectMatching } from '~/composables/useProjectMatching'
import DualScoreDisplay from '~/components/financing/DualScoreDisplay.vue'
import MissingProjectCriteriaList from '~/components/financing/MissingProjectCriteriaList.vue'
import type { Offer } from '~/types/financing'
import type {
  MissingCriterion,
  ProjectScoreBreakdown,
} from '~/types/projectMatching'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const router = useRouter()
const { getOffer } = useFinancing()
const { getMatchDetails } = useProjectMatching()

const offer = ref<Offer | null>(null)
const loading = ref(true)
const error = ref('')

// F045 — Scores projet/entreprise pour ce match si project_id dans la query
const matchProjectScore = ref<number | null>(null)
const matchCompanyScore = ref<number | null>(null)
const matchDivergenceExplanation = ref<string | null>(null)
const matchMissingCriteria = ref<MissingCriterion[]>([])

const activeProjectId = computed<string | null>(() => {
  const qp = route.query.project_id
  if (typeof qp === 'string' && qp.length > 0) return qp
  return null
})

async function loadOffer(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const offerId = route.params.offer_id as string
    const result = await getOffer(offerId)
    if (result === null) {
      error.value = "Offre introuvable ou non publiée."
    } else {
      offer.value = result
    }
    // F045 — Charge le match details si project_id present dans l'URL.
    if (offerId && activeProjectId.value) {
      const detail = await getMatchDetails(activeProjectId.value, offerId)
      if (detail) {
        const anyDetail = detail as unknown as {
          project_score?: number
          company_score?: number
          divergence_explanation?: string | null
          project_score_breakdown?: ProjectScoreBreakdown
        }
        if (typeof anyDetail.project_score === 'number') {
          matchProjectScore.value = anyDetail.project_score
        }
        if (typeof anyDetail.company_score === 'number') {
          matchCompanyScore.value = anyDetail.company_score
        }
        matchDivergenceExplanation.value =
          anyDetail.divergence_explanation ?? null
        const bd = anyDetail.project_score_breakdown
        if (bd && Array.isArray((bd as ProjectScoreBreakdown).missing_criteria)) {
          matchMissingCriteria.value = (bd as ProjectScoreBreakdown).missing_criteria
        }
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur lors du chargement'
  } finally {
    loading.value = false
  }
}

function handleCompare(fundId: string): void {
  router.push(`/financing/offers?fund_id=${fundId}&compare=true`)
}

function handleApply(offerId: string): void {
  // Préparation pour F15 (générateur dossier).
  router.push(`/financing/offers/${offerId}/apply`)
}

onMounted(loadOffer)
</script>

<template>
  <div class="container mx-auto max-w-4xl px-4 py-8">
    <div v-if="loading" class="text-center py-12 text-gray-500 dark:text-gray-400">
      Chargement de l'offre...
    </div>
    <div v-else-if="error" class="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 p-4 text-red-700 dark:text-red-300">
      {{ error }}
    </div>
    <template v-else-if="offer">
      <!-- F045 — Section double score si un project_id est actif -->
      <div
        v-if="matchProjectScore !== null && matchCompanyScore !== null"
        class="mb-6 space-y-4"
      >
        <DualScoreDisplay
          :project-score="matchProjectScore"
          :company-score="matchCompanyScore"
          :divergence-explanation="matchDivergenceExplanation"
        />
        <MissingProjectCriteriaList
          v-if="matchMissingCriteria.length > 0"
          :criteria="matchMissingCriteria"
        />
      </div>

      <OfferDetail
        :offer="offer"
        @compare="handleCompare"
        @apply="handleApply"
      />
    </template>
  </div>
</template>
