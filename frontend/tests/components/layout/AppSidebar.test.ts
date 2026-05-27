import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed, onMounted } from 'vue'

// Stub des auto-imports Vue/Nuxt
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', onMounted)

import AppSidebar from '~/components/layout/AppSidebar.vue'

// Mock des composables
vi.mock('~/composables/useAuth', () => ({
  useAuth: () => ({ logout: vi.fn() }),
}))
vi.mock('~/composables/useCompanyProfile', () => ({
  useCompanyProfile: () => ({ fetchCompletion: vi.fn() }),
}))

// Stub NuxtLink comme un <a>
const NuxtLink = defineComponent({
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="to" :data-to="to"><slot /></a>',
})

describe('AppSidebar (Story 2.2 — AC2, AC4)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function mountSidebar() {
    return mount(AppSidebar, {
      global: {
        stubs: { NuxtLink },
      },
    })
  }

  it('ne contient pas d\'item "Chat IA" dans la navigation', () => {
    const wrapper = mountSidebar()
    const links = wrapper.findAll('a')
    const chatLink = links.find(l => l.attributes('data-to') === '/chat')
    expect(chatLink).toBeUndefined()
  })

  it('ne contient aucune reference a la route /chat', () => {
    const wrapper = mountSidebar()
    expect(wrapper.html()).not.toContain('data-to="/chat"')
  })

  it('contient toujours les autres items de navigation', () => {
    const wrapper = mountSidebar()
    const links = wrapper.findAll('a')
    const routes = links.map(l => l.attributes('data-to'))
    expect(routes).toContain('/dashboard')
    expect(routes).toContain('/esg')
    expect(routes).toContain('/carbon')
    expect(routes).toContain('/financing')
  })

  it('chaque lien de navigation possède une icône SVG (régression "Dossiers" sans icône)', () => {
    const wrapper = mountSidebar()
    const navLinks = wrapper.findAll('a[data-to]')
    expect(navLinks.length).toBeGreaterThan(0)
    for (const link of navLinks) {
      const to = link.attributes('data-to')
      expect(
        link.find('svg').exists(),
        `le lien de navigation "${to}" doit afficher une icône SVG`,
      ).toBe(true)
    }
  })

  it('le lien "Dossiers" (/applications) a une icône', () => {
    const wrapper = mountSidebar()
    const dossiers = wrapper.findAll('a[data-to]').find(
      l => l.attributes('data-to') === '/applications',
    )
    expect(dossiers, 'le lien /applications doit exister').toBeTruthy()
    expect(dossiers!.find('svg').exists()).toBe(true)
  })
})
