<script setup lang="ts">
// F20 — Page de détail d'une ressource.
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useResources } from '~/composables/useResources'
import type { Resource } from '~/types/resource'
import ResourceMarkdownRenderer from '~/components/resources/ResourceMarkdownRenderer.vue'
import ResourceTypeBadge from '~/components/resources/ResourceTypeBadge.vue'
import ResourceVideoPlayer from '~/components/resources/ResourceVideoPlayer.vue'

const route = useRoute()
const { getResource, incrementView } = useResources()

const resource = ref<Resource | null>(null)
const loading = ref<boolean>(true)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  const slug = String(route.params.slug)
  loading.value = true
  error.value = null
  try {
    resource.value = await getResource(slug)
    void incrementView(slug).catch(() => {
      /* silent */
    })
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : 'Ressource introuvable.'
  } finally {
    loading.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-4xl">
    <NuxtLink
      to="/resources"
      class="inline-flex items-center text-sm text-emerald-600 hover:underline dark:text-emerald-400 mb-6"
    >
      ← Retour à la bibliothèque
    </NuxtLink>

    <div
      v-if="loading"
      class="text-center py-10 text-gray-500 dark:text-gray-400"
      role="status"
    >
      Chargement…
    </div>

    <div
      v-else-if="error"
      class="rounded-md border border-red-300 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300"
      role="alert"
    >
      {{ error }}
    </div>

    <article
      v-else-if="resource"
      class="rounded-lg border border-gray-200 bg-white p-6 sm:p-8 dark:border-dark-border dark:bg-dark-card"
    >
      <div class="flex items-center gap-3 mb-4">
        <ResourceTypeBadge :type="resource.type" />
        <span class="text-xs text-gray-500 dark:text-gray-400">
          Version {{ resource.version }}
        </span>
      </div>
      <h1 class="text-3xl font-bold text-surface-text dark:text-surface-dark-text mb-3">
        {{ resource.title }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400 mb-6">
        {{ resource.description }}
      </p>

      <ResourceVideoPlayer
        v-if="resource.type === 'video' && resource.video_url"
        :video-url="resource.video_url"
        class="mb-6"
      />

      <a
        v-if="resource.type === 'template_doc' && resource.file_url"
        :href="resource.file_url"
        download
        class="inline-flex items-center mb-6 px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition"
        :aria-label="`Télécharger ${resource.title}`"
      >
        Télécharger le modèle
      </a>

      <ResourceMarkdownRenderer :content="resource.content_md" />
    </article>
  </div>
</template>
