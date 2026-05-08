<template>
  <section
    class="p-5 bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg"
    aria-labelledby="mm-panel-title"
  >
    <header class="mb-4">
      <h2
        id="mm-panel-title"
        class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
      >
        Mobile Money — flux
      </h2>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        Importez votre historique CSV/Excel pour enrichir votre score crédit.
      </p>
    </header>

    <div
      v-if="consentRequired"
      class="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md"
      role="alert"
    >
      <p class="text-amber-800 dark:text-amber-300">
        Consentement Mobile Money requis pour cette analyse.
      </p>
      <button
        type="button"
        class="mt-2 inline-block text-sm font-semibold text-amber-700 dark:text-amber-300 hover:underline"
        @click="showConsentModal = true"
      >
        Donner mon consentement
      </button>
    </div>

    <ConsentRequestModal
      :open="showConsentModal"
      consent-type="mobile_money_analysis"
      :loading="consentSubmitting"
      @cancel="showConsentModal = false"
      @confirm="handleConsentConfirm"
    />

    <form
      v-else
      class="space-y-3"
      @submit.prevent="handleUpload"
    >
      <label
        for="mm-provider"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text"
      >
        Fournisseur
      </label>
      <select
        id="mm-provider"
        v-model="provider"
        class="w-full rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text px-3 py-2"
        aria-required="true"
      >
        <option value="wave">Wave</option>
        <option value="orange_money">Orange Money</option>
        <option value="mtn_momo">MTN MoMo</option>
        <option value="moov_money">Moov Money</option>
      </select>

      <label
        for="mm-file"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mt-3"
      >
        Fichier CSV/Excel (≤ 5 Mo)
      </label>
      <input
        id="mm-file"
        type="file"
        accept=".csv,text/csv"
        class="block w-full text-sm text-gray-700 dark:text-gray-300"
        aria-required="true"
        @change="handleFileChange"
      />

      <button
        type="submit"
        :disabled="!file || loading"
        class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-md"
      >
        {{ loading ? 'Analyse en cours…' : 'Importer et analyser' }}
      </button>

      <p
        v-if="error"
        class="text-sm text-red-600 dark:text-red-400"
        role="alert"
      >
        {{ error }}
      </p>
    </form>

    <div
      v-if="analysis"
      class="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3"
      aria-label="Indicateurs Mobile Money"
    >
      <KpiCard
        label="Volume mensuel moyen (XOF)"
        :value="analysis.kpis.monthly_volume_avg"
      />
      <KpiCard
        label="Régularité 30 jours"
        :value="formatPercentage(analysis.kpis.regularity_30d)"
      />
      <KpiCard
        label="Solde moyen estimé (XOF)"
        :value="analysis.kpis.avg_balance_estimate"
      />
      <KpiCard
        label="Tendance 12 mois"
        :value="formatPercentage(analysis.kpis.growth_12m)"
      />
      <KpiCard
        label="Transactions analysées"
        :value="String(analysis.kpis.transaction_count)"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  ConsentRequiredError,
  useCreditAlternativeData,
} from '~/composables/useCreditAlternativeData'
import type {
  MobileMoneyAnalysisRead,
  Provider,
} from '~/types/creditAlternative'
import KpiCard from './MobileMoneyKpiCard.vue'
import ConsentRequestModal from './ConsentRequestModal.vue'

const { uploadMobileMoney, loading } = useCreditAlternativeData()

const provider = ref<Provider>('wave')
const file = ref<File | null>(null)
const analysis = ref<MobileMoneyAnalysisRead | null>(null)
const error = ref('')
const consentRequired = ref(false)
const showConsentModal = ref(false)
const consentSubmitting = ref(false)

async function handleConsentConfirm(): Promise<void> {
  consentSubmitting.value = true
  try {
    const { apiFetch } = useAuth()
    await apiFetch('/api/me/consents/mobile_money_analysis/grant', {
      method: 'POST',
      body: { version: '1.0' },
    })
    showConsentModal.value = false
    consentRequired.value = false
  } catch (e) {
    error.value = (e as Error).message || 'Erreur lors de l’enregistrement du consentement'
  } finally {
    consentSubmitting.value = false
  }
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
}

function formatPercentage(v: number): string {
  return `${(v * 100).toFixed(1)} %`
}

async function handleUpload() {
  if (!file.value) return
  error.value = ''
  consentRequired.value = false
  try {
    const result = await uploadMobileMoney(file.value, provider.value)
    analysis.value = result.analysis
  } catch (e) {
    if (e instanceof ConsentRequiredError) {
      consentRequired.value = true
    } else {
      error.value = (e as Error).message || 'Erreur'
    }
  }
}
</script>
