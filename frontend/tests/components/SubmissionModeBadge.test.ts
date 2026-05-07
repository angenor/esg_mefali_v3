import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SubmissionModeBadge from '~/components/financing/SubmissionModeBadge.vue'

/**
 * F07 — Tests SubmissionModeBadge.vue.
 *
 * Couvre :
 * - Rendu mode 'rolling' avec libellé.
 * - Rendu mode 'call_for_proposals'.
 * - Variantes dark mode.
 * - ARIA aria-label.
 */
describe('SubmissionModeBadge', () => {
  it("rend le libellé 'Rolling' pour mode='rolling'", () => {
    const wrapper = mount(SubmissionModeBadge, {
      props: { mode: 'rolling' },
    })
    expect(wrapper.text()).toContain('Rolling')
  })

  it("rend 'Appel à projets' pour mode='call_for_proposals'", () => {
    const wrapper = mount(SubmissionModeBadge, {
      props: { mode: 'call_for_proposals' },
    })
    expect(wrapper.text()).toContain('Appel à projets')
  })

  it("contient les classes dark mode", () => {
    const wrapper = mount(SubmissionModeBadge, {
      props: { mode: 'rolling' },
    })
    const cls = wrapper.classes().join(' ') + wrapper.html()
    expect(cls).toContain('dark:')
  })

  it("a un aria-label descriptif", () => {
    const wrapper = mount(SubmissionModeBadge, {
      props: { mode: 'rolling' },
    })
    expect(wrapper.attributes('aria-label')).toContain('continu')
  })
})
