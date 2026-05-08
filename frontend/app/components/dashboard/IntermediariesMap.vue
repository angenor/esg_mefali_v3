<script setup lang="ts">
// F21 (US3) — Carte UEMOA des intermédiaires actifs.
// Réutilise <MapBlock> F11. Lazy-load Leaflet via defineAsyncComponent.

import { computed, defineAsyncComponent } from 'vue'
import type { ActiveIntermediary } from '~/types/dashboard'

const MapBlock = defineAsyncComponent(() => import('~/components/richblocks/MapBlock.vue'))

interface Props {
  intermediaries: ActiveIntermediary[]
}

const props = defineProps<Props>()

const markers = computed(() =>
  (props.intermediaries || []).map((i) => ({
    lat: i.lat,
    lon: i.lon,
    label: i.name,
    type: 'intermediary',
    popup: {
      title: i.name,
      type: i.type,
      country: i.country,
      accreditations: i.accreditations,
      applicationsCount: i.applications_count,
      isFallbackCapital: i.is_fallback_capital,
      detailUrl: `/financing/intermediaries/${i.intermediary_id}`,
    },
  })),
)
</script>

<template>
  <section
    class="bg-white dark:bg-dark-card rounded-xl shadow-sm border border-gray-200 dark:border-dark-border p-4"
    data-testid="intermediaries-map-section"
  >
    <header class="mb-3 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text">
        Mes intermédiaires actifs
      </h2>
      <span class="text-xs text-gray-500 dark:text-gray-400">
        Zone UEMOA
      </span>
    </header>

    <div
      v-if="!intermediaries || intermediaries.length === 0"
      class="py-10 text-center"
      data-testid="intermediaries-empty-state"
    >
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">
        Vous n'avez pas encore d'intermédiaire actif.
      </p>
      <NuxtLink
        to="/financing/intermediaries"
        class="text-sm font-medium text-emerald-600 dark:text-emerald-400 hover:underline"
      >
        Parcourir l'annuaire des intermédiaires →
      </NuxtLink>
    </div>

    <div v-else class="h-80" data-testid="intermediaries-map-container">
      <MapBlock
        :markers="markers"
        :center="[12.0, -2.0]"
        :zoom="5"
      />
    </div>
  </section>
</template>
