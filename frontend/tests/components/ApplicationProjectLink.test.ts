import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ApplicationProjectLink from '~/components/applications/ApplicationProjectLink.vue'
import type { ApplicationProjectInfo } from '~/stores/applications'

// Stub NuxtLink exposant la cible via data-to (cf. pattern SuccessorBanner.test).
const NuxtLinkStub = { template: '<a :data-to="$attrs.to"><slot /></a>' }

function baseProject(
  overrides: Partial<ApplicationProjectInfo> = {},
): ApplicationProjectInfo {
  return {
    id: 'p-1',
    name: 'Ferme Solaire de Kaolack',
    status: 'seeking_funding',
    objective_env: ['renewable_energy'],
    description: 'Panneaux solaires pour irrigation maraîchère',
    ...overrides,
  }
}

function mountLink(props: Record<string, unknown>) {
  return mount(ApplicationProjectLink, {
    props,
    global: { stubs: { NuxtLink: NuxtLinkStub } },
  })
}

describe('ApplicationProjectLink (050)', () => {
  it('affiche le nom du projet lié', () => {
    const wrapper = mountLink({ project: baseProject() })
    expect(wrapper.text()).toContain('Ferme Solaire de Kaolack')
  })

  it('mode header : lie vers la page détail du projet (/profile/projects/[id])', () => {
    const wrapper = mountLink({ project: baseProject(), variant: 'header' })
    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('data-to')).toBe('/profile/projects/p-1')
  })

  it('affiche le statut du projet traduit en français', () => {
    const wrapper = mountLink({
      project: baseProject({ status: 'seeking_funding' }),
      variant: 'header',
    })
    expect(wrapper.text()).toContain('En recherche de financement')
  })

  it("affiche l'objectif environnemental traduit (mode header)", () => {
    const wrapper = mountLink({
      project: baseProject({ objective_env: ['renewable_energy'] }),
      variant: 'header',
    })
    expect(wrapper.text()).toContain('Énergie renouvelable')
  })

  it('mode compact : rappel discret du nom sans lien imbriqué (pas de <a> dans <a>)', () => {
    const wrapper = mountLink({ project: baseProject(), variant: 'compact' })
    expect(wrapper.text()).toContain('Ferme Solaire de Kaolack')
    expect(wrapper.find('a').exists()).toBe(false)
  })
})
