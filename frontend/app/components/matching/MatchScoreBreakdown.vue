<script setup lang="ts">
// F14 — MatchScoreBreakdown : graphe radar 5 axes (sector, esg, size,
// location, documents) en SVG natif. ARIA `role=img` + table fallback.

import { computed } from 'vue'
import type { MatchSubBreakdown } from '~/types/matching'

interface Props {
  breakdown: MatchSubBreakdown
  variant?: 'fund' | 'intermediary'
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'fund',
  title: 'Décomposition du score',
})

interface Axis {
  key: keyof Omit<MatchSubBreakdown, 'missingCriteria'>
  label: string
  value: number
}

const axes = computed<Axis[]>(() => [
  { key: 'sectorMatch', label: 'Secteur', value: clamp(props.breakdown.sectorMatch) },
  { key: 'esgMatch', label: 'ESG', value: clamp(props.breakdown.esgMatch) },
  { key: 'sizeMatch', label: 'Taille', value: clamp(props.breakdown.sizeMatch) },
  { key: 'locationMatch', label: 'Localisation', value: clamp(props.breakdown.locationMatch) },
  { key: 'documentsMatch', label: 'Documents', value: clamp(props.breakdown.documentsMatch) },
  { key: 'instrumentMatch', label: 'Instrument', value: clamp(props.breakdown.instrumentMatch) },
])

function clamp(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}

// Géométrie radar
const SIZE = 180
const CENTER = SIZE / 2
const RADIUS = 70
const RINGS = [0.25, 0.5, 0.75, 1]

function pointFor(index: number, ratio: number, total: number): string {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2
  const r = RADIUS * ratio
  const x = CENTER + Math.cos(angle) * r
  const y = CENTER + Math.sin(angle) * r
  return `${x.toFixed(2)},${y.toFixed(2)}`
}

const polygonPoints = computed(() =>
  axes.value
    .map((a, i) => pointFor(i, a.value / 100, axes.value.length))
    .join(' '),
)

const ringPolygons = computed(() =>
  RINGS.map((ring) => ({
    ratio: ring,
    points: axes.value
      .map((_, i) => pointFor(i, ring, axes.value.length))
      .join(' '),
  })),
)

const labelPositions = computed(() =>
  axes.value.map((a, i) => {
    const angle = (Math.PI * 2 * i) / axes.value.length - Math.PI / 2
    const r = RADIUS + 18
    return {
      label: a.label,
      value: a.value,
      x: CENTER + Math.cos(angle) * r,
      y: CENTER + Math.sin(angle) * r,
    }
  }),
)

const fillClass = computed(() =>
  props.variant === 'fund'
    ? 'fill-emerald-500/20 stroke-emerald-500 dark:fill-emerald-400/20 dark:stroke-emerald-400'
    : 'fill-blue-500/20 stroke-blue-500 dark:fill-blue-400/20 dark:stroke-blue-400',
)

const ariaLabel = computed(() => {
  const parts = axes.value
    .map((a) => `${a.label} ${a.value} sur 100`)
    .join(', ')
  return `${props.title}. ${parts}.`
})
</script>

<template>
  <div
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4"
    :data-testid="`match-score-breakdown-${variant}`"
  >
    <h3
      class="mb-3 text-sm font-semibold text-surface-text dark:text-surface-dark-text"
    >
      {{ title }}
    </h3>
    <div class="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
      <svg
        :viewBox="`0 0 ${SIZE} ${SIZE}`"
        class="w-44 h-44 shrink-0"
        role="img"
        :aria-label="ariaLabel"
      >
        <g aria-hidden="true">
          <polygon
            v-for="(ring, idx) in ringPolygons"
            :key="`ring-${idx}`"
            :points="ring.points"
            class="fill-none stroke-gray-200 dark:stroke-dark-border"
            stroke-width="1"
          />
          <line
            v-for="(label, i) in labelPositions"
            :key="`axis-${i}`"
            :x1="CENTER"
            :y1="CENTER"
            :x2="label.x"
            :y2="label.y"
            class="stroke-gray-200 dark:stroke-dark-border"
            stroke-width="1"
          />
          <polygon
            :points="polygonPoints"
            :class="fillClass"
            stroke-width="2"
          />
        </g>
        <g aria-hidden="true">
          <text
            v-for="(label, i) in labelPositions"
            :key="`lbl-${i}`"
            :x="label.x"
            :y="label.y"
            text-anchor="middle"
            dominant-baseline="middle"
            class="text-[10px] fill-gray-700 dark:fill-gray-300"
          >
            {{ label.label }}
          </text>
        </g>
      </svg>

      <ul class="text-xs space-y-1 flex-1">
        <li
          v-for="axis in axes"
          :key="axis.key"
          class="flex items-center justify-between gap-2"
        >
          <span class="text-gray-600 dark:text-gray-400">{{ axis.label }}</span>
          <span
            class="font-semibold tabular-nums text-surface-text dark:text-surface-dark-text"
          >
            {{ axis.value }}/100
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>
