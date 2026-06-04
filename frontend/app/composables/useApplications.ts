import { ref } from 'vue'
import { useApplicationsStore } from '~/stores/applications'
import type {
  ApplicationDetail,
  ApplicationSummary,
  ChecklistItem,
} from '~/stores/applications'

export function useApplications() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const appStore = useApplicationsStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref('')

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken ? { Authorization: `Bearer ${authStore.accessToken}` } : {}),
    }
  }

  async function fetchApplications(status?: string): Promise<void> {
    loading.value = true
    appStore.setLoading(true)
    appStore.setError(null)
    try {
      const url = status
        ? `${apiBase}/applications/?status=${status}`
        : `${apiBase}/applications/`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) throw new Error('Erreur lors du chargement des dossiers')
      const data = await response.json()
      appStore.setApplications(data.items, data.total)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = msg
      appStore.setError(msg)
    } finally {
      loading.value = false
      appStore.setLoading(false)
    }
  }

  async function fetchApplication(id: string): Promise<ApplicationDetail | null> {
    loading.value = true
    appStore.setLoading(true)
    appStore.setError(null)
    try {
      const response = await fetch(`${apiBase}/applications/${id}`, { headers: getHeaders() })
      if (!response.ok) throw new Error('Dossier non trouvé')
      const data: ApplicationDetail = await response.json()
      appStore.setCurrentApplication(data)
      return data
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = msg
      appStore.setError(msg)
      return null
    } finally {
      loading.value = false
      appStore.setLoading(false)
    }
  }

  /**
   * F048 (D5) — Crée un dossier de candidature via l'endpoint partagé.
   *
   * Accepte ``offerId`` (prioritaire, F07) et/ou ``projectId`` (F06). Le backend
   * dérive fund/intermediary depuis l'offre et dédoublonne le dossier draft
   * (FR-006). Lève une ``Error`` (message FR) en cas d'échec — l'appelant gère
   * l'affichage (FR-015).
   */
  async function createApplication(params: {
    offerId?: string
    projectId?: string
    fundId?: string
    matchId?: string
    intermediaryId?: string
  }): Promise<ApplicationDetail> {
    loading.value = true
    error.value = ''
    try {
      const body: Record<string, string> = {}
      if (params.offerId) body.offer_id = params.offerId
      if (params.projectId) body.project_id = params.projectId
      if (params.fundId) body.fund_id = params.fundId
      if (params.matchId) body.match_id = params.matchId
      if (params.intermediaryId) body.intermediary_id = params.intermediaryId

      const response = await fetch(`${apiBase}/applications/`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        if (response.status === 403) {
          throw new Error(
            errData.detail || "Ce projet n'appartient pas à votre compte.",
          )
        }
        if (response.status === 404) {
          throw new Error(errData.detail || 'Offre ou fonds introuvable.')
        }
        throw new Error(errData.detail || 'Erreur lors de la création du dossier')
      }
      const data: ApplicationDetail = await response.json()
      appStore.setCurrentApplication(data)
      return data
    } catch (e) {
      // Cohérence avec les autres fonctions du composable : on renseigne
      // error.value, puis on relance pour que l'appelant gère l'UI (FR-015).
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function generateSection(applicationId: string, sectionKey: string): Promise<boolean> {
    loading.value = true
    try {
      const response = await fetch(`${apiBase}/applications/${applicationId}/generate-section`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ section_key: sectionKey }),
      })
      if (!response.ok) throw new Error('Erreur lors de la génération')
      const data = await response.json()
      appStore.updateSection(sectionKey, {
        content: data.content,
        status: data.status,
        updated_at: data.updated_at,
      })
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return false
    } finally {
      loading.value = false
    }
  }

  async function updateSection(
    applicationId: string,
    sectionKey: string,
    content?: string,
    status?: string,
  ): Promise<boolean> {
    try {
      const body: Record<string, string> = {}
      if (content !== undefined) body.content = content
      if (status !== undefined) body.status = status

      const response = await fetch(`${apiBase}/applications/${applicationId}/sections/${sectionKey}`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify(body),
      })
      if (!response.ok) throw new Error('Erreur lors de la mise à jour')
      const data = await response.json()
      appStore.updateSection(sectionKey, {
        content: data.content,
        status: data.status,
        updated_at: data.updated_at,
      })
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return false
    }
  }

  async function updateStatus(applicationId: string, status: string): Promise<boolean> {
    try {
      const response = await fetch(`${apiBase}/applications/${applicationId}/status`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify({ status }),
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Transition de statut invalide')
      }
      // Recharger le dossier pour mettre a jour l'etat
      await fetchApplication(applicationId)
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return false
    }
  }

  async function exportApplication(applicationId: string, format: 'pdf' | 'docx'): Promise<void> {
    try {
      const response = await fetch(`${apiBase}/applications/${applicationId}/export`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ format }),
      })
      if (!response.ok) throw new Error("Erreur lors de l'export")

      const blob = await response.blob()
      const ext = format === 'pdf' ? 'pdf' : 'docx'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `dossier.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    }
  }

  async function fetchChecklist(applicationId: string): Promise<unknown[]> {
    try {
      const response = await fetch(`${apiBase}/applications/${applicationId}/checklist`, {
        headers: getHeaders(),
      })
      if (!response.ok) throw new Error('Erreur lors du chargement de la checklist')
      const data = await response.json()
      return data.data || []
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return []
    }
  }

  /**
   * 049 (US1/US2/US4) — Rattache (ou remplace) le document d'un item de
   * checklist. PUT idempotent ; met à jour le store (item enrichi + progression)
   * en cas de succès. Retourne ``true`` si l'opération a abouti.
   */
  async function attachDocument(
    applicationId: string,
    itemKey: string,
    documentId: string,
  ): Promise<boolean> {
    error.value = ''
    try {
      const response = await fetch(
        `${apiBase}/applications/${applicationId}/checklist/${itemKey}/document`,
        {
          method: 'PUT',
          headers: getHeaders(),
          body: JSON.stringify({ document_id: documentId }),
        },
      )
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        if (response.status === 403) {
          throw new Error(
            errData.detail || "Ce document n'appartient pas à votre organisation.",
          )
        }
        throw new Error(errData.detail || 'Erreur lors du rattachement du document')
      }
      const data = await response.json()
      appStore.setChecklistItem(itemKey, data.data.item as ChecklistItem)
      appStore.setChecklistProgress(data.data.checklist_progress)
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return false
    }
  }

  /**
   * 049 (US4) — Détache le document d'un item (→ « Manquant »). Le document
   * n'est pas supprimé (réutilisable ailleurs). Met à jour le store.
   */
  async function detachDocument(
    applicationId: string,
    itemKey: string,
  ): Promise<boolean> {
    error.value = ''
    try {
      const response = await fetch(
        `${apiBase}/applications/${applicationId}/checklist/${itemKey}/document`,
        {
          method: 'DELETE',
          headers: getHeaders(),
        },
      )
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Erreur lors du détachement du document')
      }
      const data = await response.json()
      appStore.setChecklistItem(itemKey, data.data.item as ChecklistItem)
      appStore.setChecklistProgress(data.data.checklist_progress)
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return false
    }
  }

  async function simulateFinancing(applicationId: string): Promise<Record<string, unknown> | null> {
    loading.value = true
    try {
      const response = await fetch(`${apiBase}/applications/${applicationId}/simulate`, {
        method: 'POST',
        headers: getHeaders(),
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Erreur lors de la simulation')
      }
      const data = await response.json()
      if (appStore.currentApplication) {
        appStore.setCurrentApplication({
          ...appStore.currentApplication,
          simulation: data.data,
        })
      }
      return data.data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function generatePrepSheet(applicationId: string): Promise<void> {
    try {
      const response = await fetch(`${apiBase}/applications/${applicationId}/prep-sheet`, {
        method: 'POST',
        headers: getHeaders(),
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Erreur lors de la génération')
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'fiche_preparation.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    }
  }

  return {
    loading,
    error,
    fetchApplications,
    fetchApplication,
    createApplication,
    generateSection,
    updateSection,
    updateStatus,
    exportApplication,
    fetchChecklist,
    attachDocument,
    detachDocument,
    simulateFinancing,
    generatePrepSheet,
  }
}
