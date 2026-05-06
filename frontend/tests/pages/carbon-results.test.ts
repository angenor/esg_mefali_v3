import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, onMounted, computed, watch } from 'vue'
import { useUiStore } from '~/stores/ui'

// Stub des auto-imports Vue/Nuxt
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('computed', computed)
vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('definePageMeta', vi.fn())
vi.stubGlobal('useRoute', () => ({ query: {} }))

import CarbonResults from '~/pages/carbon/results.vue'

// Mock des composables — toutes les fonctions retournent des promesses resolues
vi.mock('~/composables/useCarbon', () => ({
  useCarbon: () => ({
    fetchAssessments: vi.fn().mockResolvedValue(undefined),
    fetchAssessment: vi.fn().mockResolvedValue(undefined),
    fetchSummary: vi.fn().mockResolvedValue(null),
    fetchBenchmark: vi.fn().mockResolvedValue(null),
    loading: ref(false),
    error: ref(null),
  }),
}))

// F01 - mock useSources pour eviter useRuntimeConfig (non defini dans tests Vue)
vi.mock('~/composables/useSources', () => ({
  useSources: () => ({
    store: { error: '', getById: vi.fn(), setSource: vi.fn() },
    fetchSource: vi.fn().mockResolvedValue(null),
    searchSources: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
    cacheSource: vi.fn(),
  }),
}))

// Stub NuxtLink et Chart.js
const NuxtLink = defineComponent({
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
})
const Doughnut = defineComponent({ name: 'Doughnut', props: ['data', 'options'], template: '<canvas />' })
const Bar = defineComponent({ name: 'Bar', props: ['data', 'options'], template: '<canvas />' })

describe('pages/carbon/results.vue — liens /chat remplaces (Story 2.2 — AC1)', () => {
  let uiStore: ReturnType<typeof useUiStore>

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    uiStore = useUiStore()
  })

  function mountPage() {
    return mount(CarbonResults, {
      global: {
        stubs: { NuxtLink, Doughnut, Bar },
      },
    })
  }

  it('ne contient aucun NuxtLink vers /chat dans le template', () => {
    const wrapper = mountPage()
    expect(wrapper.html()).not.toContain('href="/chat"')
  })

  it('le bouton "Demarrer un bilan" ouvre le widget au clic', async () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const startBtn = buttons.find(b => b.text().includes('Demarrer un bilan'))

    expect(startBtn).toBeDefined()
    expect(uiStore.chatWidgetOpen).toBe(false)

    await startBtn!.trigger('click')
    expect(uiStore.chatWidgetOpen).toBe(true)
  })

  it('les boutons ont type="button"', () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const chatBtns = buttons.filter(b => b.text().includes('Demarrer un bilan'))
    chatBtns.forEach(btn => {
      expect(btn.attributes('type')).toBe('button')
    })
  })
})
