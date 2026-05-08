import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMatchesStore } from '~/stores/matches'
import type { OfferMatch } from '~/types/matching'

function makeMatch(overrides: Partial<OfferMatch> = {}): OfferMatch {
  return {
    id: 'm-' + Math.random().toString(36).slice(2, 8),
    accountId: 'acc-1',
    projectId: 'p-1',
    offerId: 'o-' + Math.random().toString(36).slice(2, 8),
    globalScore: 70,
    fundScore: 70,
    intermediaryScore: 70,
    scoreBreakdown: {},
    bottleneck: 'balanced',
    recommendedActions: [],
    status: 'suggested',
    computedAt: '2026-05-08T00:00:00Z',
    expiresAt: '2026-06-08T00:00:00Z',
    lastNotifiedAt: null,
    ...overrides,
  }
}

describe('useMatchesStore (F14)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('state initial', () => {
    const store = useMatchesStore()
    expect(store.matchesByProject).toEqual({})
    expect(store.totalsByProject).toEqual({})
    expect(store.subscriptionsByProject).toEqual({})
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('setMatches stocke par projet', () => {
    const store = useMatchesStore()
    const m1 = makeMatch()
    store.setMatches('p-1', [m1], 1)
    expect(store.getMatchesForProject('p-1')).toHaveLength(1)
    expect(store.getTotalForProject('p-1')).toBe(1)
    expect(store.getMatchesForProject('p-2')).toHaveLength(0)
  })

  it('getActiveMatches exclut les dismissed', () => {
    const store = useMatchesStore()
    const m1 = makeMatch({ status: 'suggested' })
    const m2 = makeMatch({ status: 'dismissed' })
    store.setMatches('p-1', [m1, m2], 2)
    expect(store.getActiveMatches('p-1')).toHaveLength(1)
  })

  it('getTopMatch retourne le score le plus élevé', () => {
    const store = useMatchesStore()
    store.setMatches(
      'p-1',
      [
        makeMatch({ globalScore: 50 }),
        makeMatch({ globalScore: 90 }),
        makeMatch({ globalScore: 70 }),
      ],
      3,
    )
    expect(store.getTopMatch('p-1')?.globalScore).toBe(90)
  })

  it('getTopMatch retourne null si vide', () => {
    const store = useMatchesStore()
    expect(store.getTopMatch('unknown')).toBeNull()
  })

  it('upsertMatch met à jour si existant', () => {
    const store = useMatchesStore()
    const m1 = makeMatch({ id: 'm-1', globalScore: 50 })
    store.setMatches('p-1', [m1], 1)
    const updated = makeMatch({ id: 'm-1', globalScore: 80 })
    store.upsertMatch('p-1', updated)
    expect(store.getMatchesForProject('p-1')[0]?.globalScore).toBe(80)
    expect(store.getMatchesForProject('p-1')).toHaveLength(1)
  })

  it('upsertMatch ajoute en tête si nouveau', () => {
    const store = useMatchesStore()
    store.setMatches('p-1', [makeMatch({ id: 'm-1' })], 1)
    store.upsertMatch('p-1', makeMatch({ id: 'm-2' }))
    expect(store.getMatchesForProject('p-1')[0]?.id).toBe('m-2')
  })

  it('bottleneckCount agrège correctement', () => {
    const store = useMatchesStore()
    store.setMatches(
      'p-1',
      [
        makeMatch({ bottleneck: 'fund' }),
        makeMatch({ bottleneck: 'fund' }),
        makeMatch({ bottleneck: 'balanced' }),
      ],
      3,
    )
    const counts = store.bottleneckCount('p-1')
    expect(counts.fund).toBe(2)
    expect(counts.balanced).toBe(1)
    expect(counts.intermediary).toBe(0)
  })

  it('setSubscription stocke par projet', () => {
    const store = useMatchesStore()
    store.setSubscription('p-1', {
      id: 's-1',
      projectId: 'p-1',
      minGlobalScore: 60,
      isActive: true,
    })
    expect(store.getSubscription('p-1')?.isActive).toBe(true)
    expect(store.getSubscription('p-2')).toBeNull()
  })

  it('reset vide tout', () => {
    const store = useMatchesStore()
    store.setMatches('p-1', [makeMatch()], 1)
    store.setSubscription('p-1', {
      id: 's-1',
      projectId: 'p-1',
      minGlobalScore: 60,
      isActive: true,
    })
    store.reset()
    expect(store.matchesByProject).toEqual({})
    expect(store.subscriptionsByProject).toEqual({})
  })
})
