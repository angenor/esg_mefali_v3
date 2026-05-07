<script setup lang="ts">
/**
 * F10 — SummaryCardWidget : récap d'extraction avec édition inline.
 *
 * Réf : FR-018, FR-024, US5.
 */
import { computed, ref } from 'vue'
import type {
  InteractiveQuestion,
  SummaryCardItem,
  SummaryCardModification,
  SummaryCardPayload,
  SummaryCardResponse,
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
  (e: 'submit', payload: SummaryCardResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<SummaryCardPayload>(() => {
  const p = props.question.payload as SummaryCardPayload | undefined
  return p ?? {
    question_type: 'summary_card',
    title: '',
    items: [],
    confirm_label: 'Valider',
    correct_label: 'Corriger',
  }
})

const editMode = ref(false)
const editedValues = ref<Record<string, string>>({})

const itemsWithKey = computed(() =>
  payload.value.items.map((item, idx) => ({
    ...item,
    _key: `${idx}-${item.label}`,
  })),
)

function _initEditValues() {
  const init: Record<string, string> = {}
  for (const item of payload.value.items) {
    init[item.label] = item.value === null || item.value === undefined ? '' : String(item.value)
  }
  editedValues.value = init
}

function startEdit() {
  if (inputLocked.value) return
  _initEditValues()
  editMode.value = true
}

function _coerceValue(original: SummaryCardItem, edited: string): string | number | boolean | null {
  if (typeof original.value === 'number') {
    const n = parseFloat(edited)
    return isNaN(n) ? original.value : n
  }
  if (typeof original.value === 'boolean') {
    return edited === 'true' || edited === 'oui'
  }
  return edited
}

function _doSubmit(asValidation: boolean) {
  if (inputLocked.value) return
  const modifications: SummaryCardModification[] = []
  if (editMode.value) {
    for (const item of payload.value.items) {
      if (!item.editable) continue
      const before = item.value
      const after = _coerceValue(item, editedValues.value[item.label] ?? '')
      const beforeStr = before === null || before === undefined ? '' : String(before)
      const afterStr = after === null || after === undefined ? '' : String(after)
      if (beforeStr !== afterStr) {
        modifications.push({ field: item.label, before, after })
      }
    }
  }
  const validated = asValidation || modifications.length === 0
  const resp: SummaryCardResponse = {
    question_type: 'summary_card',
    validated,
    modifications,
  }
  let display: string
  if (modifications.length === 0) {
    display = '✓ Validé'
  } else {
    const m = modifications[0]!
    display = `✓ Corrigé : ${m.field} ${m.after} (au lieu de ${m.before})`
  }
  emit('submit', resp, display)
}
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-bold text-surface-text dark:text-surface-dark-text">
      {{ payload.title }}
    </h3>

    <ul class="space-y-2 max-h-72 overflow-y-auto -mx-1 px-1">
      <li
        v-for="item in itemsWithKey"
        :key="item._key"
        class="flex items-center justify-between gap-2 py-2 px-3 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card"
      >
        <span class="text-xs text-gray-600 dark:text-gray-400 font-medium">
          {{ item.label }}
        </span>
        <input
          v-if="editMode && item.editable"
          v-model="editedValues[item.label]"
          :data-testid="`summary-edit-${item.label}-${question.id}`"
          :disabled="inputLocked"
          class="flex-1 ml-2 px-2 py-1 rounded-lg border border-indigo-300 dark:border-indigo-700 bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <span
          v-else
          class="flex items-center gap-1 text-sm font-semibold text-surface-text dark:text-surface-dark-text"
        >
          {{ item.value }}
          <svg
            v-if="item.editable && !editMode"
            class="w-3 h-3 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </span>
      </li>
    </ul>

    <div class="flex items-center justify-between gap-2 pt-1">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
        @click="emit('abandon-and-send', '')"
      >
        Répondre autrement
      </button>
      <div class="flex gap-2">
        <button
          v-if="!editMode"
          type="button"
          :disabled="inputLocked"
          :data-testid="`summary-correct-${question.id}`"
          class="px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border text-sm font-medium text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50"
          @click="startEdit"
        >
          {{ payload.correct_label }}
        </button>
        <button
          type="button"
          :disabled="inputLocked"
          :data-testid="`summary-validate-${question.id}`"
          class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg transition-all"
          @click="_doSubmit(true)"
        >
          {{ editMode ? 'Valider mes corrections' : payload.confirm_label }}
        </button>
      </div>
    </div>
  </div>
</template>
