import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import MoneyDisplay from '~/components/ui/MoneyDisplay.vue'
import type { Money } from '~/types/currency'

/**
 * F04 — Tests MoneyDisplay.vue (US2/US5).
 */

vi.mock('~/composables/useCurrency', () => ({
  useCurrency: () => ({
    format: (m: Money) => {
      const symbols: Record<string, string> = {
        XOF: 'FCFA', EUR: '€', USD: '$', GBP: '£', JPY: '¥',
      }
      return `${m.amount} ${symbols[m.currency] ?? m.currency}`
    },
    convert: vi.fn().mockResolvedValue({ amount: '1524.00', currency: 'EUR' }),
    getRate: vi.fn().mockResolvedValue(1),
    getPmeCurrency: () => 'XOF',
  }),
}))

describe('MoneyDisplay', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('rend le montant natif en mode native', async () => {
    const money: Money = { amount: '1000000', currency: 'XOF' }
    const wrapper = mount(MoneyDisplay, {
      props: { money, modeOverride: 'native' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('1000000 FCFA')
    expect(wrapper.text()).not.toContain('≈')
  })

  it('rend natif + équivalent en mode both pour devise non-PME', async () => {
    const money: Money = { amount: '1000000', currency: 'EUR' }
    const wrapper = mount(MoneyDisplay, {
      props: { money, modeOverride: 'both', showPmeCurrency: true },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('1000000 €')
    expect(wrapper.text()).toContain('1524.00')
    expect(wrapper.text()).toContain('≈')
  })

  it('omet l\'équivalent quand devise native = devise PME (XOF)', async () => {
    const money: Money = { amount: '1000', currency: 'XOF' }
    const wrapper = mount(MoneyDisplay, {
      props: { money, modeOverride: 'both' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('1000 FCFA')
    // Pas d'équivalent (≈) quand redondant.
    expect(wrapper.text()).not.toContain('≈')
  })

  it('porte les classes dark: pour le mode sombre', async () => {
    const money: Money = { amount: '500', currency: 'USD' }
    const wrapper = mount(MoneyDisplay, {
      props: { money, modeOverride: 'native' },
    })
    await flushPromises()
    const span = wrapper.find('.money-display').element as HTMLElement
    expect(span.className).toContain('dark:text-surface-dark-text')
  })

  it('affiche un tiret quand money est null', async () => {
    const wrapper = mount(MoneyDisplay, { props: { money: null } })
    await flushPromises()
    expect(wrapper.text()).toContain('—')
  })

  it('expose un title attribute (tooltip) avec la devise native', async () => {
    const money: Money = { amount: '500', currency: 'USD' }
    const wrapper = mount(MoneyDisplay, { props: { money } })
    await flushPromises()
    const span = wrapper.find('.money-display').element as HTMLElement
    expect(span.getAttribute('title')).toContain('Devise native')
  })
})
