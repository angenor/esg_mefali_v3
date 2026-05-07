import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EffectiveCriteriaList from '~/components/financing/EffectiveCriteriaList.vue'

/**
 * F07 — Tests EffectiveCriteriaList.vue.
 */
describe('EffectiveCriteriaList', () => {
  it('rend les critères avec libellés FR', () => {
    const wrapper = mount(EffectiveCriteriaList, {
      props: {
        criteria: {
          min_company_age: 5,
          max_company_revenue: 100_000_000,
          sectors: ['agriculture', 'energy'],
        },
      },
    })
    expect(wrapper.text()).toContain("Âge minimum de l'entreprise")
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('100')
  })

  it('affiche un message si aucun critère', () => {
    const wrapper = mount(EffectiveCriteriaList, {
      props: { criteria: {} },
    })
    expect(wrapper.text()).toContain('Aucun critère')
  })

  it('formate les listes (sectors) avec virgules', () => {
    const wrapper = mount(EffectiveCriteriaList, {
      props: { criteria: { sectors: ['agriculture', 'energy'] } },
    })
    expect(wrapper.text()).toContain('agriculture, energy')
  })

  it('contient classes dark mode', () => {
    const wrapper = mount(EffectiveCriteriaList, {
      props: { criteria: { min_company_age: 3 } },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:')
  })

  it('utilise role="list"', () => {
    const wrapper = mount(EffectiveCriteriaList, {
      props: { criteria: { min_company_age: 3 } },
    })
    const list = wrapper.find('[role="list"]')
    expect(list.exists()).toBe(true)
  })
})
