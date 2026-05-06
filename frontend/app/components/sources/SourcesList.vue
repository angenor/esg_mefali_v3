<script setup lang="ts">
import type { SourceListItem } from '~/types/source'
import SourceBadge from './SourceBadge.vue'

interface Props {
  sources: SourceListItem[]
  loading?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [id: string]
}>()

function handleSelect(id: string) {
  emit('select', id)
}
</script>

<template>
  <div class="space-y-3">
    <div
      v-if="loading"
      class="text-center text-gray-500 dark:text-gray-400 py-8"
    >
      Chargement des sources...
    </div>

    <div
      v-else-if="!sources || sources.length === 0"
      class="text-center text-gray-500 dark:text-gray-400 py-8"
    >
      Aucune source disponible.
    </div>

    <button
      v-for="source in sources"
      :key="source.id"
      type="button"
      class="w-full text-left p-4 rounded-xl bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
      @click="handleSelect(source.id)"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <h3 class="text-base font-semibold text-surface-text dark:text-surface-dark-text">
            {{ source.title }}
          </h3>
          <div class="mt-1 text-sm text-gray-600 dark:text-gray-400">
            {{ source.publisher }} - version {{ source.version }} -
            {{ source.date_publi }}
          </div>
          <div
            v-if="source.section"
            class="mt-1 text-xs text-gray-500 dark:text-gray-500 italic"
          >
            {{ source.section }}
          </div>
        </div>
        <SourceBadge :status="source.verification_status" />
      </div>
    </button>
  </div>
</template>
