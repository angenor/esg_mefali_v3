<script setup lang="ts">
/**
 * F10 — FormWidget : mini-formulaire 1-10 champs validable en un clic.
 *
 * Réf : FR-018, FR-023, US4.
 */
import { computed, ref, watch } from 'vue'
import { z } from 'zod'
import type {
  FormField,
  FormPayload,
  FormResponse,
  InteractiveQuestion,
} from '~/types/interactive-question'

interface Props {
  question: InteractiveQuestion
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'submit', payload: FormResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<FormPayload>(() => {
  const p = props.question.payload as FormPayload | undefined
  return p ?? {
    question_type: 'form',
    title: '',
    fields: [],
    submit_label: 'Enregistrer',
  }
})

const values = ref<Record<string, string | number | boolean | null>>({})
const errors = ref<Record<string, string>>({})

// Initialisation des valeurs par défaut
watch(
  () => payload.value.fields,
  (fields) => {
    const initial: Record<string, string | number | boolean | null> = {}
    for (const f of fields) {
      initial[f.name] = f.default ?? null
    }
    values.value = initial
  },
  { immediate: true },
)

function _zodSchemaFor(field: FormField): z.ZodTypeAny {
  let schema: z.ZodTypeAny
  switch (field.type) {
    case 'number':
    case 'money': {
      let s = z.number()
      if (field.validation?.min !== undefined && field.validation.min !== null) {
        s = s.min(field.validation.min)
      }
      if (field.validation?.max !== undefined && field.validation.max !== null) {
        s = s.max(field.validation.max)
      }
      schema = s
      break
    }
    case 'date':
      schema = z.string()
      break
    case 'select':
      schema = z.string()
      break
    default: {
      let s = z.string()
      if (field.validation?.min_length !== undefined && field.validation.min_length !== null) {
        s = s.min(field.validation.min_length)
      }
      if (field.validation?.max_length !== undefined && field.validation.max_length !== null) {
        s = s.max(field.validation.max_length)
      }
      if (field.validation?.pattern) {
        s = s.regex(new RegExp(field.validation.pattern))
      }
      schema = s
    }
  }
  if (!field.required) {
    schema = schema.optional().nullable()
  }
  return schema
}

function _validateField(field: FormField, value: unknown): string | null {
  try {
    _zodSchemaFor(field).parse(value)
    return null
  } catch (e) {
    if (e instanceof z.ZodError) {
      return e.issues[0]?.message ?? 'Champ invalide'
    }
    return 'Champ invalide'
  }
}

function onFieldInput(field: FormField, value: string | number | boolean | null) {
  values.value = { ...values.value, [field.name]: value }
  const err = _validateField(field, value)
  errors.value = { ...errors.value, [field.name]: err ?? '' }
}

const canSubmit = computed(() => {
  if (inputLocked.value) return false
  // Tous les champs requis doivent être remplis
  for (const f of payload.value.fields) {
    if (f.required) {
      const v = values.value[f.name]
      if (v === null || v === undefined || v === '') return false
    }
    if (errors.value[f.name]) return false
  }
  return true
})

function _doSubmit() {
  if (!canSubmit.value) return
  // Re-valider tous les champs
  let hasError = false
  const newErrors: Record<string, string> = {}
  for (const f of payload.value.fields) {
    const err = _validateField(f, values.value[f.name])
    if (err) {
      newErrors[f.name] = err
      hasError = true
    }
  }
  errors.value = newErrors
  if (hasError) return

  // Construire le summary_label : titre + 1-2 valeurs significatives
  const sigFields = payload.value.fields.slice(0, 3)
  const sigValues = sigFields
    .map(f => `${values.value[f.name] ?? ''}`)
    .filter(v => v.length > 0)
    .join(', ')
  const summary = sigValues ? `${payload.value.title} : ${sigValues}` : payload.value.title

  emit(
    'submit',
    {
      question_type: 'form',
      values: values.value,
      summary_label: summary,
    },
    `✓ ${summary}`,
  )
}

function inputType(field: FormField): string {
  if (field.type === 'date') return 'date'
  if (field.type === 'number' || field.type === 'money') return 'number'
  return 'text'
}
</script>

<template>
  <form
    class="space-y-3"
    role="form"
    :aria-label="payload.title"
    @submit.prevent="_doSubmit"
  >
    <h3 class="text-sm font-bold text-surface-text dark:text-surface-dark-text">
      {{ payload.title }}
    </h3>

    <div class="space-y-2 max-h-72 overflow-y-auto -mx-1 px-1">
      <label
        v-for="field in payload.fields"
        :key="field.name"
        class="block"
      >
        <span class="text-xs font-medium text-gray-700 dark:text-gray-300">
          {{ field.label }}
          <span v-if="field.required" class="text-red-500">*</span>
        </span>

        <!-- Textarea -->
        <textarea
          v-if="field.type === 'textarea'"
          :value="values[field.name] as string ?? ''"
          :placeholder="field.placeholder ?? undefined"
          :disabled="inputLocked"
          :data-testid="`form-${field.name}-${question.id}`"
          rows="3"
          class="mt-1 w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 resize-none"
          @input="(e) => onFieldInput(field, (e.target as HTMLTextAreaElement).value)"
        />

        <!-- Select -->
        <select
          v-else-if="field.type === 'select'"
          :value="values[field.name] as string ?? ''"
          :disabled="inputLocked"
          :data-testid="`form-${field.name}-${question.id}`"
          class="mt-1 w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          @change="(e) => onFieldInput(field, (e.target as HTMLSelectElement).value)"
        >
          <option value="" disabled>Sélectionner…</option>
          <option
            v-for="opt in field.validation?.options ?? []"
            :key="opt.id"
            :value="opt.id"
          >
            {{ opt.label }}
          </option>
        </select>

        <!-- Standard input (text/number/date/money) -->
        <input
          v-else
          :type="inputType(field)"
          :value="values[field.name] ?? ''"
          :placeholder="field.placeholder ?? undefined"
          :disabled="inputLocked"
          :data-testid="`form-${field.name}-${question.id}`"
          class="mt-1 w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          @input="(e) => {
            const target = e.target as HTMLInputElement
            const raw = target.value
            const v = field.type === 'number' || field.type === 'money'
              ? (raw === '' ? null : parseFloat(raw))
              : raw
            onFieldInput(field, v as string | number)
          }"
        />

        <p
          v-if="errors[field.name]"
          role="alert"
          class="text-xs text-red-600 dark:text-red-400 mt-1"
        >
          {{ errors[field.name] }}
        </p>
      </label>
    </div>

    <div class="flex items-center justify-between pt-1">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
        @click="emit('abandon-and-send', '')"
      >
        Annuler
      </button>
      <button
        type="submit"
        :disabled="!canSubmit"
        :data-testid="`form-submit-${question.id}`"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg transition-all"
      >
        {{ payload.submit_label }}
      </button>
    </div>
  </form>
</template>
