// F16 — Store Pinia volatile pour le simulateur (aucune persistance disque).

import { defineStore } from 'pinia'
import type { MultiSimulateResponse } from '~/types/simulator'

interface SimulatorState {
  selectedProjectId: string | null
  selectedOfferIds: string[]
  lastResult: MultiSimulateResponse | null
}

export const useSimulatorStore = defineStore('simulator', {
  state: (): SimulatorState => ({
    selectedProjectId: null,
    selectedOfferIds: [],
    lastResult: null,
  }),

  getters: {
    canSimulate: (state) =>
      state.selectedProjectId !== null
      && state.selectedOfferIds.length >= 1
      && state.selectedOfferIds.length <= 5,
    offersCount: (state) => state.selectedOfferIds.length,
  },

  actions: {
    setSelectedProject(projectId: string | null) {
      this.selectedProjectId = projectId
    },
    toggleOffer(offerId: string) {
      const idx = this.selectedOfferIds.indexOf(offerId)
      if (idx >= 0) {
        this.selectedOfferIds.splice(idx, 1)
        return
      }
      // Hard cap 5 (FR-014)
      if (this.selectedOfferIds.length >= 5) {
        return
      }
      this.selectedOfferIds.push(offerId)
    },
    clearOffers() {
      this.selectedOfferIds = []
    },
    setLastResult(result: MultiSimulateResponse | null) {
      this.lastResult = result
    },
    reset() {
      this.selectedProjectId = null
      this.selectedOfferIds = []
      this.lastResult = null
    },
  },
})
