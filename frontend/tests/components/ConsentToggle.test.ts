import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ConsentToggle from '~/components/ConsentToggle.vue'
import type { ConsentItem } from '~/composables/useDataPrivacy'

const MOCK_CONSENT: ConsentItem = {
  type: 'mobile_money_analysis',
  granted: false,
  granted_at: null,
  revoked_at: null,
  legal_basis: 'consent',
  version: 'v1.0',
  label: 'Analyse de mes flux Mobile Money',
  description: 'Permet d\'inclure vos données Mobile Money dans le scoring.',
}

describe('ConsentToggle', () => {
  it('rend le label et la description', () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: MOCK_CONSENT },
    })
    expect(wrapper.text()).toContain('Analyse de mes flux Mobile Money')
    expect(wrapper.text()).toContain('Mobile Money dans le scoring')
  })

  it('affiche la base légale et la version', () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: MOCK_CONSENT },
    })
    expect(wrapper.text()).toContain('consent')
    expect(wrapper.text()).toContain('v1.0')
  })

  it('a le bon role=switch et aria-checked', () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: MOCK_CONSENT },
    })
    const button = wrapper.find('button[role="switch"]')
    expect(button.exists()).toBe(true)
    expect(button.attributes('aria-checked')).toBe('false')
  })

  it('aria-checked=true quand granted=true', () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: { ...MOCK_CONSENT, granted: true } },
    })
    const button = wrapper.find('button[role="switch"]')
    expect(button.attributes('aria-checked')).toBe('true')
  })

  it('émet @toggle au clic avec le type et la valeur inversée', async () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: MOCK_CONSENT },
    })
    await wrapper.find('button[role="switch"]').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
    expect(wrapper.emitted('toggle')![0]).toEqual([
      'mobile_money_analysis',
      true,
    ])
  })

  it('n\'émet pas @toggle quand loading=true', async () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: MOCK_CONSENT, loading: true },
    })
    await wrapper.find('button[role="switch"]').trigger('click')
    expect(wrapper.emitted('toggle')).toBeFalsy()
  })

  it('contient les classes dark mode', () => {
    const wrapper = mount(ConsentToggle, {
      props: { consent: MOCK_CONSENT },
    })
    expect(wrapper.html()).toContain('dark:bg-dark-card')
    expect(wrapper.html()).toContain('dark:border-dark-border')
  })
})
