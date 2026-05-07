<script setup lang="ts">
import { useFinancing } from '~/composables/useFinancing'
import type { Offer } from '~/types/financing'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const router = useRouter()
const { getOffer } = useFinancing()

const offer = ref<Offer | null>(null)
const loading = ref(true)
const error = ref('')

async function loadOffer(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const offerId = route.params.offer_id as string
    const result = await getOffer(offerId)
    if (result === null) {
      error.value = "Offre introuvable ou non publiée."
    } else {
      offer.value = result
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur lors du chargement'
  } finally {
    loading.value = false
  }
}

function handleCompare(fundId: string): void {
  router.push(`/financing/offers?fund_id=${fundId}&compare=true`)
}

function handleApply(offerId: string): void {
  // Préparation pour F15 (générateur dossier).
  router.push(`/financing/offers/${offerId}/apply`)
}

onMounted(loadOffer)
</script>

<template>
  <div class="container mx-auto max-w-4xl px-4 py-8">
    <div v-if="loading" class="text-center py-12 text-gray-500 dark:text-gray-400">
      Chargement de l'offre...
    </div>
    <div v-else-if="error" class="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 p-4 text-red-700 dark:text-red-300">
      {{ error }}
    </div>
    <OfferDetail
      v-else-if="offer"
      :offer="offer"
      @compare="handleCompare"
      @apply="handleApply"
    />
  </div>
</template>
