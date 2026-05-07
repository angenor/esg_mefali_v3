import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('~/stores/auth', () => ({
  useAuthStore: () => ({ accessToken: 'test-token' }),
}))

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://localhost:8000/api' },
}))

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

describe('useProjects composable (F06)', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  it('expose les 8 méthodes attendues', async () => {
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    expect(typeof api.listProjects).toBe('function')
    expect(typeof api.getProject).toBe('function')
    expect(typeof api.createProject).toBe('function')
    expect(typeof api.updateProject).toBe('function')
    expect(typeof api.deleteProject).toBe('function')
    expect(typeof api.duplicateProject).toBe('function')
    expect(typeof api.linkDocument).toBe('function')
    expect(typeof api.getProjectApplications).toBe('function')
  })

  it('listProjects appelle GET /api/projects sans query', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, limit: 25 }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    const result = await api.listProjects()
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects',
      expect.objectContaining({ headers: expect.any(Object) }),
    )
    expect(result?.total).toBe(0)
  })

  it('listProjects ajoute les filtres en query params', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, limit: 25 }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    await api.listProjects({ status: 'seeking_funding', page: 2, limit: 10 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('status=seeking_funding')
    expect(url).toContain('page=2')
    expect(url).toContain('limit=10')
  })

  it('createProject envoie un POST avec le payload', async () => {
    const fakeDetail = { id: 'p-1', name: 'P', status: 'draft' }
    fetchMock.mockResolvedValue({ ok: true, json: async () => fakeDetail })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    const result = await api.createProject({ name: 'P' })
    const call = fetchMock.mock.calls[0]
    expect(call[0]).toBe('http://localhost:8000/api/projects')
    expect(call[1].method).toBe('POST')
    expect(JSON.parse(call[1].body)).toEqual({ name: 'P' })
    expect(result?.id).toBe('p-1')
  })

  it('updateProject envoie un PATCH', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'p-1', name: 'New' }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    await api.updateProject('p-1', { name: 'New' })
    const call = fetchMock.mock.calls[0]
    expect(call[0]).toBe('http://localhost:8000/api/projects/p-1')
    expect(call[1].method).toBe('PATCH')
  })

  it('deleteProject ajoute force=true en query', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, blocked_by: [], hint: null }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    await api.deleteProject('p-1', true)
    const call = fetchMock.mock.calls[0]
    expect(call[0]).toBe('http://localhost:8000/api/projects/p-1?force=true')
    expect(call[1].method).toBe('DELETE')
  })

  it('deleteProject 409 retourne blocked_by', async () => {
    fetchMock.mockResolvedValue({
      status: 409,
      ok: false,
      json: async () => ({
        detail: {
          ok: false,
          blocked_by: [
            { application_id: 'a1', fund_name: 'GCF', status: 'submitted_to_fund' },
          ],
          hint: 'force=true pour confirmer',
        },
      }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    const result = await api.deleteProject('p-1', false)
    expect(result?.ok).toBe(false)
    expect(result?.blocked_by.length).toBe(1)
    expect(result?.blocked_by[0].fund_name).toBe('GCF')
  })

  it('duplicateProject envoie new_name', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'p-2', name: 'New' }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    await api.duplicateProject('p-1', 'New')
    const call = fetchMock.mock.calls[0]
    expect(call[0]).toBe('http://localhost:8000/api/projects/p-1/duplicate')
    expect(JSON.parse(call[1].body)).toEqual({ new_name: 'New' })
  })

  it('linkDocument POST sur /documents avec doc_type', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'pd-1',
        project_id: 'p-1',
        document_id: 'd-1',
        doc_type: 'business_plan',
        created_at: '2026-05-07T00:00:00Z',
      }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    await api.linkDocument('p-1', 'd-1', 'business_plan')
    const call = fetchMock.mock.calls[0]
    expect(call[0]).toBe('http://localhost:8000/api/projects/p-1/documents')
    expect(call[1].method).toBe('POST')
    expect(JSON.parse(call[1].body)).toEqual({
      document_id: 'd-1',
      doc_type: 'business_plan',
    })
  })

  it('getProjectApplications GET /applications', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => [] })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    const result = await api.getProjectApplications('p-1')
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://localhost:8000/api/projects/p-1/applications',
    )
    expect(result).toEqual([])
  })

  it('getProject 404 met error', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404, json: async () => ({}) })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    const result = await api.getProject('p-x')
    expect(result).toBeNull()
    expect(api.error.value).toContain('introuvable')
  })

  it('createProject 422 met error', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'invalid' }),
    })
    const { useProjects } = await import('~/composables/useProjects')
    const api = useProjects()
    const result = await api.createProject({ name: '' })
    expect(result).toBeNull()
    expect(api.error.value).toBeTruthy()
  })
})
