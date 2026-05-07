import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import DualReferentialView from '~/components/esg/DualReferentialView.vue'
import type { DualReferentialResponse, ReferentialScore } from '~/types/esg'

function makeScore(code: string, score: number): ReferentialScore {
  return {
    id: `rs-${code}`,
    assessment_id: 'as-1',
    referential_id: `rf-${code}`,
    referential_code: code,
    referential_name: code === 'gcf' ? 'Green Climate Fund' : code === 'boad_ess' ? 'BOAD ESS' : 'ESG Mefali',
    referential_version: '1.0',
    overall_score: score,
    pillar_scores: {},
    coverage_rate: 0.8,
    covered_criteria: [],
    missing_criteria: [],
    gap_to_threshold: score - 50,
    eligibility: score >= 50,
    computed_at: '2026-05-07T12:00:00Z',
    computed_by: 'auto',
    computed_request_id: null,
    is_fallback: false,
  }
}

const globalConfig = { stubs: { ScoreCircle: true } }

describe('DualReferentialView', () => {
  it('renders both fund and intermediary cards in dual view', () => {
    const dualResponse: DualReferentialResponse = {
      fund_score: makeScore('gcf', 45),
      intermediary_score: makeScore('boad_ess', 68),
      bottleneck: {
        bottleneck_referential_code: 'gcf',
        bottleneck_referential_name: 'Green Climate Fund',
        bottleneck_score: 45,
        other_referential_code: 'boad_ess',
        other_referential_score: 68,
        gap: 23,
        eligibility_min: false,
        top_3_critical_indicators: ['E1', 'S2', 'G3'],
      },
      is_dual_view: true,
    }
    const wrapper = mount(DualReferentialView, {
      props: { dualResponse },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('Selon le fonds')
    expect(wrapper.text()).toContain('Selon l\'intermédiaire')
    expect(wrapper.text()).toContain('Green Climate Fund')
    expect(wrapper.text()).toContain('BOAD ESS')
  })

  it('renders single card when is_dual_view=false', () => {
    const dualResponse: DualReferentialResponse = {
      fund_score: makeScore('mefali', 70),
      intermediary_score: null,
      bottleneck: null,
      is_dual_view: false,
    }
    const wrapper = mount(DualReferentialView, {
      props: { dualResponse },
      global: globalConfig,
    })
    expect(wrapper.text()).toContain('Référentiel unique')
    expect(wrapper.text()).toContain('pas de goulot')
    expect(wrapper.text()).not.toContain('Selon le fonds')
  })

  it('forwards focus-indicators event from BottleneckBanner', async () => {
    const dualResponse: DualReferentialResponse = {
      fund_score: makeScore('gcf', 45),
      intermediary_score: makeScore('boad_ess', 68),
      bottleneck: {
        bottleneck_referential_code: 'gcf',
        bottleneck_referential_name: 'Green Climate Fund',
        bottleneck_score: 45,
        other_referential_code: 'boad_ess',
        other_referential_score: 68,
        gap: 23,
        eligibility_min: false,
        top_3_critical_indicators: ['E1', 'S2'],
      },
      is_dual_view: true,
    }
    const wrapper = mount(DualReferentialView, {
      props: { dualResponse },
      global: globalConfig,
    })
    const btn = wrapper.findAll('button').find((b) => b.text().includes('Renseigner'))
    expect(btn).toBeDefined()
    await btn!.trigger('click')
    expect(wrapper.emitted('focus-indicators')).toBeTruthy()
  })
})
