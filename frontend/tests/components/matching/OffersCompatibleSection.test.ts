import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import OffersCompatibleSection from '~/components/matching/OffersCompatibleSection.vue'
import type { EnrichedMatch } from '~/components/matching/OffersCompatibleSection.vue'

function makeEnriched(overrides: Partial<EnrichedMatch> = {}): EnrichedMatch {
  return {
    id: 'm-1',
    accountId: 'acc-1',
    projectId: 'p-1',
    offerId: 'o-1',
    globalScore: 75,
    fundScore: 70,
    intermediaryScore: 80,
    scoreBreakdown: {},
    bottleneck: 'balanced',
    recommendedActions: [{ label: 'Compléter le bilan carbone' }],
    status: 'suggested',
    computedAt: '2026-05-08T00:00:00Z',
    expiresAt: '2026-06-08T00:00:00Z',
    lastNotifiedAt: null,
    fundName: 'GCF',
    intermediaryName: 'BOAD',
    drilldownUrl: '/financing/offers/o-1',
    ...overrides,
  }
}

describe('OffersCompatibleSection (F14)', () => {
  it('rend empty state si aucun match', () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: { matches: [], projectId: 'p-1' },
    })
    expect(wrapper.text()).toContain('Aucune offre compatible')
    expect(wrapper.find('[data-testid="offers-empty-state"]').exists()).toBe(true)
  })

  it('rend les matches enrichis triés par score', () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: {
        matches: [
          makeEnriched({ id: 'm-1', globalScore: 50, fundName: 'Low' }),
          makeEnriched({ id: 'm-2', globalScore: 90, fundName: 'High' }),
        ],
        projectId: 'p-1',
      },
    })
    const cards = wrapper.findAll('[data-testid^="match-card-"]')
    expect(cards).toHaveLength(2)
    expect(cards[0]?.text()).toContain('High')
  })

  it('émet recompute au clic sur Recalculer', async () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: { matches: [], projectId: 'p-1' },
    })
    await wrapper
      .find('[data-testid="recompute-matches-btn"]')
      .trigger('click')
    expect(wrapper.emitted('recompute')).toBeTruthy()
  })

  it('émet compare-fund au clic sur Comparer', async () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: { matches: [makeEnriched()], projectId: 'p-1' },
    })
    await wrapper.find('[data-testid="compare-fund-m-1"]').trigger('click')
    expect(wrapper.emitted('compare-fund')).toBeTruthy()
    expect(wrapper.emitted('compare-fund')?.[0]?.[0]).toBe('o-1')
  })

  it('émet navigate au clic sur le titre', async () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: { matches: [makeEnriched()], projectId: 'p-1' },
    })
    const titleBtn = wrapper.find('[data-testid="match-card-m-1"] button')
    await titleBtn.trigger('click')
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')?.[0]?.[0]).toBe('/financing/offers/o-1')
  })

  it('affiche view-all quand total > 5', async () => {
    const matches = Array.from({ length: 6 }, (_, i) =>
      makeEnriched({ id: `m-${i}`, offerId: `o-${i}` }),
    )
    const wrapper = mount(OffersCompatibleSection, {
      props: { matches, total: 12, projectId: 'p-1' },
    })
    const link = wrapper.find('[data-testid="view-all-matches"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('12')
    await link.trigger('click')
    expect(wrapper.emitted('view-all')?.[0]?.[0]).toBe('p-1')
  })

  it('affiche les actions recommandées (max 3)', () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: {
        matches: [
          makeEnriched({
            recommendedActions: [
              { label: 'Action 1' },
              { label: 'Action 2' },
              { label: 'Action 3' },
              { label: 'Action 4' },
            ],
          }),
        ],
        projectId: 'p-1',
      },
    })
    expect(wrapper.text()).toContain('Action 1')
    expect(wrapper.text()).toContain('Action 3')
    expect(wrapper.text()).not.toContain('Action 4')
  })

  it('expose dark mode', () => {
    const wrapper = mount(OffersCompatibleSection, {
      props: { matches: [makeEnriched()], projectId: 'p-1' },
    })
    expect(wrapper.html()).toMatch(/dark:/)
  })
})
