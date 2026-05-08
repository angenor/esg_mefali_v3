import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useResources } from '~/composables/useResources'

const fetchMock = vi.fn()

;(globalThis as unknown as { $fetch: typeof fetchMock }).$fetch = fetchMock
;(
  globalThis as unknown as { useRuntimeConfig: () => unknown }
).useRuntimeConfig = () => ({ public: { apiBase: 'http://localhost:8000/api' } })

describe('useResources', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('listResources construit la query string', async () => {
    fetchMock.mockResolvedValue({ items: [], total: 0, page: 1, limit: 20 })
    const { listResources } = useResources()
    await listResources({ type: 'guide', q: 'BOAD' })
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('type=guide')
    expect(url).toContain('q=BOAD')
  })

  it('getResource appelle /api/resources/<slug>', async () => {
    fetchMock.mockResolvedValue({})
    const { getResource } = useResources()
    await getResource('mon-slug')
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('/resources/mon-slug')
  })

  it('incrementView fait un POST', async () => {
    fetchMock.mockResolvedValue({ slug: 'x', view_count: 1 })
    const { incrementView } = useResources()
    await incrementView('x')
    const opts = fetchMock.mock.calls[0]?.[1] as { method: string }
    expect(opts.method).toBe('POST')
  })

  it('getIntermediaryGuide cible /api/intermediaries/<id>/guide', async () => {
    fetchMock.mockResolvedValue({})
    const { getIntermediaryGuide } = useResources()
    await getIntermediaryGuide('xyz')
    const url = fetchMock.mock.calls[0]?.[0] as string
    expect(url).toContain('/intermediaries/xyz/guide')
  })
})
