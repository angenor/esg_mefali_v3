<script setup lang="ts">
/**
 * F10 — NumberWidget : saisie numérique formatée avec devise optionnelle.
 *
 * Features :
 * - Formatage milliers fr-FR (`Intl.NumberFormat`)
 * - Validation bornes min/max côté client
 * - Sélecteur devise (XOF/EUR/USD/CDF)
 * - Affichage équivalent monétaire (≈ 1 524 €) via fx-rates avec fallback constants
 * - Boutons +/- avec step
 *
 * Réf : FR-018, FR-022, US3.
 */
import { computed, ref, watch } from 'vue'
import type {
  InteractiveQuestion,
  NumberPayload,
  NumberResponse,
  SupportedCurrency,
} from '~/types/interactive-question'

interface Props {
  question: InteractiveQuestion
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'submit', payload: NumberResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<NumberPayload>(() => {
  const p = props.question.payload as NumberPayload | undefined
  return p ?? {
    question_type: 'number',
    unit: '',
    step: 1,
  }
})

// Constantes statiques de fallback (parité fixe BCEAO XOF↔EUR=655.957)
const FX_FALLBACK = {
  XOF_per_EUR: 655.957,
  XOF_per_USD: 600.0,
  XOF_per_CDF: 0.35,
}

const fxRates = ref<{ XOF_per_EUR: number; XOF_per_USD: number; XOF_per_CDF: number }>(FX_FALLBACK)
const isApprox = ref(true) // Tant qu'on n'a pas chargé depuis l'API
const value = ref<number | null>(payload.value.default ?? null)
const currency = ref<SupportedCurrency | null>(payload.value.currency ?? null)
const errorMsg = ref('')

// Charger les taux de change (best effort, fallback sur constants)
async function _loadFxRates() {
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiBase
    const resp = await fetch(`${apiBase}/referential/fx-rates`)
    if (resp.ok) {
      const data = await resp.json()
      if (data && typeof data.XOF_per_EUR === 'number') {
        fxRates.value = data
        isApprox.value = false
      }
    }
  } catch {
    // Best effort : fallback sur constants
  }
}

if (typeof window !== 'undefined') {
  _loadFxRates()
}

const formattedValue = computed(() => {
  if (value.value === null) return ''
  return new Intl.NumberFormat('fr-FR').format(value.value)
})

const equivalent = computed<string | null>(() => {
  if (value.value === null || !currency.value) return null
  // Convertir vers EUR par défaut si la devise n'est pas EUR
  if (currency.value === 'EUR') return null
  let eurValue: number | null = null
  if (currency.value === 'XOF') {
    eurValue = value.value / fxRates.value.XOF_per_EUR
  } else if (currency.value === 'USD') {
    eurValue = (value.value * fxRates.value.XOF_per_USD) / fxRates.value.XOF_per_EUR
  } else if (currency.value === 'CDF') {
    eurValue = (value.value * fxRates.value.XOF_per_CDF) / fxRates.value.XOF_per_EUR
  }
  if (eurValue === null) return null
  const formatted = new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(eurValue)
  return `≈ ${formatted}${isApprox.value ? ' (approx.)' : ''}`
})

watch(value, (v) => {
  errorMsg.value = ''
  if (v === null) return
  if (payload.value.min !== null && payload.value.min !== undefined && v < payload.value.min) {
    errorMsg.value = `La valeur doit être ≥ ${payload.value.min}`
  } else if (payload.value.max !== null && payload.value.max !== undefined && v > payload.value.max) {
    errorMsg.value = `La valeur doit être ≤ ${payload.value.max}`
  }
})

function increment() {
  if (inputLocked.value) return
  const cur = value.value ?? payload.value.default ?? 0
  value.value = cur + payload.value.step
}

function decrement() {
  if (inputLocked.value) return
  const cur = value.value ?? payload.value.default ?? 0
  value.value = cur - payload.value.step
}

const canSubmit = computed(() => {
  return !inputLocked.value && value.value !== null && !errorMsg.value
})

function _doSubmit() {
  if (!canSubmit.value || value.value === null) return
  const cur = currency.value
  const unit = payload.value.unit
  const formatted = `${formattedValue.value} ${cur === 'XOF' ? 'FCFA' : (cur ?? unit)}`.trim()
  const resp: NumberResponse = {
    question_type: 'number',
    value: value.value,
    currency: cur,
    formatted,
  }
  emit('submit', resp, `✓ ${formatted}`)
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-stretch gap-2">
      <!-- Bouton - -->
      <button
        type="button"
        :disabled="inputLocked"
        :data-testid="`number-decrement-${question.id}`"
        class="px-3 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card hover:bg-gray-50 dark:hover:bg-dark-hover text-lg font-bold disabled:opacity-50"
        @click="decrement"
      >
        −
      </button>

      <!-- Input numérique -->
      <input
        v-model.number="value"
        type="number"
        :step="payload.step"
        :min="payload.min ?? undefined"
        :max="payload.max ?? undefined"
        :disabled="inputLocked"
        :data-testid="`number-input-${question.id}`"
        :aria-label="`Saisie numérique ${payload.unit}`"
        :placeholder="payload.default !== null && payload.default !== undefined ? String(payload.default) : '0'"
        class="flex-1 px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text text-right tabular-nums font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
      />

      <!-- Bouton + -->
      <button
        type="button"
        :disabled="inputLocked"
        :data-testid="`number-increment-${question.id}`"
        class="px-3 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card hover:bg-gray-50 dark:hover:bg-dark-hover text-lg font-bold disabled:opacity-50"
        @click="increment"
      >
        +
      </button>

      <!-- Sélecteur devise -->
      <select
        v-if="payload.currency"
        v-model="currency"
        :disabled="inputLocked"
        :data-testid="`number-currency-${question.id}`"
        class="px-3 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm font-semibold disabled:opacity-50"
      >
        <option value="XOF">XOF</option>
        <option value="EUR">EUR</option>
        <option value="USD">USD</option>
        <option value="CDF">CDF</option>
      </select>
      <span
        v-else
        class="self-center px-2 text-sm text-gray-600 dark:text-gray-400 font-medium"
      >
        {{ payload.unit }}
      </span>
    </div>

    <!-- Affichage formaté + équivalent -->
    <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
      <span v-if="formattedValue">
        {{ formattedValue }}
        <span v-if="currency === 'XOF'">FCFA</span>
        <span v-else-if="currency">{{ currency }}</span>
      </span>
      <span v-if="equivalent" class="text-indigo-600 dark:text-indigo-400 font-medium">
        {{ equivalent }}
      </span>
    </div>

    <!-- Erreur de validation -->
    <p
      v-if="errorMsg"
      role="alert"
      class="text-xs text-red-600 dark:text-red-400 font-medium"
    >
      {{ errorMsg }}
    </p>

    <div class="flex items-center justify-between pt-1">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
        @click="emit('abandon-and-send', '')"
      >
        Répondre autrement
      </button>
      <button
        type="button"
        :disabled="!canSubmit"
        :data-testid="`number-submit-${question.id}`"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-lg transition-all"
        @click="_doSubmit"
      >
        Valider
      </button>
    </div>
  </div>
</template>
