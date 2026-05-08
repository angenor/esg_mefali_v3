// F21 — Composable de gestion des rapports carbone PDF.

import { ref } from 'vue'
import type {
  CarbonReportGenerateResponse,
  CarbonReportListItem,
  CarbonReportListResponse,
  CarbonReportStatus,
} from '~/types/carbon-report'
import { useAuthStore } from '~/stores/auth'

interface PollOptions {
  timeoutMs?: number
  intervalMs?: number
}

export function useCarbonReports() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref<string>('')
  const reports = ref<CarbonReportListItem[]>([])

  function getHeaders(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (authStore.accessToken) h.Authorization = `Bearer ${authStore.accessToken}`
    return h
  }

  async function generate(
    assessmentId: string,
  ): Promise<CarbonReportGenerateResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(
        `${apiBase}/reports/carbon/${assessmentId}/generate`,
        { method: 'POST', headers: getHeaders() },
      )
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(
          body.detail || 'Erreur lors de la génération du rapport carbone',
        )
      }
      return (await response.json()) as CarbonReportGenerateResponse
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function getStatus(reportId: string): Promise<{
    id: string
    status: CarbonReportStatus
    generated_at: string | null
  } | null> {
    try {
      const response = await fetch(`${apiBase}/reports/${reportId}/status`, {
        headers: getHeaders(),
      })
      if (!response.ok) throw new Error('Erreur lors de la vérification du statut')
      return await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    }
  }

  async function pollUntilReady(
    reportId: string,
    options: PollOptions = {},
  ): Promise<CarbonReportStatus> {
    const timeoutMs = options.timeoutMs ?? 30000
    const intervalMs = options.intervalMs ?? 2000
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      const result = await getStatus(reportId)
      if (!result) return 'failed'
      if (
        result.status === 'ready'
        || result.status === 'completed'
        || result.status === 'failed'
      ) {
        return result.status
      }
      await new Promise<void>((resolve) => setTimeout(resolve, intervalMs))
    }
    return 'generating'
  }

  function download(reportId: string): void {
    const token = authStore.accessToken
    const url = `${apiBase}/reports/${reportId}/download`
    const link = document.createElement('a')
    link.href = `${url}?token=${encodeURIComponent(token || '')}`
    link.click()
  }

  async function list(page = 1, limit = 20): Promise<CarbonReportListResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
        type: 'carbon',
      })
      const response = await fetch(`${apiBase}/reports/?${params}`, {
        headers: getHeaders(),
      })
      if (!response.ok) throw new Error('Erreur lors du chargement des rapports carbone')
      const data = (await response.json()) as CarbonReportListResponse
      reports.value = data.items
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    reports,
    generate,
    getStatus,
    pollUntilReady,
    download,
    list,
  }
}
