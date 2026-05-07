<script setup lang="ts">
// F04 — Composant Money typed avec affichage natif + équivalent PME.

import { computed, onMounted, ref, watch } from 'vue'

import { useUiStore } from '~/stores/ui'
import { useCurrency } from '~/composables/useCurrency'
import { CURRENCY_SYMBOLS, type Currency, type Money } from '~/types/currency'

interface Props {
  money: Money | null | undefined
  /** Affiche l'équivalent en devise PME (par défaut true). */
  showPmeCurrency?: boolean
  /** Optionnel : forcer un mode d'affichage (sinon lit le store ui). */
  modeOverride?: 'native' | 'pme' | 'both' | null
}

const props = withDefaults(defineProps<Props>(), {
  showPmeCurrency: true,
  modeOverride: null,
})

const ui = useUiStore()
const currency = useCurrency()

const equivalentMoney = ref<Money | null>(null)

const effectiveMode = computed(() => props.modeOverride ?? ui.displayCurrencyMode)

const pmeCurrency = currency.getPmeCurrency()

const isSameCurrency = computed<boolean>(() => {
  return !!props.money && props.money.currency === pmeCurrency
})

async function refreshEquivalent() {
  if (
    !props.money
    || !props.showPmeCurrency
    || isSameCurrency.value
    || effectiveMode.value === 'native'
  ) {
    equivalentMoney.value = null
    return
  }
  try {
    equivalentMoney.value = await currency.convert(props.money, pmeCurrency)
  }
  catch {
    equivalentMoney.value = null
  }
}

onMounted(() => {
  refreshEquivalent()
})
watch(() => [props.money, effectiveMode.value, props.showPmeCurrency], () => {
  refreshEquivalent()
})

const nativeText = computed<string>(() => {
  if (!props.money) return ''
  return currency.format(props.money)
})
const equivalentText = computed<string>(() => {
  return equivalentMoney.value ? currency.format(equivalentMoney.value) : ''
})

const showNative = computed<boolean>(() => {
  if (!props.money) return false
  return effectiveMode.value !== 'pme' || isSameCurrency.value
})
const showEquivalent = computed<boolean>(() => {
  if (!props.money || !props.showPmeCurrency || isSameCurrency.value) return false
  if (effectiveMode.value === 'native') return false
  return equivalentMoney.value !== null
})
</script>

<template>
  <span
    class="money-display inline-flex items-center gap-1 text-surface-text dark:text-surface-dark-text"
    :title="props.money ? `Devise native : ${CURRENCY_SYMBOLS[props.money.currency as Currency]}` : ''"
  >
    <span v-if="showNative" class="money-display__native font-medium">
      {{ nativeText }}
    </span>
    <span
      v-if="showEquivalent"
      class="money-display__equivalent text-sm text-gray-500 dark:text-gray-400 ml-1"
    >
      ({{ '≈' }} {{ equivalentText }})
    </span>
    <span v-if="!props.money" class="text-gray-400 dark:text-gray-500 italic">
      —
    </span>
  </span>
</template>
