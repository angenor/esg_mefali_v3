<script setup lang="ts">
/**
 * F18 — Widget QCM (avec ou sans justification).
 *
 * Extrait de InteractiveQuestionInputBar.vue lors du refactor F10 (dispatcher).
 * Logique fonctionnellement identique, design conservé pour zéro régression.
 */
import { computed, ref, watch } from 'vue'
import type {
  InteractiveQuestion,
  InteractiveQuestionAnswer,
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
  (e: 'submit', payload: InteractiveQuestionAnswer): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)
const requiresJustification = computed(() => props.question.requires_justification ?? false)

const selectedQcm = ref<Set<string>>(new Set())
const justification = ref('')

watch(
  () => props.question.id,
  () => {
    selectedQcm.value = new Set()
    justification.value = ''
  },
)

const selectedCount = computed(() => selectedQcm.value.size)

const canSubmit = computed(() => {
  if (inputLocked.value) return false
  const minS = props.question.min_selections ?? 1
  const maxS = props.question.max_selections ?? 1
  if (selectedCount.value < minS || selectedCount.value > maxS) return false
  if (requiresJustification.value && justification.value.trim().length === 0) return false
  return true
})

function toggleQcm(optionId: string) {
  if (inputLocked.value) return
  const next = new Set(selectedQcm.value)
  if (next.has(optionId)) {
    next.delete(optionId)
  } else if (next.size < (props.question.max_selections ?? 1)) {
    next.add(optionId)
  }
  selectedQcm.value = next
}

function isQcmChecked(optionId: string): boolean {
  return selectedQcm.value.has(optionId)
}

function canCheckMoreQcm(): boolean {
  return selectedCount.value < (props.question.max_selections ?? 1)
}

function doSubmit() {
  if (!canSubmit.value) return
  emit('submit', {
    values: Array.from(selectedQcm.value),
    justification: requiresJustification.value ? justification.value : undefined,
  })
}
</script>

<template>
  <div class="space-y-3">
    <div class="grid gap-2 sm:grid-cols-2">
      <button
        v-for="option in question.options ?? []"
        :key="option.id"
        type="button"
        role="checkbox"
        :data-testid="`interactive-choice-${option.id}`"
        :aria-checked="isQcmChecked(option.id)"
        :disabled="inputLocked || (!isQcmChecked(option.id) && !canCheckMoreQcm())"
        :class="[
          'group relative px-4 py-3 rounded-2xl border-2 text-left transition-all duration-200',
          'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card',
          isQcmChecked(option.id)
            ? 'border-indigo-500 bg-gradient-to-br from-indigo-500/15 to-purple-500/15 dark:from-indigo-500/25 dark:to-purple-500/25 shadow-md'
            : 'border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card hover:border-indigo-400 dark:hover:border-indigo-600 hover:shadow-sm',
          (!isQcmChecked(option.id) && !canCheckMoreQcm()) && 'opacity-40 cursor-not-allowed',
          loading && 'cursor-wait',
        ]"
        @click="toggleQcm(option.id)"
      >
        <div class="flex items-start gap-2.5">
          <div
            :class="[
              'flex-shrink-0 w-5 h-5 rounded-md border-2 flex items-center justify-center mt-0.5 transition-all',
              isQcmChecked(option.id)
                ? 'border-indigo-500 bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm'
                : 'border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card',
            ]"
          >
            <svg
              v-if="isQcmChecked(option.id)"
              class="w-3 h-3 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="4"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <span
            v-if="option.emoji"
            class="text-xl flex-shrink-0 transition-transform group-hover:scale-110"
          >
            {{ option.emoji }}
          </span>
          <div class="flex-1 min-w-0">
            <div
              :class="[
                'text-sm font-semibold leading-snug',
                isQcmChecked(option.id)
                  ? 'text-indigo-700 dark:text-indigo-200'
                  : 'text-surface-text dark:text-surface-dark-text',
              ]"
            >
              {{ option.label }}
            </div>
            <div
              v-if="option.description"
              class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2"
            >
              {{ option.description }}
            </div>
          </div>
        </div>
      </button>
    </div>

    <div
      v-if="requiresJustification"
      class="rounded-2xl border-2 border-indigo-200 dark:border-indigo-700/60 bg-white/80 dark:bg-dark-input/80 p-3"
    >
      <label class="block text-xs font-medium text-indigo-700 dark:text-indigo-300 mb-1">
        {{ question.justification_prompt || 'Raconte-nous pourquoi !' }}
      </label>
      <textarea
        v-model="justification"
        :disabled="inputLocked"
        rows="2"
        maxlength="400"
        placeholder="Ta reponse en quelques mots..."
        class="w-full resize-none bg-transparent text-sm text-surface-text dark:text-surface-dark-text placeholder-gray-400 focus:outline-none"
      />
      <div class="flex items-center justify-between mt-1">
        <span class="text-[10px] text-gray-500 dark:text-gray-400">Limite 400 caracteres</span>
        <span
          :class="[
            'text-[10px] tabular-nums font-medium',
            justification.length > 350 ? 'text-orange-500' : 'text-gray-400 dark:text-gray-500',
          ]"
        >
          {{ justification.length }} / 400
        </span>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 pt-1">
      <div class="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300">
        <span
          class="inline-flex items-center justify-center min-w-[1.5rem] h-6 px-2 rounded-full bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 tabular-nums font-bold"
        >
          {{ selectedCount }}
        </span>
        <span>
          sur {{ question.max_selections ?? 1 }} max
          <span v-if="(question.min_selections ?? 1) > 1">(min {{ question.min_selections }})</span>
        </span>
      </div>
      <button
        type="button"
        :disabled="!canSubmit"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-indigo-500/30 transition-all"
        @click="doSubmit"
      >
        Valider ma selection
      </button>
    </div>

    <div class="flex items-center justify-end">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition-colors disabled:opacity-50"
        @click="emit('abandon-and-send', '')"
      >
        Repondre autrement
      </button>
    </div>
  </div>
</template>
