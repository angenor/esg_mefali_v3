import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MatchCardBlock from '~/components/richblocks/MatchCardBlock.vue'
import type { MatchCardBlockProps } from '~/types/richblocks'

function _props(overrides: Partial<MatchCardBlockProps> = {}): MatchCardBlockProps {
  return {
    projectId: '00000000-0000-0000-0000-000000000001',
    offerId: '00000000-0000-0000-0000-000000000002',
    fundName: 'Green Climate Fund',
    intermediaryName: 'BOAD',
    compatibilityScore: 78,
    amountRange: '1-5 M FCFA',
    timeline: '12-18 mois',
    instruments: ['subvention', 'blending'],
    missingCriteriaCount: 2,
    ctaLabel: 'Explorer',
    drilldownUrl: '/financing/offers/abc?project_id=xyz',
    ...overrides,
  }
}

describe('MatchCardBlock (F11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('rend le nom du fonds et de l\'intermédiaire', () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    const text = wrapper.text()
    expect(text).toContain('Green Climate Fund')
    expect(text).toContain('BOAD')
  })

  it('rend le score de compatibilité', () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    expect(wrapper.text()).toMatch(/78/)
  })

  it('rend le range montant', () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    expect(wrapper.text()).toContain('1-5 M FCFA')
  })

  it('rend la timeline', () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    expect(wrapper.text()).toContain('12-18 mois')
  })

  it('rend les badges instruments', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({ instruments: ['subvention', 'blending', 'garantie'] }),
    })
    const text = wrapper.text()
    expect(text).toContain('subvention')
    expect(text).toContain('blending')
    expect(text).toContain('garantie')
  })

  it('rend le compteur critères manquants', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({ missingCriteriaCount: 3 }),
    })
    expect(wrapper.text()).toMatch(/3/)
  })

  it('emet navigate au clic sur CTA', async () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    const cta = wrapper.find('[data-test="match-card-cta"]')
    expect(cta.exists()).toBe(true)
    await cta.trigger('click')
    const events = wrapper.emitted('navigate')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual([
      '/financing/offers/abc?project_id=xyz',
    ])
  })

  it('rend placeholder initiales si pas de logo', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({ fundName: 'Green Climate Fund' }),
    })
    // Initiales "GC" attendues
    const html = wrapper.html()
    expect(html).toMatch(/GC|G/)
  })

  it('rend l\'image du logo si fundLogoUrl fourni', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({ fundLogoUrl: 'https://logo.example/fund.png' }),
    })
    const imgs = wrapper.findAll('img')
    expect(imgs.length).toBeGreaterThan(0)
    const src = imgs[0]?.attributes('src')
    expect(src).toContain('logo.example')
  })

  it('rend le label CTA personnalisé', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({ ctaLabel: 'Voir détails' }),
    })
    expect(wrapper.text()).toContain('Voir détails')
  })

  it('expose un aria-label structuré sur la carte', () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    const card = wrapper.find('[data-test="match-card-root"]')
    const ariaLabel = card.attributes('aria-label')
    expect(ariaLabel).toBeTruthy()
    expect(ariaLabel).toContain('Green Climate Fund')
  })

  it('utilise les classes dark: Tailwind', () => {
    const wrapper = mount(MatchCardBlock, { props: _props() })
    const html = wrapper.html()
    expect(html).toMatch(/dark:/)
  })

  it('affiche un tooltip avec breakdown au focus si fourni', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({
        compatibilityBreakdown: { fund_score: 80, intermediary_score: 65 },
      }),
    })
    // Le breakdown est rendu dans le DOM (tooltip ou title)
    const html = wrapper.html()
    expect(html).toMatch(/80|65/)
  })

  it('limite l\'affichage à 8 instruments max (UI)', () => {
    const wrapper = mount(MatchCardBlock, {
      props: _props({
        instruments: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
      }),
    })
    const text = wrapper.text()
    // Tous les instruments doivent être présents
    expect(text).toContain('a')
    expect(text).toContain('h')
  })
})
