<script setup lang="ts">
// F045 — MissingProjectCriteriaList : liste des criteres manquants avec source F01.
//
// Affiche jusqu'a 5 missing_criteria (cf. ProjectScoreBreakdown.missing_criteria)
// avec icone par kind + label FR + lien <SourceLink> si source_id present.

import type { MissingCriterion } from '~/types/projectMatching'

interface Props {
  criteria: MissingCriterion[]
  /** Titre de la liste (défaut : « Critères projet à renforcer »). */
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Critères projet à renforcer',
})

function iconForKind(kind: MissingCriterion['kind']): string {
  switch (kind) {
    case 'below_threshold':
      return '⚠️'
    case 'missing':
      return '◌'
    case 'wrong_value':
      return '✗'
    default:
      return '•'
  }
}

function classForKind(kind: MissingCriterion['kind']): string {
  switch (kind) {
    case 'below_threshold':
      return 'text-amber-600 dark:text-amber-400'
    case 'missing':
      return 'text-gray-500 dark:text-gray-400'
    case 'wrong_value':
      return 'text-rose-600 dark:text-rose-400'
    default:
      return 'text-gray-500 dark:text-gray-400'
  }
}
</script>

<template>
  <section
    v-if="criteria && criteria.length > 0"
    aria-labelledby="missing-criteria-title"
    class="rounded-xl border border-gray-200 bg-white p-4
           dark:border-dark-border dark:bg-dark-card"
  >
    <h3
      id="missing-criteria-title"
      class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3"
    >
      {{ title }}
    </h3>

    <ul class="space-y-2">
      <li
        v-for="(c, idx) in criteria.slice(0, 5)"
        :key="c.key + '-' + idx"
        class="flex items-start gap-2 text-sm"
      >
        <span
          :class="['flex-shrink-0 mt-0.5', classForKind(c.kind)]"
          aria-hidden="true"
        >
          {{ iconForKind(c.kind) }}
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-gray-800 dark:text-gray-200">{{ c.label_fr }}</p>
          <p
            v-if="c.current_value !== null && c.current_value !== undefined && c.target_value !== null && c.target_value !== undefined"
            class="mt-0.5 text-xs text-gray-500 dark:text-gray-400"
          >
            Actuel : {{ c.current_value }} — Cible : {{ c.target_value }}
          </p>
          <a
            v-if="c.source_id"
            :href="`/sources/${c.source_id}`"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-0.5 inline-block text-xs text-blue-600 hover:underline
                   dark:text-blue-400"
          >
            Voir la source
          </a>
        </div>
      </li>
    </ul>
  </section>
</template>
