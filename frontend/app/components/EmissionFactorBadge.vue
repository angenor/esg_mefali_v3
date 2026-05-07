<script setup lang="ts">
// EmissionFactorBadge — F17
// Affiche un facteur d'emission avec son label, sa valeur et un picto Source
// cliquable. Variante "approximatif" affichee si le facteur a ete degrade
// (annee anterieure ou pays global).
//
// Compatible dark mode et accessible (role region + aria-label descriptif).

import { computed } from 'vue'
import SourceLink from '~/components/sources/SourceLink.vue'

interface FactorProp {
  code: string
  label: string
  value: number
  unit: string
  country?: string
  year?: number
}

interface SourceProp {
  id: string
  publisher?: string
  title?: string
  url?: string
  page?: number
}

interface Props {
  factor: FactorProp
  source: SourceProp | null
  isApproximate?: boolean
  fallbackReason?: 'year_older' | 'country_global' | null
}

const props = withDefaults(defineProps<Props>(), {
  isApproximate: false,
  fallbackReason: null,
})

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

function handleOpenSource(sourceId: string) {
  emit('open-source', sourceId)
}

const approximateTooltip = computed(() => {
  if (props.fallbackReason === 'year_older') {
    return "Facteur d'annee anterieure : la valeur la plus recente disponible a ete utilisee."
  }
  if (props.fallbackReason === 'country_global') {
    return 'Facteur generique regional : pays non couvert par le catalogue.'
  }
  return 'Facteur approximatif.'
})

const ariaLabel = computed(() => {
  return `Facteur d'emission : ${props.factor.label}`
})
</script>

<template>
  <div
    class="emission-factor-badge inline-flex items-center gap-2 px-2 py-1 rounded-md bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border"
    role="region"
    :aria-label="ariaLabel"
  >
    <span class="text-sm text-surface-text dark:text-surface-dark-text">
      {{ factor.label }}
    </span>
    <span class="font-mono text-xs text-gray-600 dark:text-gray-400">
      {{ factor.value }} {{ factor.unit }}
    </span>
    <SourceLink
      v-if="source && source.id"
      :source-id="source.id"
      :aria-label="`Voir la source du facteur ${factor.label}`"
      @open="handleOpenSource"
    />
    <span
      v-if="isApproximate"
      role="img"
      aria-label="Facteur approximatif"
      :title="approximateTooltip"
      class="inline-flex items-center justify-center w-4 h-4 text-amber-500 dark:text-amber-400"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        class="w-3.5 h-3.5"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fill-rule="evenodd"
          d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
          clip-rule="evenodd"
        />
      </svg>
    </span>
  </div>
</template>
