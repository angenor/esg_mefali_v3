// F16 — Composable simulateur multi-offres sourcé.
//
// Volatile : aucune persistance locale autre que le state Pinia, qui est
// vidé à la déconnexion (FR-012).

import { ref } from 'vue'
import { useAuth, ApiFetchError, SessionExpiredError } from '~/composables/useAuth'
import { useSimulatorStore } from '~/stores/simulator'
import type {
  MultiSimulateRequest,
  MultiSimulateResponse,
} from '~/types/simulator'

export function useSimulator() {
  const { apiFetch, handleAuthFailure } = useAuth()
  const store = useSimulatorStore()
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function simulateMulti(
    projectId: string,
    offerIds: string[],
  ): Promise<MultiSimulateResponse | null> {
    if (offerIds.length === 0) {
      error.value = 'Aucune offre sélectionnée.'
      return null
    }
    if (offerIds.length > 5) {
      error.value = 'Au plus 5 offres par comparaison.'
      return null
    }
    loading.value = true
    error.value = null
    const body: MultiSimulateRequest = { offer_ids: offerIds }
    try {
      const response = await apiFetch<MultiSimulateResponse>(
        `/api/projects/${projectId}/simulate-multi`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
      )
      store.setLastResult(response)
      return response
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        await handleAuthFailure()
        return null
      }
      if (err instanceof ApiFetchError) {
        if (err.status === 404) {
          error.value = 'Projet introuvable.'
        } else if (err.status === 403) {
          error.value = 'Une ou plusieurs offres sont inaccessibles.'
        } else if (err.status === 422) {
          error.value = 'Requête invalide (1 à 5 offres).'
        } else {
          error.value = err.message || 'Erreur de simulation.'
        }
      } else {
        error.value = 'Erreur réseau.'
      }
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    simulateMulti,
  }
}
