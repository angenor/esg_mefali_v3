<script setup lang="ts">
// F25 — État vide / aucun résultat du catalogue admin.
// Couvre 2 cas :
//   - mode='empty'   : onglet sans aucun élément en base ("Aucun élément
//                      enregistré dans cette catégorie").
//   - mode='no-match': filtre/recherche sans résultat (FR-012), bouton
//                      "Réinitialiser les filtres" émis vers le parent.
import { computed } from 'vue'

interface Props {
  mode?: 'empty' | 'no-match'
  query?: string | null
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'empty',
  query: null,
  label: 'éléments',
})

const emit = defineEmits<{
  (event: 'reset'): void
}>()

const title = computed(() => {
  if (props.mode === 'no-match') return 'Aucun résultat'
  return `Aucun ${props.label} enregistré dans cette catégorie`
})

const message = computed(() => {
  if (props.mode === 'no-match') {
    return props.query
      ? `Aucun résultat ne correspond à « ${props.query} ».`
      : 'Aucun résultat ne correspond aux filtres appliqués.'
  }
  return 'Quand des éléments seront créés, ils apparaîtront ici.'
})
</script>

<template>
  <div
    role="status"
    aria-live="polite"
    class="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card px-6 py-12 text-center"
  >
    <span aria-hidden="true" class="text-3xl">📭</span>
    <h3 class="text-base font-semibold text-surface-text dark:text-surface-dark-text">
      {{ title }}
    </h3>
    <p class="text-sm text-gray-600 dark:text-gray-400 max-w-md">
      {{ message }}
    </p>
    <button
      v-if="mode === 'no-match'"
      type="button"
      class="mt-2 inline-flex items-center gap-2 rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 dark:bg-red-800 dark:hover:bg-red-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-dark-card"
      @click="emit('reset')"
    >
      Réinitialiser les filtres
    </button>
  </div>
</template>
