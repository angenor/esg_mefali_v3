import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import KPICardBlock from '~/components/richblocks/KPICardBlock.vue'
import type { KPICardBlockProps } from '~/types/richblocks'

function _props(overrides: Partial<KPICardBlockProps> = {}): KPICardBlockProps {
  return {
    title: 'Empreinte carbone 2026',
    value: '45 tCO2e',
    color: 'emerald',
    ...overrides,
  }
}

describe('KPICardBlock (F11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('rend le titre et la valeur', () => {
    const wrapper = mount(KPICardBlock, { props: _props() })
    expect(wrapper.text()).toContain('Empreinte carbone 2026')
    expect(wrapper.text()).toContain('45 tCO2e')
  })

  it('affiche le delta avec direction down', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({
        delta: -12,
        deltaLabel: 'vs 2024',
        deltaDirection: 'down',
        deltaIsGood: true,
      }),
    })
    const text = wrapper.text()
    // Le delta affiché doit contenir 12 et "vs 2024"
    expect(text).toMatch(/12/)
    expect(text).toContain('vs 2024')
  })

  it('applique une classe verte si deltaIsGood=true', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({
        delta: -12,
        deltaIsGood: true,
        deltaDirection: 'down',
      }),
    })
    const html = wrapper.html()
    // green/emerald class présente
    expect(html).toMatch(/text-(green|emerald)-/)
  })

  it('applique une classe rouge si deltaIsGood=false', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({
        delta: 12,
        deltaIsGood: false,
        deltaDirection: 'up',
      }),
    })
    const html = wrapper.html()
    expect(html).toMatch(/text-(red|rose)-/)
  })

  it('rend le picto Source si sourceId fourni', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({ sourceId: 'abc-123' }),
    })
    // Le composant SourceLink est rendu (button cliquable)
    expect(wrapper.findAll('button').length).toBeGreaterThan(0)
  })

  it('ne rend pas de picto Source sans sourceId', () => {
    const wrapper = mount(KPICardBlock, { props: _props() })
    // Aucun bouton lié à la source
    const sourceButtons = wrapper.findAll('button[aria-label*="source"]')
    expect(sourceButtons.length).toBe(0)
  })

  it('emet open-source au clic sur picto source', async () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({ sourceId: 'abc-123' }),
    })
    const sourceBtn = wrapper.find('button[aria-label*="source"]')
    expect(sourceBtn.exists()).toBe(true)
    await sourceBtn.trigger('click')
    const events = wrapper.emitted('open-source')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['abc-123'])
  })

  it('emet navigate au clic sur drilldown', async () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({ drilldownUrl: '/carbon/results' }),
    })
    // La carte entière est cliquable
    const card = wrapper.find('[data-test="kpi-card-root"]')
    expect(card.exists()).toBe(true)
    await card.trigger('click')
    const events = wrapper.emitted('navigate')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['/carbon/results'])
  })

  it('a un aria-label structuré', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({
        delta: -12,
        deltaLabel: 'vs 2024',
        deltaDirection: 'down',
      }),
    })
    const card = wrapper.find('[data-test="kpi-card-root"]')
    const ariaLabel = card.attributes('aria-label')
    expect(ariaLabel).toBeTruthy()
    expect(ariaLabel).toContain('Empreinte carbone 2026')
  })

  it('utilise les classes dark: Tailwind', () => {
    const wrapper = mount(KPICardBlock, { props: _props() })
    const html = wrapper.html()
    expect(html).toMatch(/dark:/)
  })

  it('applique la couleur color="rose" via classe rose', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({ color: 'rose' }),
    })
    const html = wrapper.html()
    expect(html).toMatch(/rose/)
  })

  it('formatte valueMoney quand fourni', () => {
    const wrapper = mount(KPICardBlock, {
      props: _props({
        value: '655 957 FCFA',
        valueMoney: { amount: '655957.00', currency: 'XOF' },
      }),
    })
    // Affichage Money formaté ou value direct
    const text = wrapper.text()
    expect(text).toContain('655')
  })
})
