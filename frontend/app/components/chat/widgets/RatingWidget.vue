<script setup lang="ts">
/**
 * F10 — RatingWidget : étoiles 1-5 ou points 1-10 avec hover preview.
 *
 * Réf : FR-018, US7.
 */
import { computed, ref } from 'vue'
import type {
  InteractiveQuestion,
  RatingPayload,
  RatingResponse,
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
  (e: 'submit', payload: RatingResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<RatingPayload>(() => {
  const p = props.question.payload as RatingPayload | undefined
  return p ?? { question_type: 'rating', scale: 5 }
})

const value = ref<number | null>(null)
const hoverValue = ref<number | null>(null)

const previewValue = computed(() => hoverValue.value ?? value.value ?? 0)
const isStars = computed(() => payload.value.scale <= 5)

const previewLabel = computed<string | null>(() => {
  const idx = (hoverValue.value ?? value.value ?? 0) - 1
  return payload.value.labels?.[idx] ?? null
})

const canSubmit = computed(() => !inputLocked.value && value.value !== null)

function pick(n: number) {
  if (inputLocked.value) return
  value.value = n
}

function _doSubmit() {
  if (!canSubmit.value || value.value === null) return
  const lbl = payload.value.labels?.[value.value - 1] ?? null
  const display = lbl
    ? `✓ ${value.value}/${payload.value.scale} (${lbl})`
    : `✓ ${value.value}/${payload.value.scale}`
  emit(
    'submit',
    {
      question_type: 'rating',
      value: value.value,
      scale: payload.value.scale,
      label: lbl,
    },
    display,
  )
}
</script>

<template>
  <div class="space-y-3">
    <div
      role="radiogroup"
      :aria-label="question.prompt"
      class="flex items-center gap-2"
    >
      <button
        v-for="n in payload.scale"
        :key="n"
        type="button"
        role="radio"
        :aria-checked="value === n"
        :data-testid="`rating-${n}-${question.id}`"
        :disabled="inputLocked"
        :class="[
          'transition-all',
          isStars
            ? 'text-3xl'
            : 'w-9 h-9 rounded-full border-2 flex items-center justify-center text-sm font-bold',
          isStars && previewValue >= n
            ? 'text-yellow-400'
            : isStars
              ? 'text-gray-300 dark:text-gray-600'
              : (previewValue >= n
                ? 'border-indigo-500 bg-indigo-500 text-white'
                : 'border-gray-300 dark:border-dark-border text-gray-500'),
        ]"
        @click="pick(n)"
        @mouseenter="hoverValue = n"
        @mouseleave="hoverValue = null"
      >
        <template v-if="isStars">★</template>
        <template v-else>{{ n }}</template>
      </button>
    </div>

    <p
      v-if="previewLabel"
      class="text-sm text-indigo-600 dark:text-indigo-400 font-medium"
    >
      {{ previewLabel }}
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
        :data-testid="`rating-submit-${question.id}`"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg transition-all"
        @click="_doSubmit"
      >
        Valider
      </button>
    </div>
  </div>
</template>
