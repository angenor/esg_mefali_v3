<script setup lang="ts">
// F16 — Page Simulateur : sélection projet + offres (1..5), bouton lancer,
// rendu carte unique ou comparateur multi-offres. Volatile : aucune
// persistance après navigation.

import { computed, ref } from 'vue'
import { useSimulator } from '~/composables/useSimulator'
import { useSimulatorStore } from '~/stores/simulator'
import SimulationComparator from '~/components/financing/SimulationComparator.vue'

// Le middleware d'authentification est appliqué globalement via
// `app/middleware/auth.global.ts` ; il ne doit pas être référencé par nom
// dans `definePageMeta` (sinon Nuxt lève "Unknown route middleware: 'auth'"
// car les middlewares globaux ne sont pas exposés au registre nommé).
// Pas de definePageMeta nécessaire ici.

const store = useSimulatorStore()
const { simulateMulti, loading, error } = useSimulator()

const projectIdInput = ref(store.selectedProjectId ?? '')
const offerIdInput = ref('')

const offerCount = computed(() => store.selectedOfferIds.length)

function setProject() {
  store.setSelectedProject(projectIdInput.value.trim() || null)
}

function addOffer() {
  const oid = offerIdInput.value.trim()
  if (oid) {
    store.toggleOffer(oid)
    offerIdInput.value = ''
  }
}

function removeOffer(oid: string) {
  store.toggleOffer(oid)
}

async function launch() {
  if (!store.selectedProjectId || !store.canSimulate) return
  await simulateMulti(store.selectedProjectId, store.selectedOfferIds)
}

function handleOpenSource(sourceId: string) {
  // Délègue à la modale de source globale (montée par le layout).
  // Pour MVP F16 : log côté console — l'intégration F01 SourceModal est
  // déjà câblée dans les autres pages via un eventBus / store séparé.
  console.info('[F16] open source requested:', sourceId)
}
</script>

<template>
  <main
    class="container mx-auto px-4 py-8 max-w-7xl bg-surface-bg dark:bg-surface-dark-bg min-h-screen"
  >
    <header class="mb-8">
      <h1
        class="text-3xl font-bold text-surface-text dark:text-surface-dark-text"
      >
        Simulateur de financement
      </h1>
      <p class="text-gray-600 dark:text-gray-400 mt-2">
        Compare jusqu'à 5 offres pour ton projet. Tous les chiffres sont
        sourcés et cliquables.
      </p>
    </header>

    <section
      class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 mb-6"
    >
      <h2
        class="text-lg font-semibold mb-4 text-surface-text dark:text-surface-dark-text"
      >
        Configuration
      </h2>

      <div class="space-y-4">
        <div>
          <label
            for="project-id"
            class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
          >
            Identifiant projet
          </label>
          <div class="flex gap-2">
            <input
              id="project-id"
              v-model="projectIdInput"
              type="text"
              class="flex-1 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text px-3 py-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              placeholder="UUID du projet vert"
              @blur="setProject"
            >
            <button
              type="button"
              class="px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 dark:hover:bg-emerald-500 transition focus:ring-2 focus:ring-emerald-500"
              @click="setProject"
            >
              Valider
            </button>
          </div>
        </div>

        <div>
          <label
            for="offer-id"
            class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
          >
            Ajouter une offre ({{ offerCount }} / 5)
          </label>
          <div class="flex gap-2">
            <input
              id="offer-id"
              v-model="offerIdInput"
              type="text"
              class="flex-1 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text px-3 py-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              placeholder="UUID de l'offre"
              :disabled="offerCount >= 5"
              @keyup.enter="addOffer"
            >
            <button
              type="button"
              class="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 dark:hover:bg-blue-500 transition focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="offerCount >= 5"
              @click="addOffer"
            >
              Ajouter
            </button>
          </div>
        </div>

        <ul
          v-if="store.selectedOfferIds.length > 0"
          class="flex flex-wrap gap-2"
          aria-label="Offres sélectionnées"
        >
          <li
            v-for="oid in store.selectedOfferIds"
            :key="oid"
            class="inline-flex items-center px-3 py-1 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200 text-sm"
          >
            {{ oid.slice(0, 8) }}
            <button
              type="button"
              class="ml-2 text-blue-600 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
              :aria-label="`Retirer l'offre ${oid.slice(0, 8)}`"
              @click="removeOffer(oid)"
            >
              ×
            </button>
          </li>
        </ul>

        <div class="pt-2">
          <button
            type="button"
            class="w-full md:w-auto px-6 py-2.5 rounded-md bg-emerald-600 text-white font-semibold hover:bg-emerald-700 dark:hover:bg-emerald-500 transition focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!store.canSimulate || loading"
            @click="launch"
          >
            {{ loading ? 'Calcul en cours…' : 'Lancer la simulation' }}
          </button>
        </div>
      </div>
    </section>

    <section
      v-if="error"
      class="rounded-md border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 p-4 text-red-800 dark:text-red-200 mb-6"
      role="alert"
    >
      {{ error }}
    </section>

    <section v-if="store.lastResult" aria-live="polite">
      <h2
        class="text-xl font-semibold mb-4 text-surface-text dark:text-surface-dark-text"
      >
        Résultats
      </h2>
      <SimulationComparator
        :response="store.lastResult"
        @open-source="handleOpenSource"
      />
    </section>

    <section
      v-else-if="!loading"
      class="rounded-md border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-8 text-center"
    >
      <p class="text-gray-600 dark:text-gray-400">
        Sélectionne un projet et 1 à 5 offres puis lance la simulation pour
        voir le détail des coûts, du ROI, de l'impact carbone et de la
        timeline — chaque chiffre source-cliquable.
      </p>
    </section>
  </main>
</template>
