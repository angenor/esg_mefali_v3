<script setup lang="ts">
// F14 — Page de gestion des alertes nouvelles offres pour un projet.

import { onMounted, ref } from 'vue'
import MatchAlertToggle from '~/components/matching/MatchAlertToggle.vue'
import { useMatching } from '~/composables/useMatching'
import { useMatchesStore } from '~/stores/matches'
import type { MatchAlertSubscription } from '~/types/matching'

definePageMeta({ layout: 'default' })

const route = useRoute()
const matchesStore = useMatchesStore()
const { getSubscription, updateSubscription, loading, error } = useMatching()

const projectId = (route.params as { id: string }).id
const subscription = ref<MatchAlertSubscription | null>(null)
const errorMsg = ref<string | null>(null)
const successMsg = ref<string | null>(null)

async function load() {
  errorMsg.value = null
  const sub = await getSubscription(projectId)
  if (!sub) {
    errorMsg.value = error.value || 'Aucun abonnement trouvé.'
    return
  }
  subscription.value = sub
  matchesStore.setSubscription(projectId, sub)
}

async function onToggle(isActive: boolean) {
  successMsg.value = null
  errorMsg.value = null
  const updated = await updateSubscription(projectId, { isActive })
  if (!updated) {
    errorMsg.value = error.value || 'Erreur de mise à jour.'
    return
  }
  subscription.value = updated
  matchesStore.setSubscription(projectId, updated)
  successMsg.value = isActive
    ? 'Alertes activées.'
    : 'Alertes désactivées.'
}

async function onUpdateThreshold(minScore: number) {
  successMsg.value = null
  errorMsg.value = null
  const updated = await updateSubscription(projectId, {
    minGlobalScore: minScore,
  })
  if (!updated) {
    errorMsg.value = error.value || 'Erreur de mise à jour.'
    return
  }
  subscription.value = updated
  matchesStore.setSubscription(projectId, updated)
  successMsg.value = `Seuil minimum mis à jour : ${minScore}.`
}

onMounted(load)
</script>

<template>
  <div class="max-w-2xl mx-auto p-4 sm:p-6">
    <header class="mb-5">
      <h1 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
        Alertes du projet
      </h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Soyez prévenu·e dès qu'une nouvelle offre compatible apparaît.
      </p>
    </header>

    <div
      v-if="errorMsg"
      role="alert"
      data-testid="alerts-error"
      class="mb-3 rounded-md border border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-950/30 p-3 text-sm text-rose-700 dark:text-rose-300"
    >
      {{ errorMsg }}
    </div>
    <div
      v-if="successMsg"
      role="status"
      data-testid="alerts-success"
      class="mb-3 rounded-md border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm text-emerald-700 dark:text-emerald-300"
    >
      {{ successMsg }}
    </div>

    <MatchAlertToggle
      :subscription="subscription"
      :loading="loading"
      @toggle="onToggle"
      @update-threshold="onUpdateThreshold"
    />
  </div>
</template>
