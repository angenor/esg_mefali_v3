<script setup lang="ts">
// F14 — MissingCriteriaList : liste compacte des critères manquants
// avec <SourceLink> F01 cliquable. Émet `open-source` au parent.

import SourceLink from '~/components/sources/SourceLink.vue'
import type { MissingCriterion } from '~/types/matching'

interface Props {
  criteria: MissingCriterion[]
  title?: string
}

withDefaults(defineProps<Props>(), {
  title: 'Critères manquants',
})

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

function onOpenSource(sourceId: string) {
  emit('open-source', sourceId)
}
</script>

<template>
  <section
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4"
    aria-labelledby="missing-criteria-heading"
    data-testid="matching-missing-criteria"
  >
    <h3
      id="missing-criteria-heading"
      class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3"
    >
      {{ title }} ({{ criteria.length }})
    </h3>

    <p
      v-if="criteria.length === 0"
      class="text-sm text-gray-500 dark:text-gray-400"
    >
      Aucun critère manquant détecté.
    </p>

    <ul v-else role="list" class="space-y-2 text-sm">
      <li
        v-for="(criterion, idx) in criteria"
        :key="`${criterion.indicatorId ?? criterion.label}-${idx}`"
        class="flex items-start justify-between gap-2 rounded border border-gray-100 dark:border-dark-border/60 bg-gray-50 dark:bg-dark-input/40 px-3 py-2"
        :data-testid="`missing-criterion-${idx}`"
      >
        <span class="text-surface-text dark:text-surface-dark-text">
          {{ criterion.label }}
          <span
            v-if="criterion.indicatorCode"
            class="ml-1 text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400"
          >
            ({{ criterion.indicatorCode }})
          </span>
        </span>
        <SourceLink
          v-if="criterion.sourceId"
          :source-id="criterion.sourceId"
          :aria-label="`Voir la source pour ${criterion.label}`"
          @open="onOpenSource"
        />
      </li>
    </ul>
  </section>
</template>
