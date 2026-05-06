<template>
  <span :class="badgeClasses">
    <span aria-hidden="true">{{ icon }}</span>
    <span>{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Role } from '~/types'

interface Props {
  role: Role
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'sm',
})

const isAdmin = computed(() => props.role === 'ADMIN')
const label = computed(() => (isAdmin.value ? 'Administrateur' : 'PME'))
const icon = computed(() => (isAdmin.value ? '🛡️' : '🏢'))

const badgeClasses = computed(() => {
  // F02 — palette stricte :
  //   ADMIN : rouge (signaler la zone privilegiee, mode sombre inclus)
  //   PME   : emerald (collaborateur ordinaire)
  const sizing =
    props.size === 'md'
      ? 'px-3 py-1 text-sm font-semibold'
      : 'px-2 py-0.5 text-xs font-medium'
  if (isAdmin.value) {
    return [
      'inline-flex items-center gap-1 rounded-full',
      'bg-red-700 text-white dark:bg-red-900 dark:text-red-50',
      'ring-1 ring-red-800/50 dark:ring-red-700/60',
      sizing,
    ].join(' ')
  }
  return [
    'inline-flex items-center gap-1 rounded-full',
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200',
    'ring-1 ring-emerald-200/70 dark:ring-emerald-700/60',
    sizing,
  ].join(' ')
})
</script>
