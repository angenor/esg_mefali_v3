<script setup lang="ts">
// SourceLink : picto inline cliquable rendu a cote d'un chiffre/score/critere.
// Au clic, declenche l'ouverture d'une SourceModal (gere par le parent).

interface Props {
  sourceId: string | null
  ariaLabel?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  open: [sourceId: string]
}>()

function handleClick() {
  if (props.sourceId) {
    emit('open', props.sourceId)
  }
}
</script>

<template>
  <button
    v-if="sourceId"
    type="button"
    class="inline-flex items-center justify-center w-4 h-4 ml-1 align-middle text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 dark:focus:ring-offset-dark-card rounded"
    :aria-label="ariaLabel || 'Voir la source de cette donnee'"
    @click.stop="handleClick"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="w-3.5 h-3.5"
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
    >
      <path
        d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"
      />
      <path
        d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z"
      />
    </svg>
  </button>
</template>
