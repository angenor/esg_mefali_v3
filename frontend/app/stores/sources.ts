import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Source } from '~/types/source'

const TTL_MS = 5 * 60 * 1000 // 5 minutes

interface CacheEntry {
  source: Source
  fetchedAt: number
}

export const useSourcesStore = defineStore('sources', () => {
  const cache = ref<Record<string, CacheEntry>>({})
  const loading = ref(false)
  const error = ref('')

  function getById(id: string): Source | null {
    const entry = cache.value[id]
    if (!entry) return null
    if (Date.now() - entry.fetchedAt > TTL_MS) {
      // expired
      delete cache.value[id]
      return null
    }
    return entry.source
  }

  function setSource(source: Source): void {
    cache.value = {
      ...cache.value,
      [source.id]: { source, fetchedAt: Date.now() },
    }
  }

  function invalidate(id: string): void {
    const next = { ...cache.value }
    delete next[id]
    cache.value = next
  }

  function setLoading(val: boolean): void {
    loading.value = val
  }

  function setError(msg: string): void {
    error.value = msg
  }

  function reset(): void {
    cache.value = {}
    loading.value = false
    error.value = ''
  }

  return {
    cache,
    loading,
    error,
    getById,
    setSource,
    invalidate,
    setLoading,
    setError,
    reset,
  }
})
