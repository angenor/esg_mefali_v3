/**
 * T022 — Smoke test du store Pinia F047 projectEsg.
 */
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// Stub useRuntimeConfig + useAuthStore (Nuxt auto-imports)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://api.test/api' },
}))
;(globalThis as Record<string, unknown>).useAuthStore = () => ({
  accessToken: 'fake-token',
})

describe('projectEsg store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initialise un état vide', async () => {
    const { useProjectEsgStore } = await import('~/stores/projectEsg')
    const store = useProjectEsgStore()
    expect(store.assessments).toEqual([])
    expect(store.currentAssessment).toBeNull()
    expect(store.progressPercent).toBe(0)
    expect(store.isFinalized).toBe(false)
  })

  it('reset() vide les compteurs et le courant', async () => {
    const { useProjectEsgStore } = await import('~/stores/projectEsg')
    const store = useProjectEsgStore()
    store.lastScore = 75
    store.lastMissingCriteria = [{ id: 'a', code: 'X', label: 'y' }]
    store.reset()
    expect(store.lastScore).toBeNull()
    expect(store.lastMissingCriteria).toEqual([])
  })

  it('progressPercent calcule le ratio couverts/(couverts+manquants)', async () => {
    const { useProjectEsgStore } = await import('~/stores/projectEsg')
    const store = useProjectEsgStore()
    store.currentAssessment = {
      id: '00000000-0000-0000-0000-000000000001',
      account_id: 'a',
      project_id: 'p',
      referential_id: 'r',
      referential_version: '1.0',
      state: 'draft',
      score: null,
      pillar_scores: {},
      covered_criteria: ['c1', 'c2', 'c3'],
      missing_criteria: ['c4'],
      coverage_rate: null,
      snapshot_data: null,
      finalized_at: null,
      superseded_at: null,
      created_by: 'u',
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
      responses: [],
    }
    expect(store.progressPercent).toBe(75) // 3/(3+1) = 75%
  })
})
