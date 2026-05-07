import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectsStore } from '~/stores/projects'
import type { ProjectSummary } from '~/types/project'

function makeProject(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    id: 'p-' + Math.random().toString(36).slice(2, 8),
    name: 'Test',
    status: 'draft',
    maturity: null,
    objective_env: [],
    target_amount: null,
    expected_impact_tco2e: null,
    auto_generated: false,
    applications_count: 0,
    created_at: '2026-05-07T00:00:00Z',
    ...overrides,
  }
}

describe('useProjectsStore (F06)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('state initial', () => {
    const store = useProjectsStore()
    expect(store.projects).toEqual([])
    expect(store.total).toBe(0)
    expect(store.currentProject).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('setProjects met à jour la liste et total', () => {
    const store = useProjectsStore()
    const p1 = makeProject()
    const p2 = makeProject()
    store.setProjects([p1, p2], 2)
    expect(store.projects.length).toBe(2)
    expect(store.total).toBe(2)
  })

  it('activeProjects exclut cancelled et closed', () => {
    const store = useProjectsStore()
    const p1 = makeProject({ status: 'draft' })
    const p2 = makeProject({ status: 'cancelled' })
    const p3 = makeProject({ status: 'closed' })
    const p4 = makeProject({ status: 'seeking_funding' })
    store.setProjects([p1, p2, p3, p4], 4)
    expect(store.activeProjects.length).toBe(2)
    expect(store.activeCount).toBe(2)
  })

  it('archivedProjects retourne uniquement cancelled/closed', () => {
    const store = useProjectsStore()
    const p1 = makeProject({ status: 'cancelled' })
    const p2 = makeProject({ status: 'closed' })
    const p3 = makeProject({ status: 'draft' })
    store.setProjects([p1, p2, p3], 3)
    expect(store.archivedProjects.length).toBe(2)
  })

  it('byStatus filtre correctement', () => {
    const store = useProjectsStore()
    const p1 = makeProject({ status: 'funded' })
    const p2 = makeProject({ status: 'funded' })
    const p3 = makeProject({ status: 'draft' })
    store.setProjects([p1, p2, p3], 3)
    expect(store.byStatus('funded').length).toBe(2)
    expect(store.byStatus('draft').length).toBe(1)
  })

  it('addProject prepend', () => {
    const store = useProjectsStore()
    const p1 = makeProject({ name: 'A' })
    store.setProjects([p1], 1)
    const p2 = makeProject({ name: 'B' })
    store.addProject(p2)
    expect(store.projects[0].name).toBe('B')
    expect(store.total).toBe(2)
  })

  it('updateProjectInList met à jour par id', () => {
    const store = useProjectsStore()
    const p1 = makeProject({ name: 'Old', id: 'p1' })
    store.setProjects([p1], 1)
    store.updateProjectInList({ ...p1, name: 'New' })
    expect(store.projects[0].name).toBe('New')
  })

  it('removeFromList supprime par id', () => {
    const store = useProjectsStore()
    const p1 = makeProject({ id: 'p1' })
    const p2 = makeProject({ id: 'p2' })
    store.setProjects([p1, p2], 2)
    store.removeFromList('p1')
    expect(store.projects.length).toBe(1)
    expect(store.projects[0].id).toBe('p2')
    expect(store.total).toBe(1)
  })

  it('reset remet l\'état initial', () => {
    const store = useProjectsStore()
    store.setProjects([makeProject()], 1)
    store.setError('test')
    store.reset()
    expect(store.projects).toEqual([])
    expect(store.total).toBe(0)
    expect(store.error).toBeNull()
  })
})
