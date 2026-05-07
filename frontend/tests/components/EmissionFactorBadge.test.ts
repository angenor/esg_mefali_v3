import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmissionFactorBadge from '~/components/EmissionFactorBadge.vue'

/**
 * F17 — Tests EmissionFactorBadge.vue (T025).
 *
 * Couvre :
 * - Rendu label + valeur + unite.
 * - Forwarding sourceId au SourceLink.
 * - Picto warning si isApproximate=true.
 * - Tooltip coherent avec fallbackReason.
 * - Classes dark mode presentes.
 * - Attributs ARIA exacts.
 */
describe('EmissionFactorBadge', () => {
  const baseFactor = {
    code: 'electricity_ci_2024',
    label: "Electricite reseau Cote d'Ivoire 2024",
    value: 0.456,
    unit: 'kgCO2e/kWh',
    country: 'CI',
    year: 2024,
  }

  const baseSource = {
    id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    publisher: 'IEA',
    title: 'IEA Africa Energy Outlook 2024',
  }

  it('rend le label et la valeur du facteur', () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: { factor: baseFactor, source: baseSource },
    })
    expect(wrapper.text()).toContain("Electricite reseau Cote d'Ivoire 2024")
    expect(wrapper.text()).toContain('0.456')
    expect(wrapper.text()).toContain('kgCO2e/kWh')
  })

  it("forward la prop source vers SourceLink (presence du picto cliquable)", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: { factor: baseFactor, source: baseSource },
    })
    // SourceLink rend un <button> si source.id est defini.
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it("ne rend PAS le SourceLink quand source est null", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: { factor: baseFactor, source: null },
    })
    // Pas de button SourceLink rendu.
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it("affiche le picto warning quand isApproximate=true", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: {
        factor: baseFactor,
        source: baseSource,
        isApproximate: true,
        fallbackReason: 'country_global',
      },
    })
    const warningSpan = wrapper.find('[role="img"]')
    expect(warningSpan.exists()).toBe(true)
    expect(warningSpan.attributes('aria-label')).toContain('approximatif')
  })

  it("ne rend PAS le picto warning quand isApproximate=false", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: {
        factor: baseFactor,
        source: baseSource,
        isApproximate: false,
      },
    })
    const warningSpan = wrapper.find('[role="img"]')
    expect(warningSpan.exists()).toBe(false)
  })

  it("tooltip coherent avec fallbackReason='year_older'", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: {
        factor: baseFactor,
        source: baseSource,
        isApproximate: true,
        fallbackReason: 'year_older',
      },
    })
    const warningSpan = wrapper.find('[role="img"]')
    expect(warningSpan.attributes('title')).toMatch(/annee anterieure|annee/i)
  })

  it("tooltip coherent avec fallbackReason='country_global'", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: {
        factor: baseFactor,
        source: baseSource,
        isApproximate: true,
        fallbackReason: 'country_global',
      },
    })
    const warningSpan = wrapper.find('[role="img"]')
    expect(warningSpan.attributes('title')).toMatch(/regional|generique|pays/i)
  })

  it("respecte les classes dark mode (bg-white, dark:bg-dark-card)", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: { factor: baseFactor, source: baseSource },
    })
    const root = wrapper.find('.emission-factor-badge')
    const cls = root.classes().join(' ')
    expect(cls).toContain('bg-white')
    expect(cls).toContain('dark:bg-dark-card')
    expect(cls).toContain('border-gray-200')
    expect(cls).toContain('dark:border-dark-border')
  })

  it("attributs ARIA : role='region' + aria-label descriptif", () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: { factor: baseFactor, source: baseSource },
    })
    const root = wrapper.find('.emission-factor-badge')
    expect(root.attributes('role')).toBe('region')
    expect(root.attributes('aria-label')).toContain("Facteur d'emission")
    expect(root.attributes('aria-label')).toContain("Cote d'Ivoire")
  })

  it("emet 'open-source' quand SourceLink est clique", async () => {
    const wrapper = mount(EmissionFactorBadge, {
      props: { factor: baseFactor, source: baseSource },
    })
    const button = wrapper.find('button')
    await button.trigger('click')
    const events = wrapper.emitted('open-source')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual([baseSource.id])
  })
})
