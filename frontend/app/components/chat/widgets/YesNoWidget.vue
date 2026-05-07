<script setup lang="ts">
/**
 * F10 — YesNoWidget : confirmation binaire (mode normal ou destructif).
 *
 * En mode destructif (`payload.destructive === true`) :
 * - Bouton confirm rouge avec animation hold 2s
 * - Tooltip ARIA « Action irréversible »
 * - Click court (< 2s) ne soumet pas
 *
 * Réf : FR-018, FR-019, FR-030, FR-031, US1.
 */
import { computed } from 'vue'
import { useHoldToConfirm } from '~/composables/useHoldToConfirm'
import type {
  InteractiveQuestion,
  YesNoPayload,
  YesNoResponse,
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
  (e: 'submit', payload: YesNoResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<YesNoPayload>(() => {
  const p = props.question.payload as YesNoPayload | undefined
  return p ?? {
    question_type: 'yes_no',
    confirm_label: 'Oui',
    deny_label: 'Non',
    destructive: false,
  }
})

const isDestructive = computed(() => payload.value.destructive === true)

function _emitConfirm() {
  if (inputLocked.value) return
  const label = payload.value.confirm_label
  emit(
    'submit',
    { question_type: 'yes_no', value: true, label },
    `✓ ${label}`,
  )
}

function _emitDeny() {
  if (inputLocked.value) return
  const label = payload.value.deny_label
  emit(
    'submit',
    { question_type: 'yes_no', value: false, label },
    `✗ ${label}`,
  )
}

const hold = useHoldToConfirm({
  durationMs: 2000,
  onConfirmed: _emitConfirm,
})
</script>

<template>
  <div class="space-y-3">
    <div class="grid gap-2 sm:grid-cols-2">
      <!-- Bouton CONFIRMER -->
      <button
        v-if="isDestructive"
        type="button"
        :disabled="inputLocked"
        :aria-label="payload.confirm_label"
        :aria-describedby="`yesno-hold-${question.id}`"
        :title="`Action irréversible — ${payload.confirm_label}`"
        :data-testid="`yesno-confirm-${question.id}`"
        :class="[
          'relative px-4 py-3 rounded-2xl border-2 text-left font-semibold transition-all',
          'focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card',
          'border-red-300 bg-gradient-to-br from-red-500 to-red-600 text-white shadow-lg shadow-red-500/30',
          'dark:border-red-700 dark:from-red-700 dark:to-red-800 dark:shadow-red-700/30',
          'hover:from-red-600 hover:to-red-700 disabled:opacity-50 disabled:cursor-not-allowed',
          hold.isHolding.value && 'scale-[0.98]',
        ]"
        @pointerdown="hold.onPointerDown"
        @pointerup="hold.onPointerUp"
        @pointerleave="hold.onPointerCancel"
        @pointercancel="hold.onPointerCancel"
        @keydown="hold.onKeyDown"
        @keyup="hold.onKeyUp"
      >
        <span class="flex items-center justify-center gap-2">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{{ payload.confirm_label }}</span>
        </span>
        <!-- Anneau de progression hold -->
        <div
          v-if="hold.isHolding.value && !hold.prefersReducedMotion.value"
          class="absolute inset-0 rounded-2xl pointer-events-none"
          :style="{
            background: `conic-gradient(rgba(255,255,255,0.55) ${hold.progress.value * 360}deg, transparent 0deg)`,
            mixBlendMode: 'overlay',
          }"
          aria-hidden="true"
        />
      </button>

      <!-- Bouton CONFIRMER (mode normal, non-destructif) -->
      <button
        v-else
        type="button"
        :disabled="inputLocked"
        :data-testid="`yesno-confirm-${question.id}`"
        class="px-4 py-3 rounded-2xl border-2 border-indigo-500 bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-semibold shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40 transition-all disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card"
        @click="_emitConfirm"
      >
        <span class="flex items-center justify-center gap-2">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <span>{{ payload.confirm_label }}</span>
        </span>
      </button>

      <!-- Bouton DENY (gris) -->
      <button
        type="button"
        :disabled="inputLocked"
        :data-testid="`yesno-deny-${question.id}`"
        class="px-4 py-3 rounded-2xl border-2 border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text font-semibold hover:bg-gray-50 dark:hover:bg-dark-hover transition-all disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 dark:focus:ring-offset-dark-card"
        @click="_emitDeny"
      >
        {{ payload.deny_label }}
      </button>
    </div>

    <!-- Instructions hold (lue par screen reader, visible si destructif) -->
    <p
      v-if="isDestructive"
      :id="`yesno-hold-${question.id}`"
      class="text-xs text-red-600 dark:text-red-400 text-center font-medium"
      role="status"
      aria-live="polite"
    >
      {{ hold.holdInstructions.value }}
    </p>

    <!-- Bouton « Répondre librement » (pattern F18 conservé) -->
    <div class="pt-1 flex items-center justify-end">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition-colors disabled:opacity-50"
        @click="emit('abandon-and-send', '')"
      >
        Répondre autrement
      </button>
    </div>
  </div>
</template>

<style scoped>
@media (prefers-reduced-motion: reduce) {
  button {
    transition: none !important;
  }
}
</style>
