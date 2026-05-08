<script setup lang="ts">
// F21 (US1) — Liste des candidatures par offre avec lien « Voir toutes » au-delà.

import type { ApplicationCard } from '~/types/dashboard'
import ApplicationStatusCard from '~/components/dashboard/ApplicationStatusCard.vue'

interface Props {
  cards: ApplicationCard[]
  totalActive?: number
}

const props = withDefaults(defineProps<Props>(), {
  totalActive: 0,
})
</script>

<template>
  <section
    class="bg-white dark:bg-dark-card rounded-xl shadow-sm border border-gray-200 dark:border-dark-border p-4"
    data-testid="applications-by-offer-section"
  >
    <header class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text">
        Mes candidatures actives
      </h2>
      <span
        v-if="totalActive > 0"
        class="text-xs text-gray-500 dark:text-gray-400"
        data-testid="applications-counter"
      >
        {{ totalActive }} active{{ totalActive > 1 ? 's' : '' }}
      </span>
    </header>

    <div v-if="cards.length === 0" class="py-8 text-center" data-testid="applications-empty-state">
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">
        Vous n'avez pas encore de candidature active.
      </p>
      <NuxtLink
        to="/financing/offers"
        class="text-sm font-medium text-emerald-600 dark:text-emerald-400 hover:underline"
      >
        Découvrir les offres de financement →
      </NuxtLink>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <ApplicationStatusCard
        v-for="card in cards"
        :key="card.application_id"
        :card="card"
      />
    </div>

    <footer v-if="totalActive > cards.length" class="mt-4 text-right">
      <NuxtLink
        to="/applications"
        class="text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:underline"
        data-testid="applications-see-all-link"
      >
        Voir toutes mes candidatures →
      </NuxtLink>
    </footer>
  </section>
</template>
