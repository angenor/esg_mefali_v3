import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import OfferDetail from '~/components/financing/OfferDetail.vue'
import type { Offer } from '~/types/financing'

/**
 * F07 — Tests OfferDetail.vue.
 */
describe('OfferDetail', () => {
  const offer: Offer = {
    id: 'offer-1',
    fund_id: 'fund-1',
    intermediary_id: 'interm-1',
    fund: {
      id: 'fund-1',
      name: 'GCF',
      organization: 'Green Climate Fund',
    },
    intermediary: {
      id: 'interm-1',
      name: 'BOAD',
      country: 'SN',
    },
    name: 'GCF via BOAD',
    accepted_languages: ['FR'],
    target_sector: ['agriculture'],
    effective_criteria: { min_company_age: 5 },
    effective_required_documents: [
      { title: 'Statuts', source_id: 'src-1', mandatory: true },
    ],
    effective_fees: {
      total_min: { amount: '500000.00', currency: 'XOF' },
      total_max: { amount: '2500000.00', currency: 'XOF' },
    },
    is_active: true,
    publication_status: 'published',
    source_id: 'src-1',
    version: '1.0',
    valid_from: '2026-01-01',
  }

  const stubs = {
    NuxtLink: {
      template: '<a :href="to"><slot /></a>',
      props: ['to'],
    },
    EffectiveCriteriaList: { template: '<div data-testid="criteria"></div>' },
    EffectiveDocumentsList: { template: '<div data-testid="docs"></div>' },
    EffectiveFees: { template: '<div data-testid="fees"></div>' },
  }

  it("affiche le nom de l'offre", () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('GCF via BOAD')
  })

  it('affiche la section Fonds source', () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('Fonds source')
    expect(wrapper.text()).toContain('GCF')
  })

  it("affiche la section Intermédiaire", () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('Intermédiaire')
    expect(wrapper.text()).toContain('BOAD')
  })

  it("intègre les sous-composants", () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    expect(wrapper.find('[data-testid="criteria"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="docs"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="fees"]').exists()).toBe(true)
  })

  it("bouton Comparer présent", () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    const btn = wrapper.findAll('button').find(b => b.text().includes('Comparer'))
    expect(btn).toBeDefined()
  })

  it("bouton Candidater présent", () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    const btn = wrapper.findAll('button').find(b => b.text().includes('Candidater'))
    expect(btn).toBeDefined()
  })

  it("émet 'compare' au clic", async () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    const btn = wrapper.findAll('button').find(b => b.text().includes('Comparer'))
    await btn!.trigger('click')
    expect(wrapper.emitted('compare')).toBeTruthy()
    expect(wrapper.emitted('compare')![0]).toEqual(['fund-1'])
  })

  it("émet 'apply' au clic", async () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    const btn = wrapper.findAll('button').find(b => b.text().includes('Candidater'))
    await btn!.trigger('click')
    expect(wrapper.emitted('apply')).toBeTruthy()
    expect(wrapper.emitted('apply')![0]).toEqual(['offer-1'])
  })

  it("classes dark mode présentes", () => {
    const wrapper = mount(OfferDetail, {
      props: { offer },
      global: { stubs },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:')
  })
})
