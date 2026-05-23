<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useProjects } from '~/composables/useProjects'
import { useProjectsStore } from '~/stores/projects'
import ProjectFundsSection from '~/components/financing/ProjectFundsSection.vue'
import type { ProjectCreatePayload, ProjectDetail } from '~/types/project'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()
const {
  loading,
  error,
  getProject,
  updateProject,
  deleteProject,
} = useProjects()

const project = ref<ProjectDetail | null>(null)
const errorMsg = ref<string | null>(null)
const showDeleteModal = ref(false)
const blockedApplications = ref<
  { application_id: string; fund_name: string; status: string }[]
>([])

const projectId = (route.params as { id: string }).id

async function load() {
  errorMsg.value = null
  const detail = await getProject(projectId)
  if (!detail) {
    errorMsg.value = error.value || 'Projet introuvable'
    return
  }
  project.value = detail
  projectsStore.setCurrentProject(detail)
}

async function onSubmit(payload: ProjectCreatePayload) {
  errorMsg.value = null
  const updated = await updateProject(projectId, payload)
  if (!updated) {
    errorMsg.value = error.value || 'Erreur de mise à jour'
    return
  }
  project.value = updated
}

async function onDelete(force = false) {
  const result = await deleteProject(projectId, force)
  if (!result) {
    errorMsg.value = error.value || 'Erreur de suppression'
    return
  }
  if (!result.ok) {
    blockedApplications.value = result.blocked_by
    showDeleteModal.value = true
    return
  }
  showDeleteModal.value = false
  router.push('/profile/projects')
}

function onDuplicate() {
  router.push(`/profile/projects/${projectId}/duplicate`)
}

function onCancel() {
  router.push('/profile/projects')
}

onMounted(load)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <!-- Header -->
    <div class="mb-6 flex items-start justify-between gap-3">
      <div>
        <h2 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
          Modifier le projet
        </h2>
        <p
          v-if="project?.auto_generated"
          class="mt-1 text-xs text-amber-600 dark:text-amber-400"
        >
          Projet généré automatiquement — à compléter
        </p>
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          class="px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover"
          @click="onDuplicate"
        >
          Dupliquer
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm rounded-md border border-red-300 dark:border-red-700 bg-white dark:bg-dark-card text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
          @click="onDelete(false)"
        >
          Supprimer
        </button>
      </div>
    </div>

    <div
      v-if="loading && !project"
      class="flex items-center justify-center py-16"
    >
      <div
        class="w-8 h-8 border-3 border-brand-green border-t-transparent rounded-full animate-spin"
      />
    </div>

    <template v-else-if="project">
      <ProjectForm
        mode="edit"
        :initial-project="project"
        :loading="loading"
        :error="errorMsg"
        @submit="onSubmit"
        @cancel="onCancel"
      />

      <!-- F045 — Section Fonds compatibles avec ce projet (top 5) -->
      <div class="mt-6">
        <ProjectFundsSection :project-id="projectId" />
      </div>

      <!-- F047 — Lien vers l'évaluation ESG-projet -->
      <div
        class="mt-6 p-4 rounded-lg ring-1 ring-emerald-200 dark:ring-emerald-800 bg-emerald-50 dark:bg-emerald-900/20"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-emerald-900 dark:text-emerald-200">
              Évaluation ESG du projet
            </h3>
            <p class="mt-1 text-xs text-emerald-800 dark:text-emerald-300">
              Évaluez ce projet contre IFC PS / GCF ESS / BOAD ESS pour générer
              un score 0..100 sourcé et améliorer votre matching.
            </p>
          </div>
          <NuxtLink
            :to="`/profile/projects/${projectId}/esg`"
            class="shrink-0 px-3 py-1.5 text-sm font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700"
          >
            Évaluer ESG →
          </NuxtLink>
        </div>
      </div>
    </template>

    <!-- Modale de blocage suppression -->
    <Teleport to="body">
      <div
        v-if="showDeleteModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        role="dialog"
        aria-modal="true"
        @click.self="showDeleteModal = false"
      >
        <div
          class="w-full max-w-md rounded-lg bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border shadow-xl p-6"
        >
          <h3
            class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-3"
          >
            Suppression bloquée
          </h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
            Ce projet possède {{ blockedApplications.length }} candidature(s)
            active(s) :
          </p>
          <ul
            class="text-sm text-gray-700 dark:text-gray-300 mb-4 space-y-1 max-h-40 overflow-auto"
          >
            <li
              v-for="b in blockedApplications"
              :key="b.application_id"
              class="border-l-2 border-amber-400 pl-2"
            >
              {{ b.fund_name }} — {{ b.status }}
            </li>
          </ul>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Forcer la suppression archivera le projet (statut « Annulé ») mais
            les candidatures resteront liées.
          </p>
          <div class="flex items-center justify-end gap-3">
            <button
              type="button"
              class="px-4 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover"
              @click="showDeleteModal = false"
            >
              Annuler
            </button>
            <button
              type="button"
              class="px-4 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 font-medium"
              @click="onDelete(true)"
            >
              Forcer la suppression
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
