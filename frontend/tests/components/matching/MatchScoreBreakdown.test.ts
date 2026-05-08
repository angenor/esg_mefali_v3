import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MatchScoreBreakdown from '~/components/matching/MatchScoreBreakdown.vue'
import type { MatchSubBreakdown } from '~/types/matching'

function makeBreakdown(
  overrides: Partial<MatchSubBreakdown> = {},
): MatchSubBreakdown {
  return {
    sectorMatch: 80,
    esgMatch: 70,
    sizeMatch: 60,
    locationMatch: 100,
    documentsMatch: 50,
    instrumentMatch: 90,
    missingCriteria: [],
    ...overrides,
  }
}

describe('MatchScoreBreakdown (F14)', () => {
  it('rend les 6 axes avec valeurs', () => {
    const wrapper = mount(MatchScoreBreakdown, {
      props: { breakdown: makeBreakdown() },
    })
    expect(wrapper.text()).toContain('Secteur')
    expect(wrapper.text()).toContain('ESG')
    expect(wrapper.text()).toContain('Taille')
    expect(wrapper.text()).toContain('Localisation')
    expect(wrapper.text()).toContain('Documents')
    expect(wrapper.text()).toContain('Instrument')
    expect(wrapper.text()).toContain('80/100')
    expect(wrapper.text()).toContain('100/100')
  })

  it('SVG a role=img et aria-label', () => {
    const wrapper = mount(MatchScoreBreakdown, {
      props: { breakdown: makeBreakdown(), title: 'Mon score' },
    })
    const svg = wrapper.find('svg')
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toContain('Mon score')
  })

  it('clamp les valeurs hors bornes', () => {
    const wrapper = mount(MatchScoreBreakdown, {
      props: {
        breakdown: makeBreakdown({ sectorMatch: 150, esgMatch: -20 }),
      },
    })
    expect(wrapper.text()).toContain('100/100') // clamp haut
    expect(wrapper.text()).toContain('0/100') // clamp bas
  })

  it('variante intermediary applique stroke bleu', () => {
    const wrapper = mount(MatchScoreBreakdown, {
      props: { breakdown: makeBreakdown(), variant: 'intermediary' },
    })
    expect(wrapper.html()).toContain('blue')
    expect(wrapper.attributes('data-testid')).toBe(
      'match-score-breakdown-intermediary',
    )
  })

  it('expose dark mode classes', () => {
    const wrapper = mount(MatchScoreBreakdown, {
      props: { breakdown: makeBreakdown() },
    })
    expect(wrapper.html()).toMatch(/dark:/)
  })
})
