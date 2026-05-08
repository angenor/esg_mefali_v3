<script setup lang="ts">
// F20 — Page fiche pratique d'un intermédiaire.
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useResources } from '~/composables/useResources'
import type { Resource } from '~/types/resource'
import IntermediaryGuideView from '~/components/resources/IntermediaryGuideView.vue'

const route = useRoute()
const { getIntermediaryGuide } = useResources()

const guide = ref<Resource | null>(null)
const loading = ref<boolean>(true)
const notFound = ref<boolean>(false)

async function load(): Promise<void> {
  loading.value = true
  notFound.value = false
  try {
    guide.value = await getIntermediaryGuide(String(route.params.id))
  } catch (err) {
    const status = (err as { status?: number; statusCode?: number })?.status ??
      (err as { status?: number; statusCode?: number })?.statusCode
    if (status === 404) notFound.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-4xl">
    <div
      v-if="loading"
      class="text-center py-10 text-gray-500 dark:text-gray-400"
      role="status"
    >
      Chargement…
    </div>

    <div
      v-else-if="notFound"
      class="rounded-lg border border-gray-200 bg-white p-8 text-center dark:border-dark-border dark:bg-dark-card"
    >
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        Aucune fiche pratique disponible pour cet intermédiaire pour le moment.
      </p>
      <NuxtLink
        to="/financing"
        class="inline-flex items-center text-emerald-600 hover:underline dark:text-emerald-400"
      >
        Retour à la liste des financements
      </NuxtLink>
    </div>

    <IntermediaryGuideView v-else-if="guide" :resource="guide" />
  </div>
</template>
