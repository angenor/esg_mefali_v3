<script setup lang="ts">
import { useFinancing } from '~/composables/useFinancing'
import type { OfferSummary } from '~/types/financing'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const { listOffers } = useFinancing()

const offers = ref<OfferSummary[]>([])
const loading = ref(true)
const error = ref('')

const intermediaryId = computed(() => route.params.intermediary_id as string)

async function loadOffers(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await listOffers({ intermediary_id: intermediaryId.value })
    offers.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur lors du chargement'
  } finally {
    loading.value = false
  }
}

onMounted(loadOffers)
</script>

<template>
  <div class="container mx-auto max-w-4xl px-4 py-8">
    <h1 class="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
      Détail de l'intermédiaire
    </h1>

    <div v-if="loading" class="text-center py-12 text-gray-500 dark:text-gray-400">
      Chargement...
    </div>
    <div
      v-else-if="error"
      class="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 p-4 text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <div v-else>
      <p class="mb-6 text-gray-600 dark:text-gray-400">
        Offres distribuées par cet intermédiaire :
      </p>
      <div
        v-if="offers.length === 0"
        class="rounded-lg border-2 border-dashed border-gray-300 dark:border-dark-border p-8 text-center text-gray-500 dark:text-gray-400"
      >
        Aucune offre publiée pour cet intermédiaire.
      </div>
      <div v-else class="grid gap-4 sm:grid-cols-2">
        <OfferCard
          v-for="offer in offers"
          :key="offer.id"
          :offer="offer"
        />
      </div>
    </div>
  </div>
</template>
