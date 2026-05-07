import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  ESGAssessment,
  ESGAssessmentSummary,
  ReferentialScore,
  ScoreResponse,
} from '~/types/esg'

export const useEsgStore = defineStore('esg', () => {
  const assessments = ref<ESGAssessmentSummary[]>([])
  const currentAssessment = ref<ESGAssessment | null>(null)
  const currentScore = ref<ScoreResponse | null>(null)
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // F13 — Scoring multi-référentiels
  const referentialScores = ref<ReferentialScore[]>([])
  const selectedReferential = ref<string>('mefali')
  const isRecomputing = ref(false)
  const recomputeRequestId = ref<string | null>(null)

  const hasAssessments = computed(() => assessments.value.length > 0)
  const latestCompleted = computed(() =>
    assessments.value.find(a => a.status === 'completed') ?? null
  )

  // F13 getters
  const currentReferentialScore = computed(() =>
    referentialScores.value.find(s => s.referential_code === selectedReferential.value) ?? null
  )
  const scoresWithCoverageOk = computed(() =>
    referentialScores.value.filter(s => s.coverage_rate >= 0.5)
  )

  function setAssessments(data: ESGAssessmentSummary[], count: number) {
    assessments.value = data
    total.value = count
  }

  function setCurrentAssessment(data: ESGAssessment | null) {
    currentAssessment.value = data
  }

  function setCurrentScore(data: ScoreResponse | null) {
    currentScore.value = data
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setError(message: string | null) {
    error.value = message
  }

  function reset() {
    assessments.value = []
    currentAssessment.value = null
    currentScore.value = null
    total.value = 0
    loading.value = false
    error.value = null
    referentialScores.value = []
    selectedReferential.value = 'mefali'
    isRecomputing.value = false
    recomputeRequestId.value = null
  }

  // F13 — setters
  function setReferentialScores(scores: ReferentialScore[]) {
    referentialScores.value = scores
  }

  function setSelectedReferential(code: string) {
    selectedReferential.value = code
  }

  function setIsRecomputing(value: boolean, requestId: string | null = null) {
    isRecomputing.value = value
    recomputeRequestId.value = requestId
  }

  return {
    assessments,
    currentAssessment,
    currentScore,
    total,
    loading,
    error,
    hasAssessments,
    latestCompleted,
    setAssessments,
    setCurrentAssessment,
    setCurrentScore,
    setLoading,
    setError,
    reset,
    // F13
    referentialScores,
    selectedReferential,
    isRecomputing,
    recomputeRequestId,
    currentReferentialScore,
    scoresWithCoverageOk,
    setReferentialScores,
    setSelectedReferential,
    setIsRecomputing,
  }
})
