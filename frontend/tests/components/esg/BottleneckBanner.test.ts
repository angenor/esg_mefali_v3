import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BottleneckBanner from '~/components/esg/BottleneckBanner.vue'
import type { BottleneckInfo } from '~/types/esg'

function makeBottleneck(overrides: Partial<BottleneckInfo> = {}): BottleneckInfo {
  return {
    bottleneck_referential_code: 'gcf',
    bottleneck_referential_name: 'Green Climate Fund',
    bottleneck_score: 45,
    other_referential_code: 'boad_ess',
    other_referential_score: 68,
    gap: 23,
    eligibility_min: false,
    top_3_critical_indicators: ['E1', 'S2', 'G3'],
    ...overrides,
  }
}

describe('BottleneckBanner', () => {
  it('renders bottleneck name and score', () => {
    const wrapper = mount(BottleneckBanner, {
      props: { bottleneck: makeBottleneck() },
    })
    expect(wrapper.text()).toContain('Green Climate Fund')
    expect(wrapper.text()).toContain('45/100')
  })

  it('lists top 3 critical indicators', () => {
    const wrapper = mount(BottleneckBanner, {
      props: { bottleneck: makeBottleneck() },
    })
    expect(wrapper.text()).toContain('E1')
    expect(wrapper.text()).toContain('S2')
    expect(wrapper.text()).toContain('G3')
  })

  it('emits focus-indicators when clicking « Renseigner maintenant »', async () => {
    const wrapper = mount(BottleneckBanner, {
      props: { bottleneck: makeBottleneck() },
    })
    const btn = wrapper.findAll('button').find((b) => b.text().includes('Renseigner'))
    expect(btn).toBeDefined()
    await btn!.trigger('click')
    expect(wrapper.emitted('focus-indicators')).toBeTruthy()
    expect((wrapper.emitted('focus-indicators') as string[][][])[0][0]).toEqual([
      'E1',
      'S2',
      'G3',
    ])
  })

  it('shows red severity when not eligible', () => {
    const wrapper = mount(BottleneckBanner, {
      props: { bottleneck: makeBottleneck({ eligibility_min: false, gap: 10 }) },
    })
    expect(wrapper.text()).toContain('non éligible actuellement')
  })

  it('shows green severity when eligible and small gap', () => {
    const wrapper = mount(BottleneckBanner, {
      props: { bottleneck: makeBottleneck({ eligibility_min: true, gap: 2 }) },
    })
    const html = wrapper.html()
    expect(html).toContain('bg-green-50')
  })

  it('applies dark mode classes', () => {
    const wrapper = mount(BottleneckBanner, {
      props: { bottleneck: makeBottleneck() },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-')
  })

  it('hides Renseigner button when no critical indicators', () => {
    const wrapper = mount(BottleneckBanner, {
      props: {
        bottleneck: makeBottleneck({ top_3_critical_indicators: [] }),
      },
    })
    const btn = wrapper.findAll('button').find((b) => b.text().includes('Renseigner'))
    expect(btn).toBeUndefined()
  })
})
