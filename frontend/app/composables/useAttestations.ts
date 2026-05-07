import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'
import type {
  AttestationRead,
  AttestationSummary,
  AttestationType,
  VerificationResult,
} from '~/types/attestation'

/**
 * Composable pour la gestion des attestations vérifiables (F08).
 *
 * Méthodes :
 * - generateAttestation(type) : POST /api/attestations
 * - listAttestations() : GET /api/attestations
 * - getAttestation(id) : GET /api/attestations/{id}
 * - revokeAttestation(id, reason) : POST /api/attestations/{id}/revoke
 * - downloadPdf(id) : GET /api/attestations/{id}/download
 * - verifyPublic(id) : GET /api/public/verify/{id} (no-auth)
 */
export function useAttestations() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref('')

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  async function generateAttestation(
    type: AttestationType,
  ): Promise<AttestationRead | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/attestations`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ attestation_type: type }),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || "Erreur lors de la génération de l'attestation")
      }
      return (await response.json()) as AttestationRead
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function listAttestations(): Promise<AttestationSummary[]> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/attestations`, {
        headers: getHeaders(),
      })
      if (!response.ok) {
        throw new Error('Erreur lors du chargement des attestations')
      }
      return (await response.json()) as AttestationSummary[]
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return []
    } finally {
      loading.value = false
    }
  }

  async function getAttestation(id: string): Promise<AttestationRead | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/attestations/${id}`, {
        headers: getHeaders(),
      })
      if (!response.ok) {
        throw new Error('Attestation introuvable')
      }
      return (await response.json()) as AttestationRead
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function revokeAttestation(
    id: string,
    reason: string,
  ): Promise<AttestationSummary | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/attestations/${id}/revoke`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ reason }),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Erreur lors de la révocation')
      }
      return (await response.json()) as AttestationSummary
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function downloadPdf(id: string, filename: string = 'attestation.pdf'): Promise<boolean> {
    try {
      const response = await fetch(`${apiBase}/attestations/${id}/download`, {
        headers: getHeaders(),
      })
      if (!response.ok) {
        throw new Error('Téléchargement échoué')
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return false
    }
  }

  async function copyToClipboard(text: string): Promise<boolean> {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text)
        return true
      }
      // Fallback ancien
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
      return true
    } catch {
      return false
    }
  }

  async function verifyPublic(id: string): Promise<VerificationResult | null> {
    try {
      const response = await fetch(`${apiBase}/public/verify/${id}`)
      if (!response.ok) {
        return null
      }
      return (await response.json()) as VerificationResult
    } catch {
      return null
    }
  }

  return {
    loading,
    error,
    generateAttestation,
    listAttestations,
    getAttestation,
    revokeAttestation,
    downloadPdf,
    copyToClipboard,
    verifyPublic,
  }
}
