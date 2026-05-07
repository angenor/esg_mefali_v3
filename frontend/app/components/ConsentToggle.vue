<script setup lang="ts">
import { computed } from 'vue'
import type { ConsentItem } from '~/composables/useDataPrivacy'

interface Props {
  consent: ConsentItem
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  toggle: [type: ConsentItem['type'], granted: boolean]
}>()

const isGranted = computed(() => props.consent.granted)
const ariaLabel = computed(
  () => `${props.consent.label} — actuellement ${isGranted.value ? 'accordé' : 'non accordé'}`,
)

function handleToggle() {
  if (props.loading) return
  emit('toggle', props.consent.type, !isGranted.value)
}
</script>

<template>
  <div
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4 transition-colors"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1">
        <h3
          class="text-sm font-semibold text-surface-text dark:text-surface-dark-text"
        >
          {{ consent.label }}
        </h3>
        <p class="mt-1 text-xs text-gray-600 dark:text-gray-400">
          {{ consent.description }}
        </p>
        <div class="mt-2 flex flex-wrap gap-2 text-[11px]">
          <span
            class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark-hover text-gray-600 dark:text-gray-300"
          >
            Base légale : {{ consent.legal_basis }}
          </span>
          <span
            class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark-hover text-gray-600 dark:text-gray-300"
          >
            Version {{ consent.version }}
          </span>
        </div>
      </div>
      <button
        type="button"
        role="switch"
        :aria-checked="isGranted"
        :aria-label="ariaLabel"
        :disabled="loading"
        :class="[
          'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:focus:ring-offset-dark-bg disabled:opacity-50 disabled:cursor-not-allowed',
          isGranted ? 'bg-emerald-600' : 'bg-gray-300 dark:bg-gray-600',
        ]"
        @click="handleToggle"
      >
        <span
          aria-hidden="true"
          :class="[
            'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
            isGranted ? 'translate-x-5' : 'translate-x-0',
          ]"
        />
      </button>
    </div>
  </div>
</template>
