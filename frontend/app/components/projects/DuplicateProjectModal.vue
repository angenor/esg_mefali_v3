<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useFocusTrap } from '~/composables/useFocusTrap'

interface Props {
  open: boolean
  sourceName?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  sourceName: '',
  loading: false,
})

const emit = defineEmits<{
  submit: [newName: string | undefined]
  cancel: []
}>()

const newName = ref('')
const validationError = ref<string | null>(null)
const dialogRef = ref<HTMLElement | null>(null)

const { activate, deactivate } = useFocusTrap(dialogRef)

watch(
  () => props.open,
  async (open) => {
    if (open) {
      newName.value = props.sourceName ? `${props.sourceName} (copie)` : ''
      validationError.value = null
      await nextTick()
      activate()
    } else {
      deactivate()
    }
  },
)

function onSubmit(e: Event) {
  e.preventDefault()
  if (newName.value.length > 200) {
    validationError.value = 'Le nom ne peut dépasser 200 caractères.'
    return
  }
  emit('submit', newName.value.trim() || undefined)
}

function onCancel() {
  emit('cancel')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="onCancel"
    >
      <div
        ref="dialogRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="duplicate-modal-title"
        class="w-full max-w-md rounded-lg bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border shadow-xl"
      >
        <form @submit="onSubmit">
          <div class="p-6">
            <h2
              id="duplicate-modal-title"
              class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4"
            >
              Dupliquer le projet
            </h2>
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Le nouveau projet sera créé en statut « Brouillon ». Les
              documents associés ne sont pas copiés — vous pourrez les lier
              manuellement.
            </p>
            <label
              for="duplicate-new-name"
              class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
            >
              Nouveau nom
            </label>
            <input
              id="duplicate-new-name"
              v-model="newName"
              type="text"
              maxlength="200"
              class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
              placeholder="Nom du nouveau projet"
            />
            <p
              v-if="validationError"
              class="mt-2 text-sm text-red-600 dark:text-red-400"
            >
              {{ validationError }}
            </p>
          </div>
          <div
            class="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 dark:bg-dark-hover border-t border-gray-200 dark:border-dark-border rounded-b-lg"
          >
            <button
              type="button"
              class="px-4 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover"
              @click="onCancel"
            >
              Annuler
            </button>
            <button
              type="submit"
              :disabled="loading"
              class="px-4 py-2 text-sm rounded-md bg-brand-green text-white hover:bg-emerald-700 disabled:opacity-50 font-medium"
            >
              Dupliquer
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
