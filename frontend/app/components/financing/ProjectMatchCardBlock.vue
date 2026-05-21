<script setup lang="ts">
// F045 — ProjectMatchCardBlock : carte de matching projet-centric pour SSE F11.
//
// Affiche 2 scores separes (project_score / company_score) + divergence FR
// + top 3 missing_criteria + sources F01. Dark mode complet, ARIA region.

import { computed } from 'vue'
import type { ProjectMatchCardBlockPayload } from '~/types/projectMatching'

interface Props {
  payload: ProjectMatchCardBlockPayload
}

const props = defineProps<Props>()

const emit = defineEmits<{
  navigate: [url: string]
}>()

function badgeClass(score: number): string {
  if (score >= 75) {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
  }
  if (score >= 50) {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
  }
  return 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300'
}

const projectScoreClass = computed(() => badgeClass(props.payload.project_score))
const companyScoreClass = computed(() => badgeClass(props.payload.company_score))

const ariaLabel = computed(() => {
  const inter = props.payload.intermediary_name
    ? ` via ${props.payload.intermediary_name}`
    : ''
  return (
    `Match projet : ${props.payload.fund_name}${inter}. ` +
    `Score projet ${props.payload.project_score} sur 100. ` +
    `Score entreprise ${props.payload.company_score} sur 100. ` +
    `${props.payload.divergence}.`
  )
})

function onClick(): void {
  emit('navigate', props.payload.fund_url)
}

function trackByKey<T extends { key: string }>(item: T): string {
  return item.key
}
</script>

<template>
  <article
    role="region"
    :aria-label="ariaLabel"
    class="rounded-xl border bg-white p-4 shadow-sm transition hover:shadow-md
           border-gray-200 dark:bg-dark-card dark:border-dark-border"
  >
    <header class="flex items-start justify-between gap-3 mb-3">
      <div class="min-w-0">
        <h3
          class="text-sm font-semibold text-surface-text dark:text-surface-dark-text truncate"
        >
          {{ payload.fund_name }}
        </h3>
        <p
          v-if="payload.intermediary_name"
          class="text-xs text-gray-600 dark:text-gray-400 truncate"
        >
          via {{ payload.intermediary_name }}
        </p>
      </div>
    </header>

    <div class="grid grid-cols-2 gap-2 mb-3" role="group" aria-label="Scores">
      <div class="flex flex-col items-start">
        <span class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Match projet
        </span>
        <span
          :class="['inline-flex items-center rounded px-2 py-0.5 text-sm font-semibold', projectScoreClass]"
        >
          {{ payload.project_score }}%
        </span>
      </div>
      <div class="flex flex-col items-start">
        <span class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Match entreprise
        </span>
        <span
          :class="['inline-flex items-center rounded px-2 py-0.5 text-sm font-semibold', companyScoreClass]"
        >
          {{ payload.company_score }}%
        </span>
      </div>
    </div>

    <p class="text-xs italic text-gray-700 dark:text-gray-300 mb-3">
      {{ payload.divergence }}
    </p>

    <ul
      v-if="payload.missing_criteria_top_3 && payload.missing_criteria_top_3.length > 0"
      class="text-xs text-gray-600 dark:text-gray-400 space-y-1 mb-3"
      aria-label="Critères manquants principaux"
    >
      <li
        v-for="m in payload.missing_criteria_top_3"
        :key="trackByKey(m)"
        class="flex items-start gap-1"
      >
        <span aria-hidden="true" class="text-amber-500 dark:text-amber-400">•</span>
        <span>{{ m.label_fr }}</span>
      </li>
    </ul>

    <div
      v-if="payload.sources && payload.sources.length > 0"
      class="flex flex-wrap gap-1 mb-3"
    >
      <a
        v-for="(src, idx) in payload.sources"
        :key="src.source_id ?? `src-${idx}`"
        :href="src.url ?? '#'"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-0.5 rounded border border-blue-200 bg-blue-50
               px-1.5 py-0.5 text-[10px] text-blue-700 hover:bg-blue-100
               dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-300
               dark:hover:bg-blue-900/50"
      >
        <span aria-hidden="true">📎</span>
        <span class="truncate max-w-[120px]">{{ src.source_name }}</span>
      </a>
    </div>

    <button
      type="button"
      class="w-full rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium
             text-white transition hover:bg-emerald-700
             focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2
             dark:bg-emerald-500 dark:hover:bg-emerald-400 dark:focus:ring-offset-dark-card"
      :aria-label="`Voir l'offre ${payload.fund_name}`"
      @click="onClick"
    >
      Voir l'offre
    </button>
  </article>
</template>
