<script setup lang="ts">
import { computed, ref } from 'vue'

interface Props {
  expected: string
  matchMessage?: string
  mismatchMessage?: string
  buttonLabel?: string
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  matchMessage: 'Hash conforme — le PDF n\'a pas été altéré.',
  mismatchMessage: 'Hash non conforme — le PDF reçu diffère de l\'original.',
  buttonLabel: 'Comparer',
  placeholder: 'Collez ici le hash imprimé sur votre PDF',
})

const emit = defineEmits<{
  (e: 'compared', payload: { match: boolean }): void
}>()

const inputValue = ref('')
const checked = ref(false)

const trimmedInput = computed(() => inputValue.value.trim())
const isMatch = computed(
  () =>
    checked.value &&
    trimmedInput.value.length === 64 &&
    trimmedInput.value === props.expected,
)
const isMismatch = computed(
  () => checked.value && trimmedInput.value !== props.expected,
)

function compare() {
  checked.value = true
  emit('compared', { match: trimmedInput.value === props.expected })
}

function onInput(e: Event) {
  inputValue.value = (e.target as HTMLInputElement).value
  checked.value = false
}
</script>

<template>
  <div class="space-y-2">
    <label
      for="hash-compare"
      class="block text-sm font-medium text-gray-700 dark:text-gray-300"
    >
      <slot name="title">Comparer avec votre PDF</slot>
    </label>
    <div class="flex flex-col sm:flex-row gap-2">
      <input
        id="hash-compare"
        type="text"
        :value="inputValue"
        :placeholder="placeholder"
        class="flex-1 min-h-[44px] px-3 py-2 text-sm font-mono bg-white dark:bg-dark-input text-gray-900 dark:text-white border border-gray-300 dark:border-dark-border rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
        :aria-describedby="checked ? 'hash-compare-feedback' : undefined"
        autocomplete="off"
        spellcheck="false"
        @input="onInput"
      >
      <button
        type="button"
        class="min-h-[44px] px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="!trimmedInput"
        @click="compare"
      >
        {{ buttonLabel }}
      </button>
    </div>
    <p
      v-if="isMatch"
      id="hash-compare-feedback"
      class="text-sm text-emerald-700 dark:text-emerald-300 flex items-center gap-1"
    >
      <svg
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="3"
          d="M5 13l4 4L19 7"
        />
      </svg>
      {{ matchMessage }}
    </p>
    <p
      v-else-if="isMismatch"
      id="hash-compare-feedback"
      class="text-sm text-rose-700 dark:text-rose-300 flex items-center gap-1"
    >
      <svg
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="3"
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
      {{ mismatchMessage }}
    </p>
  </div>
</template>
