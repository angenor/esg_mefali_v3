/**
 * F13 — Composable pour le scoring ESG multi-référentiels.
 *
 * Encapsule les appels API et le polling pour les recalculs async.
 */

import { ref, computed } from 'vue'
import { useAuth, SessionExpiredError } from '~/composables/useAuth'
import type {
  ComparisonResult,
  GenerateReportRequest,
  RecomputeRequestResponse,
  ReferentialScore,
} from '~/types/esg'

export function useEsgMultiReferential() {
  const { apiFetch, handleAuthFailure } = useAuth()

  const loading = ref(false)
  const error = ref('')
  const sessionExpired = ref(false)

  async function handleError(e: unknown, fallback: string): Promise<void> {
    if (e instanceof SessionExpiredError) {
      sessionExpired.value = true
      await handleAuthFailure()
      return
    }
    error.value = e instanceof Error ? e.message : fallback
  }

  /**
   * Liste des scores courants (superseded_by IS NULL) pour une évaluation.
   */
  async function getReferentialScores(
    assessmentId: string,
  ): Promise<ReferentialScore[]> {
    loading.value = true
    error.value = ''
    try {
      return await apiFetch<ReferentialScore[]>(
        `/esg/assessments/${assessmentId}/referential-scores`,
      )
    } catch (e) {
      await handleError(e, 'Erreur lors du chargement des scores multi-référentiels')
      return []
    } finally {
      loading.value = false
    }
  }

  /**
   * Historique des scores supersédés pour un référentiel donné.
   */
  async function getReferentialScoresHistory(
    assessmentId: string,
    referentialId?: string,
  ): Promise<ReferentialScore[]> {
    loading.value = true
    error.value = ''
    try {
      const params = referentialId ? `?referential_id=${referentialId}` : ''
      return await apiFetch<ReferentialScore[]>(
        `/esg/assessments/${assessmentId}/referential-scores/history${params}`,
      )
    } catch (e) {
      await handleError(e, 'Erreur lors du chargement de l’historique')
      return []
    } finally {
      loading.value = false
    }
  }

  /**
   * Enqueue un recalcul async d'un référentiel ciblé (ou tous si non fourni).
   * Retourne un recompute_request_id pour le polling.
   */
  async function recomputeScore(
    assessmentId: string,
    referentielId?: string,
  ): Promise<RecomputeRequestResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const params = referentielId ? `?referentiel_id=${referentielId}` : ''
      return await apiFetch<RecomputeRequestResponse>(
        `/esg/assessments/${assessmentId}/recompute-score${params}`,
        { method: 'POST' },
      )
    } catch (e) {
      await handleError(e, 'Erreur lors du recalcul')
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Polling : appelle getReferentialScores toutes les `intervalMs` jusqu'à
   * détecter un computed_at plus récent que `since` ou jusqu'au timeout.
   */
  async function pollReferentialScores(
    assessmentId: string,
    since: Date,
    intervalMs = 2000,
    timeoutMs = 30000,
  ): Promise<ReferentialScore[]> {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      const scores = await getReferentialScores(assessmentId)
      const updated = scores.some((s) => new Date(s.computed_at) > since)
      if (updated) {
        return scores
      }
      await new Promise((r) => setTimeout(r, intervalMs))
    }
    // Timeout : retourner ce qu'on a
    return await getReferentialScores(assessmentId)
  }

  /**
   * Génère un rapport PDF multi-référentiels.
   */
  async function generateMultiReferentialReport(
    assessmentId: string,
    referentials: string[] = ['mefali'],
    includeAppendixSources = true,
  ): Promise<{ report_id: string; status: string } | null> {
    loading.value = true
    error.value = ''
    try {
      const body: GenerateReportRequest = {
        referentials,
        include_appendix_sources: includeAppendixSources,
      }
      return await apiFetch<{ report_id: string; status: string }>(
        `/reports/esg/${assessmentId}/generate`,
        {
          method: 'POST',
          body: JSON.stringify(body),
        },
      )
    } catch (e) {
      await handleError(e, 'Erreur lors de la génération du rapport')
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    sessionExpired: computed(() => sessionExpired.value),
    getReferentialScores,
    getReferentialScoresHistory,
    recomputeScore,
    pollReferentialScores,
    generateMultiReferentialReport,
  }
}
