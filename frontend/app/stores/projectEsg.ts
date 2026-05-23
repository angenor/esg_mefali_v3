/**
 * F047 — Store Pinia pour l'évaluation ESG-projet.
 * État courant + actions wrappant le composable useProjectEsg.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useProjectEsg } from '~/composables/useProjectEsg'
import type {
  ProjectEsgAssessmentDetail,
  ProjectEsgAssessmentRead,
  ProjectEsgCriterionResponseSavePayload,
} from '~/types/projectEsg'

export const useProjectEsgStore = defineStore('projectEsg', () => {
  const api = useProjectEsg()

  const assessments = ref<ProjectEsgAssessmentRead[]>([])
  const currentAssessment = ref<ProjectEsgAssessmentDetail | null>(null)
  const lastScore = ref<number | null>(null)
  const lastMissingCriteria = ref<Array<{ id: string; code: string; label: string }>>(
    [],
  )

  const loading = computed(() => api.loading.value)
  const error = computed(() => api.error.value)

  const isFinalized = computed(
    () => currentAssessment.value?.state === 'finalized',
  )
  const progressPercent = computed(() => {
    const a = currentAssessment.value
    if (!a) return 0
    const total = a.covered_criteria.length + a.missing_criteria.length
    return total === 0 ? 0 : Math.round((a.covered_criteria.length / total) * 100)
  })

  async function loadList(projectId: string) {
    const items = await api.listAssessments(projectId)
    if (items) assessments.value = items
  }

  async function startAssessment(projectId: string, referentialId: string) {
    const created = await api.createAssessment(projectId, {
      referential_id: referentialId,
    })
    if (created) {
      await loadDetail(projectId, created.id)
      await loadList(projectId)
    }
    return created
  }

  async function loadDetail(projectId: string, assessmentId: string) {
    const detail = await api.getAssessment(projectId, assessmentId)
    if (detail) currentAssessment.value = detail
    return detail
  }

  async function saveCriterion(
    projectId: string,
    payload: ProjectEsgCriterionResponseSavePayload,
  ) {
    if (!currentAssessment.value) return null
    const row = await api.saveCriterion(
      projectId,
      currentAssessment.value.id,
      payload,
    )
    if (row) {
      await loadDetail(projectId, currentAssessment.value.id)
    }
    return row
  }

  async function finalize(projectId: string) {
    if (!currentAssessment.value) return null
    const result = await api.finalize(projectId, currentAssessment.value.id)
    if (result) {
      lastScore.value = result.score
      lastMissingCriteria.value = result.missing_criteria
      await loadDetail(projectId, currentAssessment.value.id)
      await loadList(projectId)
    }
    return result
  }

  async function removeAssessment(projectId: string, assessmentId: string) {
    const ok = await api.deleteAssessment(projectId, assessmentId)
    if (ok) {
      if (currentAssessment.value?.id === assessmentId) {
        currentAssessment.value = null
      }
      await loadList(projectId)
    }
    return ok
  }

  function reset() {
    assessments.value = []
    currentAssessment.value = null
    lastScore.value = null
    lastMissingCriteria.value = []
  }

  return {
    // state
    assessments,
    currentAssessment,
    lastScore,
    lastMissingCriteria,
    loading,
    error,
    // getters
    isFinalized,
    progressPercent,
    // actions
    loadList,
    startAssessment,
    loadDetail,
    saveCriterion,
    finalize,
    removeAssessment,
    reset,
  }
})
