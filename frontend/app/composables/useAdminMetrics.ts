// F09 PRIO 3 — Composable admin /metrics (overview).
import { useAuth } from '~/composables/useAuth'

export interface AdminMetricsOverview {
  sources: {
    total: number
    breakdown: Record<string, number>
  }
  accounts: {
    total: number
    active: number
    inactive: number
    new_30d: number
    pending_deletion: number
  }
  applications: {
    total: number
    by_status: Record<string, number>
    submission_rate: number
  }
  attestations: {
    total: number
    active: number
    revoked: number
    expired: number
  }
  llm_costs: {
    note: string
    available: boolean
  }
  generated_at: string
}

export function useAdminMetrics() {
  const { apiFetch } = useAuth()

  async function fetchOverview(): Promise<AdminMetricsOverview> {
    return await apiFetch<AdminMetricsOverview>('/admin/metrics/overview')
  }

  return { fetchOverview }
}
