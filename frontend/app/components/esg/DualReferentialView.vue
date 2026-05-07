<script setup lang="ts">
/**
 * F13 — Vue côte-à-côte des scores Fund + Intermediary pour une offre (US2).
 *
 * Affiche 2 ReferentialScoreCard, un BottleneckBanner et gère le fallback.
 */
import { computed } from 'vue'
import type { DualReferentialResponse } from '~/types/esg'
import ReferentialScoreCard from './ReferentialScoreCard.vue'
import BottleneckBanner from './BottleneckBanner.vue'

interface Props {
  dualResponse: DualReferentialResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'focus-indicators': [codes: string[]]
}>()

const isDual = computed(() => props.dualResponse.is_dual_view)
</script>

<template>
  <div class="space-y-4">
    <BottleneckBanner
      v-if="dualResponse.bottleneck"
      :bottleneck="dualResponse.bottleneck"
      @focus-indicators="(codes) => emit('focus-indicators', codes)"
    />

    <div
      v-if="isDual"
      class="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      <div>
        <h4 class="mb-2 text-sm font-medium text-gray-600 dark:text-gray-400">
          Selon le fonds
        </h4>
        <ReferentialScoreCard :score="dualResponse.fund_score" />
      </div>
      <div v-if="dualResponse.intermediary_score">
        <h4 class="mb-2 text-sm font-medium text-gray-600 dark:text-gray-400">
          Selon l'intermédiaire
        </h4>
        <ReferentialScoreCard :score="dualResponse.intermediary_score" />
      </div>
    </div>

    <div v-else>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">
        Référentiel unique pour cette offre — pas de goulot d'étranglement.
      </p>
      <ReferentialScoreCard :score="dualResponse.fund_score" />
    </div>
  </div>
</template>
