import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ObjectiveEnvValue, ProjectStatus } from '~/types/project'

export interface SectionsProgress {
  total: number
  generated: number
  validated: number
}

/**
 * 050 — Projet vert auquel le dossier se rapporte (lien 1:1, F06). ``status``
 * réutilise ``ProjectStatus`` pour résoudre le libellé via ``STATUS_LABELS``
 * (``~/types/project``). ``null`` pour les dossiers legacy sans projet.
 */
export interface ApplicationProjectInfo {
  id: string
  name: string
  status: ProjectStatus
  objective_env: ObjectiveEnvValue[]
  description: string | null
}

export interface ChecklistProgress {
  provided: number
  total: number
}

export interface ApplicationSummary {
  id: string
  fund_name: string
  intermediary_name: string | null
  // 050 — rappel du projet lié sur la carte de dossier (null si legacy).
  project: ApplicationProjectInfo | null
  target_type: string
  status: string
  status_label: string
  sections_progress: SectionsProgress
  checklist_progress: ChecklistProgress
  created_at: string
  updated_at: string
}

export interface FundInfo {
  id: string
  name: string
  organization: string
}

export interface IntermediaryInfo {
  id: string
  name: string
  contact_email: string | null
  contact_phone: string | null
  physical_address: string | null
}

export interface SectionData {
  title: string
  content: string | null
  status: string
  updated_at: string | null
}

export interface DocumentRef {
  id: string
  original_filename: string
  mime_type: string
  status: string
}

export interface ChecklistItem {
  key: string
  name: string
  status: string
  document_id: string | null
  required_by: string
  // 049 — sous-objet enrichi par l'API (null si pas/plus rattaché).
  document?: DocumentRef | null
}

export interface ApplicationDetail {
  id: string
  fund: FundInfo
  intermediary: IntermediaryInfo | null
  match: { id: string; compatibility_score: number } | null
  // 050 — projet vert ciblé par le dossier (null si legacy project_id NULL).
  project: ApplicationProjectInfo | null
  target_type: string
  status: string
  status_label: string
  sections: Record<string, SectionData>
  checklist: ChecklistItem[]
  checklist_progress: ChecklistProgress
  intermediary_prep: Record<string, unknown> | null
  simulation: Record<string, unknown> | null
  created_at: string
  updated_at: string
  submitted_at: string | null
}

export const useApplicationsStore = defineStore('applications', () => {
  const applications = ref<ApplicationSummary[]>([])
  const applicationsTotal = ref(0)
  const currentApplication = ref<ApplicationDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const activeTab = ref<string>('sections')

  const hasApplications = computed(() => applications.value.length > 0)

  function setApplications(data: ApplicationSummary[], total: number) {
    applications.value = data
    applicationsTotal.value = total
  }

  function setCurrentApplication(data: ApplicationDetail | null) {
    currentApplication.value = data
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setError(value: string | null) {
    error.value = value
  }

  function setActiveTab(tab: string) {
    activeTab.value = tab
  }

  function updateSection(sectionKey: string, data: Partial<SectionData>) {
    if (currentApplication.value && currentApplication.value.sections[sectionKey]) {
      currentApplication.value = {
        ...currentApplication.value,
        sections: {
          ...currentApplication.value.sections,
          [sectionKey]: {
            ...currentApplication.value.sections[sectionKey],
            ...data,
          },
        },
      }
    }
  }

  /**
   * 049 — Remplace (par sa ``key``) un item de checklist du dossier courant par
   * sa version enrichie renvoyée par l'API (mise à jour optimiste après
   * rattachement / détachement).
   */
  function setChecklistItem(itemKey: string, item: ChecklistItem) {
    if (!currentApplication.value) return
    currentApplication.value = {
      ...currentApplication.value,
      checklist: currentApplication.value.checklist.map(it =>
        it.key === itemKey ? item : it,
      ),
    }
  }

  /** 049 — Met à jour la progression documentaire du dossier courant. */
  function setChecklistProgress(progress: ChecklistProgress) {
    if (!currentApplication.value) return
    currentApplication.value = {
      ...currentApplication.value,
      checklist_progress: progress,
    }
  }

  function reset() {
    applications.value = []
    applicationsTotal.value = 0
    currentApplication.value = null
    loading.value = false
    error.value = null
    activeTab.value = 'sections'
  }

  return {
    applications,
    applicationsTotal,
    currentApplication,
    loading,
    error,
    activeTab,
    hasApplications,
    setApplications,
    setCurrentApplication,
    setLoading,
    setError,
    setActiveTab,
    updateSection,
    setChecklistItem,
    setChecklistProgress,
    reset,
  }
})
