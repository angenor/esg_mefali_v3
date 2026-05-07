<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useFocusTrap } from '~/composables/useFocusTrap'

interface Props {
  modelValue: boolean
  attestationDisplayId?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', reason: string): void
}>()

const reason = ref('')
const containerRef = ref<HTMLElement | null>(null)
const { activate, deactivate } = useFocusTrap(containerRef)

const isValid = computed(() => reason.value.trim().length >= 10)
const remainingChars = computed(() => 500 - reason.value.length)

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      reason.value = ''
      await nextTick()
      activate()
    } else {
      deactivate()
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

function confirm() {
  if (!isValid.value) return
  emit('confirm', reason.value.trim())
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      @click.self="close"
      @keydown="onKey"
    >
      <div
        ref="containerRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="revoke-title"
        class="w-full max-w-md bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg shadow-xl p-6"
      >
        <h2
          id="revoke-title"
          class="text-lg font-bold text-gray-900 dark:text-white mb-2"
        >
          Révoquer cette attestation ?
        </h2>
        <p
          v-if="attestationDisplayId"
          class="text-sm text-gray-600 dark:text-gray-400 mb-3"
        >
          Attestation
          <span class="font-mono font-semibold">{{ attestationDisplayId }}</span>
        </p>
        <p class="text-sm text-gray-700 dark:text-gray-300 mb-4">
          Cette action est définitive. La page publique de vérification affichera désormais
          un badge <strong>RÉVOQUÉE</strong> avec votre raison.
        </p>

        <label
          for="revoke-reason"
          class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          Raison de la révocation (min. 10 caractères)
        </label>
        <textarea
          id="revoke-reason"
          v-model="reason"
          rows="3"
          maxlength="500"
          class="w-full px-3 py-2 text-sm bg-white dark:bg-dark-input text-gray-900 dark:text-white border border-gray-300 dark:border-dark-border rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500 dark:focus:ring-rose-400 placeholder-gray-400 dark:placeholder-gray-500"
          placeholder="Ex. : Mise à jour majeure du profil financier"
        />
        <div class="flex items-center justify-between mt-1 text-xs">
          <span
            :class="
              isValid
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-gray-500 dark:text-gray-400'
            "
          >
            {{ reason.trim().length }} / 10 minimum
          </span>
          <span class="text-gray-400 dark:text-gray-500">
            {{ remainingChars }} restants
          </span>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button
            type="button"
            class="px-4 py-2 text-sm font-medium bg-gray-100 dark:bg-dark-input text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-dark-border rounded hover:bg-gray-200 dark:hover:bg-dark-hover transition-colors"
            @click="close"
          >
            Annuler
          </button>
          <button
            type="button"
            class="px-4 py-2 text-sm font-medium bg-rose-600 text-white rounded hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            :disabled="!isValid"
            @click="confirm"
          >
            Confirmer la révocation
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
