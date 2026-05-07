<script setup lang="ts">
// F11 — MatchCardBlock : carte projet ↔ offre cliquable.
// Rendu inline dans le chat avec score circulaire SVG, range montant,
// timeline, badges instruments, compteur critères manquants, CTA Explorer.

import { computed, ref } from 'vue'
import type { MatchCardBlockProps } from '~/types/richblocks'

const props = defineProps<MatchCardBlockProps>()

const emit = defineEmits<{
  navigate: [url: string]
}>()

// Initiales pour placeholder logo (2 premières lettres mots de chaque nom)
function getInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  if (words.length === 1) return (words[0]?.slice(0, 2) ?? '?').toUpperCase()
  return ((words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')).toUpperCase()
}

const fundInitials = computed(() => getInitials(props.fundName))
const intermediaryInitials = computed(() => getInitials(props.intermediaryName))

// Score circulaire (cercle SVG)
const SCORE_RADIUS = 24
const SCORE_CIRCUMFERENCE = 2 * Math.PI * SCORE_RADIUS

const scoreDashOffset = computed(() => {
  const ratio = props.compatibilityScore / 100
  return SCORE_CIRCUMFERENCE * (1 - ratio)
})

const scoreColorClass = computed(() => {
  if (props.compatibilityScore >= 75) return 'stroke-emerald-500 dark:stroke-emerald-400'
  if (props.compatibilityScore >= 50) return 'stroke-amber-500 dark:stroke-amber-400'
  return 'stroke-rose-500 dark:stroke-rose-400'
})

const scoreTextColorClass = computed(() => {
  if (props.compatibilityScore >= 75) return 'text-emerald-700 dark:text-emerald-300'
  if (props.compatibilityScore >= 50) return 'text-amber-700 dark:text-amber-300'
  return 'text-rose-700 dark:text-rose-300'
})

const breakdownTooltip = computed(() => {
  if (!props.compatibilityBreakdown) return ''
  return Object.entries(props.compatibilityBreakdown)
    .map(([k, v]) => `${k}: ${v}`)
    .join(' | ')
})

const ariaLabel = computed(() => {
  return [
    'Carte de matching projet-offre',
    `${props.fundName} via ${props.intermediaryName}`,
    `score ${props.compatibilityScore} sur 100`,
    `${props.amountRange}, ${props.timeline}`,
    props.missingCriteriaCount > 0
      ? `${props.missingCriteriaCount} critère(s) manquant(s)`
      : 'tous critères couverts',
  ].join(', ')
})

function handleCtaClick() {
  emit('navigate', props.drilldownUrl)
}

const showBreakdown = ref(false)
</script>

<template>
  <div
    data-test="match-card-root"
    class="match-card-block my-3 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4 transition-all hover:shadow-md"
    :aria-label="ariaLabel"
  >
    <!-- Header : 2 logos + score circulaire -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <!-- Logo fonds -->
        <div
          class="flex-shrink-0 w-12 h-12 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center overflow-hidden border border-emerald-200 dark:border-emerald-800"
          :aria-label="`Logo ${fundName}`"
        >
          <img
            v-if="fundLogoUrl"
            :src="fundLogoUrl"
            :alt="fundName"
            class="w-full h-full object-contain"
            loading="lazy"
          >
          <span
            v-else
            class="text-sm font-bold text-emerald-700 dark:text-emerald-300"
          >
            {{ fundInitials }}
          </span>
        </div>

        <!-- Logo intermédiaire -->
        <div
          class="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center overflow-hidden border border-blue-200 dark:border-blue-800"
          :aria-label="`Logo ${intermediaryName}`"
        >
          <img
            v-if="intermediaryLogoUrl"
            :src="intermediaryLogoUrl"
            :alt="intermediaryName"
            class="w-full h-full object-contain"
            loading="lazy"
          >
          <span
            v-else
            class="text-xs font-bold text-blue-700 dark:text-blue-300"
          >
            {{ intermediaryInitials }}
          </span>
        </div>
      </div>

      <!-- Noms -->
      <div class="flex-1 min-w-0">
        <p class="text-sm font-semibold text-gray-900 dark:text-surface-dark-text truncate">
          {{ fundName }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
          via {{ intermediaryName }}
        </p>
      </div>

      <!-- Score circulaire -->
      <div
        class="relative flex-shrink-0"
        :title="breakdownTooltip"
        @mouseenter="showBreakdown = true"
        @mouseleave="showBreakdown = false"
        @focusin="showBreakdown = true"
        @focusout="showBreakdown = false"
      >
        <svg width="60" height="60" viewBox="0 0 60 60" aria-hidden="true">
          <!-- Cercle de fond -->
          <circle
            cx="30"
            cy="30"
            :r="SCORE_RADIUS"
            fill="none"
            class="stroke-gray-200 dark:stroke-dark-border"
            stroke-width="4"
          />
          <!-- Cercle progress -->
          <circle
            cx="30"
            cy="30"
            :r="SCORE_RADIUS"
            fill="none"
            :class="scoreColorClass"
            stroke-width="4"
            stroke-linecap="round"
            :stroke-dasharray="SCORE_CIRCUMFERENCE"
            :stroke-dashoffset="scoreDashOffset"
            transform="rotate(-90 30 30)"
            class-bonus="transition-all duration-500"
          />
          <text
            x="30"
            y="35"
            text-anchor="middle"
            class="text-sm font-bold"
            :class="scoreTextColorClass"
            fill="currentColor"
          >
            {{ compatibilityScore }}
          </text>
        </svg>
        <!-- Tooltip décomposition (hidden by default, accessible via title attribute) -->
        <div
          v-if="showBreakdown && compatibilityBreakdown"
          class="absolute right-0 top-full mt-1 z-10 px-2 py-1 text-xs bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 rounded shadow-lg whitespace-nowrap"
          role="tooltip"
        >
          <span
            v-for="(v, k) in compatibilityBreakdown"
            :key="k"
            class="block"
          >
            {{ k }}: {{ v }}
          </span>
        </div>
      </div>
    </div>

    <!-- Body : range / timeline / instruments -->
    <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
      <div>
        <p class="text-gray-500 dark:text-gray-400">Montant</p>
        <p class="font-medium text-gray-900 dark:text-surface-dark-text">
          {{ amountRange }}
        </p>
      </div>
      <div>
        <p class="text-gray-500 dark:text-gray-400">Délai</p>
        <p class="font-medium text-gray-900 dark:text-surface-dark-text">
          {{ timeline }}
        </p>
      </div>
    </div>

    <!-- Badges instruments -->
    <div class="mt-2 flex flex-wrap gap-1">
      <span
        v-for="inst in instruments"
        :key="inst"
        class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300"
      >
        {{ inst }}
      </span>
    </div>

    <!-- Footer : compteur critères + CTA -->
    <div class="mt-3 flex items-center justify-between">
      <div class="text-xs">
        <span
          v-if="missingCriteriaCount > 0"
          class="text-amber-700 dark:text-amber-400"
        >
          {{ missingCriteriaCount }} critère{{ missingCriteriaCount > 1 ? 's' : '' }} manquant{{ missingCriteriaCount > 1 ? 's' : '' }}
        </span>
        <span
          v-else
          class="text-emerald-700 dark:text-emerald-400"
        >
          Tous critères couverts
        </span>
      </div>

      <button
        type="button"
        data-test="match-card-cta"
        class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-emerald-600 dark:bg-emerald-700 text-white hover:bg-emerald-700 dark:hover:bg-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 dark:focus:ring-offset-dark-card transition-colors"
        @click="handleCtaClick"
      >
        {{ ctaLabel }} →
      </button>
    </div>
  </div>
</template>
