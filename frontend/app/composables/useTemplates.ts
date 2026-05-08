/**
 * F15 — Composable lecture des Templates Dossier.
 *
 * Lecture publique des templates publiés (catalogue admin-only en
 * mutation). Utilisé par la page de candidature pour afficher le
 * template effectif et ses sections.
 */

import { ref } from 'vue'
import type { TemplateRead, TemplateListResponse } from '~/types/template'

export function useTemplates() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const loading = ref(false)
  const error = ref<string | null>(null)
  const templates = ref<TemplateRead[]>([])
  const total = ref(0)

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  async function listTemplates(filters?: {
    instrument_type?: string
    language?: string
    status?: string
    limit?: number
  }): Promise<TemplateListResponse> {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (filters?.instrument_type) params.set('instrument_type', filters.instrument_type)
      if (filters?.language) params.set('language', filters.language)
      if (filters?.status) params.set('status', filters.status)
      if (filters?.limit) params.set('limit', String(filters.limit))

      const url = `${apiBase}/templates${params.toString() ? `?${params.toString()}` : ''}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        throw new Error(`Erreur lors du chargement des templates (${response.status})`)
      }
      const data: TemplateListResponse = await response.json()
      templates.value = data.items
      total.value = data.total
      return data
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getTemplate(id: string): Promise<TemplateRead> {
    loading.value = true
    error.value = null
    try {
      const url = `${apiBase}/templates/${id}`
      const response = await fetch(url, { headers: getHeaders() })
      if (!response.ok) {
        throw new Error(`Template introuvable (${response.status})`)
      }
      return (await response.json()) as TemplateRead
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    templates,
    total,
    listTemplates,
    getTemplate,
  }
}
