<script setup lang="ts">
import { computed } from 'vue'
import type { AttestationStatus } from '~/types/attestation'

interface Props {
  status: AttestationStatus
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const labelByStatus: Record<AttestationStatus, string> = {
  authentic: 'AUTHENTIQUE',
  revoked: 'RÉVOQUÉE',
  expired: 'EXPIRÉE',
  invalid: 'INVALIDE',
}

const colorByStatus: Record<AttestationStatus, string> = {
  authentic:
    'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-200 dark:border-emerald-700',
  revoked:
    'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-900/40 dark:text-rose-200 dark:border-rose-700',
  expired:
    'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-700',
  invalid:
    'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-900/40 dark:text-rose-200 dark:border-rose-700',
}

const sizeClasses = computed(() => {
  if (props.size === 'sm') return 'px-2 py-0.5 text-[10px] font-bold tracking-wider'
  if (props.size === 'lg') return 'px-4 py-2 text-base font-bold tracking-wider'
  return 'px-3 py-1 text-xs font-bold tracking-wider'
})

const label = computed(() => labelByStatus[props.status])
const colorClasses = computed(() => colorByStatus[props.status])
</script>

<template>
  <span
    role="status"
    aria-live="polite"
    :class="[
      'inline-flex items-center gap-1 rounded-full border uppercase',
      colorClasses,
      sizeClasses,
    ]"
  >
    <slot name="icon">
      <svg
        v-if="status === 'authentic'"
        class="w-3 h-3"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="3"
          d="M5 13l4 4L19 7"
        />
      </svg>
      <svg
        v-else-if="status === 'revoked' || status === 'invalid'"
        class="w-3 h-3"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="3"
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
      <svg
        v-else-if="status === 'expired'"
        class="w-3 h-3"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="3"
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    </slot>
    {{ label }}
  </span>
</template>
