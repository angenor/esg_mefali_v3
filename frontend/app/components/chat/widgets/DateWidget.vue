<script setup lang="ts">
/**
 * F10 — DateWidget : saisie date unique (ISO 8601, format français).
 *
 * Réf : FR-018, US6.
 */
import { computed, ref } from 'vue'
import type {
  DatePayload,
  DateResponse,
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
  (e: 'submit', payload: DateResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<DatePayload>(() => {
  const p = props.question.payload as DatePayload | undefined
  return p ?? { question_type: 'date' }
})

const value = ref<string>(payload.value.default ?? '')

function formatFr(iso: string): string {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' }).format(new Date(iso))
  } catch {
    return iso
  }
}

const canSubmit = computed(() => !inputLocked.value && value.value.length > 0)

function _doSubmit() {
  if (!canSubmit.value) return
  const label = formatFr(value.value)
  emit(
    'submit',
    { question_type: 'date', value: value.value, label },
    `✓ ${label}`,
  )
}
</script>

<template>
  <div class="space-y-3">
    <input
      v-model="value"
      type="date"
      :min="payload.min ?? undefined"
      :max="payload.max ?? undefined"
      :disabled="inputLocked"
      lang="fr"
      :data-testid="`date-input-${question.id}`"
      :aria-label="question.prompt"
      class="w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
    />

    <p
      v-if="value"
      class="text-sm text-indigo-600 dark:text-indigo-400 font-medium"
    >
      {{ formatFr(value) }}
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
        :data-testid="`date-submit-${question.id}`"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg transition-all"
        @click="_doSubmit"
      >
        Valider
      </button>
    </div>
  </div>
</template>
