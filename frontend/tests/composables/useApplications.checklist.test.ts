import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.stubGlobal('useAuthStore', () => ({ accessToken: 'test-token' }))

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://localhost:8000/api' },
}))

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

function seedCurrentApplication(store: ReturnType<typeof import('~/stores/applications').useApplicationsStore>) {
  store.setCurrentApplication({
    id: 'app-1',
    fund: { id: 'f1', name: 'GCF', organization: 'GCF' },
    intermediary: null,
    match: null,
    target_type: 'fund_direct',
    status: 'draft',
    status_label: 'Brouillon',
    sections: {},
    checklist: [
      { key: 'company_registration', name: 'RCCM', status: 'missing', document_id: null, required_by: 'fund_direct', document: null },
      { key: 'esg_report', name: 'Rapport ESG', status: 'missing', document_id: null, required_by: 'fund_direct', document: null },
    ],
    checklist_progress: { provided: 0, total: 2 },
    intermediary_prep: null,
    simulation: null,
    created_at: '2026-06-03',
    updated_at: '2026-06-03',
    submitted_at: null,
  } as unknown as Parameters<typeof store.setCurrentApplication>[0])
}

describe('useApplications — checklist (049)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock.mockReset()
  })

  it('attachDocument fait un PUT sur le bon endpoint et met à jour le store', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          item: {
            key: 'company_registration',
            name: 'RCCM',
            status: 'provided',
            document_id: 'doc-1',
            required_by: 'fund_direct',
            document: { id: 'doc-1', original_filename: 'rccm.pdf', mime_type: 'application/pdf', status: 'uploaded' },
          },
          checklist_progress: { provided: 1, total: 2 },
        },
      }),
    })

    const { useApplications } = await import('~/composables/useApplications')
    const { useApplicationsStore } = await import('~/stores/applications')
    const store = useApplicationsStore()
    seedCurrentApplication(store)

    const api = useApplications()
    const ok = await api.attachDocument('app-1', 'company_registration', 'doc-1')

    expect(ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/applications/app-1/checklist/company_registration/document',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ document_id: 'doc-1' }),
      }),
    )
    const item = store.currentApplication!.checklist.find(it => it.key === 'company_registration')!
    expect(item.status).toBe('provided')
    expect(item.document?.original_filename).toBe('rccm.pdf')
    expect(store.currentApplication!.checklist_progress).toEqual({ provided: 1, total: 2 })
  })

  it('attachDocument 403 → renvoie false et message FR', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Ce document n'appartient pas à votre organisation." }),
    })

    const { useApplications } = await import('~/composables/useApplications')
    const { useApplicationsStore } = await import('~/stores/applications')
    seedCurrentApplication(useApplicationsStore())

    const api = useApplications()
    const ok = await api.attachDocument('app-1', 'company_registration', 'doc-x')

    expect(ok).toBe(false)
    expect(api.error.value).toContain("n'appartient pas")
  })

  it('detachDocument fait un DELETE et met à jour le store', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          item: { key: 'company_registration', name: 'RCCM', status: 'missing', document_id: null, required_by: 'fund_direct', document: null },
          checklist_progress: { provided: 0, total: 2 },
        },
      }),
    })

    const { useApplications } = await import('~/composables/useApplications')
    const { useApplicationsStore } = await import('~/stores/applications')
    const store = useApplicationsStore()
    seedCurrentApplication(store)
    // simuler un item déjà fourni
    store.setChecklistItem('company_registration', {
      key: 'company_registration', name: 'RCCM', status: 'provided', document_id: 'doc-1', required_by: 'fund_direct',
      document: { id: 'doc-1', original_filename: 'rccm.pdf', mime_type: 'application/pdf', status: 'uploaded' },
    })

    const api = useApplications()
    const ok = await api.detachDocument('app-1', 'company_registration')

    expect(ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/applications/app-1/checklist/company_registration/document',
      expect.objectContaining({ method: 'DELETE' }),
    )
    const item = store.currentApplication!.checklist.find(it => it.key === 'company_registration')!
    expect(item.status).toBe('missing')
    expect(item.document).toBeNull()
    expect(store.currentApplication!.checklist_progress).toEqual({ provided: 0, total: 2 })
  })
})

describe('store applications — mutators checklist (049, progression)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('setChecklistProgress met à jour la progression du dossier courant', async () => {
    const { useApplicationsStore } = await import('~/stores/applications')
    const store = useApplicationsStore()
    seedCurrentApplication(store)

    store.setChecklistProgress({ provided: 2, total: 2 })
    expect(store.currentApplication!.checklist_progress).toEqual({ provided: 2, total: 2 })
  })

  it('setChecklistItem remplace un item par sa clé sans toucher aux autres', async () => {
    const { useApplicationsStore } = await import('~/stores/applications')
    const store = useApplicationsStore()
    seedCurrentApplication(store)

    store.setChecklistItem('esg_report', {
      key: 'esg_report', name: 'Rapport ESG', status: 'provided', document_id: 'doc-9', required_by: 'fund_direct',
      document: { id: 'doc-9', original_filename: 'esg.pdf', mime_type: 'application/pdf', status: 'uploaded' },
    })

    const esg = store.currentApplication!.checklist.find(it => it.key === 'esg_report')!
    const rccm = store.currentApplication!.checklist.find(it => it.key === 'company_registration')!
    expect(esg.status).toBe('provided')
    expect(rccm.status).toBe('missing') // inchangé
  })
})
