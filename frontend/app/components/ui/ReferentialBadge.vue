<script setup lang="ts">
// F04 — Badge cliquable qui affiche la version du référentiel mobilisé.

import { computed } from 'vue'

import type { ReferentialDescriptor } from '~/types/currency'

interface Props {
  referential: ReferentialDescriptor | null | undefined
  /** Étiquette préfixe (par défaut « Évalué selon »). */
  prefix?: string
}

const props = withDefaults(defineProps<Props>(), {
  prefix: 'Évalué selon',
})

const emit = defineEmits<{
  (event: 'open-source-modal', referentialId: string): void
}>()

const formattedDate = computed<string>(() => {
  if (!props.referential?.valid_from) return ''
  // Format ISO YYYY-MM-DD → DD/MM/YYYY
  const parts = props.referential.valid_from.split('-')
  if (parts.length !== 3) return props.referential.valid_from
  return `${parts[2]}/${parts[1]}/${parts[0]}`
})

const label = computed<string>(() => {
  if (!props.referential) return ''
  return `${props.prefix} Référentiel ${props.referential.name} v${props.referential.version}`
    + (formattedDate.value ? ` du ${formattedDate.value}` : '')
})

function handleClick() {
  if (props.referential?.id) {
    emit('open-source-modal', props.referential.id)
  }
}
</script>

<template>
  <button
    v-if="referential"
    type="button"
    :aria-label="label"
    class="referential-badge inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 transition hover:bg-blue-100 hover:underline dark:border-dark-border dark:bg-dark-card dark:text-blue-300 dark:hover:bg-dark-hover"
    @click="handleClick"
  >
    <svg
      class="h-3 w-3 flex-shrink-0"
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
    >
      <path
        fill-rule="evenodd"
        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
        clip-rule="evenodd"
      />
    </svg>
    <span>{{ label }}</span>
  </button>
</template>
