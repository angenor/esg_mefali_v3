<script setup lang="ts">
/**
 * F047 — Choix du référentiel cible (IFC PS / GCF ESS / BOAD ESS).
 * ARIA radiogroup, dark mode, descriptions FR.
 */
import { computed } from 'vue'
import type { EsgReferentialRef } from '~/types/projectEsg'

interface Props {
  referentials: EsgReferentialRef[]
  modelValue: string | null
  disabled?: boolean
}
const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const selected = computed({
  get: () => props.modelValue,
  set: (v: string | null) => {
    if (v) emit('update:modelValue', v)
  },
})

function selectRef(id: string) {
  if (!props.disabled) selected.value = id
}
</script>

<template>
  <div
    role="radiogroup"
    aria-label="Choix du référentiel ESG-projet"
    class="grid gap-3 md:grid-cols-3"
  >
    <button
      v-for="ref in referentials"
      :key="ref.id"
      type="button"
      role="radio"
      :aria-checked="selected === ref.id"
      :disabled="disabled"
      :class="[
        'text-left p-4 rounded-lg ring-1 transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500',
        selected === ref.id
          ? 'bg-emerald-50 dark:bg-emerald-900/30 ring-emerald-400 dark:ring-emerald-600'
          : 'bg-white dark:bg-dark-card ring-gray-200 dark:ring-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover',
        disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
      ]"
      @click="selectRef(ref.id)"
    >
      <div class="font-semibold text-surface-text dark:text-surface-dark-text">
        {{ ref.label }}
      </div>
      <div class="mt-1 text-xs text-gray-600 dark:text-gray-400">
        {{ ref.description }}
      </div>
      <div class="mt-2 text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-500">
        {{ ref.code }}
      </div>
    </button>
  </div>
</template>
