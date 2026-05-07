<script setup lang="ts">
// F09 — Badge de statut générique pour publication / vérification.
//
// Variants : draft (gris) | pending (jaune) | verified (bleu) | outdated (rouge)
// | published (vert) | revoked (rouge foncé).
//
// Dark mode obligatoire (CLAUDE.md).
import { computed } from 'vue'

interface Props {
  variant:
    | 'draft'
    | 'pending'
    | 'verified'
    | 'outdated'
    | 'published'
    | 'revoked'
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined,
})

const labelMap: Record<string, string> = {
  draft: 'Brouillon',
  pending: 'En attente',
  verified: 'Vérifié',
  outdated: 'Obsolète',
  published: 'Publié',
  revoked: 'Révoqué',
}

const text = computed(() => props.label ?? labelMap[props.variant] ?? props.variant)

const classes = computed(() => {
  switch (props.variant) {
    case 'draft':
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
    case 'pending':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200'
    case 'verified':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
    case 'outdated':
      return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
    case 'published':
      return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
    case 'revoked':
      return 'bg-red-200 text-red-900 dark:bg-red-950/60 dark:text-red-100'
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
  }
})
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="classes"
  >
    {{ text }}
  </span>
</template>
