<script setup lang="ts">
/**
 * F10 — UnsupportedWidget : fallback pour types inconnus.
 *
 * Garantit la résilience aux versions futures : si l'enum côté backend ajoute
 * un nouveau type que ce frontend ne connaît pas, ce composant rend un
 * textarea générique avec un libellé explicite, plutôt que de casser le rendu
 * de la conversation.
 *
 * Réf : FR-026, edge case « Type de widget inconnu côté frontend ».
 */
import { computed, ref } from 'vue'
import type { InteractiveQuestion } from '~/types/interactive-question'

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
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)
const text = ref('')

if (typeof window !== 'undefined' && typeof console !== 'undefined') {
  console.warn(
    '[UnsupportedWidget] Type de widget non supporté :',
    props.question.question_type,
    '— rendu via le fallback textarea.',
  )
}

function send() {
  if (inputLocked.value || !text.value.trim()) return
  emit('abandon-and-send', text.value.trim())
  text.value = ''
}
</script>

<template>
  <div class="space-y-3">
    <p class="text-xs text-orange-600 dark:text-orange-400 font-medium">
      Type de widget non supporté ({{ question.question_type }}) — répondez librement.
    </p>
    <textarea
      v-model="text"
      :disabled="inputLocked"
      rows="3"
      maxlength="2000"
      placeholder="Tapez votre réponse libre…"
      :data-testid="`unsupported-textarea-${question.id}`"
      class="w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 resize-none"
    />
    <div class="flex items-center justify-end">
      <button
        type="button"
        :disabled="inputLocked || !text.trim()"
        :data-testid="`unsupported-send-${question.id}`"
        class="px-4 py-1.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-lg"
        @click="send"
      >
        Envoyer
      </button>
    </div>
  </div>
</template>
