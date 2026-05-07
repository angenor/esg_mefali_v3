import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import DeletionConfirmModal from '~/components/DeletionConfirmModal.vue'

describe('DeletionConfirmModal', () => {
  it('rend le titre et la description quand open=true', () => {
    const wrapper = mount(DeletionConfirmModal, {
      props: { open: true },
      attachTo: document.body,
    })
    expect(document.body.innerHTML).toContain(
      'Supprimer définitivement votre compte ?',
    )
    wrapper.unmount()
  })

  it('a le bon role=dialog et aria-modal', () => {
    const wrapper = mount(DeletionConfirmModal, {
      props: { open: true },
      attachTo: document.body,
    })
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).not.toBeNull()
    expect(dialog?.getAttribute('aria-modal')).toBe('true')
    wrapper.unmount()
  })

  it('le bouton Confirmer est désactivé tant que les 3 étapes ne sont pas complétées', async () => {
    const wrapper = mount(DeletionConfirmModal, {
      props: { open: true },
      attachTo: document.body,
    })
    const confirmBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Confirmer la suppression'),
    ) as HTMLButtonElement | undefined
    expect(confirmBtn).toBeDefined()
    expect(confirmBtn?.disabled).toBe(true)
    wrapper.unmount()
  })

  it('émet @cancel au clic sur Annuler', async () => {
    const wrapper = mount(DeletionConfirmModal, {
      props: { open: true },
      attachTo: document.body,
    })
    await wrapper.vm.$nextTick()
    const cancelBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Annuler',
    ) as HTMLButtonElement | undefined
    expect(cancelBtn).toBeDefined()
    cancelBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()
    // Teleport déplace le DOM hors du wrapper ; on vérifie l'émission via
    // emitted() directement (Vue capture quand-même les emit même en Teleport).
    const emitted = wrapper.emitted('cancel')
    expect(emitted).toBeTruthy()
    wrapper.unmount()
  })

  it('le bouton Confirmer est activé quand les 3 étapes sont remplies', async () => {
    const wrapper = mount(DeletionConfirmModal, {
      props: { open: true },
      attachTo: document.body,
    })
    // Cocher la case
    const checkbox = document.querySelector(
      'input[name="acknowledge_consequences"]',
    ) as HTMLInputElement
    checkbox.click()
    // Saisir password
    const passwordInput = document.querySelector(
      '#deletion-password',
    ) as HTMLInputElement
    passwordInput.value = 'secretpwd'
    passwordInput.dispatchEvent(new Event('input'))
    // Saisir confirmation_text
    const confInput = document.querySelector(
      '#deletion-confirmation',
    ) as HTMLInputElement
    confInput.value = 'SUPPRIMER'
    confInput.dispatchEvent(new Event('input'))
    await wrapper.vm.$nextTick()
    const confirmBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Confirmer la suppression'),
    ) as HTMLButtonElement | undefined
    expect(confirmBtn?.disabled).toBe(false)
    wrapper.unmount()
  })
})
