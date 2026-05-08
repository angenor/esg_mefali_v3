<script setup lang="ts">
// F20 — Carte d'aperçu d'une ressource (cliquable, dark mode).
import { computed } from 'vue'
import type { ResourceListItem } from '~/types/resource'
import ResourceTypeBadge from '~/components/resources/ResourceTypeBadge.vue'

interface Props {
  resource: ResourceListItem
}

const props = defineProps<Props>()

const formattedDate = computed<string>(() => {
  try {
    return new Date(props.resource.updated_at).toLocaleDateString('fr-FR')
  } catch {
    return ''
  }
})

const duration = computed<string | null>(() => {
  const s = props.resource.duration_seconds
  if (s === null || s === undefined) return null
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
})
</script>

<template>
  <NuxtLink
    :to="`/resources/${resource.slug}`"
    class="block rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md hover:border-emerald-300 dark:border-dark-border dark:bg-dark-card dark:hover:border-emerald-600"
    :aria-label="`Ouvrir la ressource ${resource.title}`"
  >
    <div class="flex items-start justify-between mb-3">
      <ResourceTypeBadge :type="resource.type" />
      <span
        v-if="duration"
        class="text-xs text-gray-500 dark:text-gray-400"
        :aria-label="`Durée ${duration}`"
      >
        {{ duration }}
      </span>
    </div>
    <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-2">
      {{ resource.title }}
    </h3>
    <p class="text-sm text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
      {{ resource.description }}
    </p>
    <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-500">
      <span>Mis à jour le {{ formattedDate }}</span>
      <span :aria-label="`${resource.view_count} consultations`">
        {{ resource.view_count }} vue{{ resource.view_count > 1 ? 's' : '' }}
      </span>
    </div>
  </NuxtLink>
</template>
