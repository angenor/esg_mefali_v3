import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSourcesStore } from '~/stores/sources'
import type { Source } from '~/types/source'

const fakeSource: Source = {
  id: 'a',
  url: 'https://x.com/a.pdf',
  title: 'Test',
  publisher: 'ADEME',
  version: 'v1',
  date_publi: '2024-01-01',
  page: null,
  section: null,
  captured_at: '2024-01-01T00:00:00Z',
  captured_by: 'u1',
  verified_by: 'u2',
  verification_status: 'verified',
  verified_at: '2024-01-02T00:00:00Z',
  outdated_reason: null,
  created_by_user_id: 'u1',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

describe('useSourcesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('cache miss : getById retourne null si non cache', () => {
    const store = useSourcesStore()
    expect(store.getById('inexistant')).toBeNull()
  })

  it('cache hit : setSource puis getById retourne la source', () => {
    const store = useSourcesStore()
    store.setSource(fakeSource)
    expect(store.getById('a')).toEqual(fakeSource)
  })

  it('TTL : entre expirent apres 5 minutes', () => {
    vi.useFakeTimers()
    const store = useSourcesStore()
    store.setSource(fakeSource)
    expect(store.getById('a')).toEqual(fakeSource)
    // Avancer de 5 min + 1 ms
    vi.advanceTimersByTime(5 * 60 * 1000 + 1)
    expect(store.getById('a')).toBeNull()
    vi.useRealTimers()
  })

  it('invalidate : supprime une entree du cache', () => {
    const store = useSourcesStore()
    store.setSource(fakeSource)
    store.invalidate('a')
    expect(store.getById('a')).toBeNull()
  })

  it('reset : vide tout le cache', () => {
    const store = useSourcesStore()
    store.setSource(fakeSource)
    store.setError('oops')
    store.setLoading(true)
    store.reset()
    expect(store.getById('a')).toBeNull()
    expect(store.error).toBe('')
    expect(store.loading).toBe(false)
  })
})
