/**
 * T023 [US1] — Composable useProjectEsg : wrappers fetch + gestion d'erreur
 * 404/409/422 avec messages FR.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://api.test/api' },
}))
;(globalThis as Record<string, unknown>).useAuthStore = () => ({
  accessToken: 'fake-token',
})

const fetchMock = vi.fn()
;(globalThis as Record<string, unknown>).fetch = fetchMock as unknown

describe('useProjectEsg composable (F047 US1)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('listAssessments envoie GET avec filtre state', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    })
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const out = await api.listAssessments('proj-1', 'draft')
    expect(out).toEqual([])
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/projects/proj-1/esg-assessments?state=draft',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('createAssessment retourne le payload backend', async () => {
    const fakeAssessment = {
      id: 'a-1',
      state: 'draft',
      project_id: 'proj-1',
    }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => fakeAssessment,
    })
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const out = await api.createAssessment('proj-1', {
      referential_id: 'ref-ifc-ps',
    } as never)
    expect(out).toEqual(fakeAssessment)
  })

  it('saveCriterion → 422 retourne null + message FR détaillé', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'source_id et unsourced mutuellement exclusifs' }),
    })
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const out = await api.saveCriterion('proj-1', 'a-1', {
      criterion_id: 'c-1',
      response_type: 'qcu',
      response_value: { choice: 'yes' },
      source_id: 'src-1',
      unsourced: true,
    } as never)
    expect(out).toBeNull()
    expect(api.error.value).toMatch(/source_id/i)
  })

  it('finalize → 409 retourne null + message FR par défaut', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => null,
    })
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const out = await api.finalize('proj-1', 'a-1')
    expect(out).toBeNull()
    expect(api.error.value).toMatch(/Conflit/i)
  })

  it('finalize → 404 retourne null + message FR par défaut', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => null,
    })
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const out = await api.getAssessment('proj-1', 'a-1')
    expect(out).toBeNull()
    expect(api.error.value).toMatch(/introuvable/i)
  })

  it('deleteAssessment retourne true en 204 (success)', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => null,
    })
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const ok = await api.deleteAssessment('proj-1', 'a-1')
    expect(ok).toBe(true)
    expect(api.error.value).toBe('')
  })

  it('réseau échoué → error.value contient le message', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'))
    const { useProjectEsg } = await import('~/composables/useProjectEsg')
    const api = useProjectEsg()
    const out = await api.listAssessments('proj-1')
    expect(out).toBeNull()
    expect(api.error.value).toBe('network down')
  })
})
