// F14 — Store Pinia matches : cache local des matches projet/offre,
// comparateurs par fond, abonnements aux alertes.

import { defineStore } from 'pinia'
import type {
  ComparisonResult,
  MatchAlertSubscription,
  MatchBottleneck,
  OfferMatch,
} from '~/types/matching'

interface MatchesState {
  matchesByProject: Record<string, OfferMatch[]>
  totalsByProject: Record<string, number>
  comparisonsByFund: Record<string, ComparisonResult>
  subscriptionsByProject: Record<string, MatchAlertSubscription>
  loading: boolean
  error: string | null
}

export const useMatchesStore = defineStore('matches', {
  state: (): MatchesState => ({
    matchesByProject: {},
    totalsByProject: {},
    comparisonsByFund: {},
    subscriptionsByProject: {},
    loading: false,
    error: null,
  }),

  getters: {
    getMatchesForProject(state) {
      return (projectId: string): OfferMatch[] =>
        state.matchesByProject[projectId] ?? []
    },
    getTotalForProject(state) {
      return (projectId: string): number =>
        state.totalsByProject[projectId] ?? 0
    },
    getActiveMatches(state) {
      return (projectId: string): OfferMatch[] =>
        (state.matchesByProject[projectId] ?? []).filter(
          (m) => m.status !== 'dismissed',
        )
    },
    getTopMatch(state) {
      return (projectId: string): OfferMatch | null => {
        const list = state.matchesByProject[projectId] ?? []
        if (list.length === 0) return null
        return [...list].sort((a, b) => b.globalScore - a.globalScore)[0] ?? null
      }
    },
    getComparison(state) {
      return (fundId: string): ComparisonResult | null =>
        state.comparisonsByFund[fundId] ?? null
    },
    getSubscription(state) {
      return (projectId: string): MatchAlertSubscription | null =>
        state.subscriptionsByProject[projectId] ?? null
    },
    bottleneckCount(state) {
      return (projectId: string): Record<MatchBottleneck, number> => {
        const list = state.matchesByProject[projectId] ?? []
        return list.reduce<Record<MatchBottleneck, number>>(
          (acc, m) => {
            acc[m.bottleneck] = (acc[m.bottleneck] ?? 0) + 1
            return acc
          },
          { fund: 0, intermediary: 0, balanced: 0 },
        )
      }
    },
  },

  actions: {
    setMatches(projectId: string, matches: OfferMatch[], total: number) {
      this.matchesByProject = {
        ...this.matchesByProject,
        [projectId]: matches,
      }
      this.totalsByProject = {
        ...this.totalsByProject,
        [projectId]: total,
      }
    },
    setComparison(fundId: string, comparison: ComparisonResult) {
      this.comparisonsByFund = {
        ...this.comparisonsByFund,
        [fundId]: comparison,
      }
    },
    setSubscription(projectId: string, subscription: MatchAlertSubscription) {
      this.subscriptionsByProject = {
        ...this.subscriptionsByProject,
        [projectId]: subscription,
      }
    },
    setLoading(loading: boolean) {
      this.loading = loading
    },
    setError(error: string | null) {
      this.error = error
    },
    upsertMatch(projectId: string, match: OfferMatch) {
      const list = this.matchesByProject[projectId] ?? []
      const idx = list.findIndex((m) => m.id === match.id)
      const next =
        idx >= 0
          ? list.map((m, i) => (i === idx ? match : m))
          : [match, ...list]
      this.matchesByProject = {
        ...this.matchesByProject,
        [projectId]: next,
      }
    },
    reset() {
      this.matchesByProject = {}
      this.totalsByProject = {}
      this.comparisonsByFund = {}
      this.subscriptionsByProject = {}
      this.loading = false
      this.error = null
    },
  },
})
