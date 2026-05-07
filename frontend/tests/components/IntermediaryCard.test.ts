import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import IntermediaryCard from '~/components/financing/IntermediaryCard.vue'

describe('IntermediaryCard', () => {
  const intermediary = {
    id: 'i1',
    name: 'BOAD',
    country: 'SN',
    organization_type: 'development_bank',
    success_rate: 0.75,
  }

  it('affiche le nom et le pays', () => {
    const wrapper = mount(IntermediaryCard, {
      props: { intermediary },
    })
    expect(wrapper.text()).toContain('BOAD')
    expect(wrapper.text()).toContain('SN')
  })

  it("affiche le taux de succès en pourcentage", () => {
    const wrapper = mount(IntermediaryCard, {
      props: { intermediary },
    })
    expect(wrapper.text()).toContain('75%')
  })

  it("classes dark mode", () => {
    const wrapper = mount(IntermediaryCard, {
      props: { intermediary },
    })
    expect(wrapper.html()).toContain('dark:')
  })
})
