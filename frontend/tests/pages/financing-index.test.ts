import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, onMounted, computed } from 'vue'
import { useUiStore } from '~/stores/ui'

// Stub des auto-imports Vue/Nuxt
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('computed', computed)
vi.stubGlobal('ref', ref)
vi.stubGlobal('definePageMeta', vi.fn())
// F07 — useRuntimeConfig pour le feature flag USE_OFFER_VIEW
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { useOfferView: false },
}))

import FinancingIndex from '~/pages/financing/index.vue'

// Mock des composables
vi.mock('~/composables/useFinancing', () => ({
  useFinancing: () => ({
    fetchMatches: vi.fn(),
    fetchFunds: vi.fn(),
    fetchIntermediaries: vi.fn(),
    listOffers: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 }),
    loading: ref(false),
    error: ref(null),
  }),
}))

// Stub NuxtLink
const NuxtLink = defineComponent({
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
})

describe('pages/financing/index.vue — liens /chat remplaces (Story 2.2 — AC1)', () => {
  let uiStore: ReturnType<typeof useUiStore>

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    uiStore = useUiStore()
  })

  function mountPage() {
    return mount(FinancingIndex, {
      global: {
        stubs: { NuxtLink },
      },
    })
  }

  it('ne contient aucun NuxtLink vers /chat dans le template', () => {
    const wrapper = mountPage()
    expect(wrapper.html()).not.toContain('href="/chat"')
  })

  it('le bouton "Conseils IA" ouvre le widget au clic', async () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const adviceBtn = buttons.find(b => b.text().includes('Conseils IA'))

    expect(adviceBtn).toBeDefined()
    expect(uiStore.chatWidgetOpen).toBe(false)

    await adviceBtn!.trigger('click')
    expect(uiStore.chatWidgetOpen).toBe(true)
  })

  it('les boutons ont type="button"', () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const chatBtns = buttons.filter(b => b.text().includes('Conseils IA'))
    chatBtns.forEach(btn => {
      expect(btn.attributes('type')).toBe('button')
    })
  })
})
