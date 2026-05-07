import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import RevokeAttestationModal from '~/components/attestations/RevokeAttestationModal.vue'

describe('RevokeAttestationModal', () => {
  it('ne s\'affiche pas si modelValue=false', () => {
    const wrapper = mount(RevokeAttestationModal, {
      props: { modelValue: false },
      attachTo: document.body,
    })
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    wrapper.unmount()
  })

  it('s\'affiche si modelValue=true', () => {
    const wrapper = mount(RevokeAttestationModal, {
      props: { modelValue: true, attestationDisplayId: 'ATT-2026-00001' },
      attachTo: document.body,
    })
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).toBeTruthy()
    expect(dialog?.textContent).toContain('ATT-2026-00001')
    wrapper.unmount()
  })

  it('a aria-modal=true et aria-labelledby', () => {
    const wrapper = mount(RevokeAttestationModal, {
      props: { modelValue: true },
      attachTo: document.body,
    })
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.getAttribute('aria-modal')).toBe('true')
    expect(dialog?.getAttribute('aria-labelledby')).toBe('revoke-title')
    wrapper.unmount()
  })

  it('bouton Confirmer désactivé si reason < 10 chars', async () => {
    const wrapper = mount(RevokeAttestationModal, {
      props: { modelValue: true },
      attachTo: document.body,
    })
    const ta = document.querySelector('textarea') as HTMLTextAreaElement
    ta.value = 'short'
    ta.dispatchEvent(new Event('input'))
    await wrapper.vm.$nextTick()
    const buttons = Array.from(document.querySelectorAll('button'))
    const confirmBtn = buttons.find((b) => b.textContent?.includes('Confirmer'))!
    expect(confirmBtn.hasAttribute('disabled')).toBe(true)
    wrapper.unmount()
  })

  it('émet "confirm" avec la raison si reason >= 10 chars', async () => {
    const wrapper = mount(RevokeAttestationModal, {
      props: { modelValue: true },
      attachTo: document.body,
    })
    const ta = document.querySelector('textarea') as HTMLTextAreaElement
    ta.value = 'Mise à jour majeure du profil'
    ta.dispatchEvent(new Event('input'))
    await wrapper.vm.$nextTick()
    const confirmBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Confirmer'),
    )!
    expect(confirmBtn.hasAttribute('disabled')).toBe(false)
    confirmBtn.click()
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted('confirm')
    expect(events).toBeTruthy()
    expect((events![0] as string[])[0]).toBe('Mise à jour majeure du profil')
    wrapper.unmount()
  })

  it('émet update:modelValue=false sur clic Annuler', async () => {
    const wrapper = mount(RevokeAttestationModal, {
      props: { modelValue: true },
      attachTo: document.body,
    })
    const cancelBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Annuler'),
    )!
    cancelBtn.click()
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect((events![0] as boolean[])[0]).toBe(false)
    wrapper.unmount()
  })
})
