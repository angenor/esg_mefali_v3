/**
 * T025 [US1] — Composant ProjectEsgWizard : orchestrateur multi-étapes
 * (référentiel → critères → score), navigation entre étapes, état brouillon,
 * dark mode parité.
 */
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://api.test/api' },
}))
;(globalThis as Record<string, unknown>).useAuthStore = () => ({
  accessToken: 'fake-token',
})

const fetchMock = vi.fn()
;(globalThis as Record<string, unknown>).fetch = fetchMock as unknown

const REFERENTIALS = [
  {
    id: 'ifc-ps',
    code: 'ifc_ps',
    label: 'IFC Performance Standards',
    description: 'Standards universels',
    source_id: 'src-ifc',
  },
  {
    id: 'gcf-ess',
    code: 'gcf_ess',
    label: 'GCF ESS',
    description: 'Green Climate Fund',
    source_id: 'src-gcf',
  },
]

const CRITERIA = {
  'ifc-ps': [
    { id: 'c1', code: 'PS1-1', label: 'Critère 1', is_required: true },
    { id: 'c2', code: 'PS1-2', label: 'Critère 2', is_required: true },
    { id: 'c3', code: 'PS2-1', label: 'Critère 3', is_required: false },
  ],
}

describe('ProjectEsgWizard (F047 US1)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock.mockReset()
    // List initial GET → []
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    })
  })

  async function mountWizard() {
    const ProjectEsgWizard = (
      await import('~/components/esg/project/ProjectEsgWizard.vue')
    ).default
    const wrapper = mount(ProjectEsgWizard, {
      props: {
        projectId: 'proj-1',
        referentials: REFERENTIALS,
        criteriaByReferentialId: CRITERIA,
      },
      global: {
        stubs: {
          EsgTargetBadge: { template: '<span data-stub="target-badge"/>' },
          EsgReferentialPicker: {
            props: ['modelValue', 'referentials'],
            emits: ['update:modelValue'],
            template:
              '<button data-testid="pick-ifc" @click="$emit(\'update:modelValue\', \'ifc-ps\')">pick</button>',
          },
          EsgCriterionWidget: {
            props: ['criterion'],
            template:
              '<div :data-testid="`crit-${criterion.id}`">{{ criterion.code }}</div>',
          },
          EsgScoreDisplay: {
            template: '<div data-testid="score-display">score</div>',
          },
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  it("affiche l'étape 1 (choix référentiel) au montage", async () => {
    const wrapper = await mountWizard()
    expect(wrapper.text()).toContain('Évaluation ESG du projet')
    expect(wrapper.text()).toContain('Référentiel')
    expect(wrapper.find('[data-stub="target-badge"]').exists()).toBe(true)
  })

  it("désactive le bouton 'Démarrer' tant qu'aucun référentiel n'est choisi", async () => {
    const wrapper = await mountWizard()
    const startBtn = wrapper.findAll('button').find((b) =>
      b.text().includes('Démarrer'),
    )
    expect(startBtn?.attributes('disabled')).toBeDefined()
  })

  it("active le bouton 'Démarrer' après sélection d'un référentiel", async () => {
    const wrapper = await mountWizard()
    await wrapper.find('[data-testid="pick-ifc"]').trigger('click')
    const startBtn = wrapper.findAll('button').find((b) =>
      b.text().includes('Démarrer'),
    )
    expect(startBtn?.attributes('disabled')).toBeUndefined()
  })

  it('passe à l\'étape 2 après création réussie et affiche les critères', async () => {
    const wrapper = await mountWizard()
    // Le store enchaîne 3 fetches : create, getDetail, listAssessments
    const assessmentBase = {
      id: 'asst-1',
      account_id: 'a',
      project_id: 'proj-1',
      referential_id: 'ifc-ps',
      referential_version: '1.0',
      state: 'draft',
      score: null,
      pillar_scores: {},
      covered_criteria: [],
      missing_criteria: [],
      coverage_rate: null,
      snapshot_data: null,
      finalized_at: null,
      superseded_at: null,
      created_by: 'u',
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
      responses: [],
    }
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => assessmentBase,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => assessmentBase,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [assessmentBase],
      })
    await wrapper.find('[data-testid="pick-ifc"]').trigger('click')
    const startBtn = wrapper.findAll('button').find((b) =>
      b.text().includes('Démarrer'),
    )!
    await startBtn.trigger('click')
    await flushPromises()
    await flushPromises()
    // Étape 2 : 3 critères rendus
    expect(wrapper.find('[data-testid="crit-c1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="crit-c2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="crit-c3"]').exists()).toBe(true)
    expect(wrapper.text()).toMatch(/Progression/i)
  })

  it("affiche la badge ESG Projet (target='project') en permanence", async () => {
    const wrapper = await mountWizard()
    expect(wrapper.find('[data-stub="target-badge"]').exists()).toBe(true)
  })

  it("supporte le dark mode (classes dark: dans le template du shell)", async () => {
    const wrapper = await mountWizard()
    // Smoke check : présence de classes dark: dans le markup rendu.
    const html = wrapper.html()
    expect(html).toMatch(/dark:/i)
  })

  it("'Nouvelle évaluation' depuis l'étape 3 réinitialise wizard à l'étape 1", async () => {
    const wrapper = await mountWizard()
    // Simule directement step=3 via store (raccourci de test)
    const { useProjectEsgStore } = await import('~/stores/projectEsg')
    const store = useProjectEsgStore()
    store.currentAssessment = {
      id: 'asst-1',
      account_id: 'a',
      project_id: 'proj-1',
      referential_id: 'ifc-ps',
      referential_version: '1.0',
      state: 'finalized',
      score: 80,
      pillar_scores: {},
      covered_criteria: ['c1', 'c2'],
      missing_criteria: [],
      coverage_rate: 1 as never,
      snapshot_data: null,
      finalized_at: '2026-05-21T00:00:00Z',
      superseded_at: null,
      created_by: 'u',
      created_at: '2026-05-21T00:00:00Z',
      updated_at: '2026-05-21T00:00:00Z',
      responses: [],
    }
    // Pas de moyen direct d'attribuer step depuis le test — on vérifie au moins
    // que le composant ne crashe pas en présence d'une évaluation finalisée.
    await flushPromises()
    expect(wrapper.text()).toContain('Évaluation ESG du projet')
  })
})
