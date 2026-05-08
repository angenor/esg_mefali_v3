import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MissingCriteriaList from '~/components/matching/MissingCriteriaList.vue'
import type { MissingCriterion } from '~/types/matching'

describe('MissingCriteriaList (F14)', () => {
  it('rend empty state si aucun critère', () => {
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria: [] },
    })
    expect(wrapper.text()).toContain('Aucun critère manquant')
  })

  it('rend la liste de critères', () => {
    const criteria: MissingCriterion[] = [
      { label: 'Empreinte carbone', indicatorCode: 'E1', sourceId: 'src-1' },
      { label: 'Politique RH', indicatorCode: 'S2', sourceId: null },
    ]
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria },
    })
    expect(wrapper.text()).toContain('Empreinte carbone')
    expect(wrapper.text()).toContain('Politique RH')
    expect(wrapper.text()).toContain('Critères manquants (2)')
  })

  it('affiche un SourceLink quand sourceId présent', () => {
    const criteria: MissingCriterion[] = [
      { label: 'Empreinte carbone', sourceId: 'src-1' },
    ]
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria },
    })
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThanOrEqual(1)
  })

  it("n'affiche pas SourceLink quand sourceId null", () => {
    const criteria: MissingCriterion[] = [
      { label: 'Sans source', sourceId: null },
    ]
    const wrapper = mount(MissingCriteriaList, { props: { criteria } })
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it('émet open-source au clic sur SourceLink', async () => {
    const criteria: MissingCriterion[] = [
      { label: 'Empreinte', sourceId: 'src-1' },
    ]
    const wrapper = mount(MissingCriteriaList, { props: { criteria } })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('open-source')).toBeTruthy()
    expect(wrapper.emitted('open-source')?.[0]?.[0]).toBe('src-1')
  })

  it('expose dark mode classes', () => {
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria: [{ label: 'X', sourceId: null }] },
    })
    expect(wrapper.html()).toMatch(/dark:/)
  })
})
