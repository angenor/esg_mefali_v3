<script setup lang="ts">
import type { EffectiveDocument } from '~/types/financing'

interface Props {
  documents: EffectiveDocument[]
}

defineProps<Props>()
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
      Documents requis
    </h3>
    <div v-if="!documents || documents.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
      Aucun document spécifique requis.
    </div>
    <ul v-else class="space-y-2" role="list">
      <li
        v-for="(doc, idx) in documents"
        :key="idx"
        class="flex items-start gap-3 rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-3"
      >
        <span
          class="mt-0.5 h-2 w-2 flex-shrink-0 rounded-full"
          :class="doc.mandatory
            ? 'bg-red-500 dark:bg-red-400'
            : 'bg-gray-400 dark:bg-gray-500'"
          aria-hidden="true"
        />
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900 dark:text-white">
            {{ doc.title }}
            <span
              v-if="doc.mandatory"
              class="ml-2 inline-flex items-center rounded-full bg-red-100 dark:bg-red-900/30 px-2 py-0.5 text-xs font-medium text-red-700 dark:text-red-300"
              aria-label="Document obligatoire"
            >
              Obligatoire
            </span>
            <span
              v-else
              class="ml-2 inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-700 dark:text-gray-300"
            >
              Optionnel
            </span>
          </p>
          <p
            v-if="doc.format_spec"
            class="mt-1 text-xs text-gray-500 dark:text-gray-400"
          >
            Format : {{ doc.format_spec }}
          </p>
        </div>
      </li>
    </ul>
  </div>
</template>
