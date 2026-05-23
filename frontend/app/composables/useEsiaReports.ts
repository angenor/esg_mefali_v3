// F047 bugfix UI (2026-05-23) — Composable pour la liste des rapports
// ESIA-light F047 et leur téléchargement direct depuis la page /reports.

import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'

export interface EsiaReportListItem {
  assessment_id: string
  project_id: string
  project_name: string
  referential_id: string
  referential_code: string
  referential_label: string
  score: number | null
  coverage_rate: number | null
  finalized_at: string | null
  has_pdf: boolean
  file_size: number | null
}

export interface EsiaReportListResponse {
  items: EsiaReportListItem[]
  total: number
  page: number
  limit: number
}

export function useEsiaReports() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref<string>('')
  const reports = ref<EsiaReportListItem[]>([])

  function getHeaders(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (authStore.accessToken) h.Authorization = `Bearer ${authStore.accessToken}`
    return h
  }

  async function list(
    page = 1, limit = 20,
  ): Promise<EsiaReportListResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
      })
      const response = await fetch(`${apiBase}/reports/esia?${params}`, {
        headers: getHeaders(),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(
          (body as { detail?: string }).detail
          || 'Erreur lors du chargement des rapports ESIA',
        )
      }
      const data = (await response.json()) as EsiaReportListResponse
      reports.value = data.items
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Télécharge le PDF ESIA d'un assessment finalisé. Si le PDF n'existe
   * pas encore sur disque, le backend le régénère à la volée.
   */
  async function download(
    projectId: string, assessmentId: string,
  ): Promise<void> {
    try {
      const response = await fetch(
        `${apiBase}/projects/${projectId}/esg-assessment/${assessmentId}/report/download`,
        { headers: getHeaders() },
      )
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(
          (body as { detail?: string }).detail
          || 'Erreur lors du téléchargement',
        )
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `esia-${assessmentId}.pdf`
      link.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    }
  }

  return {
    loading,
    error,
    reports,
    list,
    download,
  }
}
