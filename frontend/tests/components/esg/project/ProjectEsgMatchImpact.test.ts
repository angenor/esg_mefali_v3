/**
 * T063 [US4] — Test ProjectEsgMatchImpact : affiche 2 colonnes (avant/après)
 * et utilise DualScoreDisplay en sous-composant.
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectEsgMatchImpact from '~/components/esg/project/ProjectEsgMatchImpact.vue'

describe('ProjectEsgMatchImpact (F047 US4)', () => {
  it('affiche le bloc avec avant et après', () => {
    const wrapper = mount(ProjectEsgMatchImpact, {
      props: {
        before: {
          fund_name: 'Green Climate Fund',
          project_score: 45,
          company_score: 60,
          divergence_explanation: null,
          project_esg_subscore: null,
        },
        after: {
          fund_name: 'Green Climate Fund',
          project_score: 72,
          company_score: 60,
          divergence_explanation: null,
          project_esg_subscore: null,
        },
      },
      global: {
        stubs: {
          DualScoreDisplay: { template: '<div data-testid="dual-score"></div>' },
        },
      },
    })
    const region = wrapper.find('[data-testid="project-esg-match-impact"]')
    expect(region.exists()).toBe(true)
    expect(region.text()).toContain('Green Climate Fund')
    // Deux DualScoreDisplay (avant + après)
    expect(wrapper.findAll('[data-testid="dual-score"]').length).toBe(2)
  })

  it('cache la colonne avant si aucun snapshot pré-évaluation', () => {
    const wrapper = mount(ProjectEsgMatchImpact, {
      props: {
        before: null,
        after: {
          fund_name: 'Test Fund',
          project_score: 80,
          company_score: 50,
          divergence_explanation: null,
          project_esg_subscore: null,
        },
      },
      global: {
        stubs: {
          DualScoreDisplay: { template: '<div data-testid="dual-score"></div>' },
        },
      },
    })
    expect(wrapper.findAll('[data-testid="dual-score"]').length).toBe(1)
    expect(wrapper.text()).toContain('Aucun matching pré-évaluation')
  })
})
