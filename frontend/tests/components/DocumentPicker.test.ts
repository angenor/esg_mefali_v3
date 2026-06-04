import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentPicker from '~/components/documents/DocumentPicker.vue'

const { fetchMock, storeState } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  storeState: { documents: [] as Array<Record<string, unknown>>, isLoading: false },
}))

vi.mock('~/composables/useDocuments', () => ({
  useDocuments: () => ({ store: storeState, fetchDocuments: fetchMock }),
}))

const FullscreenModalStub = {
  name: 'FullscreenModal',
  props: ['visible'],
  emits: ['close'],
  template: '<div v-if="visible" class="modal-stub"><slot /></div>',
}
const DocumentListStub = {
  name: 'DocumentList',
  props: { documents: Array, isLoading: Boolean, selectableOnly: Boolean },
  emits: ['select', 'delete'],
  template: '<div class="dl-stub" />',
}

const stubs = { FullscreenModal: FullscreenModalStub, DocumentList: DocumentListStub }

function mountPicker(visible = true) {
  return mount(DocumentPicker, { props: { visible }, global: { stubs } })
}

describe('DocumentPicker (049, US2)', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    storeState.documents = []
    storeState.isLoading = false
  })

  it('charge les documents à l\'ouverture avec une limite haute (pas de page 1 tronquée)', () => {
    mountPicker(true)
    expect(fetchMock).toHaveBeenCalledWith({ limit: 200 })
  })

  it('liste TOUS les documents du compte (aucun filtrage par origine, FR-002a) en mode sélecteur', () => {
    storeState.documents = [
      { id: 'd1', original_filename: 'a.pdf', mime_type: 'application/pdf', file_size: 1, status: 'uploaded', document_type: null, has_analysis: false, created_at: '2026-06-03' },
      // document créé via l'upload checklist : doit aussi être listé
      { id: 'd2', original_filename: 'checklist-upload.pdf', mime_type: 'application/pdf', file_size: 1, status: 'uploaded', document_type: null, has_analysis: false, created_at: '2026-06-03' },
    ]
    const wrapper = mountPicker(true)
    const list = wrapper.findComponent(DocumentListStub)
    expect(list.exists()).toBe(true)
    expect(list.props('documents')).toHaveLength(2)
    // En mode sélecteur, les actions destructrices sont masquées (selectableOnly).
    expect(list.props('selectableOnly')).toBeTruthy()
  })

  it('sélection → émet l\'id du document et ferme', async () => {
    storeState.documents = [
      { id: 'd1', original_filename: 'a.pdf', mime_type: 'application/pdf', file_size: 1, status: 'uploaded', document_type: null, has_analysis: false, created_at: '2026-06-03' },
    ]
    const wrapper = mountPicker(true)
    wrapper.findComponent(DocumentListStub).vm.$emit('select', { id: 'd1' })

    expect(wrapper.emitted('select')?.[0]).toEqual(['d1'])
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('état vide → message + invite au téléversement', () => {
    storeState.documents = []
    const wrapper = mountPicker(true)
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Aucun document disponible')
    expect(wrapper.text()).toContain('Téléversez')
    expect(wrapper.findComponent(DocumentListStub).exists()).toBe(false)
  })
})
