<script setup lang="ts">
/**
 * F13 — Bandeau « Goulot d'étranglement » pour la dual view (US2).
 *
 * Affiche le référentiel le plus restrictif + top 3 critères + bouton
 * « Renseigner maintenant ».
 */
import { computed } from 'vue'
import type { BottleneckInfo } from '~/types/esg'

interface Props {
  bottleneck: BottleneckInfo
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'focus-indicators': [codes: string[]]
}>()

const severity = computed(() => {
  if (!props.bottleneck.eligibility_min) return 'critical'
  if (props.bottleneck.gap > 5) return 'warning'
  return 'info'
})

const bgClass = computed(() => {
  switch (severity.value) {
    case 'critical':
      return 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700 text-red-800 dark:text-red-200'
    case 'warning':
      return 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700 text-yellow-800 dark:text-yellow-200'
    default:
      return 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700 text-green-800 dark:text-green-200'
  }
})

function handleFocus() {
  emit('focus-indicators', props.bottleneck.top_3_critical_indicators)
}
</script>

<template>
  <div
    role="alert"
    :class="['rounded-lg border p-4', bgClass]"
  >
    <h3 class="text-base font-semibold mb-2">
      Goulot d'étranglement : référentiel {{ bottleneck.bottleneck_referential_name }} ({{ bottleneck.bottleneck_score.toFixed(0) }}/100)
    </h3>
    <p class="text-sm">
      Pour décrocher cette offre, renseignez en priorité ces critères manquants :
    </p>

    <ul
      v-if="bottleneck.top_3_critical_indicators.length > 0"
      class="mt-2 space-y-1 text-sm"
    >
      <li
        v-for="code in bottleneck.top_3_critical_indicators"
        :key="code"
        class="flex items-center gap-2"
      >
        <span class="font-mono">{{ code }}</span>
      </li>
    </ul>

    <p class="mt-2 text-sm">
      Éligibilité effective :
      <strong>
        min({{ bottleneck.bottleneck_referential_code }}={{ bottleneck.bottleneck_score.toFixed(0) }},
        {{ bottleneck.other_referential_code }}={{ bottleneck.other_referential_score.toFixed(0) }})
        = {{ bottleneck.bottleneck_score.toFixed(0) }}/100
      </strong>
      —
      <span v-if="bottleneck.eligibility_min">éligible</span>
      <span v-else>non éligible actuellement</span>
    </p>

    <button
      v-if="bottleneck.top_3_critical_indicators.length > 0"
      type="button"
      class="mt-3 rounded-md bg-primary text-white px-4 py-2 text-sm font-medium hover:bg-primary/90 transition"
      @click="handleFocus"
    >
      Renseigner maintenant
    </button>
  </div>
</template>
