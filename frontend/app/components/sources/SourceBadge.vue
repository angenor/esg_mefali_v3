<script setup lang="ts">
import type { VerificationStatus } from '~/types/source'

interface Props {
  status: VerificationStatus
  reason?: string | null
}

const props = defineProps<Props>()

const labels: Record<VerificationStatus, string> = {
  draft: 'Brouillon',
  pending: 'En attente',
  verified: 'Verifiee',
  outdated: 'Obsolete',
}

const colors: Record<VerificationStatus, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  pending: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  verified: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  outdated: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
    :class="colors[status]"
    :title="status === 'outdated' && reason ? reason : undefined"
  >
    <span
      class="w-1.5 h-1.5 rounded-full"
      :class="{
        'bg-gray-500': status === 'draft',
        'bg-orange-500': status === 'pending',
        'bg-green-500': status === 'verified',
        'bg-red-500': status === 'outdated',
      }"
      aria-hidden="true"
    />
    {{ labels[status] }}
    <span v-if="status === 'outdated' && reason" class="ml-1 italic">
      : {{ reason }}
    </span>
  </span>
</template>
