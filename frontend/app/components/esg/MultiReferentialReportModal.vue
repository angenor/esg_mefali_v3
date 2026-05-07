<script setup lang="ts">
/**
 * F13 — Modale « Générer un rapport PDF multi-référentiels » (US3).
 *
 * Affiche les checkboxes pour les référentiels disponibles + l'option
 * « Inclure annexe sources ». Désactive un référentiel si coverage < 50%.
 */
import { ref, computed, watch } from 'vue'
import type { ReferentialScore } from '~/types/esg'

interface Props {
  modelValue: boolean
  referentialScores: ReferentialScore[]
  isGenerating?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isGenerating: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'generate': [params: { referentials: string[]; include_appendix_sources: boolean }]
}>()

const selectedRefs = ref<Set<string>>(new Set(['mefali']))
const includeAppendix = ref(true)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      // Reset on open : Mefali coché par défaut
      selectedRefs.value = new Set(['mefali'])
      includeAppendix.value = true
    }
  },
)

function toggleRef(code: string, coverageInsufficient: boolean) {
  if (coverageInsufficient) return  // ignore le toggle si insuffisant
  if (selectedRefs.value.has(code)) {
    selectedRefs.value.delete(code)
  } else {
    selectedRefs.value.add(code)
  }
  selectedRefs.value = new Set(selectedRefs.value)
}

function close() {
  emit('update:modelValue', false)
}

function handleGenerate() {
  emit('generate', {
    referentials: Array.from(selectedRefs.value),
    include_appendix_sources: includeAppendix.value,
  })
}

const canGenerate = computed(() => selectedRefs.value.size > 0 && !props.isGenerating)
</script>

<template>
  <div
    v-if="modelValue"
    role="dialog"
    aria-modal="true"
    aria-labelledby="report-modal-title"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    @click.self="close"
  >
    <div class="max-w-md w-full rounded-lg bg-white dark:bg-dark-card p-6 shadow-xl">
      <h3
        id="report-modal-title"
        class="mb-4 text-lg font-semibold text-surface-text dark:text-surface-dark-text"
      >
        Générer un rapport PDF
      </h3>

      <p class="mb-4 text-sm text-gray-600 dark:text-gray-400">
        Sélectionnez les référentiels à inclure dans le rapport :
      </p>

      <div class="space-y-2 mb-4">
        <label
          v-for="score in referentialScores"
          :key="score.referential_code"
          class="flex items-center gap-2 text-sm cursor-pointer"
          :class="{ 'opacity-50 cursor-not-allowed': score.coverage_rate < 0.5 }"
        >
          <input
            type="checkbox"
            :checked="selectedRefs.has(score.referential_code)"
            :disabled="score.coverage_rate < 0.5"
            @change="toggleRef(score.referential_code, score.coverage_rate < 0.5)"
            class="h-4 w-4"
          />
          <span class="text-surface-text dark:text-surface-dark-text">
            {{ score.referential_name }}
          </span>
          <span
            v-if="score.coverage_rate < 0.5"
            class="text-xs text-orange-600 dark:text-orange-400"
          >
            (couverture {{ Math.round(score.coverage_rate * 100) }} %)
          </span>
        </label>
      </div>

      <label class="flex items-center gap-2 text-sm cursor-pointer mb-4">
        <input
          type="checkbox"
          v-model="includeAppendix"
          class="h-4 w-4"
        />
        <span class="text-surface-text dark:text-surface-dark-text">
          Inclure l'annexe « Sources et références »
        </span>
      </label>

      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 rounded-md border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-dark-hover transition"
          @click="close"
        >
          Annuler
        </button>
        <button
          type="button"
          class="flex-1 rounded-md bg-primary text-white px-3 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition"
          :disabled="!canGenerate"
          @click="handleGenerate"
        >
          <span v-if="isGenerating">Génération en cours…</span>
          <span v-else>Générer</span>
        </button>
      </div>
    </div>
  </div>
</template>
