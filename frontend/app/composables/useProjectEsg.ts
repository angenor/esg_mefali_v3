/**
 * F047 — Composable d'accès aux endpoints REST évaluation ESG-projet.
 * Wraps fetch + gestion d'erreur 404/409/422 avec messages FR.
 */
import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'
import type {
  ProjectEsgAssessmentCreatePayload,
  ProjectEsgAssessmentDetail,
  ProjectEsgAssessmentFinalizeResult,
  ProjectEsgAssessmentRead,
  ProjectEsgCriterionResponseRead,
  ProjectEsgCriterionResponseSavePayload,
} from '~/types/projectEsg'

export function useProjectEsg() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref('')

  function headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(auth.accessToken
        ? { Authorization: `Bearer ${auth.accessToken}` }
        : {}),
    }
  }

  function extractError(status: number, body: unknown): string {
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? (body as { detail: unknown }).detail
        : null
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as { message: unknown }).message)
    }
    if (status === 404) return 'Ressource introuvable.'
    if (status === 409) return 'Conflit : opération non autorisée dans cet état.'
    if (status === 422) return 'Données invalides — vérifiez votre saisie.'
    return `Erreur ${status}`
  }

  async function _request<T>(url: string, init: RequestInit): Promise<T | null> {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch(url, { ...init, headers: headers() })
      if (res.status === 204) return null
      const body = await res.json().catch(() => null)
      if (!res.ok) {
        error.value = extractError(res.status, body)
        return null
      }
      return body as T
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur réseau'
      return null
    } finally {
      loading.value = false
    }
  }

  async function listAssessments(
    projectId: string,
    state?: 'draft' | 'finalized',
  ): Promise<ProjectEsgAssessmentRead[] | null> {
    const qs = state ? `?state=${state}` : ''
    return _request<ProjectEsgAssessmentRead[]>(
      `${apiBase}/projects/${projectId}/esg-assessments${qs}`,
      { method: 'GET' },
    )
  }

  async function createAssessment(
    projectId: string,
    payload: ProjectEsgAssessmentCreatePayload,
  ): Promise<ProjectEsgAssessmentRead | null> {
    return _request<ProjectEsgAssessmentRead>(
      `${apiBase}/projects/${projectId}/esg-assessment`,
      { method: 'POST', body: JSON.stringify(payload) },
    )
  }

  async function getAssessment(
    projectId: string,
    assessmentId: string,
  ): Promise<ProjectEsgAssessmentDetail | null> {
    return _request<ProjectEsgAssessmentDetail>(
      `${apiBase}/projects/${projectId}/esg-assessment/${assessmentId}`,
      { method: 'GET' },
    )
  }

  async function saveCriterion(
    projectId: string,
    assessmentId: string,
    payload: ProjectEsgCriterionResponseSavePayload,
  ): Promise<ProjectEsgCriterionResponseRead | null> {
    return _request<ProjectEsgCriterionResponseRead>(
      `${apiBase}/projects/${projectId}/esg-assessment/${assessmentId}/criterion`,
      { method: 'POST', body: JSON.stringify(payload) },
    )
  }

  async function finalize(
    projectId: string,
    assessmentId: string,
  ): Promise<ProjectEsgAssessmentFinalizeResult | null> {
    return _request<ProjectEsgAssessmentFinalizeResult>(
      `${apiBase}/projects/${projectId}/esg-assessment/${assessmentId}/finalize`,
      { method: 'POST', body: JSON.stringify({}) },
    )
  }

  async function deleteAssessment(
    projectId: string,
    assessmentId: string,
  ): Promise<boolean> {
    const res = await _request<null>(
      `${apiBase}/projects/${projectId}/esg-assessment/${assessmentId}`,
      { method: 'DELETE' },
    )
    return error.value === ''
  }

  return {
    loading,
    error,
    listAssessments,
    createAssessment,
    getAssessment,
    saveCriterion,
    finalize,
    deleteAssessment,
  }
}
