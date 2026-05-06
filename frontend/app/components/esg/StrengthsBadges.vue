<script setup lang="ts">
import SourceLink from '~/components/sources/SourceLink.vue'
import type { ESGStrength } from '~/types/esg'

defineProps<{
  strengths: ESGStrength[]
  sourceIdByCriteria?: Record<string, string>
}>()

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

const pillarColors: Record<string, string> = {
  environment: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  social: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  governance: 'bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300',
}
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <div
      v-for="strength in strengths"
      :key="strength.criteria_code"
      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium"
      :class="pillarColors[strength.pillar] ?? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
      </svg>
      <span>{{ strength.title }}</span>
      <span class="text-xs opacity-75">{{ strength.score }}/10</span>
      <!-- F01 picto source cliquable -->
      <SourceLink
        v-if="sourceIdByCriteria && sourceIdByCriteria[strength.criteria_code]"
        :source-id="sourceIdByCriteria[strength.criteria_code] ?? null"
        aria-label="Voir la source de ce point fort"
        @open="(id) => emit('open-source', id)"
      />
    </div>
    <p
      v-if="strengths.length === 0"
      class="text-sm text-gray-500 dark:text-gray-400 italic"
    >
      Aucun point fort identifie pour le moment.
    </p>
  </div>
</template>
