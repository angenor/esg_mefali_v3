<script setup lang="ts">
import SourceLink from '~/components/sources/SourceLink.vue'

// Carte de score synthétique pour le dashboard
interface ScoreSourceRef {
  source_id: string
  title?: string
  publisher?: string | null
  version?: string | null
  url?: string | null
}

interface Props {
  label: string
  score: number | null
  grade: string | null
  icon: string
  trend?: string | null
  subtitle?: string | null
  sourceId?: string | null
  // F21 (US4) — Sources multiples F01 cliquables.
  sources?: ScoreSourceRef[] | null
}

const props = withDefaults(defineProps<Props>(), {
  trend: null,
  subtitle: null,
  sourceId: null,
  sources: null,
})

// F21 — Détecter l'absence de sourçage : badge « Non sourcé ».
const hasSources = computed(
  () =>
    !!(props.sourceId || (props.sources && props.sources.length > 0)),
)

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

// Couleur du badge de grade
function gradeColor(grade: string | null): string {
  if (!grade) return 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
  if (grade.startsWith('A')) return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
  if (grade.startsWith('B')) return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
  if (grade.startsWith('C')) return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
  return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
}

// Couleur du score
function scoreColor(score: number | null): string {
  if (score === null) return 'text-gray-400 dark:text-gray-600'
  if (score >= 80) return 'text-green-600 dark:text-green-400'
  if (score >= 60) return 'text-blue-600 dark:text-blue-400'
  if (score >= 40) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}
</script>

<template>
  <div
    class="bg-white dark:bg-dark-card rounded-xl shadow-sm border border-gray-200 dark:border-dark-border p-5 flex flex-col gap-3"
  >
    <!-- En-tête -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-xl">{{ icon }}</span>
        <span class="text-sm font-medium text-gray-600 dark:text-gray-400">{{ label }}</span>
      </div>
      <!-- Grade badge -->
      <span
        v-if="grade"
        :class="['text-xs font-bold px-2 py-0.5 rounded-full', gradeColor(grade)]"
      >
        {{ grade }}
      </span>
    </div>

    <!-- Score principal -->
    <div v-if="score !== null" class="flex items-end gap-2">
      <span :class="['text-3xl font-bold', scoreColor(score)]">{{ Math.round(score) }}</span>
      <span class="text-sm text-gray-400 dark:text-gray-600 mb-1">/100</span>
      <!-- Tendance -->
      <span v-if="trend === 'up'" class="text-green-500 text-lg mb-1" title="En hausse">↑</span>
      <span v-else-if="trend === 'down'" class="text-red-500 text-lg mb-1" title="En baisse">↓</span>
      <!-- F01 picto source cliquable (legacy single source) -->
      <SourceLink
        v-if="sourceId"
        :source-id="sourceId"
        :aria-label="`Voir la source du score ${label}`"
        @open="(id) => emit('open-source', id)"
      />
      <!-- F21 (US4) — Sources multiples cliquables -->
      <template v-if="!sourceId && sources && sources.length > 0">
        <SourceLink
          v-for="src in sources"
          :key="src.source_id"
          :source-id="src.source_id"
          :aria-label="`Voir la source ${src.title || src.source_id} du score ${label}`"
          @open="(id) => emit('open-source', id)"
        />
      </template>
      <!-- F21 (US4) — Badge « Non sourcé » -->
      <span
        v-if="score !== null && !hasSources"
        class="ml-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
        data-testid="score-unsourced-badge"
        aria-label="Score non sourcé"
      >Non sourcé</span>
    </div>

    <!-- État vide -->
    <div v-else class="flex flex-col gap-1">
      <span class="text-2xl font-bold text-gray-300 dark:text-gray-700">—</span>
      <span class="text-xs text-gray-400 dark:text-gray-600">Aucune donnée</span>
    </div>

    <!-- Sous-titre -->
    <p v-if="subtitle" class="text-xs text-gray-500 dark:text-gray-500">{{ subtitle }}</p>

    <!-- Slot pour mini graphique -->
    <slot />
  </div>
</template>
