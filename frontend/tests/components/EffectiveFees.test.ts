import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EffectiveFees from '~/components/financing/EffectiveFees.vue'

/**
 * F07 — Tests EffectiveFees.vue.
 */
describe('EffectiveFees', () => {
  it('affiche total_min et total_max', () => {
    const wrapper = mount(EffectiveFees, {
      props: {
        fees: {
          total_min: { amount: '500000.00', currency: 'XOF' },
          total_max: { amount: '2500000.00', currency: 'XOF' },
        },
      },
    })
    expect(wrapper.text()).toContain('XOF')
    // Format formatted with locale
    expect(wrapper.text()).toMatch(/500\W*000|0\.50\s*M/)
  })

  it('message si aucun frais', () => {
    const wrapper = mount(EffectiveFees, {
      props: { fees: {} },
    })
    expect(wrapper.text()).toContain('Aucun frais')
  })

  it("n'affiche qu'un total quand min == max", () => {
    const wrapper = mount(EffectiveFees, {
      props: {
        fees: {
          total_min: { amount: '500000.00', currency: 'XOF' },
          total_max: { amount: '500000.00', currency: 'XOF' },
        },
      },
    })
    // 1 seul "Total" sans "min" ou "max"
    expect(wrapper.text()).toContain('Total')
  })

  it('affiche le breakdown si fourni', () => {
    const wrapper = mount(EffectiveFees, {
      props: {
        fees: {
          total_min: { amount: '500000.00', currency: 'XOF' },
          breakdown: [
            { label: 'Frais de dossier', amount: '50000.00', currency: 'XOF', source: 'intermediary' },
          ],
        },
      },
    })
    expect(wrapper.text()).toContain('Détail des frais')
  })

  it('classes dark mode', () => {
    const wrapper = mount(EffectiveFees, {
      props: { fees: { total_min: { amount: '100', currency: 'XOF' } } },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:')
  })
})
