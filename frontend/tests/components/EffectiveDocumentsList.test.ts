import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EffectiveDocumentsList from '~/components/financing/EffectiveDocumentsList.vue'

/**
 * F07 — Tests EffectiveDocumentsList.vue.
 */
describe('EffectiveDocumentsList', () => {
  const docs = [
    {
      title: 'Statuts juridiques',
      source_id: 'src-1',
      mandatory: true,
      format_spec: 'PDF',
    },
    {
      title: 'Audit',
      source_id: 'src-2',
      mandatory: false,
    },
  ]

  it('affiche tous les documents', () => {
    const wrapper = mount(EffectiveDocumentsList, {
      props: { documents: docs },
    })
    expect(wrapper.text()).toContain('Statuts juridiques')
    expect(wrapper.text()).toContain('Audit')
  })

  it('badge Obligatoire pour documents mandatory', () => {
    const wrapper = mount(EffectiveDocumentsList, {
      props: { documents: docs },
    })
    expect(wrapper.text()).toContain('Obligatoire')
    expect(wrapper.text()).toContain('Optionnel')
  })

  it('affiche format_spec', () => {
    const wrapper = mount(EffectiveDocumentsList, {
      props: { documents: docs },
    })
    expect(wrapper.text()).toContain('PDF')
  })

  it('message si aucun document', () => {
    const wrapper = mount(EffectiveDocumentsList, {
      props: { documents: [] },
    })
    expect(wrapper.text()).toContain('Aucun document')
  })

  it('classes dark mode présentes', () => {
    const wrapper = mount(EffectiveDocumentsList, {
      props: { documents: docs },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:')
  })
})
