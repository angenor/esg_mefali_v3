<script setup lang="ts">
/**
 * F13 — Sélecteur de référentiel ESG.
 *
 * Permet à la PME de basculer entre Mefali, GCF, IFC PS, BOAD ESS, GRI 2021.
 * Émet `update:modelValue` avec le code du référentiel sélectionné.
 */
import { computed } from 'vue'
import type { ReferentialOption } from '~/types/esg'

interface Props {
  options: ReferentialOption[]
  modelValue: string
  /** Désactive le sélecteur (ex : pendant un recalcul). */
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const selected = computed({
  get: () => props.modelValue,
  set: (val: string) => emit('update:modelValue', val),
})
</script>

<template>
  <label class="flex items-center gap-2 text-sm">
    <span class="font-medium text-surface-text dark:text-surface-dark-text">
      Référentiel :
    </span>
    <select
      v-model="selected"
      :disabled="disabled"
      role="listbox"
      aria-label="Sélectionner un référentiel ESG"
      class="rounded-md border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <option
        v-for="opt in options"
        :key="opt.code"
        :value="opt.code"
        role="option"
      >
        {{ opt.name }}
      </option>
    </select>
  </label>
</template>
