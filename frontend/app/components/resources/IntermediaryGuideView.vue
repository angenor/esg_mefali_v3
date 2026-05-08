<script setup lang="ts">
// F20 — Vue dédiée à une fiche pratique d'intermédiaire.
import type { Resource } from '~/types/resource'
import ResourceMarkdownRenderer from '~/components/resources/ResourceMarkdownRenderer.vue'

interface Props {
  resource: Resource
}

defineProps<Props>()
</script>

<template>
  <article
    class="rounded-lg border border-gray-200 bg-white p-6 dark:border-dark-border dark:bg-dark-card"
    role="region"
    :aria-label="`Fiche pratique : ${resource.title}`"
  >
    <header class="mb-6">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text mb-2">
        {{ resource.title }}
      </h1>
      <p class="text-sm text-gray-600 dark:text-gray-400">
        {{ resource.description }}
      </p>
    </header>
    <ResourceMarkdownRenderer :content="resource.content_md" />
  </article>
</template>
