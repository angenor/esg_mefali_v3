<script setup lang="ts">
import type { OfferIntermediarySummary } from '~/types/financing'

interface Props {
  intermediary: OfferIntermediarySummary
}

defineProps<Props>()
</script>

<template>
  <article class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5">
    <h3 class="text-base font-semibold text-gray-900 dark:text-white">
      {{ intermediary.name }}
    </h3>
    <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
      {{ intermediary.country }}
    </p>
    <div class="mt-3 flex flex-wrap gap-2">
      <span
        v-if="intermediary.organization_type"
        class="inline-flex items-center rounded-full bg-purple-100 dark:bg-purple-900/30 px-2.5 py-0.5 text-xs font-medium text-purple-700 dark:text-purple-300"
      >
        {{ intermediary.organization_type }}
      </span>
      <span
        v-if="intermediary.success_rate !== null && intermediary.success_rate !== undefined"
        class="inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300"
      >
        Taux de succès : {{ Math.round((intermediary.success_rate || 0) * 100) }}%
      </span>
    </div>
  </article>
</template>
