// F20 — Store Pinia pour la bibliothèque Resources.
import { defineStore } from 'pinia'
import type {
  Resource,
  ResourceFiltersQuery,
  ResourceListItem,
} from '~/types/resource'

interface ResourcesState {
  items: ResourceListItem[]
  total: number
  currentResource: Resource | null
  intermediaryGuide: Resource | null
  filters: ResourceFiltersQuery
  loading: boolean
  error: string | null
}

export const useResourcesStore = defineStore('resources', {
  state: (): ResourcesState => ({
    items: [],
    total: 0,
    currentResource: null,
    intermediaryGuide: null,
    filters: {},
    loading: false,
    error: null,
  }),
  getters: {
    byType:
      (state) =>
      (type: string): ResourceListItem[] =>
        state.items.filter((r) => r.type === type),
  },
  actions: {
    setItems(items: ResourceListItem[], total: number): void {
      this.items = items
      this.total = total
    },
    setCurrentResource(resource: Resource | null): void {
      this.currentResource = resource
    },
    setIntermediaryGuide(resource: Resource | null): void {
      this.intermediaryGuide = resource
    },
    setFilters(filters: ResourceFiltersQuery): void {
      this.filters = { ...filters }
    },
    reset(): void {
      this.items = []
      this.total = 0
      this.currentResource = null
      this.intermediaryGuide = null
      this.filters = {}
      this.loading = false
      this.error = null
    },
  },
})
