import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectImpactBadges from '~/components/projects/ProjectImpactBadges.vue'
import type { ProjectDetail, ProjectSummary } from '~/types/project'

function summary(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    id: 'p',
    name: 'P',
    status: 'draft',
    maturity: null,
    objective_env: ['renewable_energy'],
    target_amount: null,
    expected_impact_tco2e: null,
    auto_generated: false,
    applications_count: 0,
    created_at: '2026-05-07T00:00:00Z',
    ...overrides,
  }
}

describe('ProjectImpactBadges (F06)', () => {
  it('role list présent', () => {
    const wrapper = mount(ProjectImpactBadges, {
      props: { project: summary() },
    })
    expect(wrapper.find('[role="list"]').exists()).toBe(true)
  })

  it('badge objectif rendu avec libellé français', () => {
    const wrapper = mount(ProjectImpactBadges, {
      props: { project: summary({ objective_env: ['renewable_energy'] }) },
    })
    expect(wrapper.text()).toContain('Énergie renouvelable')
  })

  it('badge CO2e rendu si > 0', () => {
    const wrapper = mount(ProjectImpactBadges, {
      props: { project: summary({ expected_impact_tco2e: '120.5' }) },
    })
    expect(wrapper.text()).toContain('tCO2e')
  })

  it('badge CO2e absent si 0 ou null', () => {
    const wrapper = mount(ProjectImpactBadges, {
      props: { project: summary({ expected_impact_tco2e: null }) },
    })
    expect(wrapper.text()).not.toContain('tCO2e')
  })

  it('badges multiples objectifs', () => {
    const wrapper = mount(ProjectImpactBadges, {
      props: {
        project: summary({
          objective_env: ['renewable_energy', 'mitigation', 'water'],
        }),
      },
    })
    const text = wrapper.text()
    expect(text).toContain('Énergie renouvelable')
    expect(text).toContain('Atténuation')
    expect(text).toContain('Eau')
  })

  it('classes dark: présentes', () => {
    const wrapper = mount(ProjectImpactBadges, {
      props: { project: summary() },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-emerald-900/20')
  })

  it('rend les emplois si > 0 (ProjectDetail)', () => {
    const detail: ProjectDetail = {
      ...summary(),
      account_id: 'a-1',
      description: null,
      duration_months: null,
      financing_structure: null,
      expected_jobs_created: 5,
      expected_beneficiaries: null,
      expected_hectares_restored: null,
      expected_other_impacts: null,
      location_country: null,
      location_region: null,
      updated_at: '2026-05-07T00:00:00Z',
      project_documents: [],
    }
    const wrapper = mount(ProjectImpactBadges, {
      props: { project: detail },
    })
    expect(wrapper.text()).toContain('5 emplois')
  })
})
