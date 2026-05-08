<script setup lang="ts">
// F14 — Comparateur multi-intermédiaires pour un fonds donné, dans le
// contexte d'un projet précis (?project_id=X obligatoire).
// Adapte ComparisonResult (F14 backend) en props ComparisonTableBlock (F11).

import { computed, onMounted, ref } from 'vue'
import ComparisonTableBlock from '~/components/richblocks/ComparisonTableBlock.vue'
import { useMatching } from '~/composables/useMatching'
import { useMatchesStore } from '~/stores/matches'
import type {
  ComparisonResult,
  ComparisonRow as ApiRow,
  ComparisonValue as ApiValue,
} from '~/types/matching'
import type {
  ComparisonRowProps,
  ComparisonSubjectProps,
  ComparisonTableBlockProps,
  ComparisonValueProps,
  ComparisonValueType,
} from '~/types/richblocks'

definePageMeta({ layout: false })

const route = useRoute()
const router = useRouter()
const matchesStore = useMatchesStore()
const { compareOffersForFund, loading, error } = useMatching()

const fundId = (route.params as { fund_id: string }).fund_id
const projectId = (route.query.project_id as string) ?? ''

const comparison = ref<ComparisonResult | null>(null)
const errorMsg = ref<string | null>(null)

async function load() {
  if (!projectId) {
    errorMsg.value =
      'Un identifiant de projet est requis pour comparer les intermédiaires.'
    return
  }
  errorMsg.value = null
  const result = await compareOffersForFund(projectId, fundId)
  if (!result) {
    errorMsg.value = error.value || 'Impossible de charger la comparaison.'
    return
  }
  comparison.value = result
  matchesStore.setComparison(fundId, result)
}

function isComparisonValueType(v: string): v is ComparisonValueType {
  return ['money', 'percentage', 'duration', 'rating', 'boolean', 'string'].includes(v)
}

function adaptValue(v: ApiValue): ComparisonValueProps {
  return {
    subjectId: v.subjectId,
    value:
      typeof v.raw === 'number' || typeof v.raw === 'string'
        ? v.raw
        : v.display,
    money:
      v.raw && typeof v.raw === 'object' && 'amount' in (v.raw as object)
        ? (v.raw as { amount: string; currency: string })
        : null,
    annotation: v.display,
    sourceId: v.sourceId ?? null,
  }
}

function adaptRow(r: ApiRow): ComparisonRowProps {
  const type: ComparisonValueType = isComparisonValueType(r.type)
    ? (r.type as ComparisonValueType)
    : 'string'
  return {
    label: r.label,
    values: r.values.map(adaptValue),
    type,
    higherIsBetter: r.values.some((v) => v.isWinner),
  }
}

function adaptSubject(s: { id: string; label: string }): ComparisonSubjectProps {
  return {
    id: s.id,
    label: s.label,
    sublabel: null,
    drilldownUrl: `/financing/offers/${s.id}?project_id=${projectId}`,
  }
}

const tableProps = computed<ComparisonTableBlockProps | null>(() => {
  if (!comparison.value) return null
  return {
    title: 'Comparaison des intermédiaires',
    subjects: comparison.value.subjects.map(adaptSubject),
    rows: comparison.value.rows.map(adaptRow),
    highlightWinner: true,
  }
})

function onNavigate(url: string) {
  router.push(url)
}

function onOpenSource() {
  // Délégué au composant SourceModal global ; F14 pages utilisent l'event
  // pour log mais l'ouverture est déléguée à un host (page-level).
}

onMounted(load)
</script>

<template>
  <div class="max-w-6xl mx-auto p-4 sm:p-6">
    <header class="mb-5">
      <button
        type="button"
        class="text-sm text-gray-600 dark:text-gray-400 hover:underline"
        data-testid="comparator-back"
        @click="router.back()"
      >
        ← Retour
      </button>
      <h1
        class="mt-2 text-xl font-bold text-gray-900 dark:text-surface-dark-text"
      >
        Comparer les intermédiaires
      </h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Fonds {{ fundId }} —
        <span v-if="projectId">Projet {{ projectId }}</span>
        <span v-else class="text-rose-600 dark:text-rose-400">
          (aucun projet sélectionné)
        </span>
      </p>
    </header>

    <div
      v-if="errorMsg"
      class="mb-4 rounded-md border border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-950/30 p-3 text-sm text-rose-700 dark:text-rose-300"
      role="alert"
      data-testid="comparator-error"
    >
      {{ errorMsg }}
    </div>

    <div
      v-if="loading && !comparison"
      class="flex items-center justify-center py-12"
      role="status"
      aria-label="Chargement de la comparaison"
    >
      <div
        class="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"
      />
    </div>

    <ComparisonTableBlock
      v-else-if="tableProps"
      v-bind="tableProps"
      data-testid="comparator-table"
      @navigate="onNavigate"
      @open-source="onOpenSource"
    />

    <div
      v-else-if="!errorMsg"
      class="rounded-md border border-dashed border-gray-300 dark:border-dark-border p-8 text-center"
      data-testid="comparator-empty"
    >
      <p class="text-sm text-gray-600 dark:text-gray-400">
        Aucun intermédiaire à comparer pour ce fonds.
      </p>
    </div>
  </div>
</template>
