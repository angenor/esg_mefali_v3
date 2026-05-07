<script setup lang="ts">
import { computed } from 'vue'
import type { OfferSummary } from '~/types/financing'

interface Props {
  offer: OfferSummary
}

const props = defineProps<Props>()

const processingTimeRange = computed(() => {
  const min = props.offer.effective_processing_time_days_min
  const max = props.offer.effective_processing_time_days_max
  if (!min && !max) return null
  if (min && max && min !== max) return `${min}-${max}j`
  return `${min || max}j`
})

const languageLabels: Record<string, string> = {
  FR: 'Français',
  EN: 'Anglais',
  PT: 'Portugais',
  AR: 'Arabe',
}
</script>

<template>
  <article
    class="group relative flex flex-col gap-3 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5 transition hover:border-blue-300 dark:hover:border-blue-500/50 hover:shadow-md"
  >
    <header class="flex items-start justify-between gap-3">
      <h3 class="text-base font-semibold text-gray-900 dark:text-white line-clamp-2">
        {{ offer.name }}
      </h3>
      <div class="flex flex-shrink-0 gap-1">
        <span
          v-for="lang in offer.accepted_languages"
          :key="lang"
          class="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/30 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300"
          :aria-label="`Langue acceptée : ${languageLabels[lang] || lang}`"
          :title="languageLabels[lang] || lang"
        >
          {{ lang }}
        </span>
      </div>
    </header>

    <div class="flex flex-wrap gap-2 text-xs">
      <span
        v-if="processingTimeRange"
        class="inline-flex items-center gap-1 rounded-full bg-gray-100 dark:bg-gray-700 px-2.5 py-1 text-gray-700 dark:text-gray-300"
        :aria-label="`Délai de traitement : ${processingTimeRange}`"
      >
        <span aria-hidden="true">⏱</span>
        {{ processingTimeRange }}
      </span>
      <span
        v-if="offer.publication_status === 'published'"
        class="inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-2.5 py-1 text-emerald-700 dark:text-emerald-300"
      >
        Publié
      </span>
    </div>

    <NuxtLink
      :to="`/financing/offers/${offer.id}`"
      class="absolute inset-0"
      :aria-label="`Voir le détail de l'offre ${offer.name}`"
    />

    <footer class="mt-auto flex items-center justify-between text-sm">
      <span class="text-gray-500 dark:text-gray-400">
        Voir le détail
      </span>
      <span
        class="text-blue-600 dark:text-blue-400 group-hover:translate-x-1 transition-transform"
        aria-hidden="true"
      >
        →
      </span>
    </footer>
  </article>
</template>
