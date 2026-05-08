import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ConsentRequestModal from '~/components/credit/ConsentRequestModal.vue'

const STUBS = { Teleport: { template: '<div><slot /></div>' } }

describe('ConsentRequestModal', () => {
  it("ne rend rien quand open=false", () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: false, consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('affiche le titre et la description correctement pour Mobile Money', () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    expect(wrapper.text()).toContain('Analyse Mobile Money')
    expect(wrapper.text()).toContain('Wave')
    expect(wrapper.text()).toContain('hash')
  })

  it('affiche les bons libellés pour Photos IA', () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'photos_ia_analysis' },
      global: { stubs: STUBS },
    })
    expect(wrapper.text()).toContain('Analyse IA des photos')
    expect(wrapper.text()).toContain('chiffrées')
  })

  it('affiche les bons libellés pour Données publiques + cap 10 %', () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'public_data_analysis' },
      global: { stubs: STUBS },
    })
    expect(wrapper.text()).toContain('Analyse de données publiques')
    expect(wrapper.text()).toContain('10 %')
  })

  it('émet @confirm quand on clique sur le bouton principal', async () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    const buttons = wrapper.findAll('button')
    const confirmBtn = buttons.find((b) => b.text().includes('accorde'))
    await confirmBtn?.trigger('click')
    expect(wrapper.emitted('confirm')).toBeTruthy()
  })

  it('émet @cancel quand on clique sur Annuler', async () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    const buttons = wrapper.findAll('button')
    const cancelBtn = buttons.find((b) => b.text() === 'Annuler')
    await cancelBtn?.trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('contient les classes dark mode', () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    expect(wrapper.html()).toContain('dark:bg-dark-card')
    expect(wrapper.html()).toContain('dark:border-dark-border')
  })

  it('a les attributs ARIA dialog modal', () => {
    const wrapper = mount(ConsentRequestModal, {
      props: { open: true, consentType: 'mobile_money_analysis' },
      global: { stubs: STUBS },
    })
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.attributes('aria-labelledby')).toBeTruthy()
    expect(dialog.attributes('aria-describedby')).toBeTruthy()
  })

  it('désactive le bouton confirmer pendant loading', () => {
    const wrapper = mount(ConsentRequestModal, {
      props: {
        open: true,
        consentType: 'mobile_money_analysis',
        loading: true,
      },
      global: { stubs: STUBS },
    })
    const buttons = wrapper.findAll('button')
    const confirmBtn = buttons.find((b) => b.text().includes('Enregistrement'))
    expect(confirmBtn?.attributes('disabled')).toBeDefined()
  })
})
