/**
 * F18 — Composable Mobile Money + Photos IA + Données publiques.
 *
 * Tous les appels qui requièrent un consentement (Mobile Money, Photos,
 * Données publiques) propagent fidèlement le 403 ``consent_required`` du
 * backend pour que l'UI puisse présenter le lien vers le centre de
 * consentements F05.
 */

import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'
import type {
  CreditPhotoRead,
  MethodologyResponse,
  MobileMoneyAnalysisRead,
  MobileMoneyImportRead,
  MobileMoneyUploadResponse,
  Provider,
  PublicDataSourceCreate,
  PublicDataSourceRead,
} from '~/types/creditAlternative'

export class ConsentRequiredError extends Error {
  consentType: string

  constructor(consentType: string, message?: string) {
    super(message ?? `Consentement ${consentType} requis`)
    this.name = 'ConsentRequiredError'
    this.consentType = consentType
  }
}

export function useCreditAlternativeData() {
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase
  const authStore = useAuthStore()

  const loading = ref(false)
  const error = ref('')

  function authHeaders(): Record<string, string> {
    return authStore.accessToken
      ? { Authorization: `Bearer ${authStore.accessToken}` }
      : {}
  }

  async function handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 403) {
      const body = await response.json().catch(() => ({}))
      const detail = body?.detail ?? body
      const consentType =
        (typeof detail === 'object' && detail?.consent_type) ?? 'unknown'
      throw new ConsentRequiredError(
        consentType,
        typeof detail === 'object' ? detail?.detail : undefined
      )
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(
        body?.detail?.detail ?? body?.detail ?? `HTTP ${response.status}`
      )
    }
    return (await response.json()) as T
  }

  async function uploadMobileMoney(
    file: File,
    provider: Provider
  ): Promise<MobileMoneyUploadResponse> {
    loading.value = true
    error.value = ''
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('provider', provider)
      const resp = await fetch(`${apiBase}/credit/mobile-money/upload`, {
        method: 'POST',
        headers: authHeaders(),
        body: fd,
      })
      return await handleResponse<MobileMoneyUploadResponse>(resp)
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getMobileMoneyAnalysis(): Promise<MobileMoneyAnalysisRead | null> {
    const resp = await fetch(`${apiBase}/credit/mobile-money/analysis`, {
      headers: authHeaders(),
    })
    return await handleResponse<MobileMoneyAnalysisRead | null>(resp)
  }

  async function listImports(): Promise<MobileMoneyImportRead[]> {
    const resp = await fetch(`${apiBase}/credit/mobile-money/imports`, {
      headers: authHeaders(),
    })
    return await handleResponse<MobileMoneyImportRead[]>(resp)
  }

  async function declarePublicData(
    payload: PublicDataSourceCreate
  ): Promise<PublicDataSourceRead> {
    loading.value = true
    error.value = ''
    try {
      const resp = await fetch(`${apiBase}/credit/public-data/declare`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      return await handleResponse<PublicDataSourceRead>(resp)
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function listPublicData(): Promise<PublicDataSourceRead[]> {
    const resp = await fetch(`${apiBase}/credit/public-data`, {
      headers: authHeaders(),
    })
    return await handleResponse<PublicDataSourceRead[]>(resp)
  }

  async function deletePublicData(id: string): Promise<void> {
    const resp = await fetch(`${apiBase}/credit/public-data/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (resp.status === 204) return
    await handleResponse<void>(resp)
  }

  async function getMethodology(): Promise<MethodologyResponse> {
    // Endpoint public — pas de Bearer
    const resp = await fetch(`${apiBase}/credit/methodology`)
    return await handleResponse<MethodologyResponse>(resp)
  }

  return {
    loading,
    error,
    uploadMobileMoney,
    getMobileMoneyAnalysis,
    listImports,
    declarePublicData,
    listPublicData,
    deletePublicData,
    getMethodology,
  }
}
