<script setup lang="ts">
// F23 — Editeur des règles d'activation.
import { computed, ref, watch } from 'vue'
import type { ActivationRules } from '~/types/skills'

const props = defineProps<{
  modelValue: ActivationRules
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: ActivationRules): void
}>()

const local = ref<ActivationRules>({
  page_slugs: [],
  intent_keywords: [],
  active_module: [],
  offer_id: null,
  fund_id: null,
  intermediary_id: null,
  ...props.modelValue,
})

watch(
  () => props.modelValue,
  (v) => {
    local.value = {
      page_slugs: [],
      intent_keywords: [],
      active_module: [],
      offer_id: null,
      fund_id: null,
      intermediary_id: null,
      ...v,
    }
  },
)

function emitUpdate() {
  emit('update:modelValue', { ...local.value })
}

const pageSlugsCsv = computed({
  get: () => (local.value.page_slugs || []).join(', '),
  set: (v: string) => {
    local.value.page_slugs = v.split(',').map((s) => s.trim()).filter(Boolean)
    emitUpdate()
  },
})

const intentKeywordsCsv = computed({
  get: () => (local.value.intent_keywords || []).join(', '),
  set: (v: string) => {
    local.value.intent_keywords = v.split(',').map((s) => s.trim()).filter(Boolean)
    emitUpdate()
  },
})

const activeModuleCsv = computed({
  get: () => (local.value.active_module || []).join(', '),
  set: (v: string) => {
    local.value.active_module = v.split(',').map((s) => s.trim()).filter(Boolean)
    emitUpdate()
  },
})
</script>

<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
        Pages (slugs séparés par virgules)
      </label>
      <input
        v-model="pageSlugsCsv"
        type="text"
        placeholder="/esg, /financing"
        class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
      />
    </div>
    <div>
      <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
        Intent keywords (séparés par virgules)
      </label>
      <input
        v-model="intentKeywordsCsv"
        type="text"
        placeholder="ESG, GCF, BOAD"
        class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
      />
    </div>
    <div>
      <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
        Active module (séparés par virgules)
      </label>
      <input
        v-model="activeModuleCsv"
        type="text"
        placeholder="esg_scoring, application"
        class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
      />
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div>
        <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
          offer_id
        </label>
        <input
          v-model="local.offer_id"
          type="text"
          placeholder="UUID offer"
          class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
          @input="emitUpdate"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
          fund_id
        </label>
        <input
          v-model="local.fund_id"
          type="text"
          placeholder="UUID fund"
          class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
          @input="emitUpdate"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
          intermediary_id
        </label>
        <input
          v-model="local.intermediary_id"
          type="text"
          placeholder="UUID intermediary"
          class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
          @input="emitUpdate"
        />
      </div>
    </div>
  </div>
</template>
