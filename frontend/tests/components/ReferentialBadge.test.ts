import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ReferentialBadge from '~/components/ui/ReferentialBadge.vue'

/**
 * F04 — Tests ReferentialBadge.vue (US3/US5).
 */
describe('ReferentialBadge', () => {
  const referential = {
    id: 'ref-uuid-1',
    name: 'ESG Mefali',
    version: '1.2',
    valid_from: '2026-02-10',
  }

  it('affiche le libellé français complet', () => {
    const wrapper = mount(ReferentialBadge, { props: { referential } })
    expect(wrapper.text()).toContain('Évalué selon Référentiel ESG Mefali v1.2 du 10/02/2026')
  })

  it('émet open-source-modal au clic', async () => {
    const wrapper = mount(ReferentialBadge, { props: { referential } })
    await wrapper.find('button').trigger('click')
    const events = wrapper.emitted('open-source-modal')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['ref-uuid-1'])
  })

  it('porte les classes dark:', () => {
    const wrapper = mount(ReferentialBadge, { props: { referential } })
    const btn = wrapper.find('button').element as HTMLElement
    expect(btn.className).toContain('dark:border-dark-border')
    expect(btn.className).toContain('dark:bg-dark-card')
  })

  it('porte un aria-label informatif', () => {
    const wrapper = mount(ReferentialBadge, { props: { referential } })
    const btn = wrapper.find('button').element as HTMLElement
    expect(btn.getAttribute('aria-label')).toContain('Référentiel ESG Mefali')
  })

  it('ne rend rien si referential est null', () => {
    const wrapper = mount(ReferentialBadge, { props: { referential: null } })
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
