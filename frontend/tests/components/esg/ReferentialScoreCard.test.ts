import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ReferentialScoreCard from '~/components/esg/ReferentialScoreCard.vue'
import type { ReferentialScore } from '~/types/esg'

function makeScore(overrides: Partial<ReferentialScore> = {}): ReferentialScore {
  return {
    id: 'rs-1',
    assessment_id: 'as-1',
    referential_id: 'rf-1',
    referential_code: 'mefali',
    referential_name: 'ESG Mefali',
    referential_version: '1.0',
    overall_score: 70,
    pillar_scores: {
      environment: { score: 70, weight: 0.33, criteria_count: 10 },
    },
    coverage_rate: 0.9,
    covered_criteria: [],
    missing_criteria: [],
    gap_to_threshold: 20,
    eligibility: true,
    computed_at: '2026-05-07T12:00:00Z',
    computed_by: 'auto',
    computed_request_id: null,
    is_fallback: false,
    ...overrides,
  }
}

const globalConfig = { stubs: { ScoreCircle: true } }

describe('ReferentialScoreCard', () => {
  it('renders overall_score and referential name', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore() },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('ESG Mefali')
    expect(wrapper.text()).toContain('Version 1.0')
  })

  it('shows orange coverage badge when coverage_rate < 0.5', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore({ coverage_rate: 0.3 }) },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('Couverture indicateurs : 30 %')
    expect(wrapper.text()).toContain('score indicatif')
  })

  it('hides card when overall_score is null (insufficient coverage)', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore({ overall_score: null }) },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('non calculable')
  })

  it('shows fallback badge when is_fallback=true', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore({ is_fallback: true }) },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('Référentiel Mefali — fallback')
  })

  it('shows eligibility badge when eligibility is set', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore({ eligibility: true }) },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('Éligible')
  })

  it('shows non-eligible badge when eligibility=false', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore({ eligibility: false }) },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('Non éligible')
  })

  it('emits include-in-report event when button clicked', async () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore(), showIncludeInReport: true },
      global: globalConfig,
    })
    const buttons = wrapper.findAll('button')
    const btn = buttons.find((b) => b.text().includes('Inclure'))
    expect(btn).toBeDefined()
    await btn!.trigger('click')
    expect(wrapper.emitted('include-in-report')).toBeTruthy()
    expect((wrapper.emitted('include-in-report') as string[][])[0][0]).toBe('mefali')
  })

  it('disables include-in-report button when coverage_rate < 0.5', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore({ coverage_rate: 0.3 }), showIncludeInReport: true },
      global: globalConfig,
    })
    const btn = wrapper.findAll('button').find((b) => b.text().includes('Inclure'))
    expect(btn?.attributes('disabled')).toBeDefined()
  })

  it('applies dark mode classes', () => {
    const wrapper = mount(ReferentialScoreCard, {
      props: { score: makeScore() },
      global: globalConfig,
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-card')
    expect(html).toContain('dark:text-surface-dark-text')
  })
})
