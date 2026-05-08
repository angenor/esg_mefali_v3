import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSimulatorStore } from '~/stores/simulator'
import type { MultiSimulateResponse } from '~/types/simulator'

describe('useSimulatorStore (F16)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('état initial vide', () => {
    const store = useSimulatorStore()
    expect(store.selectedProjectId).toBeNull()
    expect(store.selectedOfferIds).toEqual([])
    expect(store.lastResult).toBeNull()
    expect(store.canSimulate).toBe(false)
    expect(store.offersCount).toBe(0)
  })

  it('setSelectedProject change le projet courant', () => {
    const store = useSimulatorStore()
    store.setSelectedProject('p-1')
    expect(store.selectedProjectId).toBe('p-1')
  })

  it('toggleOffer ajoute puis retire une offre', () => {
    const store = useSimulatorStore()
    store.toggleOffer('o-1')
    expect(store.selectedOfferIds).toEqual(['o-1'])
    store.toggleOffer('o-1')
    expect(store.selectedOfferIds).toEqual([])
  })

  it('toggleOffer impose hard cap à 5 offres', () => {
    const store = useSimulatorStore()
    for (let i = 0; i < 7; i++) {
      store.toggleOffer(`o-${i}`)
    }
    expect(store.selectedOfferIds.length).toBe(5)
  })

  it('canSimulate exige projet + 1..5 offres', () => {
    const store = useSimulatorStore()
    expect(store.canSimulate).toBe(false)
    store.setSelectedProject('p-1')
    expect(store.canSimulate).toBe(false)
    store.toggleOffer('o-1')
    expect(store.canSimulate).toBe(true)
  })

  it('reset vide tout le state', () => {
    const store = useSimulatorStore()
    store.setSelectedProject('p-1')
    store.toggleOffer('o-1')
    store.setLastResult({
      project_id: 'p-1',
      per_offer: {},
      comparison_metadata: {
        cheapest_offer_id: null,
        fastest_offer_id: null,
        degraded_offers: [],
        total_offers: 1,
      },
      factor_snapshot_loaded_at: '2026-05-08T00:00:00Z',
    } as MultiSimulateResponse)
    store.reset()
    expect(store.selectedProjectId).toBeNull()
    expect(store.selectedOfferIds).toEqual([])
    expect(store.lastResult).toBeNull()
  })

  it('clearOffers vide uniquement les offres', () => {
    const store = useSimulatorStore()
    store.setSelectedProject('p-1')
    store.toggleOffer('o-1')
    store.clearOffers()
    expect(store.selectedOfferIds).toEqual([])
    expect(store.selectedProjectId).toBe('p-1')
  })
})
