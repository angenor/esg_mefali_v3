/**
 * F05 — Pinia store des 7 consentements granulaires.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useAuth } from '~/composables/useAuth'
import type { ConsentItem, ConsentType } from '~/composables/useDataPrivacy'

export const useConsentsStore = defineStore('consents', () => {
  const items = ref<ConsentItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const byType = computed<Record<ConsentType, ConsentItem | undefined>>(() => {
    const map: Partial<Record<ConsentType, ConsentItem>> = {}
    for (const item of items.value) {
      map[item.type] = item
    }
    return map as Record<ConsentType, ConsentItem | undefined>
  })

  function getStatus(type: ConsentType): boolean {
    return byType.value[type]?.granted === true
  }

  async function fetchAll(): Promise<void> {
    const { apiFetch } = useAuth()
    loading.value = true
    error.value = null
    try {
      items.value = await apiFetch<ConsentItem[]>('/api/me/consents')
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    } finally {
      loading.value = false
    }
  }

  async function grant(type: ConsentType): Promise<boolean> {
    const { apiFetch } = useAuth()
    const previous = byType.value[type]
    // Optimistic UI
    const idx = items.value.findIndex((i) => i.type === type)
    if (idx !== -1) {
      const updated: ConsentItem = {
        ...items.value[idx],
        granted: true,
        granted_at: new Date().toISOString(),
        revoked_at: null,
      }
      items.value = [
        ...items.value.slice(0, idx),
        updated,
        ...items.value.slice(idx + 1),
      ]
    }
    try {
      await apiFetch(`/api/me/consents/${type}/grant`, { method: 'POST' })
      return true
    } catch (e: unknown) {
      // Rollback
      if (previous && idx !== -1) {
        items.value = [
          ...items.value.slice(0, idx),
          previous,
          ...items.value.slice(idx + 1),
        ]
      }
      error.value = e instanceof Error ? e.message : 'Erreur'
      return false
    }
  }

  async function revoke(type: ConsentType): Promise<boolean> {
    const { apiFetch } = useAuth()
    const previous = byType.value[type]
    const idx = items.value.findIndex((i) => i.type === type)
    if (idx !== -1) {
      const updated: ConsentItem = {
        ...items.value[idx],
        granted: false,
        revoked_at: new Date().toISOString(),
      }
      items.value = [
        ...items.value.slice(0, idx),
        updated,
        ...items.value.slice(idx + 1),
      ]
    }
    try {
      await apiFetch(`/api/me/consents/${type}/revoke`, { method: 'POST' })
      return true
    } catch (e: unknown) {
      if (previous && idx !== -1) {
        items.value = [
          ...items.value.slice(0, idx),
          previous,
          ...items.value.slice(idx + 1),
        ]
      }
      error.value = e instanceof Error ? e.message : 'Erreur'
      return false
    }
  }

  return {
    items,
    loading,
    error,
    byType,
    getStatus,
    fetchAll,
    grant,
    revoke,
  }
})
