<script setup lang="ts">
import { computed } from 'vue'
import type { ProjectSummary } from '~/types/project'

interface Props {
  projects: ProjectSummary[]
  total: number
  loading?: boolean
  error?: string | null
  page?: number
  limit?: number
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
  page: 1,
  limit: 25,
})

const emit = defineEmits<{
  'view-applications': [id: string]
  'view-detail': [id: string]
  'page-change': [page: number]
}>()

const totalPages = computed(() =>
  Math.max(1, Math.ceil(props.total / props.limit)),
)

const isEmpty = computed(
  () => !props.loading && props.projects.length === 0 && !props.error,
)

function goToPage(p: number) {
  if (p < 1 || p > totalPages.value) return
  emit('page-change', p)
}
</script>

<template>
  <div>
    <!-- Loading -->
    <div
      v-if="loading"
      class="flex items-center justify-center py-12"
      role="status"
      aria-label="Chargement"
    >
      <div
        class="w-8 h-8 border-3 border-brand-green border-t-transparent rounded-full animate-spin"
      />
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400"
      role="alert"
    >
      {{ error }}
    </div>

    <!-- Empty -->
    <div
      v-else-if="isEmpty"
      class="text-center py-12 px-4 rounded-lg bg-gray-50 dark:bg-dark-card border border-gray-200 dark:border-dark-border"
    >
      <p class="text-base font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Aucun projet pour le moment
      </p>
      <p class="text-sm text-gray-500 dark:text-gray-400">
        Créez votre premier projet vert pour commencer.
      </p>
    </div>

    <!-- Grid -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
      data-testid="projects-grid"
    >
      <ProjectCard
        v-for="p in projects"
        :key="p.id"
        :project="p"
        @view-applications="(id: string) => emit('view-applications', id)"
        @view-detail="(id: string) => emit('view-detail', id)"
      />
    </div>

    <!-- Pagination -->
    <div
      v-if="totalPages > 1 && !loading && !error"
      class="mt-6 flex items-center justify-center gap-2"
    >
      <button
        type="button"
        :disabled="page <= 1"
        class="px-3 py-1 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-dark-hover"
        @click="goToPage(page - 1)"
      >
        Précédent
      </button>
      <span class="text-sm text-gray-500 dark:text-gray-400">
        Page {{ page }} / {{ totalPages }}
      </span>
      <button
        type="button"
        :disabled="page >= totalPages"
        class="px-3 py-1 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-dark-hover"
        @click="goToPage(page + 1)"
      >
        Suivant
      </button>
    </div>
  </div>
</template>
