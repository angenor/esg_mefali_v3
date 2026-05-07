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

import EsgResults from '~/pages/esg/results.vue'

// Mock des composables — toutes les fonctions retournent des promesses resolues
vi.mock('~/composables/useEsg', () => ({
  useEsg: () => ({
    fetchAssessments: vi.fn().mockResolvedValue(undefined),
    fetchAssessment: vi.fn().mockResolvedValue(undefined),
    fetchScore: vi.fn().mockResolvedValue(undefined),
    fetchBenchmark: vi.fn().mockResolvedValue(null),
    loading: ref(false),
    error: ref(null),
  }),
}))

// F13 — Mock du composable multi-référentiels
vi.mock('~/composables/useEsgMultiReferential', () => ({
  useEsgMultiReferential: () => ({
    getReferentialScores: vi.fn().mockResolvedValue([]),
    recomputeScore: vi.fn().mockResolvedValue(null),
    generateMultiReferentialReport: vi.fn().mockResolvedValue(null),
    pollReferentialScores: vi.fn().mockResolvedValue([]),
    getReferentialScoresHistory: vi.fn().mockResolvedValue([]),
    loading: computed(() => false),
    error: computed(() => ''),
    sessionExpired: computed(() => false),
  }),
}))

// Stub NuxtLink
const NuxtLink = defineComponent({
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
})

describe('pages/esg/results.vue — liens /chat remplaces (Story 2.2 — AC1)', () => {
  let uiStore: ReturnType<typeof useUiStore>

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    uiStore = useUiStore()
  })

  function mountPage() {
    return mount(EsgResults, {
      global: {
        stubs: { NuxtLink },
      },
    })
  }

  it('ne contient aucun NuxtLink vers /chat dans le template', () => {
    const wrapper = mountPage()
    expect(wrapper.html()).not.toContain('href="/chat"')
  })

  it('le bouton "Demarrer une evaluation" ouvre le widget au clic', async () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const startBtn = buttons.find(b => b.text().includes('Demarrer une evaluation'))

    expect(startBtn).toBeDefined()
    expect(uiStore.chatWidgetOpen).toBe(false)

    await startBtn!.trigger('click')
    expect(uiStore.chatWidgetOpen).toBe(true)
  })

  it('les boutons ont type="button"', () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const chatBtns = buttons.filter(b => b.text().includes('Demarrer une evaluation'))
    chatBtns.forEach(btn => {
      expect(btn.attributes('type')).toBe('button')
    })
  })
})
