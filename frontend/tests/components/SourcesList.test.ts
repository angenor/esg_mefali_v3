import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SourcesList from '~/components/sources/SourcesList.vue'
import type { SourceListItem } from '~/types/source'

const fakeSources: SourceListItem[] = [
  {
    id: 'a',
    url: 'https://x.com/a.pdf',
    title: 'ADEME Doc A',
    publisher: 'ADEME',
    version: 'v1',
    date_publi: '2024-01-01',
    page: null,
    section: 'Annexe 1',
    verification_status: 'verified',
  },
  {
    id: 'b',
    url: 'https://x.com/b.pdf',
    title: 'IPCC Doc B',
    publisher: 'IPCC',
    version: 'AR6',
    date_publi: '2022-04-04',
    page: 12,
    section: null,
    verification_status: 'verified',
  },
]

/**
 * F01 — Tests SourcesList.vue (liste de sources cliquables).
 */
describe('SourcesList', () => {
  it('rend tous les items de la liste', () => {
    const wrapper = mount(SourcesList, { props: { sources: fakeSources } })
    expect(wrapper.text()).toContain('ADEME Doc A')
    expect(wrapper.text()).toContain('IPCC Doc B')
  })

  it("affiche un message 'Aucune source disponible' si la liste est vide", () => {
    const wrapper = mount(SourcesList, { props: { sources: [] } })
    expect(wrapper.text()).toContain('Aucune source disponible')
  })

  it("affiche 'Chargement des sources' quand loading=true", () => {
    const wrapper = mount(SourcesList, {
      props: { sources: [], loading: true },
    })
    expect(wrapper.text()).toContain('Chargement des sources')
  })

  it("emet 'select' avec l'id au clic", async () => {
    const wrapper = mount(SourcesList, { props: { sources: fakeSources } })
    await wrapper.findAll('button')[0].trigger('click')
    const events = wrapper.emitted('select')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['a'])
  })

  it("affiche les classes dark: pour le mode sombre", () => {
    const wrapper = mount(SourcesList, { props: { sources: fakeSources } })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-card')
    expect(html).toContain('dark:hover:bg-dark-hover')
  })
})
