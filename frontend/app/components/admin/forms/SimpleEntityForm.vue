<script setup lang="ts">
// F09 PRIO 3 — Form générique pour les sections catalogue admin simples.
//
// Accepte une définition de champs (FieldDef) et émet `submit` avec les
// valeurs collectées. Réutilisé par ReferentialForm, IndicatorForm,
// CriterionForm, EmissionFactorForm, SimulationFactorForm, etc.
import { reactive, watch } from 'vue'

export interface FieldDef {
  key: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'json'
  required?: boolean
  options?: { value: string; label: string }[]
  placeholder?: string
  helpText?: string
  min?: number
  max?: number
  rows?: number
}

interface Props {
  fields: FieldDef[]
  initialValues?: Record<string, unknown>
  submitLabel?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  initialValues: () => ({}),
  submitLabel: 'Enregistrer',
  loading: false,
})

const emit = defineEmits<{
  (e: 'submit', values: Record<string, unknown>): void
  (e: 'cancel'): void
}>()

const values = reactive<Record<string, unknown>>({ ...props.initialValues })

watch(
  () => props.initialValues,
  (newVals) => {
    for (const key of Object.keys(newVals)) {
      values[key] = newVals[key]
    }
  },
  { deep: true },
)

function onSubmit() {
  // Conversion JSON pour les champs `json`.
  const out: Record<string, unknown> = {}
  for (const field of props.fields) {
    let v = values[field.key]
    if (field.type === 'json' && typeof v === 'string') {
      try {
        v = JSON.parse(v)
      } catch {
        // laisse la string brute, le backend renverra une 422.
      }
    }
    if (field.type === 'number' && v !== '' && v !== null && v !== undefined) {
      v = Number(v)
    }
    if (v !== '' && v !== null && v !== undefined) {
      out[field.key] = v
    }
  }
  emit('submit', out)
}
</script>

<template>
  <form
    class="space-y-4"
    data-testid="admin-simple-form"
    @submit.prevent="onSubmit"
  >
    <div
      v-for="field in fields"
      :key="field.key"
      class="space-y-1"
    >
      <label
        :for="`field-${field.key}`"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text"
      >
        {{ field.label }}
        <span v-if="field.required" class="text-rose-500" aria-hidden="true">*</span>
      </label>

      <textarea
        v-if="field.type === 'textarea' || field.type === 'json'"
        :id="`field-${field.key}`"
        v-model="values[field.key]"
        :rows="field.rows ?? 4"
        :placeholder="field.placeholder ?? ''"
        :required="field.required"
        class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:focus:ring-emerald-400"
      />

      <select
        v-else-if="field.type === 'select'"
        :id="`field-${field.key}`"
        v-model="values[field.key]"
        :required="field.required"
        class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:focus:ring-emerald-400"
      >
        <option value="">— Choisir —</option>
        <option
          v-for="opt in field.options"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </option>
      </select>

      <input
        v-else
        :id="`field-${field.key}`"
        v-model="values[field.key]"
        :type="field.type"
        :placeholder="field.placeholder ?? ''"
        :required="field.required"
        :min="field.min"
        :max="field.max"
        class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:focus:ring-emerald-400"
      />

      <p
        v-if="field.helpText"
        class="text-xs text-gray-500 dark:text-gray-400"
      >
        {{ field.helpText }}
      </p>
    </div>

    <div class="flex items-center justify-end gap-2 pt-2">
      <button
        type="button"
        class="rounded-lg border border-gray-300 dark:border-dark-border px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-dark-hover"
        @click="emit('cancel')"
      >
        Annuler
      </button>
      <button
        type="submit"
        :disabled="loading"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="admin-form-submit"
      >
        {{ loading ? 'Enregistrement…' : submitLabel }}
      </button>
    </div>
  </form>
</template>
