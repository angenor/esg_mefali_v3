import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ResourceCard from '~/components/resources/ResourceCard.vue'
import type { ResourceListItem } from '~/types/resource'

const baseResource: ResourceListItem = {
  id: 'r1',
  type: 'guide',
  title: 'Guide ESG',
  slug: 'guide-esg',
  description: 'Un guide pratique',
  category: ['governance'],
  target_audience: ['pme_small'],
  language: 'fr',
  duration_seconds: null,
  intermediary_id: null,
  version: '1.0.0',
  publication_status: 'published',
  view_count: 5,
  updated_at: '2026-01-15T12:00:00Z',
}

const NuxtLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

describe('ResourceCard', () => {
  it('affiche le titre et description', () => {
    const wrapper = mount(ResourceCard, {
      props: { resource: baseResource },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('Guide ESG')
    expect(wrapper.text()).toContain('Un guide pratique')
  })

  it('affiche le compteur de vues au pluriel', () => {
    const wrapper = mount(ResourceCard, {
      props: { resource: baseResource },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('5 vues')
  })

  it('formate la durée en mm:ss si présente', () => {
    const wrapper = mount(ResourceCard, {
      props: {
        resource: { ...baseResource, type: 'video', duration_seconds: 185 },
      },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.text()).toContain('3:05')
  })

  it('lien NuxtLink vers /resources/<slug>', () => {
    const wrapper = mount(ResourceCard, {
      props: { resource: baseResource },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.find('a').attributes('href')).toBe('/resources/guide-esg')
  })

  it('expose un aria-label accessible', () => {
    const wrapper = mount(ResourceCard, {
      props: { resource: baseResource },
      global: { stubs: { NuxtLink: NuxtLinkStub } },
    })
    expect(wrapper.find('a').attributes('aria-label')).toMatch(/Guide ESG/)
  })
})
