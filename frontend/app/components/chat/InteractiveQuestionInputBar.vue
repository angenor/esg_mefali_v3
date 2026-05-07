<script setup lang="ts">
/**
 * F10 — Dispatcher widget par `question_type`.
 *
 * Refactor du composant F18 monolithique : tous les rendus de widgets
 * (4 F18 + 9 F10) sont délégués à des sous-composants via `<component :is>`.
 * Pour les types inconnus (compatibilité ascendante), fallback vers
 * `UnsupportedWidget`.
 *
 * Préserve les props (`question`, `loading`, `disabled`) et les events
 * (`submit`, `abandon-and-send`) — aucun breaking change pour le parent
 * `InteractiveQuestionHost.vue`.
 *
 * Réf : FR-026, R10, SC-004 (zéro régression F18).
 */
import { computed, ref } from 'vue'
import type { Component } from 'vue'
import type {
  InteractiveQuestion,
  InteractiveQuestionAnswer,
  InteractiveQuestionAnswerExt,
  InteractiveQuestionResponsePayload,
  InteractiveQuestionType,
} from '~/types/interactive-question'

import SingleChoiceWidget from '~/components/chat/widgets/SingleChoiceWidget.vue'
import MultipleChoiceWidget from '~/components/chat/widgets/MultipleChoiceWidget.vue'
import YesNoWidget from '~/components/chat/widgets/YesNoWidget.vue'
import SelectWidget from '~/components/chat/widgets/SelectWidget.vue'
import NumberWidget from '~/components/chat/widgets/NumberWidget.vue'
import DateWidget from '~/components/chat/widgets/DateWidget.vue'
import DateRangeWidget from '~/components/chat/widgets/DateRangeWidget.vue'
import RatingWidget from '~/components/chat/widgets/RatingWidget.vue'
import FileUploadWidget from '~/components/chat/widgets/FileUploadWidget.vue'
import FormWidget from '~/components/chat/widgets/FormWidget.vue'
import SummaryCardWidget from '~/components/chat/widgets/SummaryCardWidget.vue'
import UnsupportedWidget from '~/components/chat/widgets/UnsupportedWidget.vue'

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
  // Réponse F18 simple (QCU/QCM)
  (e: 'submit', payload: InteractiveQuestionAnswer): void
  // F10 — réponse étendue (avec response_payload structuré)
  (e: 'submit-ext', payload: InteractiveQuestionAnswerExt): void
  (e: 'abandon-and-send', content: string): void
}>()

// Mapping statique type → composant.
const TYPE_TO_COMPONENT: Record<InteractiveQuestionType, Component> = {
  // F18 — widgets QCU/QCM
  qcu: SingleChoiceWidget,
  qcu_justification: SingleChoiceWidget,
  qcm: MultipleChoiceWidget,
  qcm_justification: MultipleChoiceWidget,
  // F10 — 9 nouveaux widgets bottom sheet
  yes_no: YesNoWidget,
  select: SelectWidget,
  number: NumberWidget,
  date: DateWidget,
  date_range: DateRangeWidget,
  rating: RatingWidget,
  file_upload: FileUploadWidget,
  form: FormWidget,
  summary_card: SummaryCardWidget,
}

const widgetComponent = computed<Component>(() => {
  const target = TYPE_TO_COMPONENT[props.question.question_type]
  return target ?? UnsupportedWidget
})

// Re-émission des events des widgets enfants vers le parent.
function onChildSubmit(answer: InteractiveQuestionAnswer) {
  emit('submit', answer)
}

function onWidgetSubmit(payload: InteractiveQuestionResponsePayload, displayText: string) {
  // F10 — convertir en InteractiveQuestionAnswerExt avec response_payload structuré.
  emit('submit-ext', {
    values: [],
    response_payload: payload,
    display_text: displayText,
  })
}

function onAbandon(content: string) {
  emit('abandon-and-send', content)
}
</script>

<template>
  <!-- Bottom sheet animé : conserve le wrapper visuel F18 -->
  <div
    class="iq-sheet relative rounded-t-3xl border-t border-x border-indigo-200/60 dark:border-indigo-700/40 bg-gradient-to-b from-indigo-50 via-white to-white dark:from-indigo-900/30 dark:via-dark-card dark:to-dark-card shadow-[0_-12px_40px_-8px_rgba(99,102,241,0.35)] dark:shadow-[0_-12px_40px_-8px_rgba(99,102,241,0.5)] overflow-hidden"
  >
    <div class="iq-sheet__accent h-1.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 bg-[length:200%_100%]" />

    <div class="flex justify-center pt-2">
      <div class="w-10 h-1 rounded-full bg-gradient-to-r from-indigo-300 to-purple-300 dark:from-indigo-600 dark:to-purple-600" />
    </div>

    <div class="px-4 pt-2 pb-3">
      <!-- Badge + prompt de la question -->
      <div class="flex items-start gap-2.5 mb-3">
        <div
          class="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shadow-md shadow-indigo-500/30"
        >
          ?
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-[10px] uppercase tracking-wider text-indigo-600 dark:text-indigo-400 font-bold mb-0.5">
            Question interactive
          </p>
          <p class="text-sm font-semibold text-surface-text dark:text-surface-dark-text leading-snug">
            {{ question.prompt }}
          </p>
        </div>
      </div>

      <!-- Dispatcher -->
      <component
        :is="widgetComponent"
        :question="question"
        :loading="loading"
        :disabled="disabled"
        @submit="onChildSubmit"
        @submit-ext="onWidgetSubmit"
        @abandon-and-send="onAbandon"
      />
    </div>
  </div>
</template>

<style scoped>
.iq-sheet {
  animation: iq-slide-up 350ms cubic-bezier(0.22, 1, 0.36, 1);
  transform-origin: bottom center;
}

@keyframes iq-slide-up {
  from {
    opacity: 0;
    transform: translateY(100%);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.iq-sheet__accent {
  animation: iq-shimmer 4s ease-in-out infinite;
}

@keyframes iq-shimmer {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .iq-sheet,
  .iq-sheet__accent {
    animation: none;
  }
}
</style>
