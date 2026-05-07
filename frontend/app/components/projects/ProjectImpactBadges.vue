<script setup lang="ts">
import { computed } from 'vue'
import {
  OBJECTIVE_ENV_LABELS,
  type ObjectiveEnvValue,
  type ProjectDetail,
  type ProjectSummary,
} from '~/types/project'

interface Props {
  project: ProjectSummary | ProjectDetail
}

const props = defineProps<Props>()

const objectiveLabels = computed<Array<{ key: ObjectiveEnvValue; label: string }>>(
  () =>
    (props.project.objective_env || []).map((v) => ({
      key: v,
      label: OBJECTIVE_ENV_LABELS[v] || v,
    })),
)

const showJobs = computed(() => {
  const detail = props.project as ProjectDetail
  return typeof detail.expected_jobs_created === 'number' && detail.expected_jobs_created > 0
})

const showBeneficiaries = computed(() => {
  const detail = props.project as ProjectDetail
  return (
    typeof detail.expected_beneficiaries === 'number' &&
    detail.expected_beneficiaries > 0
  )
})

const showCO2 = computed(() => {
  const value = props.project.expected_impact_tco2e
  return value !== null && value !== undefined && Number(value) > 0
})

const co2Display = computed(() => {
  const value = Number(props.project.expected_impact_tco2e)
  if (Number.isNaN(value)) return ''
  return `${value.toLocaleString('fr-FR')} tCO2e`
})
</script>

<template>
  <div role="list" class="flex flex-wrap gap-2">
    <span
      v-for="obj in objectiveLabels"
      :key="obj.key"
      role="listitem"
      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/40"
    >
      {{ obj.label }}
    </span>
    <span
      v-if="showCO2"
      role="listitem"
      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400 border border-blue-200 dark:border-blue-800/40"
      :title="`Impact CO2e attendu : ${co2Display}`"
    >
      {{ co2Display }}
    </span>
    <span
      v-if="showJobs"
      role="listitem"
      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400 border border-amber-200 dark:border-amber-800/40"
    >
      {{ (project as ProjectDetail).expected_jobs_created }} emplois
    </span>
    <span
      v-if="showBeneficiaries"
      role="listitem"
      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400 border border-purple-200 dark:border-purple-800/40"
    >
      {{ (project as ProjectDetail).expected_beneficiaries }} bénéficiaires
    </span>
  </div>
</template>
