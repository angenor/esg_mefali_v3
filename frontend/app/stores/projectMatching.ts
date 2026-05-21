// F045 — Store Pinia volatile pour les matches projet-centric
//
// Pas de persistance localStorage (volatile par design).

import { defineStore } from 'pinia'
import type { MatchFundsResponse } from '~/types/projectMatching'
import { useProjectMatching } from '~/composables/useProjectMatching'

interface State {
  matchesByProject: Record<string, MatchFundsResponse>
  loadingByProject: Record<string, boolean>
}

export const useProjectMatchingStore = defineStore('projectMatching', {
  state: (): State => ({
    matchesByProject: {},
    loadingByProject: {},
  }),

  actions: {
    async loadMatches(
      projectId: string,
      opts: { minScore?: number; limit?: number; forceRecompute?: boolean } = {},
    ): Promise<MatchFundsResponse | null> {
      this.loadingByProject = { ...this.loadingByProject, [projectId]: true }
      try {
        const { matchFunds } = useProjectMatching()
        const response = await matchFunds(projectId, opts)
        if (response) {
          this.matchesByProject = {
            ...this.matchesByProject,
            [projectId]: response,
          }
        }
        return response
      } finally {
        this.loadingByProject = { ...this.loadingByProject, [projectId]: false }
      }
    },

    async recompute(projectId: string): Promise<MatchFundsResponse | null> {
      return this.loadMatches(projectId, { forceRecompute: true })
    },

    clearCache(projectId: string): void {
      const { [projectId]: _drop, ...rest } = this.matchesByProject
      void _drop
      this.matchesByProject = rest
    },

    clearAll(): void {
      this.matchesByProject = {}
      this.loadingByProject = {}
    },
  },

  getters: {
    getMatches: (state) => (projectId: string): MatchFundsResponse | null =>
      state.matchesByProject[projectId] ?? null,
    isLoading: (state) => (projectId: string): boolean =>
      Boolean(state.loadingByProject[projectId]),
  },
})
