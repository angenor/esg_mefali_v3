<script setup lang="ts">
// F14 — MatchAlertToggle : switch ARIA pour activer/désactiver les
// alertes de nouveaux matches sur un projet. Persiste via API parent.

import { computed, ref, watch } from 'vue'
import type { MatchAlertSubscription } from '~/types/matching'

interface Props {
  subscription: MatchAlertSubscription | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<{
  toggle: [isActive: boolean]
  'update-threshold': [minScore: number]
}>()

const localActive = ref<boolean>(props.subscription?.isActive ?? false)
const localThreshold = ref<number>(props.subscription?.minGlobalScore ?? 60)

watch(
  () => props.subscription,
  (next) => {
    if (next) {
      localActive.value = next.isActive
      localThreshold.value = next.minGlobalScore
    }
  },
  { immediate: false },
)

function onToggle() {
  if (props.loading) return
  const next = !localActive.value
  localActive.value = next
  emit('toggle', next)
}

function onThresholdChange(event: Event) {
  const target = event.target as HTMLInputElement
  const parsed = Number.parseInt(target.value, 10)
  if (Number.isFinite(parsed)) {
    localThreshold.value = parsed
    emit('update-threshold', parsed)
  }
}

const switchClasses = computed(() =>
  localActive.value
    ? 'bg-emerald-500 dark:bg-emerald-600'
    : 'bg-gray-300 dark:bg-dark-border',
)

const knobClasses = computed(() =>
  localActive.value ? 'translate-x-5' : 'translate-x-0',
)

const ariaLabel = computed(() =>
  localActive.value
    ? 'Alertes actives. Cliquer pour désactiver les alertes de nouvelles offres.'
    : 'Alertes inactives. Cliquer pour recevoir les alertes de nouvelles offres compatibles.',
)
</script>

<template>
  <div
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4"
    data-testid="match-alert-toggle"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex-1">
        <h3
          class="text-sm font-semibold text-surface-text dark:text-surface-dark-text"
        >
          Alertes nouvelles offres
        </h3>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Recevez une notification dès qu'une nouvelle offre compatible
          dépasse votre seuil minimum de score global.
        </p>
      </div>
      <button
        type="button"
        role="switch"
        :aria-checked="localActive"
        :aria-label="ariaLabel"
        :aria-busy="loading"
        :disabled="loading"
        :data-testid="
          localActive ? 'alert-toggle-on' : 'alert-toggle-off'
        "
        :class="[
          'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card disabled:opacity-50 disabled:cursor-not-allowed',
          switchClasses,
        ]"
        @click="onToggle"
      >
        <span
          aria-hidden="true"
          :class="[
            'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform',
            knobClasses,
          ]"
        />
      </button>
    </div>

    <div v-if="localActive" class="mt-4">
      <label
        :for="`alert-threshold-${subscription?.id ?? 'new'}`"
        class="block text-xs font-medium text-gray-700 dark:text-gray-300"
      >
        Seuil minimum (score global) :
        <span class="font-semibold tabular-nums">{{ localThreshold }}</span>
      </label>
      <input
        :id="`alert-threshold-${subscription?.id ?? 'new'}`"
        type="range"
        min="0"
        max="100"
        step="5"
        :value="localThreshold"
        :disabled="loading"
        data-testid="alert-threshold-input"
        class="mt-1 w-full accent-emerald-500"
        @change="onThresholdChange"
      />
    </div>
  </div>
</template>
