import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FundCard from '~/components/financing/FundCard.vue'

describe('FundCard', () => {
  const fund = {
    id: 'fund-1',
    name: 'GCF',
    organization: 'Green Climate Fund',
    fund_type: 'multilateral',
  }

  it('affiche le nom et l\'organisation', () => {
    const wrapper = mount(FundCard, {
      props: { fund },
    })
    expect(wrapper.text()).toContain('GCF')
    expect(wrapper.text()).toContain('Green Climate Fund')
  })

  it('classes dark mode présentes', () => {
    const wrapper = mount(FundCard, {
      props: { fund },
    })
    expect(wrapper.html()).toContain('dark:')
  })
})
