<script setup lang="ts">
// F09 PRIO 3 — Carte synthétique pour le dashboard métriques admin.
//
// Affiche un titre, une valeur principale, une icône colorée et une
// liste optionnelle de sous-métriques (label / valeur).
import { computed } from 'vue'

interface SubMetric {
  label: string
  value: string | number
  highlight?: 'green' | 'red' | 'amber' | 'blue' | 'gray'
}

interface Props {
  title: string
  mainValue: string | number
  icon?: string
  color?: 'emerald' | 'rose' | 'amber' | 'blue' | 'violet' | 'gray'
  subMetrics?: SubMetric[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  color: 'emerald',
  icon: '',
  loading: false,
  subMetrics: () => [],
})

const COLOR_CLASSES = {
  emerald: 'from-emerald-500/10 to-emerald-500/5 dark:from-emerald-400/10 dark:to-emerald-400/5 border-emerald-200/40 dark:border-emerald-700/30',
  rose: 'from-rose-500/10 to-rose-500/5 dark:from-rose-400/10 dark:to-rose-400/5 border-rose-200/40 dark:border-rose-700/30',
  amber: 'from-amber-500/10 to-amber-500/5 dark:from-amber-400/10 dark:to-amber-400/5 border-amber-200/40 dark:border-amber-700/30',
  blue: 'from-blue-500/10 to-blue-500/5 dark:from-blue-400/10 dark:to-blue-400/5 border-blue-200/40 dark:border-blue-700/30',
  violet: 'from-violet-500/10 to-violet-500/5 dark:from-violet-400/10 dark:to-violet-400/5 border-violet-200/40 dark:border-violet-700/30',
  gray: 'from-gray-500/10 to-gray-500/5 dark:from-gray-400/10 dark:to-gray-400/5 border-gray-200/40 dark:border-gray-700/30',
}

const HIGHLIGHT_CLASSES = {
  green: 'text-emerald-700 dark:text-emerald-300',
  red: 'text-rose-700 dark:text-rose-300',
  amber: 'text-amber-700 dark:text-amber-300',
  blue: 'text-blue-700 dark:text-blue-300',
  gray: 'text-gray-600 dark:text-gray-400',
}

const cardClass = computed(
  () => `bg-gradient-to-br ${COLOR_CLASSES[props.color]}`,
)
</script>

<template>
  <div
    :class="[
      'rounded-2xl border p-5 shadow-sm transition-shadow hover:shadow-md',
      cardClass,
      'dark:bg-dark-card',
    ]"
    data-testid="admin-metrics-card"
  >
    <div class="flex items-start justify-between">
      <div>
        <h3
          class="text-sm font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide"
        >
          {{ title }}
        </h3>
        <p
          v-if="loading"
          class="mt-2 text-3xl font-bold text-gray-400 dark:text-gray-500"
        >
          —
        </p>
        <p
          v-else
          class="mt-2 text-3xl font-bold text-surface-text dark:text-surface-dark-text"
          data-testid="admin-metrics-card-main"
        >
          {{ mainValue }}
        </p>
      </div>
      <span
        v-if="icon"
        class="text-3xl"
        :aria-hidden="true"
      >
        {{ icon }}
      </span>
    </div>

    <ul
      v-if="subMetrics.length > 0"
      class="mt-4 space-y-1 text-xs"
    >
      <li
        v-for="sub in subMetrics"
        :key="sub.label"
        class="flex justify-between"
      >
        <span class="text-gray-600 dark:text-gray-400">{{ sub.label }}</span>
        <span
          :class="[
            'font-medium',
            sub.highlight ? HIGHLIGHT_CLASSES[sub.highlight] : 'text-surface-text dark:text-surface-dark-text',
          ]"
        >
          {{ sub.value }}
        </span>
      </li>
    </ul>
  </div>
</template>
