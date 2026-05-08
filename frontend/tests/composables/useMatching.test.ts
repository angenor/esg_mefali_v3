import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('~/stores/auth', () => ({
  useAuthStore: () => ({ accessToken: 'test-token' }),
}))

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://localhost:8000' },
}))

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

describe('useMatching composable (F14)', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  it('expose les méthodes attendues', async () => {
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    expect(typeof api.listMatches).toBe('function')
    expect(typeof api.recomputeMatches).toBe('function')
    expect(typeof api.compareOffersForFund).toBe('function')
    expect(typeof api.getMatchDetails).toBe('function')
    expect(typeof api.getSubscription).toBe('function')
    expect(typeof api.updateSubscription).toBe('function')
  })

  it('listMatches GET avec filtres', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, limit: 25 }),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    await api.listMatches('p-1', {
      minScore: 60,
      bottleneck: 'fund',
      page: 2,
      limit: 10,
    })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/api/projects/p-1/matches')
    expect(url).toContain('min_score=60')
    expect(url).toContain('bottleneck=fund')
    expect(url).toContain('page=2')
    expect(url).toContain('limit=10')
  })

  it('listMatches 401 met error', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 401, json: async () => ({}) })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.listMatches('p-1')
    expect(r).toBeNull()
    expect(api.error.value).toContain('401')
  })

  it('recomputeMatches POST 202', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({
        recomputeRequestId: 'req-1',
        totalOffersToCompute: 10,
      }),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.recomputeMatches('p-1')
    expect(r?.totalOffersToCompute).toBe(10)
    const call = fetchMock.mock.calls[0]
    expect(call[1].method).toBe('POST')
  })

  it('recomputeMatches non 202 met error', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.recomputeMatches('p-1')
    expect(r).toBeNull()
    expect(api.error.value).toBeTruthy()
  })

  it('compareOffersForFund GET avec project_id', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        fundId: 'f-1',
        projectId: 'p-1',
        subjects: [],
        rows: [],
      }),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.compareOffersForFund('p-1', 'f-1')
    expect(r?.fundId).toBe('f-1')
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/api/projects/p-1/compare?fund_id=f-1')
  })

  it('getMatchDetails 404 met error', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404, json: async () => ({}) })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.getMatchDetails('p-1', 'o-1')
    expect(r).toBeNull()
    expect(api.error.value).toContain('404')
  })

  it('getSubscription GET', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 's-1',
        projectId: 'p-1',
        minGlobalScore: 60,
        isActive: true,
      }),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.getSubscription('p-1')
    expect(r?.isActive).toBe(true)
  })

  it('updateSubscription PATCH avec snake_case body', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 's-1',
        projectId: 'p-1',
        minGlobalScore: 70,
        isActive: false,
      }),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    await api.updateSubscription('p-1', {
      isActive: false,
      minGlobalScore: 70,
    })
    const call = fetchMock.mock.calls[0]
    expect(call[1].method).toBe('PATCH')
    const body = JSON.parse(call[1].body)
    expect(body).toEqual({ is_active: false, min_global_score: 70 })
  })

  it('updateSubscription 422 met error', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'invalid' }),
    })
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.updateSubscription('p-1', { minGlobalScore: -10 })
    expect(r).toBeNull()
    expect(api.error.value).toContain('422')
  })

  it('listMatches gère erreur réseau', async () => {
    fetchMock.mockRejectedValue(new Error('boom'))
    const { useMatching } = await import('~/composables/useMatching')
    const api = useMatching()
    const r = await api.listMatches('p-1')
    expect(r).toBeNull()
    expect(api.error.value).toContain('boom')
  })
})
