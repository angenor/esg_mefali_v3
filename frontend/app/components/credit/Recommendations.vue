<script setup lang="ts">
import SourceLink from '~/components/sources/SourceLink.vue'

defineProps<{
  recommendations: Array<{
    action: string
    impact: string
    category: string
    source_id?: string | null
  }>
}>()

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

function impactBadge(impact: string): string {
  if (impact === 'high') return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
  if (impact === 'medium') return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
  return 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
}

function impactLabel(impact: string): string {
  if (impact === 'high') return 'Eleve'
  if (impact === 'medium') return 'Moyen'
  return 'Faible'
}

function categoryIcon(category: string): string {
  if (category === 'solvability') return '📊'
  if (category === 'green_impact') return '🌿'
  if (category === 'engagement') return '🤝'
  if (category === 'coverage') return '📋'
  return '💡'
}
</script>

<template>
  <div class="space-y-3">
    <div
      v-for="(rec, index) in recommendations"
      :key="index"
      class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
    >
      <span class="text-lg shrink-0">{{ categoryIcon(rec.category) }}</span>
      <div class="flex-1 min-w-0">
        <p class="text-sm text-gray-700 dark:text-gray-300">
          {{ rec.action }}
          <!-- F01 picto source cliquable -->
          <SourceLink
            v-if="rec.source_id"
            :source-id="rec.source_id"
            aria-label="Voir la source de cette recommandation"
            @open="(id) => emit('open-source', id)"
          />
        </p>
      </div>
      <span
        class="text-xs font-medium px-2 py-0.5 rounded-full shrink-0"
        :class="impactBadge(rec.impact)"
      >
        {{ impactLabel(rec.impact) }}
      </span>
    </div>
    <p v-if="recommendations.length === 0" class="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
      Aucune recommandation — votre score est excellent !
    </p>
  </div>
</template>
