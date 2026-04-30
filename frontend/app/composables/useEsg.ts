import { ref } from 'vue'
import type {
  ESGAssessment,
  ESGAssessmentList,
  ScoreResponse,
  BenchmarkResponse,
} from '~/types/esg'
import { useEsgStore } from '~/stores/esg'
import { useAuth, SessionExpiredError } from '~/composables/useAuth'

export function useEsg() {
  const esgStore = useEsgStore()
  const { apiFetch, handleAuthFailure } = useAuth()

  const loading = ref(false)
  const error = ref('')
  // Patch F : flag expose au consommateur pour suppresser le toast d'erreur
  // quand handleAuthFailure() a deja declenche la redirection /login.
  const sessionExpired = ref(false)

  // Propage un message FR et declenche handleAuthFailure si la session a expire.
  // Skip error.value sur SessionExpiredError pour eviter un flash d'erreur juste
  // avant la redirection vers /login (UX NFR9).
  async function handleError(e: unknown, fallback: string): Promise<void> {
    if (e instanceof SessionExpiredError) {
      sessionExpired.value = true
      await handleAuthFailure()
      return
    }
    error.value = e instanceof Error ? e.message : fallback
  }

  async function createAssessment(conversationId?: string): Promise<ESGAssessment | null> {
    loading.value = true
    error.value = ''
    sessionExpired.value = false
    try {
      const body = conversationId ? { conversation_id: conversationId } : undefined
      const options: RequestInit = { method: 'POST' }
      if (body) options.body = JSON.stringify(body)
      return await apiFetch<ESGAssessment>('/esg/assessments', options)
    } catch (e) {
      await handleError(e, 'Erreur lors de la creation')
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchAssessments(status?: string, page = 1, limit = 10): Promise<void> {
    loading.value = true
    error.value = ''
    esgStore.setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(limit) })
      if (status) params.set('status', status)
      const data = await apiFetch<ESGAssessmentList>(`/esg/assessments?${params}`)
      esgStore.setAssessments(data.data, data.total)
    } catch (e) {
      await handleError(e, 'Erreur lors du chargement')
      esgStore.setError(error.value)
    } finally {
      loading.value = false
      esgStore.setLoading(false)
    }
  }

  async function fetchAssessment(id: string): Promise<ESGAssessment | null> {
    loading.value = true
    error.value = ''
    try {
      const data = await apiFetch<ESGAssessment>(`/esg/assessments/${id}`)
      esgStore.setCurrentAssessment(data)
      return data
    } catch (e) {
      await handleError(e, 'Evaluation non trouvee')
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchScore(id: string): Promise<ScoreResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const data = await apiFetch<ScoreResponse>(`/esg/assessments/${id}/score`)
      esgStore.setCurrentScore(data)
      return data
    } catch (e) {
      await handleError(e, 'Score non disponible')
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchBenchmark(sector: string): Promise<BenchmarkResponse | null> {
    try {
      return await apiFetch<BenchmarkResponse>(`/esg/benchmarks/${sector}`)
    } catch (e) {
      if (e instanceof SessionExpiredError) {
        await handleAuthFailure()
      }
      return null
    }
  }

  return {
    loading,
    error,
    sessionExpired,
    createAssessment,
    fetchAssessments,
    fetchAssessment,
    fetchScore,
    fetchBenchmark,
  }
}
