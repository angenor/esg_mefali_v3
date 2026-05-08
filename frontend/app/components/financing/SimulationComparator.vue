<script setup lang="ts">
// F16 — Comparateur multi-offres : grille de SimulationDetailedCard avec
// highlights cheapest/fastest. Pour 1 offre : rend juste la carte. Pour
// 2..5 : grille responsive.

import SimulationDetailedCard from './SimulationDetailedCard.vue'
import type {
  MultiSimulateResponse,
  SimulationResult,
  DegradedColumn,
} from '~/types/simulator'
import { isSimulationResult } from '~/types/simulator'

interface Props {
  response: MultiSimulateResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

function asResult(col: SimulationResult | DegradedColumn): SimulationResult | null {
  return isSimulationResult(col) ? col : null
}

function asDegraded(col: SimulationResult | DegradedColumn): DegradedColumn | null {
  return isSimulationResult(col) ? null : col
}
</script>

<template>
  <section
    class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    role="region"
    aria-label="Comparateur de simulations"
  >
    <template v-for="(col, oid) in response.per_offer" :key="oid">
      <SimulationDetailedCard
        v-if="asResult(col)"
        :result="asResult(col)!"
        :is-cheapest="response.comparison_metadata.cheapest_offer_id === oid"
        :is-fastest="response.comparison_metadata.fastest_offer_id === oid"
        @open-source="(id) => emit('open-source', id)"
      />
      <article
        v-else
        class="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-5"
        role="region"
        aria-label="Calcul indisponible"
      >
        <h3 class="text-base font-semibold text-amber-800 dark:text-amber-200">
          Calcul indisponible
        </h3>
        <p class="text-sm text-amber-700 dark:text-amber-300 mt-2">
          Offre {{ String(oid).slice(0, 8) }}
        </p>
        <p class="text-sm text-amber-700 dark:text-amber-300 mt-2">
          Cause : {{ asDegraded(col)?.reason }}
        </p>
      </article>
    </template>
  </section>
</template>
