<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  scheduledAt: string
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  cancel: []
}>()

const formattedDate = computed(() => {
  try {
    return new Date(props.scheduledAt).toLocaleString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return props.scheduledAt
  }
})
</script>

<template>
  <div
    role="alert"
    class="rounded-lg border border-orange-300 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/30 p-4"
  >
    <div class="flex items-start justify-between gap-4">
      <div>
        <h3
          class="text-sm font-semibold text-orange-900 dark:text-orange-200"
        >
          Suppression programmée
        </h3>
        <p class="mt-1 text-sm text-orange-800 dark:text-orange-300">
          Votre compte sera supprimé définitivement le
          <strong>{{ formattedDate }}</strong
          >. Vous pouvez annuler cette suppression à tout moment d'ici cette
          date.
        </p>
      </div>
      <button
        type="button"
        :disabled="loading"
        :class="[
          'inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium',
          'bg-orange-700 hover:bg-orange-800 text-white',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 dark:focus:ring-offset-dark-bg',
        ]"
        @click="emit('cancel')"
      >
        Annuler la suppression
      </button>
    </div>
  </div>
</template>
