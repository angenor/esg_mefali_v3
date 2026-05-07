<script setup lang="ts">
import { ref } from 'vue'
import { useProjects } from '~/composables/useProjects'
import type { ProjectCreatePayload } from '~/types/project'

definePageMeta({
  layout: false,
})

const router = useRouter()
const { loading, error, createProject } = useProjects()
const errorMsg = ref<string | null>(null)

async function onSubmit(payload: ProjectCreatePayload) {
  errorMsg.value = null
  const created = await createProject(payload)
  if (!created) {
    errorMsg.value = error.value || 'Erreur de création'
    return
  }
  router.push(`/profile/projects/${created.id}`)
}

function onCancel() {
  router.push('/profile/projects')
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div class="mb-6">
      <h2 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
        Nouveau projet
      </h2>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Décrivez votre projet pour permettre le matching avec les fonds verts.
      </p>
    </div>
    <ProjectForm
      mode="create"
      :loading="loading"
      :error="errorMsg"
      @submit="onSubmit"
      @cancel="onCancel"
    />
  </div>
</template>
