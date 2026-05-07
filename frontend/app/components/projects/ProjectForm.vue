<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { Currency, Money } from '~/types/currency'
import { SUPPORTED_CURRENCIES } from '~/types/currency'
import {
  FINANCING_STRUCTURE_LABELS,
  FINANCING_STRUCTURE_VALUES,
  MATURITY_LABELS,
  MATURITY_VALUES,
  OBJECTIVE_ENV_LABELS,
  OBJECTIVE_ENV_VALUES,
  type FinancingStructure,
  type ObjectiveEnvValue,
  type ProjectCreatePayload,
  type ProjectDetail,
  type ProjectMaturity,
  type ProjectStatus,
} from '~/types/project'

type Mode = 'create' | 'edit' | 'duplicate'

interface Props {
  mode: Mode
  initialProject?: ProjectDetail | null
  loading?: boolean
  error?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  initialProject: null,
  loading: false,
  error: null,
})

const emit = defineEmits<{
  submit: [payload: ProjectCreatePayload]
  cancel: []
}>()

interface FormState {
  name: string
  description: string
  objective_env: ObjectiveEnvValue[]
  maturity: ProjectMaturity | ''
  status: ProjectStatus
  target_amount_amount: string
  target_amount_currency: Currency
  duration_months: string
  financing_structure: FinancingStructure | ''
  expected_impact_tco2e: string
  expected_jobs_created: string
  expected_beneficiaries: string
  expected_hectares_restored: string
  location_country: string
  location_region: string
}

const form = reactive<FormState>({
  name: '',
  description: '',
  objective_env: [],
  maturity: '',
  status: 'draft',
  target_amount_amount: '',
  target_amount_currency: 'XOF',
  duration_months: '',
  financing_structure: '',
  expected_impact_tco2e: '',
  expected_jobs_created: '',
  expected_beneficiaries: '',
  expected_hectares_restored: '',
  location_country: '',
  location_region: '',
})

watch(
  () => props.initialProject,
  (p) => {
    if (!p) return
    if (props.mode === 'duplicate') {
      form.name = `${p.name} (copie)`.slice(0, 200)
      form.status = 'draft'
    } else {
      form.name = p.name
      form.status = p.status
    }
    form.description = p.description || ''
    form.objective_env = [...(p.objective_env || [])]
    form.maturity = p.maturity || ''
    if (p.target_amount) {
      form.target_amount_amount = p.target_amount.amount
      form.target_amount_currency = p.target_amount.currency
    }
    form.duration_months = p.duration_months ? String(p.duration_months) : ''
    form.financing_structure = p.financing_structure || ''
    form.expected_impact_tco2e = p.expected_impact_tco2e
      ? String(p.expected_impact_tco2e)
      : ''
    form.expected_jobs_created =
      p.expected_jobs_created !== null ? String(p.expected_jobs_created) : ''
    form.expected_beneficiaries =
      p.expected_beneficiaries !== null ? String(p.expected_beneficiaries) : ''
    form.expected_hectares_restored = p.expected_hectares_restored
      ? String(p.expected_hectares_restored)
      : ''
    form.location_country = p.location_country || ''
    form.location_region = p.location_region || ''
  },
  { immediate: true },
)

const validationError = computed(() => {
  if (!form.name.trim()) return 'Le nom du projet est requis.'
  if (form.name.length > 200) return 'Le nom ne peut dépasser 200 caractères.'
  const hasAmount = form.target_amount_amount.trim().length > 0
  const hasCurrency = !!form.target_amount_currency
  if (hasAmount && !hasCurrency) return 'Devise requise pour le montant.'
  return null
})

function toggleObjective(value: ObjectiveEnvValue) {
  if (form.objective_env.includes(value)) {
    form.objective_env = form.objective_env.filter((v) => v !== value)
  } else {
    form.objective_env = [...form.objective_env, value]
  }
}

function buildPayload(): ProjectCreatePayload {
  const payload: ProjectCreatePayload = {
    name: form.name.trim(),
  }
  if (form.description.trim()) payload.description = form.description.trim()
  if (form.objective_env.length > 0) payload.objective_env = [...form.objective_env]
  if (form.maturity) payload.maturity = form.maturity as ProjectMaturity
  payload.status = form.status

  if (form.target_amount_amount.trim()) {
    const money: Money = {
      amount: form.target_amount_amount.trim(),
      currency: form.target_amount_currency,
    }
    payload.target_amount = money
  }
  if (form.duration_months.trim()) {
    const v = parseInt(form.duration_months, 10)
    if (!Number.isNaN(v) && v > 0) payload.duration_months = v
  }
  if (form.financing_structure)
    payload.financing_structure = form.financing_structure as FinancingStructure
  if (form.expected_impact_tco2e.trim())
    payload.expected_impact_tco2e = form.expected_impact_tco2e.trim()
  if (form.expected_jobs_created.trim()) {
    const v = parseInt(form.expected_jobs_created, 10)
    if (!Number.isNaN(v) && v >= 0) payload.expected_jobs_created = v
  }
  if (form.expected_beneficiaries.trim()) {
    const v = parseInt(form.expected_beneficiaries, 10)
    if (!Number.isNaN(v) && v >= 0) payload.expected_beneficiaries = v
  }
  if (form.expected_hectares_restored.trim())
    payload.expected_hectares_restored = form.expected_hectares_restored.trim()
  if (form.location_country.trim())
    payload.location_country = form.location_country.trim().toUpperCase()
  if (form.location_region.trim())
    payload.location_region = form.location_region.trim()
  return payload
}

function onSubmit(e: Event) {
  e.preventDefault()
  if (validationError.value) return
  emit('submit', buildPayload())
}
</script>

<template>
  <form
    class="space-y-6"
    @submit="onSubmit"
  >
    <div
      v-if="error"
      class="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-if="validationError"
      class="p-3 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-sm text-amber-700 dark:text-amber-400"
      role="alert"
    >
      {{ validationError }}
    </div>

    <!-- Nom -->
    <div>
      <label
        for="project-name"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Nom du projet <span class="text-red-600">*</span>
      </label>
      <input
        id="project-name"
        v-model="form.name"
        type="text"
        maxlength="200"
        class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        required
      />
    </div>

    <!-- Description -->
    <div>
      <label
        for="project-desc"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Description
      </label>
      <textarea
        id="project-desc"
        v-model="form.description"
        rows="3"
        class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
      />
    </div>

    <!-- Objectifs environnementaux -->
    <fieldset>
      <legend class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Objectifs environnementaux
      </legend>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <label
          v-for="o in OBJECTIVE_ENV_VALUES"
          :key="o"
          class="flex items-center gap-2 px-3 py-2 rounded-md border border-gray-200 dark:border-dark-border cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-hover"
          :class="
            form.objective_env.includes(o)
              ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-300 dark:border-emerald-700'
              : 'bg-white dark:bg-dark-card'
          "
        >
          <input
            type="checkbox"
            :checked="form.objective_env.includes(o)"
            class="h-4 w-4 text-brand-green focus:ring-brand-green rounded border-gray-300 dark:border-dark-border"
            @change="toggleObjective(o)"
          />
          <span class="text-sm text-surface-text dark:text-surface-dark-text">
            {{ OBJECTIVE_ENV_LABELS[o] }}
          </span>
        </label>
      </div>
    </fieldset>

    <!-- Maturité + Statut -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label
          for="project-maturity"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Maturité
        </label>
        <select
          id="project-maturity"
          v-model="form.maturity"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        >
          <option value="">— Choisir —</option>
          <option v-for="m in MATURITY_VALUES" :key="m" :value="m">
            {{ MATURITY_LABELS[m] }}
          </option>
        </select>
      </div>
      <div>
        <label
          for="project-status"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Statut
        </label>
        <ProjectStatusSelector v-model="form.status" id="project-status" />
      </div>
    </div>

    <!-- Montant + devise -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="sm:col-span-2">
        <label
          for="project-amount"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Montant cible
        </label>
        <input
          id="project-amount"
          v-model="form.target_amount_amount"
          type="number"
          step="0.01"
          min="0"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
      <div>
        <label
          for="project-currency"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Devise
        </label>
        <select
          id="project-currency"
          v-model="form.target_amount_currency"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        >
          <option v-for="c in SUPPORTED_CURRENCIES" :key="c" :value="c">
            {{ c }}
          </option>
        </select>
      </div>
    </div>

    <!-- Durée + structure financement -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label
          for="project-duration"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Durée (mois)
        </label>
        <input
          id="project-duration"
          v-model="form.duration_months"
          type="number"
          min="1"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
      <div>
        <label
          for="project-financing"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Structure de financement
        </label>
        <select
          id="project-financing"
          v-model="form.financing_structure"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        >
          <option value="">— Choisir —</option>
          <option
            v-for="f in FINANCING_STRUCTURE_VALUES"
            :key="f"
            :value="f"
          >
            {{ FINANCING_STRUCTURE_LABELS[f] }}
          </option>
        </select>
      </div>
    </div>

    <!-- Impacts attendus -->
    <fieldset class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <legend class="sr-only">Impacts attendus</legend>
      <div>
        <label
          for="project-tco2e"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Impact CO2e attendu (tCO2e)
        </label>
        <input
          id="project-tco2e"
          v-model="form.expected_impact_tco2e"
          type="number"
          step="0.0001"
          min="0"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
      <div>
        <label
          for="project-jobs"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Emplois créés attendus
        </label>
        <input
          id="project-jobs"
          v-model="form.expected_jobs_created"
          type="number"
          min="0"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
      <div>
        <label
          for="project-benef"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Bénéficiaires attendus
        </label>
        <input
          id="project-benef"
          v-model="form.expected_beneficiaries"
          type="number"
          min="0"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
      <div>
        <label
          for="project-hectares"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Hectares restaurés (ha)
        </label>
        <input
          id="project-hectares"
          v-model="form.expected_hectares_restored"
          type="number"
          step="0.01"
          min="0"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
    </fieldset>

    <!-- Localisation -->
    <fieldset class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <legend class="sr-only">Localisation</legend>
      <div>
        <label
          for="project-country"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Pays (ISO alpha-2)
        </label>
        <input
          id="project-country"
          v-model="form.location_country"
          type="text"
          maxlength="2"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green uppercase"
          placeholder="CI"
        />
      </div>
      <div class="sm:col-span-2">
        <label
          for="project-region"
          class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
        >
          Région / Ville
        </label>
        <input
          id="project-region"
          v-model="form.location_region"
          type="text"
          maxlength="100"
          class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-brand-green"
        />
      </div>
    </fieldset>

    <!-- Actions -->
    <div class="flex items-center justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-border">
      <button
        type="button"
        class="px-4 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover"
        @click="emit('cancel')"
      >
        Annuler
      </button>
      <button
        type="submit"
        :disabled="loading || !!validationError"
        class="px-4 py-2 text-sm rounded-md bg-brand-green text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
      >
        {{
          mode === 'create'
            ? 'Créer le projet'
            : mode === 'duplicate'
              ? 'Dupliquer'
              : 'Enregistrer'
        }}
      </button>
    </div>
  </form>
</template>
