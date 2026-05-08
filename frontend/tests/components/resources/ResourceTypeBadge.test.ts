import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ResourceTypeBadge from '~/components/resources/ResourceTypeBadge.vue'

describe('ResourceTypeBadge', () => {
  it('affiche le label "Guide" pour type=guide', () => {
    const wrapper = mount(ResourceTypeBadge, { props: { type: 'guide' } })
    expect(wrapper.text()).toContain('Guide')
  })

  it('affiche "FAQ" pour type=faq', () => {
    const wrapper = mount(ResourceTypeBadge, { props: { type: 'faq' } })
    expect(wrapper.text()).toContain('FAQ')
  })

  it('affiche "Fiche intermédiaire" pour intermediary_guide', () => {
    const wrapper = mount(ResourceTypeBadge, {
      props: { type: 'intermediary_guide' },
    })
    expect(wrapper.text()).toContain('Fiche intermédiaire')
  })

  it('inclut un aria-label accessible', () => {
    const wrapper = mount(ResourceTypeBadge, { props: { type: 'video' } })
    const ariaLabel = wrapper.attributes('aria-label')
    expect(ariaLabel).toMatch(/Type de ressource/i)
  })

  it('applique des classes dark mode', () => {
    const wrapper = mount(ResourceTypeBadge, {
      props: { type: 'template_doc' },
    })
    const classes = wrapper.classes().join(' ')
    expect(classes).toContain('dark:')
  })
})
