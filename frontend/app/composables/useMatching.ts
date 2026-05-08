// F14 — Composable Matching Project ↔ Offer

import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'
import type {
  ComparisonResult,
  MatchAlertSubscription,
  MatchAlertSubscriptionUpdate,
  OfferMatch,
  OfferMatchListResponse,
  RecomputeMatchesResponse,
} from '~/types/matching'

interface ListMatchesFilters {
  minScore?: number
  bottleneck?: 'fund' | 'intermediary' | 'balanced'
  fundId?: string
  page?: number
  limit?: number
}

export function useMatching() {
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

  async function listMatches(
    projectId: string,
    filters: ListMatchesFilters = {},
  ): Promise<OfferMatchListResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const params = new URLSearchParams()
      if (filters.minScore !== undefined)
        params.set('min_score', String(filters.minScore))
      if (filters.bottleneck) params.set('bottleneck', filters.bottleneck)
      if (filters.fundId) params.set('fund_id', filters.fundId)
      if (filters.page !== undefined) params.set('page', String(filters.page))
      if (filters.limit !== undefined) params.set('limit', String(filters.limit))

      const url = `${apiBase}/api/projects/${projectId}/matches?${params}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        error.value = `Erreur ${response.status}`
        return null
      }
      return (await response.json()) as OfferMatchListResponse
    } catch (e) {
      error.value = `Erreur réseau: ${(e as Error).message}`
      return null
    } finally {
      loading.value = false
    }
  }

  async function recomputeMatches(
    projectId: string,
  ): Promise<RecomputeMatchesResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(
        `${apiBase}/api/projects/${projectId}/recompute-matches`,
        { method: 'POST', headers: getHeaders() },
      )
      if (response.status !== 202) {
        error.value = `Erreur ${response.status}`
        return null
      }
      return (await response.json()) as RecomputeMatchesResponse
    } catch (e) {
      error.value = `Erreur réseau: ${(e as Error).message}`
      return null
    } finally {
      loading.value = false
    }
  }

  async function compareOffersForFund(
    projectId: string,
    fundId: string,
  ): Promise<ComparisonResult | null> {
    loading.value = true
    error.value = ''
    try {
      const url =
        `${apiBase}/api/projects/${projectId}/compare?fund_id=${fundId}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        error.value = `Erreur ${response.status}`
        return null
      }
      return (await response.json()) as ComparisonResult
    } catch (e) {
      error.value = `Erreur réseau: ${(e as Error).message}`
      return null
    } finally {
      loading.value = false
    }
  }

  async function getMatchDetails(
    projectId: string,
    offerId: string,
  ): Promise<OfferMatch | null> {
    loading.value = true
    error.value = ''
    try {
      const url =
        `${apiBase}/api/projects/${projectId}/match-details/${offerId}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        error.value = `Erreur ${response.status}`
        return null
      }
      return (await response.json()) as OfferMatch
    } catch (e) {
      error.value = `Erreur réseau: ${(e as Error).message}`
      return null
    } finally {
      loading.value = false
    }
  }

  async function getSubscription(
    projectId: string,
  ): Promise<MatchAlertSubscription | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(
        `${apiBase}/api/projects/${projectId}/match-alerts`,
        { headers: getHeaders() },
      )
      if (!response.ok) {
        error.value = `Erreur ${response.status}`
        return null
      }
      return (await response.json()) as MatchAlertSubscription
    } catch (e) {
      error.value = `Erreur réseau: ${(e as Error).message}`
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateSubscription(
    projectId: string,
    payload: MatchAlertSubscriptionUpdate,
  ): Promise<MatchAlertSubscription | null> {
    loading.value = true
    error.value = ''
    try {
      const body: Record<string, unknown> = {}
      if (payload.isActive !== undefined) body.is_active = payload.isActive
      if (payload.minGlobalScore !== undefined)
        body.min_global_score = payload.minGlobalScore

      const response = await fetch(
        `${apiBase}/api/projects/${projectId}/match-alerts`,
        {
          method: 'PATCH',
          headers: getHeaders(),
          body: JSON.stringify(body),
        },
      )
      if (!response.ok) {
        error.value = `Erreur ${response.status}`
        return null
      }
      return (await response.json()) as MatchAlertSubscription
    } catch (e) {
      error.value = `Erreur réseau: ${(e as Error).message}`
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    listMatches,
    recomputeMatches,
    compareOffersForFund,
    getMatchDetails,
    getSubscription,
    updateSubscription,
  }
}
