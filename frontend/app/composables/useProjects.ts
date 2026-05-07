import { ref } from 'vue'
import { useAuthStore } from '~/stores/auth'
import type {
  DeleteResult,
  DocType,
  DuplicateProjectRequest,
  ProjectApplicationSummary,
  ProjectCreatePayload,
  ProjectDetail,
  ProjectDocumentRead,
  ProjectFilters,
  ProjectListResponse,
  ProjectUpdatePayload,
} from '~/types/project'

/**
 * Composable F06 — accès au module Projets verts via l'API REST.
 *
 * Expose 8 méthodes async wrappées dans un état (`loading`, `error`).
 */
export function useProjects() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref('')

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  async function listProjects(
    filters: ProjectFilters = {},
  ): Promise<ProjectListResponse | null> {
    loading.value = true
    error.value = ''
    try {
      const params = new URLSearchParams()
      if (filters.status !== undefined) params.set('status', filters.status)
      if (filters.maturity !== undefined) params.set('maturity', filters.maturity)
      if (filters.objective_env !== undefined)
        params.set('objective_env', filters.objective_env)
      if (filters.auto_generated !== undefined)
        params.set('auto_generated', String(filters.auto_generated))
      if (filters.page !== undefined) params.set('page', String(filters.page))
      if (filters.limit !== undefined) params.set('limit', String(filters.limit))

      const url = `${apiBase}/projects${
        params.toString() ? `?${params.toString()}` : ''
      }`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        throw new Error('Erreur lors du chargement des projets')
      }
      const data: ProjectListResponse = await response.json()
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function getProject(id: string): Promise<ProjectDetail | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/projects/${id}`, {
        headers: getHeaders(),
      })
      if (!response.ok) {
        if (response.status === 404) {
          error.value = 'Projet introuvable'
          return null
        }
        throw new Error('Erreur lors du chargement du projet')
      }
      return (await response.json()) as ProjectDetail
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function createProject(
    payload: ProjectCreatePayload,
  ): Promise<ProjectDetail | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/projects`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        if (response.status === 422) {
          const body = await response.json().catch(() => ({}))
          error.value =
            (body && typeof body === 'object' && 'detail' in body
              ? JSON.stringify(body.detail)
              : 'Données invalides') || 'Données invalides'
          return null
        }
        throw new Error('Erreur lors de la création du projet')
      }
      return (await response.json()) as ProjectDetail
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateProject(
    id: string,
    fields: ProjectUpdatePayload,
  ): Promise<ProjectDetail | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/projects/${id}`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify(fields),
      })
      if (!response.ok) {
        if (response.status === 404) {
          error.value = 'Projet introuvable'
          return null
        }
        if (response.status === 422) {
          error.value = 'Données invalides'
          return null
        }
        throw new Error('Erreur lors de la mise à jour')
      }
      return (await response.json()) as ProjectDetail
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteProject(
    id: string,
    force = false,
  ): Promise<DeleteResult | null> {
    loading.value = true
    error.value = ''
    try {
      const url = `${apiBase}/projects/${id}${force ? '?force=true' : ''}`
      const response = await fetch(url, {
        method: 'DELETE',
        headers: getHeaders(),
      })
      if (response.status === 409) {
        const body = await response.json()
        // Body : { detail: { ok, blocked_by, hint } }
        const detail = body?.detail || body
        return {
          ok: false,
          blocked_by: detail?.blocked_by || [],
          hint: detail?.hint || null,
        }
      }
      if (!response.ok) {
        if (response.status === 404) {
          error.value = 'Projet introuvable'
          return null
        }
        throw new Error('Erreur lors de la suppression')
      }
      return (await response.json()) as DeleteResult
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function duplicateProject(
    id: string,
    newName?: string,
  ): Promise<ProjectDetail | null> {
    loading.value = true
    error.value = ''
    try {
      const payload: DuplicateProjectRequest = newName
        ? { new_name: newName }
        : {}
      const response = await fetch(`${apiBase}/projects/${id}/duplicate`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        if (response.status === 404) {
          error.value = 'Projet source introuvable'
          return null
        }
        throw new Error('Erreur lors de la duplication')
      }
      return (await response.json()) as ProjectDetail
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function linkDocument(
    projectId: string,
    documentId: string,
    docType: DocType,
  ): Promise<ProjectDocumentRead | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(
        `${apiBase}/projects/${projectId}/documents`,
        {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({ document_id: documentId, doc_type: docType }),
        },
      )
      if (!response.ok) {
        if (response.status === 409) {
          error.value = 'Document déjà associé à ce projet'
          return null
        }
        throw new Error('Erreur lors de l\'association du document')
      }
      return (await response.json()) as ProjectDocumentRead
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  async function getProjectApplications(
    id: string,
  ): Promise<ProjectApplicationSummary[] | null> {
    loading.value = true
    error.value = ''
    try {
      const response = await fetch(`${apiBase}/projects/${id}/applications`, {
        headers: getHeaders(),
      })
      if (!response.ok) {
        if (response.status === 404) {
          error.value = 'Projet introuvable'
          return null
        }
        throw new Error('Erreur lors du chargement des candidatures')
      }
      return (await response.json()) as ProjectApplicationSummary[]
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    listProjects,
    getProject,
    createProject,
    updateProject,
    deleteProject,
    duplicateProject,
    linkDocument,
    getProjectApplications,
  }
}
