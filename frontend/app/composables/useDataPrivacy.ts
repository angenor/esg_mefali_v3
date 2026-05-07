/**
 * F05 — Composable « Mes Données » : RGPD utilisateur.
 *
 * Expose :
 * - useInventory()  : compteurs et dates de dernière modification.
 * - useExport()     : déclenche l'export ZIP (mode sync ou async).
 * - useDeletion()   : verify-password, schedule, cancel.
 *
 * Tous les appels passent par ``apiFetch`` (intercepteur JWT + refresh).
 */

import { ref } from 'vue'
import { useAuth } from './useAuth'

// ── Types
export type ConsentType =
  | 'profile_analysis'
  | 'document_analysis_ai'
  | 'mobile_money_analysis'
  | 'photos_ia_analysis'
  | 'public_data_analysis'
  | 'credit_certificate_generation'
  | 'product_communications'

export type LegalBasis =
  | 'consent'
  | 'contract'
  | 'legal_obligation'
  | 'legitimate_interest'

export interface InventoryCounts {
  profile: number
  projects: number
  applications: number
  esg_assessments: number
  carbon_assessments: number
  credit_scores: number
  documents: number
  conversations: number
  messages: number
  attestations: number
  consents: number
}

export interface InventoryLastModified {
  profile: string | null
  projects: string | null
  applications: string | null
  esg_assessments: string | null
  carbon_assessments: string | null
  credit_scores: string | null
  documents: string | null
  conversations: string | null
  messages: string | null
  attestations: string | null
  consents: string | null
}

export interface InventoryResponse {
  counts: InventoryCounts
  last_modified: InventoryLastModified
}

export interface ConsentItem {
  type: ConsentType
  granted: boolean
  granted_at: string | null
  revoked_at: string | null
  legal_basis: LegalBasis
  version: string
  label: string
  description: string
}

export interface ScheduleDeletionResponse {
  deletion_scheduled_at: string
  cancel_url: string | null
  message: string
}

export interface CancelDeletionResponse {
  cancelled_at: string
  message: string
}

export function useDataPrivacy() {
  const { apiFetch } = useAuth()

  // ── Inventory
  function useInventory() {
    const data = ref<InventoryResponse | null>(null)
    const loading = ref(false)
    const error = ref<string | null>(null)

    async function fetchInventory(): Promise<void> {
      loading.value = true
      error.value = null
      try {
        data.value = await apiFetch<InventoryResponse>(
          '/api/me/data/inventory',
        )
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      } finally {
        loading.value = false
      }
    }

    return { data, loading, error, fetchInventory }
  }

  // ── Export
  function useExport() {
    const exporting = ref(false)
    const error = ref<string | null>(null)
    const asyncJobId = ref<string | null>(null)

    async function downloadExport(): Promise<void> {
      exporting.value = true
      error.value = null
      asyncJobId.value = null
      try {
        const config = useRuntimeConfig()
        const authStore = useAuthStore()
        const headers: Record<string, string> = {}
        if (authStore.accessToken) {
          headers['Authorization'] = `Bearer ${authStore.accessToken}`
        }
        const response = await fetch(
          `${config.public.apiBase}/api/me/data/export?format=json`,
          { method: 'GET', headers },
        )
        if (response.status === 202) {
          const body = await response.json()
          asyncJobId.value = body.job_id
          return
        }
        if (!response.ok) {
          throw new Error(`Erreur export : ${response.status}`)
        }
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const cd = response.headers.get('content-disposition') || ''
        const match = cd.match(/filename="?([^"]+)"?/)
        a.download = match
          ? match[1]
          : `esg-mefali-export-${new Date().toISOString().slice(0, 10)}.zip`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      } finally {
        exporting.value = false
      }
    }

    return { exporting, error, asyncJobId, downloadExport }
  }

  // ── Deletion
  function useDeletion() {
    const loading = ref(false)
    const error = ref<string | null>(null)

    async function verifyPassword(password: string): Promise<boolean> {
      loading.value = true
      error.value = null
      try {
        const res = await apiFetch<{ verified: boolean }>(
          '/api/me/account/verify-password',
          {
            method: 'POST',
            body: JSON.stringify({ password }),
          },
        )
        return res.verified
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : 'Mot de passe incorrect'
        return false
      } finally {
        loading.value = false
      }
    }

    async function scheduleDeletion(
      password: string,
      confirmation_text: string,
    ): Promise<ScheduleDeletionResponse | null> {
      loading.value = true
      error.value = null
      try {
        const res = await apiFetch<ScheduleDeletionResponse>(
          '/api/me/account/schedule-deletion',
          {
            method: 'POST',
            body: JSON.stringify({ password, confirmation_text }),
          },
        )
        return res
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : 'Erreur'
        return null
      } finally {
        loading.value = false
      }
    }

    async function cancelDeletion(): Promise<CancelDeletionResponse | null> {
      loading.value = true
      error.value = null
      try {
        const res = await apiFetch<CancelDeletionResponse>(
          '/api/me/account/cancel-deletion',
          { method: 'POST' },
        )
        return res
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : 'Erreur'
        return null
      } finally {
        loading.value = false
      }
    }

    return {
      loading,
      error,
      verifyPassword,
      scheduleDeletion,
      cancelDeletion,
    }
  }

  return { useInventory, useExport, useDeletion }
}
