<script setup lang="ts">
// F14 — BottleneckBadge : pastille colorée indiquant le goulot
// d'étranglement d'un match (fund / intermediary / balanced).

import { computed } from 'vue'
import type { MatchBottleneck } from '~/types/matching'

interface Props {
  bottleneck: MatchBottleneck
  fundScore?: number | null
  intermediaryScore?: number | null
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  fundScore: null,
  intermediaryScore: null,
  size: 'md',
})

interface Variant {
  label: string
  classes: string
  iconPath: string
  description: string
}

const variantById: Record<MatchBottleneck, Variant> = {
  fund: {
    label: 'Critères du fonds',
    classes:
      'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800',
    iconPath: 'M12 9v3m0 4h.01M5 19h14a2 2 0 001.84-2.75L13.74 4a2 2 0 00-3.48 0L3.16 16.25A2 2 0 005 19z',
    description: 'Le score du fonds limite votre éligibilité.',
  },
  intermediary: {
    label: 'Critères de l\'intermédiaire',
    classes:
      'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
    iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    description: 'Le score de l\'intermédiaire limite votre éligibilité.',
  },
  balanced: {
    label: 'Profil équilibré',
    classes:
      'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
    iconPath: 'M5 13l4 4L19 7',
    description: 'Fonds et intermédiaire sont alignés avec votre projet.',
  },
}

const variant = computed(() => variantById[props.bottleneck])

const ariaLabel = computed(() => {
  const parts: string[] = [variant.value.label]
  if (props.fundScore !== null && props.intermediaryScore !== null) {
    parts.push(
      `Score fonds ${props.fundScore} sur 100, score intermédiaire ${props.intermediaryScore} sur 100.`,
    )
  }
  parts.push(variant.value.description)
  return parts.join(' ')
})

const sizeClasses = computed(() =>
  props.size === 'sm' ? 'text-xs px-2 py-0.5 gap-1' : 'text-sm px-2.5 py-1 gap-1.5',
)
</script>

<template>
  <span
    role="status"
    :aria-label="ariaLabel"
    :data-testid="`bottleneck-badge-${bottleneck}`"
    :class="[
      'inline-flex items-center rounded-full border font-medium',
      sizeClasses,
      variant.classes,
    ]"
  >
    <svg
      class="w-3.5 h-3.5 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path :d="variant.iconPath" />
    </svg>
    <span>{{ variant.label }}</span>
  </span>
</template>
