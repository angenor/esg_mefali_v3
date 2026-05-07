<script setup lang="ts">
import { useFinancing } from '~/composables/useFinancing'
import type { OfferComparison } from '~/types/financing'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const { compareOffersForFund } = useFinancing()

const comparisons = ref<OfferComparison[]>([])
const loading = ref(true)
const error = ref('')

const fundId = computed(() => route.query.fund_id as string | undefined)

async function loadComparisons(): Promise<void> {
  if (!fundId.value) {
    error.value = 'Paramètre fund_id manquant.'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    comparisons.value = await compareOffersForFund(fundId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur lors du chargement'
  } finally {
    loading.value = false
  }
}

function formatDays(min: number | null | undefined, max: number | null | undefined): string {
  if (!min && !max) return '—'
  if (min && max && min !== max) return `${min}-${max}j`
  return `${min || max}j`
}

function formatMoney(money: { amount: string; currency: string } | null | undefined): string {
  if (!money) return '—'
  const value = parseFloat(money.amount)
  if (isNaN(value)) return money.amount
  return `${value.toLocaleString('fr-FR')} ${money.currency}`
}

onMounted(loadComparisons)
</script>

<template>
  <div class="container mx-auto max-w-6xl px-4 py-8">
    <h1 class="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
      Comparateur d'offres
    </h1>

    <div v-if="loading" class="text-center py-12 text-gray-500 dark:text-gray-400">
      Chargement des offres...
    </div>
    <div
      v-else-if="error"
      class="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 p-4 text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <div
      v-else-if="comparisons.length === 0"
      class="rounded-lg border-2 border-dashed border-gray-300 dark:border-dark-border p-8 text-center text-gray-500 dark:text-gray-400"
    >
      Aucune offre publiée pour ce fonds.
    </div>
    <div
      v-else
      class="overflow-x-auto rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card"
    >
      <table class="w-full text-sm" role="table">
        <thead class="bg-gray-50 dark:bg-dark-hover">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Offre
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Intermédiaire
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Langues
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Frais
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Délai trait.
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Délai déc.
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Documents
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Action
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 dark:divide-dark-border">
          <tr
            v-for="comp in comparisons"
            :key="comp.offer_id"
            class="hover:bg-gray-50 dark:hover:bg-dark-hover"
          >
            <td class="px-4 py-3 font-medium text-gray-900 dark:text-white">
              {{ comp.name }}
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              {{ comp.intermediary_name }} ({{ comp.intermediary_country }})
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              {{ comp.accepted_languages.join(', ') }}
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              {{ formatMoney(comp.effective_fees_total_min) }}
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              {{ formatDays(comp.effective_processing_time_days_min, comp.effective_processing_time_days_max) }}
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              {{ formatDays(comp.effective_disbursement_time_days_min, comp.effective_disbursement_time_days_max) }}
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              {{ comp.documents_count }}
            </td>
            <td class="px-4 py-3">
              <NuxtLink
                :to="`/financing/offers/${comp.offer_id}`"
                class="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Voir →
              </NuxtLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
