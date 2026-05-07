<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useProjects } from '~/composables/useProjects'
import { useProjectsStore } from '~/stores/projects'
import type { ProjectFilters } from '~/types/project'

definePageMeta({
  layout: false,
})

const router = useRouter()
const projectsStore = useProjectsStore()
const { loading, error, listProjects } = useProjects()

const filters = ref<ProjectFilters>({ ...projectsStore.filters, page: 1, limit: 25 })
const errorMsg = ref<string | null>(null)

async function refresh() {
  errorMsg.value = null
  const result = await listProjects(filters.value)
  if (result) {
    projectsStore.setProjects(result.items, result.total)
    projectsStore.setFilters(filters.value)
  } else {
    errorMsg.value = error.value || 'Erreur de chargement'
  }
}

watch(
  filters,
  () => {
    refresh()
  },
  { deep: true },
)

function onPageChange(page: number) {
  filters.value = { ...filters.value, page }
}

function onViewDetail(id: string) {
  router.push(`/profile/projects/${id}`)
}

function onViewApplications(id: string) {
  router.push(`/applications?project_id=${id}`)
}

onMounted(refresh)
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
          Mes Projets
        </h2>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Modélisez vos projets verts pour faciliter le matching avec les fonds.
        </p>
      </div>
      <NuxtLink
        to="/profile/projects/new"
        class="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-md bg-brand-green text-white hover:bg-emerald-700 font-medium"
      >
        + Créer un projet
      </NuxtLink>
    </div>

    <!-- Filtres -->
    <div class="mb-6">
      <ProjectFilters v-model="filters" />
    </div>

    <!-- Liste -->
    <ProjectList
      :projects="projectsStore.projects"
      :total="projectsStore.total"
      :loading="loading"
      :error="errorMsg"
      :page="filters.page ?? 1"
      :limit="filters.limit ?? 25"
      @view-applications="onViewApplications"
      @view-detail="onViewDetail"
      @page-change="onPageChange"
    />
  </div>
</template>
