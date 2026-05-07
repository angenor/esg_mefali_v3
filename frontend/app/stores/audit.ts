// F03 — Pinia store pour l'historique d'audit côté frontend.

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AuditEvent, AuditFilters } from '~/types/audit'

export const useAuditStore = defineStore('audit', () => {
  const events = ref<AuditEvent[]>([])
  const total = ref(0)
  const filters = ref<AuditFilters>({
    page: 1,
    limit: 50,
    order: 'desc',
  })
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  function setEvents(list: AuditEvent[], totalCount: number) {
    events.value = list
    total.value = totalCount
  }

  function setFilters(next: Partial<AuditFilters>) {
    filters.value = { ...filters.value, ...next }
  }

  function reset() {
    events.value = []
    total.value = 0
    filters.value = { page: 1, limit: 50, order: 'desc' }
    error.value = null
    isLoading.value = false
  }

  return {
    events,
    total,
    filters,
    isLoading,
    error,
    setEvents,
    setFilters,
    reset,
  }
})
