/**
 * T051 [US2] — Tests DualScoreDisplay enrichi F047 :
 * badge `is_fallback` amber + tooltip + absence du badge quand fonds avec ESS.
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DualScoreDisplay from '~/components/financing/DualScoreDisplay.vue'
import type { ProjectEsgSubScore } from '~/types/projectMatching'

function makeSubScore(overrides: Partial<ProjectEsgSubScore> = {}): ProjectEsgSubScore {
  return {
    score: 75,
    weight: 0.1,
    is_fallback: false,
    referential_used: {
      id: '00000000-0000-0000-0000-000000000001',
      code: 'ifc_ps',
      label: 'IFC Performance Standards',
      version: '1.0',
    },
    assessment_id: null,
    source_kind: 'calculated',
    unsourced: false,
    cta_hint: null,
    ...overrides,
  }
}

describe('DualScoreDisplay (F045 + F047 US2)', () => {
  it('affiche les deux scores cote a cote', () => {
    const wrapper = mount(DualScoreDisplay, {
      props: { projectScore: 80, companyScore: 60 },
      global: { stubs: { DivergenceBadge: true } },
    })
    expect(wrapper.text()).toContain('80%')
    expect(wrapper.text()).toContain('60%')
  })

  it('affiche le badge fallback quand is_fallback=true et source_kind=calculated', () => {
    const wrapper = mount(DualScoreDisplay, {
      props: {
        projectScore: 70,
        companyScore: 50,
        projectEsgSubscore: makeSubScore({
          is_fallback: true,
          source_kind: 'calculated',
          referential_used: {
            id: 'abc',
            code: 'ifc_ps',
            label: 'IFC PS',
            version: '1.0',
          },
        }),
      },
      global: { stubs: { DivergenceBadge: true } },
    })
    const badge = wrapper.find('[data-testid="project-esg-fallback-badge"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('Référentiel par défaut')
    expect(badge.attributes('title')).toContain('IFC PS')
  })

  it('cache le badge fallback quand fonds avec ESS dédié (is_fallback=false)', () => {
    const wrapper = mount(DualScoreDisplay, {
      props: {
        projectScore: 65,
        companyScore: 55,
        projectEsgSubscore: makeSubScore({
          is_fallback: false,
          source_kind: 'calculated',
          referential_used: {
            id: 'gcf',
            code: 'gcf_ess',
            label: 'GCF ESS',
            version: '2018',
          },
        }),
      },
      global: { stubs: { DivergenceBadge: true } },
    })
    expect(wrapper.find('[data-testid="project-esg-fallback-badge"]').exists()).toBe(false)
  })

  it('cache le badge fallback quand source_kind=unsourced (CTA géré ailleurs)', () => {
    const wrapper = mount(DualScoreDisplay, {
      props: {
        projectScore: 0,
        companyScore: 40,
        projectEsgSubscore: makeSubScore({
          score: 0,
          is_fallback: true,
          source_kind: 'unsourced',
          unsourced: true,
        }),
      },
      global: { stubs: { DivergenceBadge: true } },
    })
    expect(wrapper.find('[data-testid="project-esg-fallback-badge"]').exists()).toBe(false)
  })

  it('aria-label du badge inclut nom du référentiel', () => {
    const wrapper = mount(DualScoreDisplay, {
      props: {
        projectScore: 70,
        companyScore: 50,
        projectEsgSubscore: makeSubScore({
          is_fallback: true,
          source_kind: 'calculated',
        }),
      },
      global: { stubs: { DivergenceBadge: true } },
    })
    const badge = wrapper.find('[data-testid="project-esg-fallback-badge"]')
    expect(badge.attributes('aria-label')).toContain('IFC Performance Standards')
  })
})
