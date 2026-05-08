import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ConsentRevokeButton from '~/components/credit/ConsentRevokeButton.vue'

const STUBS = { Teleport: { template: '<div><slot /></div>' } }

describe('ConsentRevokeButton', () => {
  it('rend le label par défaut', () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    expect(wrapper.text()).toContain('Révoquer ce consentement')
  })

  it("ouvre la confirmation au clic et n'émet pas immédiatement", async () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'public_data_analysis' },
      global: { stubs: STUBS },
    })
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.html()).toContain('Confirmer la révocation')
    expect(wrapper.emitted('revoke')).toBeFalsy()
  })

  it('émet @revoke avec le type quand confirmé', async () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    await wrapper.findAll('button')[0].trigger('click')
    const buttons = wrapper.findAll('button')
    const confirmBtn = buttons.find((b) =>
      b.text().includes('Confirmer la révocation'),
    )
    await confirmBtn?.trigger('click')
    expect(wrapper.emitted('revoke')).toBeTruthy()
    expect(wrapper.emitted('revoke')![0]).toEqual(['mobile_money_analysis'])
  })

  it('annule la confirmation sans émettre', async () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'public_data_analysis' },
      global: { stubs: STUBS },
    })
    await wrapper.findAll('button')[0].trigger('click')
    const buttons = wrapper.findAll('button')
    const cancelBtn = buttons.find((b) => b.text() === 'Annuler')
    await cancelBtn?.trigger('click')
    expect(wrapper.emitted('revoke')).toBeFalsy()
  })

  it('mentionne explicitement la purge sous 30 jours', async () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'photos_ia_analysis' },
      global: { stubs: STUBS },
    })
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.text()).toContain('30 jours')
  })

  it("ne s'active pas en loading", async () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'mobile_money_analysis', loading: true },
      global: { stubs: STUBS },
    })
    const btn = wrapper.findAll('button')[0]
    expect(btn.attributes('disabled')).toBeDefined()
    await btn.trigger('click')
    // Pas de modale visible.
    expect(wrapper.text()).not.toContain('Confirmer la révocation')
  })

  it('a un aria-label structuré', () => {
    const wrapper = mount(ConsentRevokeButton, {
      props: { consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    const btn = wrapper.findAll('button')[0]
    expect(btn.attributes('aria-label')).toContain('mobile_money_analysis')
  })
})
