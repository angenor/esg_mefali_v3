<script setup lang="ts">
// F23 — Multi-select pour le whitelist de tools.
// Pour le MVP, on accepte une saisie libre avec validation basique côté
// serveur (UnknownToolError au save).
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const newTool = ref('')
const items = ref<string[]>([...props.modelValue])

watch(
  () => props.modelValue,
  (v) => {
    items.value = [...v]
  },
)

function add() {
  const v = newTool.value.trim()
  if (!v) return
  if (items.value.includes(v)) return
  items.value = [...items.value, v]
  newTool.value = ''
  emit('update:modelValue', items.value)
}

function remove(name: string) {
  items.value = items.value.filter((n) => n !== name)
  emit('update:modelValue', items.value)
}
</script>

<template>
  <div>
    <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
      Tool whitelist
    </label>
    <div class="flex gap-2 mb-3">
      <input
        v-model="newTool"
        type="text"
        placeholder="Ex: update_company_profile"
        class="flex-1 px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
        @keyup.enter="add"
      />
      <button
        type="button"
        class="px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white"
        @click="add"
      >
        Ajouter
      </button>
    </div>
    <div class="flex flex-wrap gap-2">
      <span
        v-for="tool in items"
        :key="tool"
        class="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 text-sm"
      >
        {{ tool }}
        <button
          type="button"
          class="text-blue-600 hover:text-blue-900 dark:text-blue-300"
          @click="remove(tool)"
        >
          ×
        </button>
      </span>
      <p v-if="items.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
        Aucun tool sélectionné.
      </p>
    </div>
  </div>
</template>
