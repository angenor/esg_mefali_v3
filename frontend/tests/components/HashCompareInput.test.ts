import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import HashCompareInput from '~/components/attestations/HashCompareInput.vue'

const HASH_A = 'a'.repeat(64)
const HASH_B = 'b'.repeat(64)

describe('HashCompareInput', () => {
  it('rend un input et un bouton "Comparer"', () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.find('button').text()).toBe('Comparer')
  })

  it('affiche le message de match si hash identique', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    await wrapper.find('input').setValue(HASH_A)
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain('Hash conforme')
  })

  it('affiche le message de mismatch si hash différent', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    await wrapper.find('input').setValue(HASH_B)
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain('Hash non conforme')
  })

  it('émet "compared" avec match=true si match', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    await wrapper.find('input').setValue(HASH_A)
    await wrapper.find('button').trigger('click')
    const events = wrapper.emitted('compared')
    expect(events).toBeTruthy()
    expect((events![0] as Array<{ match: boolean }>)[0].match).toBe(true)
  })

  it('émet "compared" avec match=false si non match', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    await wrapper.find('input').setValue('different')
    await wrapper.find('button').trigger('click')
    const events = wrapper.emitted('compared')
    expect(events).toBeTruthy()
    expect((events![0] as Array<{ match: boolean }>)[0].match).toBe(false)
  })

  it('comparaison stricte case-sensitive', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    // Modifie casse
    await wrapper.find('input').setValue(HASH_A.toUpperCase())
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain('Hash non conforme')
  })

  it('bouton désactivé si input vide', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    await wrapper.find('input').setValue('something')
    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()
  })

  it('input a aria-describedby quand un feedback est affiché', async () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    await wrapper.find('input').setValue(HASH_A)
    await wrapper.find('button').trigger('click')
    expect(wrapper.find('input').attributes('aria-describedby')).toBe(
      'hash-compare-feedback',
    )
  })

  it('boutons et input ont min-height 44px (touch-friendly)', () => {
    const wrapper = mount(HashCompareInput, {
      props: { expected: HASH_A },
    })
    const inputClasses = wrapper.find('input').classes()
    const buttonClasses = wrapper.find('button').classes()
    expect(inputClasses.some((c) => c.includes('min-h-[44px]'))).toBe(true)
    expect(buttonClasses.some((c) => c.includes('min-h-[44px]'))).toBe(true)
  })
})
