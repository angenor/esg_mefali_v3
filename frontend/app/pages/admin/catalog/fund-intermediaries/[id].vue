<script setup lang="ts">
// F25 — Fiche détaillée d'une liaison fonds × intermédiaire (US3 clarifié).
// L'ID est composite `"{fund_id}:{intermediary_id}"` ; le router parent
// décode automatiquement, mais on conserve `encodeURIComponent` lors de la
// navigation pour la sécurité des URLs.
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from '#app'
import { useAdminCatalog } from '~/composables/useAdminCatalog'
import type { FundIntermediaryDetail as FIDetail } from '~/types/adminCatalog'

definePageMeta({
  layout: 'admin',
  middleware: 'admin',
})

useHead({ title: 'Liaison fonds × intermédiaire — ESG Mefali' })

const route = useRoute()
const router = useRouter()
const { fetchFundIntermediaryDetail } = useAdminCatalog()

const detail = ref<FIDetail | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  const idParam = route.params.id
  const compositeId = Array.isArray(idParam) ? idParam[0] : idParam
  if (!compositeId) {
    error.value = 'Identifiant manquant'
    loading.value = false
    return
  }
  try {
    detail.value = await fetchFundIntermediaryDetail(decodeURIComponent(compositeId))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur de chargement'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <nav class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
      <NuxtLink
        to="/admin/catalog?tab=fund_intermediaries"
        class="text-red-700 dark:text-red-300 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
      >
        ← Retour au catalogue
      </NuxtLink>
    </nav>

    <div
      v-if="loading"
      class="rounded-md border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 text-sm text-gray-500 dark:text-gray-400"
    >
      Chargement de la fiche…
    </div>

    <div
      v-else-if="error"
      class="rounded-md border border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-900/40 px-4 py-3 text-sm text-rose-800 dark:text-rose-200"
      role="alert"
    >
      {{ error }}
    </div>

    <FundIntermediaryDetail v-else-if="detail" :detail="detail" />
  </div>
</template>
