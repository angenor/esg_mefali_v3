import { defineStore } from 'pinia'
import type {
  ProjectDetail,
  ProjectFilters,
  ProjectStatus,
  ProjectSummary,
} from '~/types/project'

interface ProjectsState {
  projects: ProjectSummary[]
  total: number
  currentProject: ProjectDetail | null
  filters: ProjectFilters
  loading: boolean
  error: string | null
}

const ARCHIVED_STATUSES: ProjectStatus[] = ['cancelled', 'closed']

export const useProjectsStore = defineStore('projects', {
  state: (): ProjectsState => ({
    projects: [],
    total: 0,
    currentProject: null,
    filters: { page: 1, limit: 25 },
    loading: false,
    error: null,
  }),

  getters: {
    activeProjects(state): ProjectSummary[] {
      return state.projects.filter(
        (p) => !ARCHIVED_STATUSES.includes(p.status),
      )
    },
    archivedProjects(state): ProjectSummary[] {
      return state.projects.filter((p) =>
        ARCHIVED_STATUSES.includes(p.status),
      )
    },
    activeCount(state): number {
      return state.projects.filter(
        (p) => !ARCHIVED_STATUSES.includes(p.status),
      ).length
    },
    byStatus(state) {
      return (status: ProjectStatus): ProjectSummary[] =>
        state.projects.filter((p) => p.status === status)
    },
  },

  actions: {
    setProjects(projects: ProjectSummary[], total: number) {
      this.projects = projects
      this.total = total
    },
    setCurrentProject(project: ProjectDetail | null) {
      this.currentProject = project
    },
    setFilters(filters: ProjectFilters) {
      this.filters = { ...this.filters, ...filters }
    },
    setLoading(loading: boolean) {
      this.loading = loading
    },
    setError(error: string | null) {
      this.error = error
    },
    addProject(project: ProjectSummary) {
      this.projects = [project, ...this.projects]
      this.total += 1
    },
    updateProjectInList(updated: ProjectSummary) {
      this.projects = this.projects.map((p) =>
        p.id === updated.id ? updated : p,
      )
      if (this.currentProject?.id === updated.id) {
        this.currentProject = {
          ...this.currentProject,
          ...updated,
        } as ProjectDetail
      }
    },
    removeFromList(id: string) {
      this.projects = this.projects.filter((p) => p.id !== id)
      this.total = Math.max(0, this.total - 1)
    },
    reset() {
      this.projects = []
      this.total = 0
      this.currentProject = null
      this.filters = { page: 1, limit: 25 }
      this.loading = false
      this.error = null
    },
  },
})
