<script setup lang="ts">
import { ref } from 'vue'
import { useDataPrivacy } from '~/composables/useDataPrivacy'

const { useExport } = useDataPrivacy()
const { exporting, error, asyncJobId, downloadExport } = useExport()
const successMessage = ref<string | null>(null)

async function handleExport() {
  successMessage.value = null
  await downloadExport()
  if (!error.value) {
    successMessage.value = asyncJobId.value
      ? 'Export en préparation. Vous recevrez un email avec le lien quand il sera prêt.'
      : 'Export téléchargé.'
  }
}
</script>

<template>
  <div>
    <button
      type="button"
      :disabled="exporting"
      :class="[
        'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium',
        'bg-emerald-600 hover:bg-emerald-700 text-white',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:focus:ring-offset-dark-bg',
      ]"
      @click="handleExport"
    >
      <span v-if="exporting" class="inline-flex items-center gap-2">
        <svg
          class="h-4 w-4 animate-spin"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          />
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        Export en cours…
      </span>
      <span v-else>Exporter mes données en JSON</span>
    </button>
    <p
      v-if="successMessage"
      class="mt-2 text-sm text-emerald-700 dark:text-emerald-400"
      aria-live="polite"
    >
      {{ successMessage }}
    </p>
    <p
      v-if="error"
      class="mt-2 text-sm text-red-700 dark:text-red-400"
      aria-live="assertive"
    >
      {{ error }}
    </p>
  </div>
</template>
