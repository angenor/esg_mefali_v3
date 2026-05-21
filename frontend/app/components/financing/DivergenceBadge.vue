<script setup lang="ts">
// F045 — DivergenceBadge : pastille colorée selon catégorie divergence (R6).

import { computed } from 'vue'
import type { DivergenceCategory } from '~/types/projectMatching'

interface Props {
  projectScore: number
  companyScore: number
  /** Optionnel : surcharge explicite (sinon calcule depuis les 2 scores). */
  category?: DivergenceCategory
  /** Texte FR detaille pour aria-describedby (parent fournit l'id). */
  tooltipText?: string
}

const props = defineProps<Props>()

const computedCategory = computed<DivergenceCategory>(() => {
  if (props.category) return props.category
  const diff = props.projectScore - props.companyScore
  if (Math.abs(diff) <= 15) return 'convergent'
  if (diff > 30) return 'projet_fort'
  if (-diff > 30) return 'entreprise_forte'
  return 'moyen'
})

const labelFr = computed(() => {
  switch (computedCategory.value) {
    case 'convergent':
      return 'Alignés'
    case 'projet_fort':
      return 'Projet vert, entreprise à renforcer'
    case 'entreprise_forte':
      return 'Entreprise forte, projet à renforcer'
    default:
      return 'Profils contrastés'
  }
})

const colorClass = computed(() => {
  switch (computedCategory.value) {
    case 'convergent':
      return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
    case 'projet_fort':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
    case 'entreprise_forte':
      return 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300'
    default:
      return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
  }
})

const ariaLabel = computed(() =>
  `Divergence : ${labelFr.value}. Score projet ${props.projectScore} sur 100, ` +
  `score entreprise ${props.companyScore} sur 100.`,
)
</script>

<template>
  <span
    :class="['inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium', colorClass]"
    role="status"
    :aria-label="ariaLabel"
    :title="tooltipText || ariaLabel"
  >
    <span aria-hidden="true">●</span>
    {{ labelFr }}
  </span>
</template>
