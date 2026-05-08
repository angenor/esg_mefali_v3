<script setup lang="ts">
// F20 — Badge type ressource (5 couleurs).
import { computed } from 'vue'
import type { ResourceType } from '~/types/resource'
import { RESOURCE_TYPE_COLORS, RESOURCE_TYPE_LABELS } from '~/types/resource'

interface Props {
  type: ResourceType
}

const props = defineProps<Props>()

const label = computed(() => RESOURCE_TYPE_LABELS[props.type])
const color = computed(() => RESOURCE_TYPE_COLORS[props.type])

const colorClasses = computed<string>(() => {
  const map: Record<string, string> = {
    emerald:
      'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
    violet:
      'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200',
    rose: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
    amber:
      'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
  }
  return map[color.value] ?? map.emerald
})
</script>

<template>
  <span
    :class="['inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium', colorClasses]"
    role="status"
    :aria-label="`Type de ressource : ${label}`"
  >
    {{ label }}
  </span>
</template>
