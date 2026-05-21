// F045 — Composable Matching projet-centric

import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'
import type {
  MatchFundsItem,
  MatchFundsRequestOptions,
  MatchFundsResponse,
} from '~/types/projectMatching'
import type {
  OfferMatch,
  OfferMatchListResponse,
  RecomputeMatchesResponse,
} from '~/types/matching'

interface ListMatchesFilters {
  minScore?: number
  page?: number
  limit?: number
}

export interface ProjectMatchingError {
  status: number
  messageFr: string
}

function translateError(status: number): string {
  if (status === 404) {
    return 'Projet introuvable ou inaccessible (vérifiez vos droits).'
  }
  if (status === 403) {
    return 'Accès refusé : compte requis pour le matching.'
  }
  if (status === 503) {
    return 'La fonctionnalité de matching projet est temporairement indisponible (migration en cours).'
  }
  if (status === 422) {
    return 'Paramètres invalides.'
  }
  return `Erreur ${status}`
}

export function useProjectMatching() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref<ProjectMatchingError | null>(null)

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  function setErr(status: number): void {
    error.value = { status, messageFr: translateError(status) }
  }

  async function matchFunds(
    projectId: string,
    opts: MatchFundsRequestOptions = {},
  ): Promise<MatchFundsResponse | null> {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (opts.minScore !== undefined) params.set('min_score', String(opts.minScore))
      if (opts.limit !== undefined) params.set('limit', String(opts.limit))
      if (opts.forceRecompute !== undefined)
        params.set('force_recompute', String(opts.forceRecompute))

      const url = `${apiBase}/projects/${projectId}/match-funds?${params}`
      const response = await fetch(url, {
        method: 'POST',
        headers: getHeaders(),
      })
      if (!response.ok) {
        setErr(response.status)
        return null
      }
      return (await response.json()) as MatchFundsResponse
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = { status: 0, messageFr: `Erreur réseau : ${msg}` }
      return null
    } finally {
      loading.value = false
    }
  }

  async function getMatches(
    projectId: string,
    filters: ListMatchesFilters = {},
  ): Promise<OfferMatchListResponse | null> {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (filters.minScore !== undefined)
        params.set('min_score', String(filters.minScore))
      if (filters.page !== undefined) params.set('page', String(filters.page))
      if (filters.limit !== undefined) params.set('limit', String(filters.limit))

      const url = `${apiBase}/projects/${projectId}/matches?${params}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        setErr(response.status)
        return null
      }
      return (await response.json()) as OfferMatchListResponse
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = { status: 0, messageFr: `Erreur réseau : ${msg}` }
      return null
    } finally {
      loading.value = false
    }
  }

  async function recomputeMatches(
    projectId: string,
  ): Promise<RecomputeMatchesResponse | null> {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(
        `${apiBase}/projects/${projectId}/recompute-matches`,
        { method: 'POST', headers: getHeaders() },
      )
      if (response.status !== 202) {
        setErr(response.status)
        return null
      }
      return (await response.json()) as RecomputeMatchesResponse
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = { status: 0, messageFr: `Erreur réseau : ${msg}` }
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
    error.value = null
    try {
      const url = `${apiBase}/projects/${projectId}/match-details/${offerId}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        setErr(response.status)
        return null
      }
      return (await response.json()) as OfferMatch
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = { status: 0, messageFr: `Erreur réseau : ${msg}` }
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    matchFunds,
    getMatches,
    recomputeMatches,
    getMatchDetails,
  }
}

export type { MatchFundsItem }
