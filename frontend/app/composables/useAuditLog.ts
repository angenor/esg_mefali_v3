// F03 — Composable pour interagir avec l'API audit log.

import type {
  AuditEvent,
  AuditEventList,
  AuditExportFormat,
  AuditFilters,
} from '~/types/audit'
import { useAuthStore } from '~/stores/auth'

function buildQueryString(filters: Partial<AuditFilters>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    params.append(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function useAuditLog() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase as string

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  /** Liste paginée pour le PME courant. */
  async function fetchMe(filters: Partial<AuditFilters> = {}): Promise<AuditEventList | null> {
    try {
      const url = `${apiBase}/audit/me${buildQueryString(filters)}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) return null
      return (await response.json()) as AuditEventList
    } catch {
      return null
    }
  }

  /** Admin : log d'un compte PME (déclenche `view_admin` côté backend). */
  async function fetchByAccount(
    accountId: string,
    filters: Partial<AuditFilters> = {},
  ): Promise<AuditEventList | null> {
    try {
      const url = `${apiBase}/admin/audit/${accountId}${buildQueryString(filters)}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) return null
      return (await response.json()) as AuditEventList
    } catch {
      return null
    }
  }

  /** Admin : log global filtrable. */
  async function fetchGlobal(filters: Partial<AuditFilters> = {}): Promise<AuditEventList | null> {
    try {
      const url = `${apiBase}/admin/audit${buildQueryString(filters)}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) return null
      return (await response.json()) as AuditEventList
    } catch {
      return null
    }
  }

  /** Téléchargement CSV (PME courant). */
  async function exportCsv(filters: Partial<AuditFilters> = {}): Promise<void> {
    return _exportFile(filters, 'csv')
  }

  /** Téléchargement JSON (PME courant). */
  async function exportJson(filters: Partial<AuditFilters> = {}): Promise<void> {
    return _exportFile(filters, 'json')
  }

  async function _exportFile(
    filters: Partial<AuditFilters>,
    format: AuditExportFormat,
  ): Promise<void> {
    const merged = { ...filters, format }
    const url = `${apiBase}/audit/me/export${buildQueryString(merged as Record<string, unknown>)}`
    const response = await fetch(url, { headers: getHeaders() })
    if (!response.ok) {
      throw new Error(`Export ${format} en échec : ${response.status}`)
    }
    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    // Le serveur propose Content-Disposition; on utilise un nom fallback.
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    a.download = `audit-log-${today}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(downloadUrl)
  }

  return {
    fetchMe,
    fetchByAccount,
    fetchGlobal,
    exportCsv,
    exportJson,
  }
}
