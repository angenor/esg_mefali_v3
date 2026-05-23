<script setup lang="ts">
/**
 * F047 — Badge distinguant ESG Entreprise (F05) vs ESG Projet (F047).
 * Mitigation R1 — confusion UX entre les 2 pipelines.
 */
import { computed } from 'vue'

interface Props {
  target: 'company' | 'project'
}
const props = defineProps<Props>()

const label = computed(() =>
  props.target === 'project' ? 'ESG Projet' : 'ESG Entreprise',
)
const colorClasses = computed(() =>
  props.target === 'project'
    ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 ring-emerald-300 dark:ring-emerald-700'
    : 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 ring-blue-300 dark:ring-blue-700',
)
const ariaLabel = computed(() =>
  props.target === 'project'
    ? 'Évaluation au niveau du projet (référentiels IFC PS / GCF ESS / BOAD ESS)'
    : 'Évaluation au niveau de l\'entreprise (référentiel Mefali / GRI 2021)',
)
</script>

<template>
  <span
    role="status"
    :aria-label="ariaLabel"
    :class="[
      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ring-1 ring-inset',
      colorClasses,
    ]"
  >
    <svg
      class="w-3 h-3"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        :d="target === 'project'
          ? 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
          : 'M3 21V7a2 2 0 012-2h14a2 2 0 012 2v14M9 21V11h6v10'"
      />
    </svg>
    {{ label }}
  </span>
</template>
