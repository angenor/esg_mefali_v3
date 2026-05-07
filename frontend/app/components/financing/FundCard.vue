<script setup lang="ts">
import type { OfferFundSummary } from '~/types/financing'

interface Props {
  fund: OfferFundSummary
}

defineProps<Props>()
</script>

<template>
  <article class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5">
    <h3 class="text-base font-semibold text-gray-900 dark:text-white">
      {{ fund.name }}
    </h3>
    <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
      {{ fund.organization }}
    </p>
    <span
      v-if="fund.fund_type"
      class="mt-3 inline-flex items-center rounded-full bg-blue-100 dark:bg-blue-900/30 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300"
    >
      {{ fund.fund_type }}
    </span>
  </article>
</template>
