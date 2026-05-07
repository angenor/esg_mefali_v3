<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  STATUS_LABELS,
  STATUS_VALUES,
  type ProjectStatus,
} from '~/types/project'

interface Props {
  modelValue: ProjectStatus
  statuses?: ProjectStatus[]
  disabled?: boolean
  id?: string
}

const props = withDefaults(defineProps<Props>(), {
  statuses: () => STATUS_VALUES,
  disabled: false,
  id: 'project-status-selector',
})

const emit = defineEmits<{
  'update:modelValue': [value: ProjectStatus]
}>()

const open = ref(false)

const currentLabel = computed(
  () => STATUS_LABELS[props.modelValue] || props.modelValue,
)

function selectStatus(status: ProjectStatus) {
  emit('update:modelValue', status)
  open.value = false
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    open.value = !open.value
  }
  if (e.key === 'Escape') {
    open.value = false
  }
}
</script>

<template>
  <div class="relative" @keydown="onKeyDown">
    <button
      :id="id"
      type="button"
      role="combobox"
      :aria-expanded="open"
      aria-haspopup="listbox"
      aria-label="Sélecteur de statut du projet"
      :disabled="disabled"
      class="w-full flex items-center justify-between px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-brand-green"
      @click="open = !open"
    >
      <span>{{ currentLabel }}</span>
      <svg
        class="w-4 h-4 text-gray-500 dark:text-gray-400"
        :class="{ 'rotate-180': open }"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fill-rule="evenodd"
          d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0l-4.25-4.39a.75.75 0 01.02-1.06z"
          clip-rule="evenodd"
        />
      </svg>
    </button>
    <ul
      v-if="open"
      role="listbox"
      class="absolute z-10 mt-1 w-full rounded-md bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border shadow-lg max-h-60 overflow-auto"
    >
      <li
        v-for="status in statuses"
        :key="status"
        role="option"
        :aria-selected="status === modelValue"
        class="px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-hover text-surface-text dark:text-surface-dark-text"
        :class="{
          'bg-emerald-50 dark:bg-emerald-900/20': status === modelValue,
        }"
        @click="selectStatus(status)"
      >
        {{ STATUS_LABELS[status] }}
      </li>
    </ul>
  </div>
</template>
