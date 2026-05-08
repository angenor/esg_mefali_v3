// F09 PRIO 3 — Composable admin /attestations (révocation cross-tenant).
import { useAuth } from '~/composables/useAuth'

export interface AdminAttestation {
  id: string
  display_id: string
  attestation_type: 'credit_score' | 'esg_assessment' | 'combined'
  valid_from: string
  valid_until: string
  revoked_at: string | null
  revoked_reason: string | null
  account_id: string
  user_id: string
  created_at: string
}

export function useAdminAttestations() {
  const { apiFetch } = useAuth()

  async function listAttestations(filters: {
    status?: string
    account_id?: string
    limit?: number
    offset?: number
  } = {}): Promise<AdminAttestation[]> {
    const usp = new URLSearchParams()
    if (filters.status) usp.set('status', filters.status)
    if (filters.account_id) usp.set('account_id', filters.account_id)
    if (filters.limit) usp.set('limit', String(filters.limit))
    if (filters.offset) usp.set('offset', String(filters.offset))
    const qs = usp.toString()
    return await apiFetch<AdminAttestation[]>(
      `/admin/attestations${qs ? `?${qs}` : ''}`,
    )
  }

  async function revokeAttestation(
    attestationId: string,
    reason: string,
  ): Promise<AdminAttestation> {
    return await apiFetch<AdminAttestation>(
      `/admin/attestations/${attestationId}/revoke`,
      {
        method: 'POST',
        body: { reason },
      },
    )
  }

  return { listAttestations, revokeAttestation }
}
