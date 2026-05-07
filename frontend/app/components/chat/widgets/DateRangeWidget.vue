<script setup lang="ts">
/**
 * F10 — DateRangeWidget : saisie intervalle de dates from/to.
 *
 * Réf : FR-018, US6.
 */
import { computed, ref } from 'vue'
import type {
  DateRangePayload,
  DateRangeResponse,
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
  (e: 'submit', payload: DateRangeResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<DateRangePayload>(() => {
  const p = props.question.payload as DateRangePayload | undefined
  return p ?? { question_type: 'date_range' }
})

const fromValue = ref<string>('')
const toValue = ref<string>('')

function formatFr(iso: string): string {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' }).format(new Date(iso))
  } catch {
    return iso
  }
}

const canSubmit = computed(() => {
  if (inputLocked.value) return false
  if (!fromValue.value || !toValue.value) return false
  return new Date(fromValue.value) <= new Date(toValue.value)
})

function _doSubmit() {
  if (!canSubmit.value) return
  const fromFmt = formatFr(fromValue.value)
  const toFmt = formatFr(toValue.value)
  const label = `Du ${fromFmt} au ${toFmt}`
  emit(
    'submit',
    {
      question_type: 'date_range',
      from: fromValue.value,
      to: toValue.value,
      label,
    },
    `✓ ${label}`,
  )
}
</script>

<template>
  <div class="space-y-3">
    <div class="grid grid-cols-2 gap-2">
      <label class="block">
        <span class="text-xs text-gray-600 dark:text-gray-400 font-medium">Du</span>
        <input
          v-model="fromValue"
          type="date"
          :min="payload.min ?? undefined"
          :max="payload.max ?? undefined"
          :disabled="inputLocked"
          lang="fr"
          :data-testid="`daterange-from-${question.id}`"
          class="w-full mt-1 px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
        />
      </label>
      <label class="block">
        <span class="text-xs text-gray-600 dark:text-gray-400 font-medium">Au</span>
        <input
          v-model="toValue"
          type="date"
          :min="fromValue || (payload.min ?? undefined)"
          :max="payload.max ?? undefined"
          :disabled="inputLocked"
          lang="fr"
          :data-testid="`daterange-to-${question.id}`"
          class="w-full mt-1 px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
        />
      </label>
    </div>

    <p
      v-if="fromValue && toValue"
      class="text-sm text-indigo-600 dark:text-indigo-400 font-medium"
    >
      Du {{ formatFr(fromValue) }} au {{ formatFr(toValue) }}
    </p>

    <div class="flex items-center justify-between pt-1">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
        @click="emit('abandon-and-send', '')"
      >
        Répondre autrement
      </button>
      <button
        type="button"
        :disabled="!canSubmit"
        :data-testid="`daterange-submit-${question.id}`"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg transition-all"
        @click="_doSubmit"
      >
        Valider
      </button>
    </div>
  </div>
</template>
