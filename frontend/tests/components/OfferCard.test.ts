import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import OfferCard from '~/components/financing/OfferCard.vue'
import type { OfferSummary } from '~/types/financing'

/**
 * F07 — Tests OfferCard.vue.
 */
describe('OfferCard', () => {
  const offer: OfferSummary = {
    id: 'offer-id-1',
    name: 'GCF via BOAD',
    fund_id: 'fund-1',
    intermediary_id: 'interm-1',
    accepted_languages: ['FR', 'EN'],
    publication_status: 'published',
    is_active: true,
    effective_processing_time_days_min: 90,
    effective_processing_time_days_max: 180,
  }

  // Stub NuxtLink pour les tests
  const NuxtLinkStub = {
    template: '<a :href="to"><slot /></a>',
    props: ['to'],
  }

  it('affiche le nom de l\'offre', () => {
    const wrapper = mount(OfferCard, {
      props: { offer },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('GCF via BOAD')
  })

  it('affiche les langues acceptées', () => {
    const wrapper = mount(OfferCard, {
      props: { offer },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('FR')
    expect(wrapper.text()).toContain('EN')
  })

  it('affiche le délai de traitement', () => {
    const wrapper = mount(OfferCard, {
      props: { offer },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('90-180j')
  })

  it("badge 'Publié' visible", () => {
    const wrapper = mount(OfferCard, {
      props: { offer },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('Publié')
  })

  it("contient classes dark mode", () => {
    const wrapper = mount(OfferCard, {
      props: { offer },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:')
  })

  it("a un aria-label sur le lien", () => {
    const wrapper = mount(OfferCard, {
      props: { offer },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('aria-label')).toContain('GCF via BOAD')
  })
})
