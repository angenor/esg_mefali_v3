<script setup lang="ts">
// F20 — Barre de filtres pour /resources.
import type { ResourceFiltersQuery, ResourceType } from '~/types/resource'
import { RESOURCE_TYPE_LABELS } from '~/types/resource'

interface Props {
  modelValue: ResourceFiltersQuery
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [filters: ResourceFiltersQuery]
}>()

const TYPES: ResourceType[] = [
  'guide',
  'template_doc',
  'video',
  'faq',
  'intermediary_guide',
]

const CATEGORIES = ['governance', 'environment', 'social', 'financing', 'carbon']

function setType(type: ResourceType | undefined): void {
  emit('update:modelValue', { ...props.modelValue, type, page: 1 })
}

function setCategory(category: string | undefined): void {
  emit('update:modelValue', { ...props.modelValue, category, page: 1 })
}

function setQuery(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', { ...props.modelValue, q: value, page: 1 })
}
</script>

<template>
  <div
    class="rounded-lg border border-gray-200 bg-white p-4 dark:border-dark-border dark:bg-dark-card"
    role="search"
    aria-label="Filtres bibliothèque ressources"
  >
    <div class="mb-4">
      <label
        for="resource-search"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Rechercher
      </label>
      <input
        id="resource-search"
        type="text"
        :value="props.modelValue.q ?? ''"
        placeholder="Mot-clé (ex : gouvernance, BOAD)"
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-emerald-500 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
        @input="setQuery"
      />
    </div>

    <div class="mb-4">
      <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Type
      </p>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          :class="[
            'px-2.5 py-1 text-xs rounded-full border transition',
            !props.modelValue.type
              ? 'bg-emerald-600 border-emerald-600 text-white'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-dark-border dark:text-gray-300 dark:hover:bg-dark-hover',
          ]"
          @click="setType(undefined)"
        >
          Tous
        </button>
        <button
          v-for="t in TYPES"
          :key="t"
          type="button"
          :class="[
            'px-2.5 py-1 text-xs rounded-full border transition',
            props.modelValue.type === t
              ? 'bg-emerald-600 border-emerald-600 text-white'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-dark-border dark:text-gray-300 dark:hover:bg-dark-hover',
          ]"
          @click="setType(t)"
        >
          {{ RESOURCE_TYPE_LABELS[t] }}
        </button>
      </div>
    </div>

    <div>
      <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Catégorie
      </p>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          :class="[
            'px-2.5 py-1 text-xs rounded-full border transition',
            !props.modelValue.category
              ? 'bg-emerald-600 border-emerald-600 text-white'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-dark-border dark:text-gray-300 dark:hover:bg-dark-hover',
          ]"
          @click="setCategory(undefined)"
        >
          Toutes
        </button>
        <button
          v-for="c in CATEGORIES"
          :key="c"
          type="button"
          :class="[
            'px-2.5 py-1 text-xs rounded-full border transition',
            props.modelValue.category === c
              ? 'bg-emerald-600 border-emerald-600 text-white'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-dark-border dark:text-gray-300 dark:hover:bg-dark-hover',
          ]"
          @click="setCategory(c)"
        >
          {{ c }}
        </button>
      </div>
    </div>
  </div>
</template>
