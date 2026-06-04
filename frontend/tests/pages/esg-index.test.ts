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

import EsgIndex from '~/pages/esg/index.vue'

// Mock des composables
vi.mock('~/composables/useEsg', () => ({
  useEsg: () => ({
    fetchAssessments: vi.fn(),
    // startNewAssessment() attend une row truthy pour ouvrir le widget ; le mock
    // doit donc fournir createAssessment + sessionExpired (sinon TypeError).
    createAssessment: vi.fn().mockResolvedValue({ id: 'new-assessment' }),
    loading: ref(false),
    error: ref(null),
    sessionExpired: ref(false),
  }),
}))

// Stub NuxtLink
const NuxtLink = defineComponent({
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
})

describe('pages/esg/index.vue — liens /chat remplaces (Story 2.2 — AC1)', () => {
  let uiStore: ReturnType<typeof useUiStore>

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    uiStore = useUiStore()
  })

  function mountPage() {
    return mount(EsgIndex, {
      global: {
        stubs: { NuxtLink },
      },
    })
  }

  it('ne contient aucun NuxtLink vers /chat dans le template', () => {
    const wrapper = mountPage()
    expect(wrapper.html()).not.toContain('href="/chat"')
  })

  it('le bouton "Nouvelle evaluation" ouvre le widget au clic', async () => {
    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const newEvalBtn = buttons.find(b => b.text().includes('Nouvelle evaluation'))

    expect(newEvalBtn).toBeDefined()
    expect(uiStore.chatWidgetOpen).toBe(false)

    await newEvalBtn!.trigger('click')
    expect(uiStore.chatWidgetOpen).toBe(true)
  })

  it('le bouton "Demarrer dans le chat" ouvre le widget au clic (etat vide)', async () => {
    const { useEsgStore } = await import('~/stores/esg')
    const esgStore = useEsgStore()
    ;(esgStore as any).assessments = []

    const wrapper = mountPage()
    const buttons = wrapper.findAll('button')
    const startBtn = buttons.find(b => b.text().includes('Demarrer dans le chat'))

    expect(startBtn).toBeDefined()
    expect(uiStore.chatWidgetOpen).toBe(false)

    await startBtn!.trigger('click')
    expect(uiStore.chatWidgetOpen).toBe(true)
  })
})

describe('pages/esg/index.vue — numérotation logique des évaluations', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function mountWithAssessments(items: unknown[]) {
    const { useEsgStore } = await import('~/stores/esg')
    const esgStore = useEsgStore()
    ;(esgStore as any).assessments = items
    return mount(EsgIndex, { global: { stubs: { NuxtLink } } })
  }

  it('numérote chronologiquement (n°1 = la plus ancienne) au lieu de « v1 » partout', async () => {
    // Le champ `version` (F04 versioning catalogue) vaut 1 pour toutes les
    // évaluations → libellé « v1 » identique et trompeur. On attend un numéro
    // séquentiel distinct par évaluation.
    const wrapper = await mountWithAssessments([
      // ordre d'affichage = plus récente d'abord (ordre API)
      { id: 'recent', version: 1, status: 'completed', sector: 'services', created_at: '2026-06-04T09:00:00Z', overall_score: 56, environment_score: 55, social_score: 52, governance_score: 60 },
      { id: 'older', version: 1, status: 'completed', sector: 'services', created_at: '2026-05-20T09:00:00Z', overall_score: 52, environment_score: 49, social_score: 55, governance_score: 51 },
    ])
    const html = wrapper.html()
    // Numéros distincts et logiques (la plus ancienne = n°1)…
    expect(html).toContain('Évaluation n°1')
    expect(html).toContain('Évaluation n°2')
    // …et plus de libellé « v{version} » identique pour toutes.
    expect(html).not.toContain('Evaluation v')
    expect(html).not.toContain('Évaluation v')
  })

  it('numérote une évaluation unique en n°1 (accent inclus)', async () => {
    const wrapper = await mountWithAssessments([
      { id: 'solo', version: 1, status: 'in_progress', sector: 'services', created_at: '2026-06-04T09:00:00Z', overall_score: null, environment_score: null, social_score: null, governance_score: null },
    ])
    expect(wrapper.html()).toContain('Évaluation n°1')
  })
})
