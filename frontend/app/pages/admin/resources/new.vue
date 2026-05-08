<script setup lang="ts">
// F20 — Page admin : création d'une ressource.
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminResources } from '~/composables/useAdminResources'
import type { ResourceCreatePayload } from '~/types/resource'
import ResourceForm from '~/components/admin/resources/ResourceForm.vue'

definePageMeta({ middleware: ['admin'], layout: 'admin' })

const { adminCreate } = useAdminResources()
const router = useRouter()

const loading = ref<boolean>(false)
const error = ref<string | null>(null)

async function handleSubmit(payload: ResourceCreatePayload): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const created = await adminCreate(payload)
    await router.push(`/admin/resources/${created.id}`)
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : 'Création impossible.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-3xl">
    <h1
      class="text-2xl font-bold text-surface-text dark:text-surface-dark-text mb-6"
    >
      Nouvelle ressource
    </h1>
    <div
      v-if="error"
      class="rounded-md border border-red-300 bg-red-50 p-3 mb-4 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300"
      role="alert"
    >
      {{ error }}
    </div>
    <ResourceForm :loading="loading" @submit="handleSubmit" />
  </div>
</template>
