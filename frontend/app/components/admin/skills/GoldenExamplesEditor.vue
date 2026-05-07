<script setup lang="ts">
// F23 — Éditeur des golden_examples (5 à 15 cas).
import { computed, ref, watch } from 'vue'
import type { GoldenExample, SkillDomain } from '~/types/skills'

const props = defineProps<{
  modelValue: GoldenExample[]
  category: SkillDomain
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: GoldenExample[]): void
}>()

const items = ref<GoldenExample[]>([...props.modelValue])

watch(
  () => props.modelValue,
  (v) => {
    items.value = [...v]
  },
)

const count = computed(() => items.value.length)
const inRange = computed(() => count.value >= 5 && count.value <= 15)

function addEmpty() {
  if (count.value >= 15) return
  items.value = [
    ...items.value,
    {
      id: `case-${count.value + 1}`,
      category: props.category,
      context: { current_page: null, active_module: null },
      user_message: '',
      expected: { tool_called: '', payload_contains: {} },
      tags: [],
    },
  ]
  emit('update:modelValue', items.value)
}

function remove(idx: number) {
  items.value = items.value.filter((_, i) => i !== idx)
  emit('update:modelValue', items.value)
}

function patchItem<T extends keyof GoldenExample>(idx: number, key: T, value: GoldenExample[T]) {
  items.value = items.value.map((it, i) => (i === idx ? { ...it, [key]: value } : it))
  emit('update:modelValue', items.value)
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <p class="text-sm text-gray-600 dark:text-gray-400">
        {{ count }} cas
        <span v-if="!inRange" class="text-red-600 dark:text-red-400">
          (entre 5 et 15 requis pour publier)
        </span>
      </p>
      <button
        type="button"
        :disabled="count >= 15"
        class="px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm"
        @click="addEmpty"
      >
        + Ajouter un cas
      </button>
    </div>
    <ul class="space-y-3">
      <li
        v-for="(it, idx) in items"
        :key="idx"
        class="p-3 rounded border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-2">
          <input
            :value="it.id"
            type="text"
            class="px-3 py-1.5 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text"
            placeholder="case-id"
            @input="(e: any) => patchItem(idx, 'id', e.target.value)"
          />
          <input
            :value="typeof it.expected.tool_called === 'string' ? it.expected.tool_called : it.expected.tool_called.join(',')"
            type="text"
            class="px-3 py-1.5 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text"
            placeholder="expected.tool_called"
            @input="(e: any) => patchItem(idx, 'expected', { ...it.expected, tool_called: e.target.value })"
          />
        </div>
        <textarea
          :value="it.user_message"
          rows="2"
          class="w-full px-3 py-1.5 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text"
          placeholder="user_message"
          @input="(e: any) => patchItem(idx, 'user_message', e.target.value)"
        ></textarea>
        <div class="mt-2 flex justify-end">
          <button
            type="button"
            class="text-red-600 hover:text-red-800 dark:text-red-400 text-sm"
            @click="remove(idx)"
          >
            Supprimer
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>
