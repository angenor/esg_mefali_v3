<template>
  <article
    class="p-3 bg-gray-50 dark:bg-dark-input border border-gray-200 dark:border-dark-border rounded-md"
    aria-label="Indicateur clé"
  >
    <p class="text-xs uppercase text-gray-500 dark:text-gray-400">
      {{ label }}
    </p>
    <p
      class="mt-1 text-lg font-semibold text-surface-text dark:text-surface-dark-text"
    >
      {{ value }}
    </p>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: string
}>()
</script>
