import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BottleneckBadge from '~/components/matching/BottleneckBadge.vue'

describe('BottleneckBadge (F14)', () => {
  it('rend le label fund avec classes rose', () => {
    const wrapper = mount(BottleneckBadge, {
      props: { bottleneck: 'fund', fundScore: 50, intermediaryScore: 80 },
    })
    expect(wrapper.text()).toContain('Critères du fonds')
    expect(wrapper.attributes('data-testid')).toBe('bottleneck-badge-fund')
    expect(wrapper.classes().some((c) => c.includes('rose')) || wrapper.html().includes('rose')).toBe(true)
  })

  it('rend le label intermediary avec classes amber', () => {
    const wrapper = mount(BottleneckBadge, {
      props: { bottleneck: 'intermediary' },
    })
    expect(wrapper.text()).toContain("Critères de l'intermédiaire")
    expect(wrapper.html()).toContain('amber')
  })

  it('rend le label balanced avec classes emerald', () => {
    const wrapper = mount(BottleneckBadge, {
      props: { bottleneck: 'balanced' },
    })
    expect(wrapper.text()).toContain('Profil équilibré')
    expect(wrapper.html()).toContain('emerald')
  })

  it('inclut le score dans aria-label quand fourni', () => {
    const wrapper = mount(BottleneckBadge, {
      props: { bottleneck: 'fund', fundScore: 40, intermediaryScore: 80 },
    })
    const aria = wrapper.attributes('aria-label') ?? ''
    expect(aria).toContain('40')
    expect(aria).toContain('80')
  })

  it('SVG décoratif a aria-hidden', () => {
    const wrapper = mount(BottleneckBadge, {
      props: { bottleneck: 'balanced' },
    })
    const svg = wrapper.find('svg')
    expect(svg.attributes('aria-hidden')).toBe('true')
  })

  it('expose dark mode classes', () => {
    const wrapper = mount(BottleneckBadge, {
      props: { bottleneck: 'balanced' },
    })
    expect(wrapper.html()).toMatch(/dark:/)
  })
})
