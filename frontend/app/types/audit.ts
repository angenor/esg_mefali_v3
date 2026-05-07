// F03 — Types TypeScript pour l'audit log append-only.
// Voir specs/021-audit-log/contracts/audit-pme.api.md et audit-admin.api.md.

export type AuditAction = 'create' | 'update' | 'delete' | 'view_admin'

export type AuditSourceOfChange = 'manual' | 'llm' | 'import' | 'admin'

export interface AuditEvent {
  id: string
  timestamp: string // ISO 8601
  user_id: string
  user_email: string | null
  account_id: string
  entity_type: string
  entity_id: string
  action: AuditAction
  field: string | null
  old_value: unknown
  new_value: unknown
  source_of_change: AuditSourceOfChange
  actor_metadata: Record<string, unknown> | null
}

export interface AuditEventList {
  events: AuditEvent[]
  total: number
  page: number
  limit: number
}

export interface AuditFilters {
  entity_type?: string | null
  entity_id?: string | null
  action?: AuditAction | null
  source_of_change?: AuditSourceOfChange | null
  since?: string | null
  until?: string | null
  page?: number
  limit?: number
  order?: 'asc' | 'desc'
  // Admin uniquement (ignoré côté PME)
  account_id?: string | null
  user_id?: string | null
}

export type AuditExportFormat = 'csv' | 'json'
