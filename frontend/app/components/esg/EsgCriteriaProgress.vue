<script setup lang="ts">
import SourceLink from '~/components/sources/SourceLink.vue'
import type { CriteriaScoreResponse, ESGPillar, PillarScoreResponse } from '~/types/esg'

const props = defineProps<{
  pillars: Record<ESGPillar, PillarScoreResponse>
  sourceIdByCriteria?: Record<string, string>
}>()

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

const pillarConfig: { key: ESGPillar; label: string; color: string; bgColor: string }[] = [
  { key: 'environment', label: 'Environnement', color: 'bg-emerald-500', bgColor: 'bg-emerald-100 dark:bg-emerald-900/30' },
  { key: 'social', label: 'Social', color: 'bg-blue-500', bgColor: 'bg-blue-100 dark:bg-blue-900/30' },
  { key: 'governance', label: 'Gouvernance', color: 'bg-violet-500', bgColor: 'bg-violet-100 dark:bg-violet-900/30' },
]

function barWidth(score: number, max: number): string {
  return `${Math.min((score / max) * 100, 100)}%`
}
</script>

<template>
  <div class="space-y-6">
    <div v-for="pillar in pillarConfig" :key="pillar.key">
      <h4 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3">
        {{ pillar.label }}
        <span class="text-gray-500 dark:text-gray-400 font-normal ml-2">
          {{ Math.round(pillars[pillar.key]?.score ?? 0) }}/100
        </span>
      </h4>
      <div class="space-y-2">
        <div
          v-for="criterion in (pillars[pillar.key]?.criteria ?? [])"
          :key="criterion.code"
          class="flex items-center gap-3"
        >
          <span class="text-xs font-mono text-gray-500 dark:text-gray-400 w-8 shrink-0">
            {{ criterion.code }}
          </span>
          <span class="text-xs text-gray-600 dark:text-gray-400 w-36 truncate shrink-0">
            {{ criterion.label }}
          </span>
          <div class="flex-1 h-2 rounded-full" :class="pillar.bgColor">
            <div
              class="h-full rounded-full transition-all duration-500"
              :class="pillar.color"
              :style="{ width: barWidth(criterion.score, criterion.max) }"
            />
          </div>
          <span class="text-xs font-medium text-surface-text dark:text-surface-dark-text w-10 text-right">
            {{ criterion.score }}/{{ criterion.max }}
          </span>
          <!-- F01 picto source cliquable -->
          <SourceLink
            v-if="sourceIdByCriteria && sourceIdByCriteria[criterion.code]"
            :source-id="sourceIdByCriteria[criterion.code] ?? null"
            aria-label="Voir la source de ce critere"
            @open="(id) => emit('open-source', id)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
