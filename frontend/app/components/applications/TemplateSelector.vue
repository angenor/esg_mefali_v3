<template>
  <div
    role="region"
    aria-labelledby="template-selector-heading"
    class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4 space-y-3"
  >
    <h3
      id="template-selector-heading"
      class="text-sm font-semibold text-surface-text dark:text-surface-dark-text"
    >
      Modèle de dossier
    </h3>

    <div v-if="loading" class="text-xs text-gray-500 dark:text-gray-400" role="status">
      Chargement des modèles…
    </div>

    <div
      v-else-if="error"
      class="text-xs text-red-600 dark:text-red-400"
      role="alert"
    >
      {{ error }}
    </div>

    <div v-else-if="!templates.length" class="text-xs text-gray-500 dark:text-gray-400">
      Aucun modèle publié pour cette offre.
      <button
        type="button"
        class="ml-1 underline hover:text-emerald-600 dark:hover:text-emerald-400"
        @click="$emit('request-template')"
      >
        Demander à un admin
      </button>
    </div>

    <div v-else class="space-y-2" role="radiogroup" aria-label="Sélection d'un modèle">
      <label
        v-for="template in templates"
        :key="template.id"
        class="flex items-start gap-3 p-3 rounded-md border cursor-pointer transition-colors"
        :class="
          modelValue === template.id
            ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
            : 'border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover'
        "
      >
        <input
          type="radio"
          :name="`template-${uid}`"
          :value="template.id"
          :checked="modelValue === template.id"
          class="mt-1"
          @change="$emit('update:modelValue', template.id)"
        />
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-surface-text dark:text-surface-dark-text">
            {{ template.name }}
          </div>
          <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {{ INSTRUMENT_LABELS[template.instrument_type] }} ·
            {{ LANGUAGE_LABELS[template.language] }} ·
            v{{ template.version }} ·
            {{ template.sections.length }} sections
          </div>
        </div>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  INSTRUMENT_LABELS,
  LANGUAGE_LABELS,
  type TemplateRead,
} from '~/types/template'

const props = defineProps<{
  modelValue: string | null
  templates: TemplateRead[]
  loading?: boolean
  error?: string | null
}>()

defineEmits<{
  'update:modelValue': [id: string]
  'request-template': []
}>()

const uid = computed(() => Math.random().toString(36).slice(2, 10))
</script>
