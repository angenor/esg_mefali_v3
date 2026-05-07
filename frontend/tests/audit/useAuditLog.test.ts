import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock auto-imports
;(globalThis as any).useRuntimeConfig = () => ({ public: { apiBase: 'http://test' } })

describe('useAuditLog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('fetchMe appelle GET /audit/me avec les filtres', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ events: [], total: 0, page: 1, limit: 50 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )

    const { useAuditLog } = await import('~/composables/useAuditLog')
    const log = useAuditLog()
    await log.fetchMe({ page: 2, limit: 25, source_of_change: 'llm' })

    expect(fetchSpy).toHaveBeenCalled()
    const url = fetchSpy.mock.calls[0]![0] as string
    expect(url).toContain('/audit/me')
    expect(url).toContain('page=2')
    expect(url).toContain('limit=25')
    expect(url).toContain('source_of_change=llm')
  })

  it('fetchByAccount appelle GET /admin/audit/{accountId}', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ events: [], total: 0, page: 1, limit: 50 }),
        { status: 200 },
      ),
    )

    const { useAuditLog } = await import('~/composables/useAuditLog')
    const log = useAuditLog()
    await log.fetchByAccount('acct-uuid')

    const url = fetchSpy.mock.calls[0]![0] as string
    expect(url).toContain('/admin/audit/acct-uuid')
  })

  it('fetchGlobal appelle GET /admin/audit', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ events: [], total: 0, page: 1, limit: 50 }),
        { status: 200 },
      ),
    )

    const { useAuditLog } = await import('~/composables/useAuditLog')
    const log = useAuditLog()
    await log.fetchGlobal({ account_id: 'acct1' })

    const url = fetchSpy.mock.calls[0]![0] as string
    expect(url).toContain('/admin/audit')
    expect(url).toContain('account_id=acct1')
  })

  it('exportCsv télécharge un blob avec format=csv', async () => {
    // Mock URL.createObjectURL et createElement
    const createObjectURL = vi.fn(() => 'blob:url')
    const revokeObjectURL = vi.fn()
    ;(globalThis as any).URL.createObjectURL = createObjectURL
    ;(globalThis as any).URL.revokeObjectURL = revokeObjectURL

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response('a,b,c', { status: 200, headers: { 'content-type': 'text/csv' } }),
    )

    const { useAuditLog } = await import('~/composables/useAuditLog')
    const log = useAuditLog()
    await log.exportCsv({ source_of_change: 'manual' })

    const url = fetchSpy.mock.calls[0]![0] as string
    expect(url).toContain('/audit/me/export')
    expect(url).toContain('format=csv')
    expect(url).toContain('source_of_change=manual')
  })

  it('exportJson appelle l\'endpoint avec format=json', async () => {
    const createObjectURL = vi.fn(() => 'blob:url')
    ;(globalThis as any).URL.createObjectURL = createObjectURL
    ;(globalThis as any).URL.revokeObjectURL = vi.fn()

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }),
    )

    const { useAuditLog } = await import('~/composables/useAuditLog')
    const log = useAuditLog()
    await log.exportJson({})

    const url = fetchSpy.mock.calls[0]![0] as string
    expect(url).toContain('format=json')
  })
})
