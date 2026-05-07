<script setup lang="ts">
// F23 — Multi-select sources verified (UUIDs).
// Pour le MVP, accepte une saisie d'UUIDs (un par ligne ou ajout manuel).
// Validation server-side (SourceNotVerifiedError, SourceNotFoundError).
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const newId = ref('')
const items = ref<string[]>([...props.modelValue])

watch(
  () => props.modelValue,
  (v) => {
    items.value = [...v]
  },
)

function add() {
  const v = newId.value.trim()
  if (!v) return
  if (items.value.includes(v)) return
  items.value = [...items.value, v]
  newId.value = ''
  emit('update:modelValue', items.value)
}

function remove(id: string) {
  items.value = items.value.filter((n) => n !== id)
  emit('update:modelValue', items.value)
}
</script>

<template>
  <div>
    <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
      Sources (UUIDs verified)
    </label>
    <div class="flex gap-2 mb-3">
      <input
        v-model="newId"
        type="text"
        placeholder="UUID source verified"
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
    <ul class="space-y-1">
      <li
        v-for="id in items"
        :key="id"
        class="flex items-center justify-between px-2 py-1 rounded bg-gray-50 dark:bg-dark-hover text-sm font-mono text-surface-text dark:text-surface-dark-text"
      >
        <span>{{ id }}</span>
        <button class="text-red-600 dark:text-red-400" @click="remove(id)">×</button>
      </li>
      <li v-if="items.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
        Aucune source sélectionnée.
      </li>
    </ul>
  </div>
</template>
