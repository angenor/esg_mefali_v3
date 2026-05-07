// F23 — Composable wrapper API CRUD admin Skills.

import type {
  SkillCreate,
  SkillEvalReport,
  SkillListFilters,
  SkillListResponse,
  SkillPublishResponse,
  SkillRead,
  SkillUpdate,
} from '~/types/skills'
import { useAuthStore } from '~/stores/auth'

function buildQueryString(filters: Partial<SkillListFilters>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    params.append(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function useAdminSkills() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase as string

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  async function listSkills(
    filters: Partial<SkillListFilters> = {},
  ): Promise<SkillListResponse> {
    const url = `${apiBase}/admin/skills${buildQueryString(filters)}`
    const response = await fetch(url, { headers: getHeaders() })
    if (!response.ok) {
      throw new Error(`listSkills failed: ${response.status}`)
    }
    return (await response.json()) as SkillListResponse
  }

  async function getSkill(id: string): Promise<SkillRead> {
    const response = await fetch(`${apiBase}/admin/skills/${id}`, {
      headers: getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`getSkill failed: ${response.status}`)
    }
    return (await response.json()) as SkillRead
  }

  async function createSkill(payload: SkillCreate): Promise<SkillRead> {
    const response = await fetch(`${apiBase}/admin/skills`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      const error: any = new Error(`createSkill failed: ${response.status}`)
      error.status = response.status
      error.detail = detail
      throw error
    }
    return (await response.json()) as SkillRead
  }

  async function updateSkill(
    id: string,
    payload: SkillUpdate,
  ): Promise<SkillRead> {
    const response = await fetch(`${apiBase}/admin/skills/${id}`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      const error: any = new Error(`updateSkill failed: ${response.status}`)
      error.status = response.status
      error.detail = detail
      throw error
    }
    return (await response.json()) as SkillRead
  }

  async function publishSkill(id: string): Promise<SkillPublishResponse> {
    const response = await fetch(`${apiBase}/admin/skills/${id}/publish`, {
      method: 'POST',
      headers: getHeaders(),
      body: '{}',
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}))
      const error: any = new Error(`publishSkill failed: ${response.status}`)
      error.status = response.status
      error.detail = detail
      throw error
    }
    return (await response.json()) as SkillPublishResponse
  }

  async function unpublishSkill(id: string): Promise<SkillRead> {
    const response = await fetch(`${apiBase}/admin/skills/${id}/unpublish`, {
      method: 'POST',
      headers: getHeaders(),
      body: '{}',
    })
    if (!response.ok) {
      throw new Error(`unpublishSkill failed: ${response.status}`)
    }
    return (await response.json()) as SkillRead
  }

  async function testSkill(id: string): Promise<SkillEvalReport> {
    const response = await fetch(`${apiBase}/admin/skills/${id}/test`, {
      method: 'POST',
      headers: getHeaders(),
      body: '{}',
    })
    if (!response.ok) {
      throw new Error(`testSkill failed: ${response.status}`)
    }
    return (await response.json()) as SkillEvalReport
  }

  async function deleteSkill(id: string): Promise<void> {
    const response = await fetch(`${apiBase}/admin/skills/${id}`, {
      method: 'DELETE',
      headers: getHeaders(),
    })
    if (!response.ok) {
      throw new Error(`deleteSkill failed: ${response.status}`)
    }
  }

  return {
    listSkills,
    getSkill,
    createSkill,
    updateSkill,
    publishSkill,
    unpublishSkill,
    testSkill,
    deleteSkill,
  }
}
