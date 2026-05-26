/**
 * T022 (F048 US3) — Handler « Candidater » de la page offre.
 *
 * Réf. contracts/frontend-apply.md T1–T3.
 * - clic → createApplication({ offerId, projectId }) + navigation vers le dossier ;
 * - erreur API → message affiché, pas de navigation ;
 * - double-clic → une seule création (garde de ré-entrance / bouton désactivé).
 *
 * (Vitest exige l'extension .test.ts — cf. vitest.config.ts include.)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, ref, computed, onMounted } from 'vue'

const pushSpy = vi.fn()
const createApplicationSpy = vi.fn()

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('definePageMeta', vi.fn())
vi.stubGlobal('useRoute', () => ({
  params: { offer_id: 'OFFER1' },
  query: { project_id: 'PROJ1' },
}))
vi.stubGlobal('useRouter', () => ({ push: pushSpy }))

vi.mock('~/composables/useFinancing', () => ({
  useFinancing: () => ({
    getOffer: vi.fn().mockResolvedValue({
      id: 'OFFER1',
      name: 'GCF via BOAD',
      fund_id: 'FUND1',
      accepted_languages: ['FR'],
    }),
  }),
}))
vi.mock('~/composables/useProjectMatching', () => ({
  useProjectMatching: () => ({ getMatchDetails: vi.fn().mockResolvedValue(null) }),
}))
vi.mock('~/composables/useApplications', () => ({
  useApplications: () => ({
    createApplication: createApplicationSpy,
    loading: ref(false),
    error: ref(''),
  }),
}))

const OfferDetailStub = defineComponent({
  name: 'OfferDetail',
  props: ['offer', 'applying'],
  emits: ['compare', 'apply'],
  template:
    '<button class="apply-btn" :disabled="applying" @click="$emit(\'apply\', offer.id)">Candidater</button>',
})
const Stub = defineComponent({ template: '<div><slot /></div>' })

import OfferPage from '~/pages/financing/offers/[offer_id].vue'

function mountPage() {
  return mount(OfferPage, {
    global: {
      stubs: {
        OfferDetail: OfferDetailStub,
        DualScoreDisplay: Stub,
        MissingProjectCriteriaList: Stub,
        NuxtLink: Stub,
      },
    },
  })
}

describe('financing/offers/[offer_id].vue — handleApply (F048 US3)', () => {
  beforeEach(() => {
    pushSpy.mockReset()
    createApplicationSpy.mockReset()
  })

  it('T1 — clic appelle createApplication et navigue vers le dossier', async () => {
    createApplicationSpy.mockResolvedValue({ id: 'APP1', status: 'draft' })
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('.apply-btn').trigger('click')
    await flushPromises()

    expect(createApplicationSpy).toHaveBeenCalledTimes(1)
    expect(createApplicationSpy).toHaveBeenCalledWith(
      expect.objectContaining({ offerId: 'OFFER1', projectId: 'PROJ1' }),
    )
    expect(pushSpy).toHaveBeenCalledWith('/applications/APP1')
  })

  it('T2 — erreur API → message affiché, pas de navigation', async () => {
    createApplicationSpy.mockRejectedValue(new Error('Création impossible'))
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('.apply-btn').trigger('click')
    await flushPromises()

    expect(pushSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Création impossible')
  })

  it('T3 — double-clic rapide → une seule création', async () => {
    let resolve!: (v: unknown) => void
    createApplicationSpy.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    const wrapper = mountPage()
    await flushPromises()

    const btn = wrapper.find('.apply-btn')
    await btn.trigger('click')
    await btn.trigger('click') // 2e clic pendant que le 1er est en cours
    resolve({ id: 'APP1', status: 'draft' })
    await flushPromises()

    expect(createApplicationSpy).toHaveBeenCalledTimes(1)
  })
})
