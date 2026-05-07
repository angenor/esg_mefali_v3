<script setup lang="ts">
// F03 — Filtres pour le log d'audit (entité, source, période).
import { reactive, watch } from 'vue'
import type { AuditAction, AuditFilters, AuditSourceOfChange } from '~/types/audit'

interface Props {
  modelValue: AuditFilters
}

interface Emits {
  (event: 'update:modelValue', value: AuditFilters): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const local = reactive({
  entity_type: props.modelValue.entity_type ?? '',
  source_of_change: (props.modelValue.source_of_change ?? '') as '' | AuditSourceOfChange,
  action: (props.modelValue.action ?? '') as '' | AuditAction,
  since: props.modelValue.since ?? '',
  until: props.modelValue.until ?? '',
})

const ENTITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Toutes les entités' },
  { value: 'company_profiles', label: 'Profil entreprise' },
  { value: 'fund_applications', label: 'Candidatures' },
  { value: 'esg_assessments', label: 'Évaluations ESG' },
  { value: 'carbon_assessments', label: 'Bilans carbone' },
  { value: 'credit_scores', label: 'Scores de crédit' },
  { value: 'action_plans', label: "Plans d'action" },
  { value: 'action_items', label: 'Actions' },
  { value: 'account', label: 'Compte (consultations admin)' },
]

const SOURCE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Toutes les sources' },
  { value: 'manual', label: 'Manuel' },
  { value: 'llm', label: 'Assistant IA' },
  { value: 'admin', label: 'Admin Mefali' },
  { value: 'import', label: 'Import' },
]

const ACTION_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Toutes les actions' },
  { value: 'create', label: 'Création' },
  { value: 'update', label: 'Modification' },
  { value: 'delete', label: 'Suppression' },
  { value: 'view_admin', label: 'Consultation Admin' },
]

function emitUpdate() {
  const next: AuditFilters = {
    ...props.modelValue,
    entity_type: local.entity_type || null,
    source_of_change: (local.source_of_change || null) as AuditSourceOfChange | null,
    action: (local.action || null) as AuditAction | null,
    since: local.since || null,
    until: local.until || null,
    page: 1,
  }
  emit('update:modelValue', next)
}

function reset() {
  local.entity_type = ''
  local.source_of_change = ''
  local.action = ''
  local.since = ''
  local.until = ''
  emitUpdate()
}
</script>

<template>
  <div
    class="rounded-lg border border-gray-200 bg-white p-4 dark:border-dark-border dark:bg-dark-card"
  >
    <h3 class="mb-3 text-sm font-semibold text-gray-900 dark:text-surface-dark-text">
      Filtres
    </h3>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <label class="flex flex-col gap-1 text-xs">
        <span class="text-gray-700 dark:text-gray-300">Entité</span>
        <select
          v-model="local.entity_type"
          class="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
          @change="emitUpdate"
        >
          <option v-for="opt in ENTITY_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <label class="flex flex-col gap-1 text-xs">
        <span class="text-gray-700 dark:text-gray-300">Source</span>
        <select
          v-model="local.source_of_change"
          class="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
          @change="emitUpdate"
        >
          <option v-for="opt in SOURCE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <label class="flex flex-col gap-1 text-xs">
        <span class="text-gray-700 dark:text-gray-300">Action</span>
        <select
          v-model="local.action"
          class="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
          @change="emitUpdate"
        >
          <option v-for="opt in ACTION_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <label class="flex flex-col gap-1 text-xs">
        <span class="text-gray-700 dark:text-gray-300">Depuis</span>
        <input
          v-model="local.since"
          type="datetime-local"
          class="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
          @change="emitUpdate"
        />
      </label>

      <label class="flex flex-col gap-1 text-xs">
        <span class="text-gray-700 dark:text-gray-300">Jusqu'à</span>
        <input
          v-model="local.until"
          type="datetime-local"
          class="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
          @change="emitUpdate"
        />
      </label>

      <button
        type="button"
        class="self-end rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-dark-border dark:bg-dark-input dark:text-gray-300 dark:hover:bg-dark-hover"
        @click="reset"
      >
        Réinitialiser
      </button>
    </div>
  </div>
</template>
