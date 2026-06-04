import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ChecklistItemRow from '~/components/applications/ChecklistItemRow.vue'

const { attachMock, detachMock, uploadMock } = vi.hoisted(() => ({
  attachMock: vi.fn(),
  detachMock: vi.fn(),
  uploadMock: vi.fn(),
}))

vi.mock('~/composables/useApplications', () => ({
  useApplications: () => ({ attachDocument: attachMock, detachDocument: detachMock }),
}))
vi.mock('~/composables/useDocuments', () => ({
  useDocuments: () => ({
    uploadDocuments: uploadMock,
    store: { documents: [], isLoading: false },
    fetchDocuments: vi.fn(),
  }),
}))

// Stubs des enfants lourds (évitent fetch / Teleport / composables internes).
const FullscreenModalStub = {
  name: 'FullscreenModal',
  props: ['visible'],
  template: '<div v-if="visible" class="modal-stub"><slot /></div>',
}
const DocumentPickerStub = {
  name: 'DocumentPicker',
  props: ['visible'],
  emits: ['select', 'close'],
  template: '<div class="picker-stub" />',
}
const DocumentPreviewStub = {
  name: 'DocumentPreview',
  props: ['documentId', 'mimeType', 'filename'],
  emits: ['close'],
  template: '<div class="preview-stub" />',
}
const DocumentUploadStub = {
  name: 'DocumentUpload',
  props: ['isUploading'],
  emits: ['upload'],
  template: '<div class="upload-stub" />',
}

const stubs = {
  FullscreenModal: FullscreenModalStub,
  DocumentPicker: DocumentPickerStub,
  DocumentPreview: DocumentPreviewStub,
  DocumentUpload: DocumentUploadStub,
}

const MISSING_ITEM = {
  key: 'company_registration',
  name: 'Registre de commerce (RCCM)',
  status: 'missing',
  document_id: null,
  required_by: 'fund_direct',
  document: null,
}
const PROVIDED_ITEM = {
  key: 'company_registration',
  name: 'Registre de commerce (RCCM)',
  status: 'provided',
  document_id: 'doc-1',
  required_by: 'fund_direct',
  document: { id: 'doc-1', original_filename: 'rccm.pdf', mime_type: 'application/pdf', status: 'uploaded' },
}

function btn(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find(b => b.text() === label)
}

function mountRow(item: Record<string, unknown>) {
  return mount(ChecklistItemRow, {
    props: { applicationId: 'app-1', item },
    global: { stubs },
  })
}

describe('ChecklistItemRow (049)', () => {
  beforeEach(() => {
    attachMock.mockReset()
    detachMock.mockReset()
    uploadMock.mockReset()
  })

  it('US1 — téléversement valide → upload puis attach, émet changed', async () => {
    uploadMock.mockResolvedValue([
      { id: 'doc-9', original_filename: 'rccm.pdf', mime_type: 'application/pdf', status: 'uploaded' },
    ])
    attachMock.mockResolvedValue(true)

    const wrapper = mountRow({ ...MISSING_ITEM })
    await btn(wrapper, 'Téléverser')!.trigger('click')

    const file = new File(['x'], 'rccm.pdf', { type: 'application/pdf' })
    wrapper.findComponent(DocumentUploadStub).vm.$emit('upload', [file])
    await flushPromises()

    expect(uploadMock).toHaveBeenCalledWith([file])
    expect(attachMock).toHaveBeenCalledWith('app-1', 'company_registration', 'doc-9')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('US1 — échec du téléversement → message d\'erreur, pas de rattachement', async () => {
    uploadMock.mockResolvedValue([]) // upload échoué / fichier invalide
    const wrapper = mountRow({ ...MISSING_ITEM })
    await btn(wrapper, 'Téléverser')!.trigger('click')

    wrapper.findComponent(DocumentUploadStub).vm.$emit('upload', [new File(['x'], 'bad.txt')])
    await flushPromises()

    expect(attachMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('téléversement a échoué')
  })

  it('US2 — choisir un existant → attach avec l\'id sélectionné', async () => {
    attachMock.mockResolvedValue(true)
    const wrapper = mountRow({ ...MISSING_ITEM })
    await btn(wrapper, 'Choisir un existant')!.trigger('click')

    wrapper.findComponent(DocumentPickerStub).vm.$emit('select', 'doc-7')
    await flushPromises()

    expect(attachMock).toHaveBeenCalledWith('app-1', 'company_registration', 'doc-7')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('US1/US4 — item fourni affiche le nom du fichier + actions', () => {
    const wrapper = mountRow({ ...PROVIDED_ITEM })
    expect(wrapper.text()).toContain('rccm.pdf')
    expect(wrapper.text()).toContain('Fourni')
    expect(btn(wrapper, 'Aperçu')).toBeTruthy()
    expect(btn(wrapper, 'Détacher')).toBeTruthy()
    expect(btn(wrapper, 'Remplacer')).toBeTruthy()
  })

  it('US3 — Aperçu ouvre DocumentPreview avec les props de item.document', async () => {
    const wrapper = mountRow({ ...PROVIDED_ITEM })
    await btn(wrapper, 'Aperçu')!.trigger('click')

    const preview = wrapper.findComponent(DocumentPreviewStub)
    expect(preview.exists()).toBe(true)
    expect(preview.props('documentId')).toBe('doc-1')
    expect(preview.props('mimeType')).toBe('application/pdf')
    expect(preview.props('filename')).toBe('rccm.pdf')
  })

  it('US4 — Détacher appelle detachDocument et émet changed', async () => {
    detachMock.mockResolvedValue(true)
    const wrapper = mountRow({ ...PROVIDED_ITEM })
    await btn(wrapper, 'Détacher')!.trigger('click')
    await flushPromises()

    expect(detachMock).toHaveBeenCalledWith('app-1', 'company_registration')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('US4 — Remplacer révèle les contrôles de remplacement', async () => {
    const wrapper = mountRow({ ...PROVIDED_ITEM })
    await btn(wrapper, 'Remplacer')!.trigger('click')
    expect(btn(wrapper, 'Téléverser un nouveau')).toBeTruthy()
    expect(btn(wrapper, 'Choisir un existant')).toBeTruthy()
  })

  it('US4 — Détacher réinitialise les contrôles de remplacement (pas d\'état UI résiduel)', async () => {
    detachMock.mockResolvedValue(true)
    const wrapper = mountRow({ ...PROVIDED_ITEM })
    await btn(wrapper, 'Remplacer')!.trigger('click')
    expect(btn(wrapper, 'Téléverser un nouveau')).toBeTruthy()
    await btn(wrapper, 'Détacher')!.trigger('click')
    await flushPromises()
    // resetControls() a refermé les contrôles de remplacement.
    expect(btn(wrapper, 'Téléverser un nouveau')).toBeFalsy()
  })

  it('dark mode : classes présentes', () => {
    const wrapper = mountRow({ ...PROVIDED_ITEM })
    expect(wrapper.html()).toContain('dark:')
  })
})
