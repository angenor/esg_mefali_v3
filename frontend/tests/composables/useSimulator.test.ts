import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * F16 — Tests useSimulator.
 * Mocke `useAuth().apiFetch` pour simuler les réponses backend.
 */

const mockApiFetch = vi.fn()
const mockHandleAuthFailure = vi.fn()

class MockApiFetchError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

class MockSessionExpiredError extends Error {}

vi.mock('~/composables/useAuth', () => ({
  useAuth: () => ({
    apiFetch: mockApiFetch,
    handleAuthFailure: mockHandleAuthFailure,
  }),
  ApiFetchError: MockApiFetchError,
  SessionExpiredError: MockSessionExpiredError,
}))

describe('useSimulator (F16)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApiFetch.mockReset()
    mockHandleAuthFailure.mockReset()
  })

  it('simulateMulti POST sur le bon endpoint et stocke le résultat', async () => {
    const fakeResponse = {
      project_id: 'p-1',
      per_offer: {},
      comparison_metadata: {
        cheapest_offer_id: null,
        fastest_offer_id: null,
        degraded_offers: [],
        total_offers: 1,
      },
      factor_snapshot_loaded_at: '2026-05-08T00:00:00Z',
    }
    mockApiFetch.mockResolvedValueOnce(fakeResponse)

    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    const out = await sim.simulateMulti('p-1', ['o-1'])

    expect(mockApiFetch).toHaveBeenCalledWith(
      '/api/projects/p-1/simulate-multi',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ offer_ids: ['o-1'] }),
      }),
    )
    expect(out).toEqual(fakeResponse)
    expect(sim.error.value).toBeNull()
  })

  it('rejette une liste vide sans appel HTTP', async () => {
    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    const out = await sim.simulateMulti('p-1', [])
    expect(mockApiFetch).not.toHaveBeenCalled()
    expect(out).toBeNull()
    expect(sim.error.value).toContain('Aucune offre')
  })

  it('rejette une liste > 5 offres sans appel HTTP', async () => {
    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    const out = await sim.simulateMulti('p-1', ['1', '2', '3', '4', '5', '6'])
    expect(mockApiFetch).not.toHaveBeenCalled()
    expect(out).toBeNull()
    expect(sim.error.value).toContain('5 offres')
  })

  it('mappe 404 → message projet introuvable', async () => {
    mockApiFetch.mockRejectedValueOnce(
      new MockApiFetchError(404, 'project_not_found'),
    )
    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    await sim.simulateMulti('p-1', ['o-1'])
    expect(sim.error.value).toContain('Projet introuvable')
  })

  it('mappe 403 → message offres inaccessibles', async () => {
    mockApiFetch.mockRejectedValueOnce(
      new MockApiFetchError(403, 'access_denied'),
    )
    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    await sim.simulateMulti('p-1', ['o-1'])
    expect(sim.error.value).toContain('inaccessibles')
  })

  it('mappe 422 → message borne 1..5', async () => {
    mockApiFetch.mockRejectedValueOnce(
      new MockApiFetchError(422, 'validation_error'),
    )
    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    await sim.simulateMulti('p-1', ['o-1'])
    expect(sim.error.value).toContain('1 à 5')
  })

  it('SessionExpiredError déclenche handleAuthFailure', async () => {
    mockApiFetch.mockRejectedValueOnce(new MockSessionExpiredError())
    const { useSimulator } = await import('~/composables/useSimulator')
    const sim = useSimulator()
    await sim.simulateMulti('p-1', ['o-1'])
    expect(mockHandleAuthFailure).toHaveBeenCalled()
  })
})
