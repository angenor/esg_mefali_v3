<script setup lang="ts">
// F25 — Badge "Incohérence détectée" (D5 research) :
//   - fond/intermédiaire/offre publié sans source obligatoire (F01)
//   - liaison fonds × intermédiaire dont accreditation_to est dépassée
//
// L'attribut `tooltip` peut être passé pour expliquer la cause spécifique.
interface Props {
  tooltip?: string
}

withDefaults(defineProps<Props>(), {
  tooltip: 'Cet élément présente une incohérence (cf. règles catalogue).',
})
</script>

<template>
  <span
    role="img"
    aria-label="Incohérence détectée"
    :title="tooltip"
    class="inline-flex items-center gap-1 rounded-full bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5 text-xs font-medium text-amber-800 dark:text-amber-200 ring-1 ring-amber-300 dark:ring-amber-700"
  >
    <span aria-hidden="true">⚠️</span>
    Incohérence
  </span>
</template>
