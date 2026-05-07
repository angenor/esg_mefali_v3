<script setup lang="ts">
import { useEsg } from '~/composables/useEsg'
import { useEsgMultiReferential } from '~/composables/useEsgMultiReferential'
import { useEsgStore } from '~/stores/esg'
import { useUiStore } from '~/stores/ui'
import type { BenchmarkResponse, ReferentialOption } from '~/types/esg'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const esgStore = useEsgStore()
const uiStore = useUiStore()
const { fetchAssessment, fetchScore, fetchBenchmark, loading, error } = useEsg()
const {
  getReferentialScores,
  recomputeScore,
  generateMultiReferentialReport,
} = useEsgMultiReferential()

const benchmark = ref<BenchmarkResponse | null>(null)
const allAssessments = ref<import('~/types/esg').ESGAssessmentSummary[]>([])
const assessmentId = computed(() => route.query.id as string | undefined)

// F13 — Multi-référentiels
const showReportModal = ref(false)
const isGeneratingReport = ref(false)

const referentialOptions = computed<ReferentialOption[]>(() =>
  esgStore.referentialScores.map((s) => ({
    code: s.referential_code,
    name: s.referential_name,
    version: s.referential_version,
  })),
)

async function loadMultiReferentialScores(id: string) {
  const scores = await getReferentialScores(id)
  esgStore.setReferentialScores(scores)
  if (scores.length > 0 && !esgStore.referentialScores.find((s) => s.referential_code === esgStore.selectedReferential)) {
    esgStore.setSelectedReferential(scores[0].referential_code)
  }
}

async function handleGenerateReport(params: { referentials: string[]; include_appendix_sources: boolean }) {
  if (!esgStore.currentAssessment) return
  isGeneratingReport.value = true
  try {
    await generateMultiReferentialReport(
      esgStore.currentAssessment.id,
      params.referentials,
      params.include_appendix_sources,
    )
  } finally {
    isGeneratingReport.value = false
    showReportModal.value = false
  }
}

onMounted(async () => {
  if (!assessmentId.value) {
    // Charger la derniere evaluation completee
    await loadLatestAssessment()
    return
  }

  await Promise.all([
    fetchAssessment(assessmentId.value),
    fetchScore(assessmentId.value),
  ])

  // Charger le benchmark du secteur et l'historique
  await Promise.all([
    loadBenchmark(),
    loadHistory(),
    loadMultiReferentialScores(assessmentId.value),
  ])
})

async function loadLatestAssessment() {
  const { fetchAssessments: fetch } = useEsg()
  await fetch('completed', 1, 1)
  const latest = esgStore.latestCompleted
  if (latest) {
    await Promise.all([
      fetchAssessment(latest.id),
      fetchScore(latest.id),
    ])
    await Promise.all([
      loadBenchmark(),
      loadHistory(),
    ])
  }
}

async function loadBenchmark() {
  if (esgStore.currentAssessment?.sector) {
    benchmark.value = await fetchBenchmark(esgStore.currentAssessment.sector)
  }
}

async function loadHistory() {
  const { fetchAssessments: fetch } = useEsg()
  await fetch('completed', 1, 50)
  allAssessments.value = esgStore.assessments
}

const pillarLabels: Record<string, string> = {
  environment: 'Environnement',
  social: 'Social',
  governance: 'Gouvernance',
}
</script>

<template>
  <div class="flex flex-col h-full bg-surface-bg dark:bg-surface-dark-bg">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border">
      <div class="flex items-center gap-3">
        <NuxtLink
          to="/esg"
          class="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </NuxtLink>
        <h1 class="text-xl font-bold text-surface-text dark:text-surface-dark-text">
          Resultats ESG
        </h1>
      </div>
      <!-- Bouton generation rapport PDF -->
      <ReportButton
        v-if="esgStore.currentAssessment?.status === 'completed'"
        :assessment-id="esgStore.currentAssessment.id"
      />
    </div>

    <div class="flex-1 overflow-y-auto p-6">
      <!-- Chargement -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>

      <!-- Erreur -->
      <div v-else-if="error" class="text-center py-12 text-red-500 dark:text-red-400">
        {{ error }}
      </div>

      <!-- Pas de donnees -->
      <div
        v-else-if="!esgStore.currentAssessment || !esgStore.currentScore"
        class="text-center py-12"
      >
        <p class="text-gray-500 dark:text-gray-400">
          Aucune evaluation terminee. Demarrez une evaluation dans le chat.
        </p>
        <button
          type="button"
          class="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors"
          @click="uiStore.openChatWidget()"
        >
          Demarrer une evaluation
        </button>
      </div>

      <!-- Resultats -->
      <div v-else class="max-w-4xl mx-auto space-y-8">
        <!-- F13 — Sélecteur multi-référentiels + bouton modale rapport -->
        <div
          v-if="referentialOptions.length > 0"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-4 flex items-center justify-between gap-4"
        >
          <ReferentialSelector
            :options="referentialOptions"
            v-model="esgStore.selectedReferential"
            :disabled="esgStore.isRecomputing"
          />
          <button
            type="button"
            class="rounded-md border border-primary text-primary hover:bg-primary hover:text-white px-3 py-1.5 text-sm font-medium transition"
            @click="showReportModal = true"
          >
            Générer un rapport PDF
          </button>
        </div>

        <!-- F13 — Carte du score référentiel sélectionné -->
        <ReferentialScoreCard
          v-if="esgStore.currentReferentialScore"
          :score="esgStore.currentReferentialScore"
          :show-include-in-report="true"
          @include-in-report="(code) => esgStore.setSelectedReferential(code)"
        />

        <!-- F13 — Liste critères manquants -->
        <MissingCriteriaList
          v-if="esgStore.currentReferentialScore && esgStore.currentReferentialScore.missing_criteria.length > 0"
          :criteria="esgStore.currentReferentialScore.missing_criteria"
          :referential-name="esgStore.currentReferentialScore.referential_name"
        />

        <!-- F13 — Modale rapport multi-référentiels -->
        <MultiReferentialReportModal
          v-model="showReportModal"
          :referential-scores="esgStore.referentialScores"
          :is-generating="isGeneratingReport"
          @generate="handleGenerateReport"
        />

        <!-- Score global + piliers -->
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-6">
            Score global
          </h2>
          <div class="flex items-center justify-center gap-12">
            <!-- Score global cercle -->
            <div class="relative" data-guide-target="esg-score-circle">
              <EsgScoreCircle
                :score="esgStore.currentScore.overall_score"
                :size="140"
                label="Global"
              />
            </div>
            <!-- Piliers -->
            <div class="space-y-4">
              <div v-for="(pillarData, key) in esgStore.currentScore.pillars" :key="key" class="flex items-center gap-4">
                <span class="text-sm font-medium text-gray-600 dark:text-gray-400 w-28">
                  {{ pillarLabels[key] ?? key }}
                </span>
                <div class="w-40 h-3 bg-gray-100 dark:bg-gray-700 rounded-full">
                  <div
                    class="h-full rounded-full transition-all duration-500"
                    :class="{
                      'bg-emerald-500': key === 'environment',
                      'bg-blue-500': key === 'social',
                      'bg-violet-500': key === 'governance',
                    }"
                    :style="{ width: `${pillarData.score}%` }"
                  />
                </div>
                <span class="text-sm font-bold text-surface-text dark:text-surface-dark-text w-12 text-right">
                  {{ Math.round(pillarData.score) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Criteres detailles -->
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Detail des criteres
          </h2>
          <EsgCriteriaProgress :pillars="esgStore.currentScore.pillars" />
        </div>

        <!-- Points forts -->
        <div
          v-if="esgStore.currentAssessment.strengths?.length"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
          data-guide-target="esg-strengths-badges"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Points forts
          </h2>
          <EsgStrengthsBadges :strengths="esgStore.currentAssessment.strengths" />
        </div>

        <!-- Recommandations -->
        <div
          v-if="esgStore.currentAssessment.recommendations?.length"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
          data-guide-target="esg-recommendations"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Recommandations
          </h2>
          <EsgRecommendations :recommendations="esgStore.currentAssessment.recommendations" />
        </div>

        <!-- Benchmark sectoriel -->
        <div
          v-if="benchmark"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Benchmark sectoriel — {{ benchmark.sector_label }}
          </h2>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div
              v-for="(value, key) in benchmark.averages"
              :key="key"
              class="text-center p-4 rounded-lg bg-gray-50 dark:bg-dark-hover"
            >
              <p class="text-2xl font-bold" :class="{
                'text-emerald-600 dark:text-emerald-400': key === 'environment',
                'text-blue-600 dark:text-blue-400': key === 'social',
                'text-violet-600 dark:text-violet-400': key === 'governance',
                'text-surface-text dark:text-surface-dark-text': key === 'overall',
              }">
                {{ value }}
              </p>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {{ key === 'overall' ? 'Global' : pillarLabels[key] ?? key }}
              </p>
              <!-- Comparaison -->
              <p
                v-if="esgStore.currentScore"
                class="text-xs mt-1"
                :class="(key === 'overall'
                  ? esgStore.currentScore.overall_score
                  : esgStore.currentScore.pillars[key as 'environment' | 'social' | 'governance']?.score ?? 0) > value
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-red-500 dark:text-red-400'"
              >
                {{ (key === 'overall'
                  ? esgStore.currentScore.overall_score
                  : esgStore.currentScore.pillars[key as 'environment' | 'social' | 'governance']?.score ?? 0) > value ? 'Au-dessus' : 'En-dessous' }}
                de la moyenne
              </p>
            </div>
          </div>
        </div>

        <!-- Historique des evaluations -->
        <div
          v-if="allAssessments.length > 1"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Evolution du score ESG
          </h2>
          <EsgScoreHistory :assessments="allAssessments" />
        </div>
        <div
          v-else-if="allAssessments.length === 1"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
        >
          <p class="text-sm text-gray-500 dark:text-gray-400 text-center">
            Le graphique d'evolution apparaitra apres votre deuxieme evaluation.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
