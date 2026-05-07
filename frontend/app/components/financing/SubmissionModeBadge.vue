<script setup lang="ts">
import { computed } from 'vue'
import type { SubmissionMode } from '~/types/financing'

interface Props {
  mode: SubmissionMode
}

const props = defineProps<Props>()

const config = computed(() => {
  if (props.mode === 'rolling') {
    return {
      label: 'Rolling',
      title: 'Soumission ouverte en continu',
      classes: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
    }
  }
  return {
    label: 'Appel à projets',
    title: 'Sessions de soumission datées',
    classes: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  }
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="config.classes"
    :aria-label="config.title"
    :title="config.title"
  >
    <span aria-hidden="true">●</span>
    {{ config.label }}
  </span>
</template>
