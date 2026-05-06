<script setup lang="ts">
import SourceLink from '~/components/sources/SourceLink.vue'
import type { ESGRecommendation } from '~/types/esg'

defineProps<{
  recommendations: ESGRecommendation[]
  sourceIdByCriteria?: Record<string, string>
}>()

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

const impactColors: Record<string, string> = {
  high: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  medium: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  low: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
}

const effortLabels: Record<string, string> = {
  high: 'Effort eleve',
  medium: 'Effort moyen',
  low: 'Effort faible',
}

const impactLabels: Record<string, string> = {
  high: 'Impact eleve',
  medium: 'Impact moyen',
  low: 'Impact faible',
}
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-200 dark:border-dark-border">
          <th class="text-left py-3 px-2 font-semibold text-gray-600 dark:text-gray-400">#</th>
          <th class="text-left py-3 px-2 font-semibold text-gray-600 dark:text-gray-400">Action</th>
          <th class="text-left py-3 px-2 font-semibold text-gray-600 dark:text-gray-400">Pilier</th>
          <th class="text-left py-3 px-2 font-semibold text-gray-600 dark:text-gray-400">Impact</th>
          <th class="text-left py-3 px-2 font-semibold text-gray-600 dark:text-gray-400">Effort</th>
          <th class="text-left py-3 px-2 font-semibold text-gray-600 dark:text-gray-400">Delai</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="rec in recommendations"
          :key="rec.criteria_code"
          class="border-b border-gray-100 dark:border-dark-border/50 hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors"
        >
          <td class="py-3 px-2 font-medium text-surface-text dark:text-surface-dark-text">
            {{ rec.priority }}
          </td>
          <td class="py-3 px-2">
            <div class="font-medium text-surface-text dark:text-surface-dark-text">
              {{ rec.title }}
              <!-- F01 picto source cliquable -->
              <SourceLink
                v-if="sourceIdByCriteria && sourceIdByCriteria[rec.criteria_code]"
                :source-id="sourceIdByCriteria[rec.criteria_code] ?? null"
                aria-label="Voir la source de cette recommandation"
                @open="(id) => emit('open-source', id)"
              />
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {{ rec.description }}
            </div>
          </td>
          <td class="py-3 px-2">
            <span class="text-xs font-medium capitalize text-gray-600 dark:text-gray-400">
              {{ rec.pillar === 'environment' ? 'Env.' : rec.pillar === 'social' ? 'Social' : 'Gouv.' }}
            </span>
          </td>
          <td class="py-3 px-2">
            <span
              class="inline-block px-2 py-0.5 rounded text-xs font-medium"
              :class="impactColors[rec.impact] ?? 'bg-gray-100 dark:bg-gray-700'"
            >
              {{ impactLabels[rec.impact] ?? rec.impact }}
            </span>
          </td>
          <td class="py-3 px-2 text-xs text-gray-600 dark:text-gray-400">
            {{ effortLabels[rec.effort] ?? rec.effort }}
          </td>
          <td class="py-3 px-2 text-xs text-gray-600 dark:text-gray-400">
            {{ rec.timeline }}
          </td>
        </tr>
      </tbody>
    </table>
    <p
      v-if="recommendations.length === 0"
      class="text-sm text-gray-500 dark:text-gray-400 italic py-4 text-center"
    >
      Aucune recommandation disponible.
    </p>
  </div>
</template>
