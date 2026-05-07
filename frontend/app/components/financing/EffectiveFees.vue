<script setup lang="ts">
import { computed } from 'vue'
import type { OfferEffectiveFees } from '~/types/financing'

interface Props {
  fees: OfferEffectiveFees
}

const props = defineProps<Props>()

function formatMoney(money: { amount: string; currency: string } | null | undefined): string {
  if (!money) return '—'
  const value = parseFloat(money.amount)
  if (isNaN(value)) return money.amount
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)} Md ${money.currency}`
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)} M ${money.currency}`
  }
  return `${value.toLocaleString('fr-FR')} ${money.currency}`
}

const hasMin = computed(() => Boolean(props.fees?.total_min))
const hasMax = computed(() => Boolean(props.fees?.total_max))
const hasBreakdown = computed(() => Array.isArray(props.fees?.breakdown) && props.fees.breakdown.length > 0)
const sameMinMax = computed(() => {
  const min = props.fees?.total_min
  const max = props.fees?.total_max
  if (!min || !max) return false
  return min.amount === max.amount && min.currency === max.currency
})
</script>

<template>
  <div class="space-y-3">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
      Frais effectifs
    </h3>

    <div v-if="!hasMin && !hasMax" class="text-sm text-gray-500 dark:text-gray-400">
      Aucun frais structuré disponible.
    </div>

    <div v-else class="space-y-2">
      <div class="flex items-baseline justify-between rounded-lg bg-gray-50 dark:bg-dark-hover px-4 py-3">
        <span class="text-sm text-gray-600 dark:text-gray-400">
          Total {{ sameMinMax ? '' : 'min.' }}
        </span>
        <span class="text-base font-semibold text-gray-900 dark:text-white">
          {{ formatMoney(fees.total_min) }}
        </span>
      </div>
      <div
        v-if="!sameMinMax && hasMax"
        class="flex items-baseline justify-between rounded-lg bg-gray-50 dark:bg-dark-hover px-4 py-3"
      >
        <span class="text-sm text-gray-600 dark:text-gray-400">Total max.</span>
        <span class="text-base font-semibold text-gray-900 dark:text-white">
          {{ formatMoney(fees.total_max) }}
        </span>
      </div>
    </div>

    <div v-if="hasBreakdown" class="mt-3">
      <details class="group">
        <summary
          class="cursor-pointer text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
        >
          Détail des frais ({{ fees.breakdown!.length }})
        </summary>
        <ul class="mt-2 space-y-1.5 text-sm" role="list">
          <li
            v-for="(item, idx) in fees.breakdown"
            :key="idx"
            class="flex justify-between text-gray-600 dark:text-gray-400"
          >
            <span>{{ (item as Record<string, unknown>).label }}</span>
            <span>
              {{ formatMoney({
                amount: (item as Record<string, unknown>).amount as string,
                currency: (item as Record<string, unknown>).currency as string,
              }) }}
            </span>
          </li>
        </ul>
      </details>
    </div>
  </div>
</template>
