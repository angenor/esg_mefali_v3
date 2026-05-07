<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

interface Props {
  open: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  confirm: [password: string, confirmationText: string]
  cancel: []
}>()

const acknowledge = ref(false)
const password = ref('')
const confirmationText = ref('')
const submitting = ref(false)
const errorMessage = ref<string | null>(null)
const dialogRef = ref<HTMLDialogElement | null>(null)
const closeButtonRef = ref<HTMLButtonElement | null>(null)

const canSubmit = computed(
  () =>
    acknowledge.value &&
    password.value.length > 0 &&
    confirmationText.value === 'SUPPRIMER',
)

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      acknowledge.value = false
      password.value = ''
      confirmationText.value = ''
      errorMessage.value = null
      await nextTick()
      closeButtonRef.value?.focus()
    }
  },
)

async function handleConfirm() {
  if (!canSubmit.value) return
  submitting.value = true
  errorMessage.value = null
  emit('confirm', password.value, confirmationText.value)
  submitting.value = false
}

function handleCancel() {
  emit('cancel')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    handleCancel()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="handleCancel"
        @keydown="onKeydown"
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="deletion-modal-title"
          aria-describedby="deletion-modal-description"
          class="w-full max-w-lg rounded-xl bg-white dark:bg-dark-card p-6 shadow-xl"
        >
          <h2
            id="deletion-modal-title"
            class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
          >
            Supprimer définitivement votre compte ?
          </h2>
          <p
            id="deletion-modal-description"
            class="mt-2 text-sm text-gray-600 dark:text-gray-400"
          >
            Cette action programme la suppression à J+30 jours. Pendant ce
            délai, vous pouvez annuler. Au-delà, toutes vos données (profil,
            projets, candidatures, attestations, conversations…) seront
            effacées définitivement (sauf l'historique d'audit anonymisé pour
            conformité légale).
          </p>

          <fieldset class="mt-5 space-y-4">
            <label class="flex items-start gap-2 text-sm">
              <input
                v-model="acknowledge"
                type="checkbox"
                name="acknowledge_consequences"
                class="mt-0.5 h-4 w-4 rounded border-gray-300 dark:border-dark-border text-emerald-600 focus:ring-emerald-500"
              />
              <span class="text-surface-text dark:text-surface-dark-text">
                Je comprends que mes candidatures en cours seront annulées et
                que mes attestations crédit en cours de validité seront
                révoquées.
              </span>
            </label>

            <label
              for="deletion-password"
              class="block text-sm font-medium text-surface-text dark:text-surface-dark-text"
            >
              Confirmer votre mot de passe
              <input
                id="deletion-password"
                v-model="password"
                type="password"
                name="password"
                autocomplete="current-password"
                class="mt-1 block w-full rounded-md border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text shadow-sm focus:ring-emerald-500 focus:border-emerald-500 px-3 py-2"
              />
            </label>

            <label
              for="deletion-confirmation"
              class="block text-sm font-medium text-surface-text dark:text-surface-dark-text"
            >
              Saisir « <strong>SUPPRIMER</strong> » pour confirmer
              <input
                id="deletion-confirmation"
                v-model="confirmationText"
                type="text"
                name="confirmation_text"
                placeholder="SUPPRIMER"
                class="mt-1 block w-full rounded-md border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text shadow-sm focus:ring-emerald-500 focus:border-emerald-500 px-3 py-2 font-mono"
              />
            </label>
          </fieldset>

          <p
            v-if="errorMessage"
            class="mt-3 text-sm text-red-600 dark:text-red-400"
            aria-live="assertive"
          >
            {{ errorMessage }}
          </p>

          <div class="mt-6 flex justify-end gap-3">
            <button
              ref="closeButtonRef"
              type="button"
              class="px-4 py-2 rounded-md text-sm font-medium border border-gray-300 dark:border-dark-border text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover focus:outline-none focus:ring-2 focus:ring-emerald-500"
              @click="handleCancel"
            >
              Annuler
            </button>
            <button
              type="button"
              :disabled="!canSubmit || submitting"
              :class="[
                'px-4 py-2 rounded-md text-sm font-medium',
                'bg-red-600 hover:bg-red-700 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'focus:outline-none focus:ring-2 focus:ring-red-500',
              ]"
              @click="handleConfirm"
            >
              Confirmer la suppression
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
