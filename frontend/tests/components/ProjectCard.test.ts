import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectCard from '~/components/projects/ProjectCard.vue'
import ProjectImpactBadges from '~/components/projects/ProjectImpactBadges.vue'
import type { ProjectSummary } from '~/types/project'

function baseProject(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    id: 'p-1',
    name: 'Panneaux solaires',
    status: 'draft',
    maturity: 'pilot',
    objective_env: ['renewable_energy'],
    target_amount: { amount: '50000000', currency: 'XOF' },
    expected_impact_tco2e: '120.0',
    auto_generated: false,
    applications_count: 0,
    created_at: '2026-05-07T00:00:00Z',
    ...overrides,
  }
}

const stubs = {
  MoneyDisplay: true,
  ProjectImpactBadges,
}

describe('ProjectCard (F06)', () => {
  it('affiche le nom du projet', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject() },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('Panneaux solaires')
  })

  it('affiche le statut traduit', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject({ status: 'seeking_funding' }) },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('En recherche de financement')
  })

  it('affiche la maturité traduite', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject({ maturity: 'pilot' }) },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('Pilote')
  })

  it('badge auto_generated quand true', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject({ auto_generated: true }) },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('automatiquement')
  })

  it('emit view-applications au clic', async () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject({ applications_count: 2 }) },
      global: { stubs },
    })
    const buttons = wrapper.findAll('button')
    const appsBtn = buttons.find((b) => b.text().includes('Voir candidatures'))
    expect(appsBtn).toBeDefined()
    await appsBtn!.trigger('click')
    expect(wrapper.emitted('view-applications')).toBeTruthy()
    expect(wrapper.emitted('view-applications')![0]).toEqual(['p-1'])
  })

  it('bouton view-applications désactivé si 0 candidature', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject({ applications_count: 0 }) },
      global: { stubs },
    })
    const buttons = wrapper.findAll('button')
    const appsBtn = buttons.find((b) => b.text().includes('Voir candidatures'))
    expect(appsBtn?.attributes('disabled')).toBeDefined()
  })

  it('classes dark: présentes', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject() },
      global: { stubs },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-card')
    expect(html).toContain('dark:border-dark-border')
    expect(html).toContain('dark:text-surface-dark-text')
  })

  it('role article + aria-label', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: baseProject() },
      global: { stubs },
    })
    const article = wrapper.find('article')
    expect(article.attributes('role')).toBe('article')
    expect(article.attributes('aria-label')).toContain('Panneaux solaires')
  })
})
