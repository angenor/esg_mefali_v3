<script setup lang="ts">
// F20 — Page admin : édition + publication d'une ressource.
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAdminResources } from '~/composables/useAdminResources'
import type {
  ResourceAdminDetail,
  ResourceCreatePayload,
} from '~/types/resource'
import ResourceForm from '~/components/admin/resources/ResourceForm.vue'

definePageMeta({ middleware: ['admin'], layout: 'admin' })

const route = useRoute()
const { adminGet, adminUpdate, adminPublish } = useAdminResources()

const detail = ref<ResourceAdminDetail | null>(null)
const loading = ref<boolean>(true)
const saving = ref<boolean>(false)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try {
    detail.value = await adminGet(String(route.params.id))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Ressource introuvable.'
  } finally {
    loading.value = false
  }
}

async function handleSubmit(payload: ResourceCreatePayload): Promise<void> {
  if (!detail.value) return
  saving.value = true
  error.value = null
  try {
    await adminUpdate(detail.value.id, {
      title: payload.title,
      description: payload.description,
      content_md: payload.content_md,
      file_url: payload.file_url,
      video_url: payload.video_url,
      duration_seconds: payload.duration_seconds,
      category: payload.category,
      target_audience: payload.target_audience,
      language: payload.language,
      source_id: payload.source_id,
    })
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur de mise à jour.'
  } finally {
    saving.value = false
  }
}

async function publishNow(): Promise<void> {
  if (!detail.value) return
  try {
    await adminPublish(detail.value.id)
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Publication impossible.'
  }
}
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-3xl">
    <div v-if="loading" class="text-gray-500 dark:text-gray-400">
      Chargement…
    </div>
    <div v-else-if="!detail" class="text-red-600 dark:text-red-400">
      Ressource introuvable.
    </div>
    <div v-else>
      <header class="flex items-center justify-between mb-6">
        <h1
          class="text-2xl font-bold text-surface-text dark:text-surface-dark-text"
        >
          Édition : {{ detail.title }}
        </h1>
        <button
          v-if="detail.publication_status === 'draft'"
          type="button"
          class="px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition"
          @click="publishNow"
        >
          Publier
        </button>
      </header>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Statut : {{ detail.publication_status }} · Version
        {{ detail.version }}
      </p>
      <div
        v-if="error"
        class="rounded-md border border-red-300 bg-red-50 p-3 mb-4 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300"
        role="alert"
      >
        {{ error }}
      </div>
      <ResourceForm
        :initial="detail"
        :loading="saving"
        @submit="handleSubmit"
      />
    </div>
  </div>
</template>
