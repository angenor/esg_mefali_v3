<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useProjects } from '~/composables/useProjects'
import type { ProjectCreatePayload, ProjectDetail } from '~/types/project'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const router = useRouter()
const { loading, error, getProject, duplicateProject } = useProjects()

const sourceProject = ref<ProjectDetail | null>(null)
const errorMsg = ref<string | null>(null)

const projectId = (route.params as { id: string }).id

async function load() {
  errorMsg.value = null
  const detail = await getProject(projectId)
  if (!detail) {
    errorMsg.value = error.value || 'Projet introuvable'
    return
  }
  sourceProject.value = detail
}

async function onSubmit(payload: ProjectCreatePayload) {
  errorMsg.value = null
  const dup = await duplicateProject(projectId, payload.name)
  if (!dup) {
    errorMsg.value = error.value || 'Erreur lors de la duplication'
    return
  }
  router.push(`/profile/projects/${dup.id}`)
}

function onCancel() {
  router.push(`/profile/projects/${projectId}`)
}

onMounted(load)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div class="mb-6">
      <h2 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
        Dupliquer le projet
      </h2>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Le nouveau projet sera créé en statut « Brouillon ». Les documents
        associés ne sont pas copiés — vous pourrez les lier manuellement
        ensuite.
      </p>
    </div>

    <div
      v-if="loading && !sourceProject"
      class="flex items-center justify-center py-16"
    >
      <div
        class="w-8 h-8 border-3 border-brand-green border-t-transparent rounded-full animate-spin"
      />
    </div>

    <ProjectForm
      v-else-if="sourceProject"
      mode="duplicate"
      :initial-project="sourceProject"
      :loading="loading"
      :error="errorMsg"
      @submit="onSubmit"
      @cancel="onCancel"
    />
  </div>
</template>
