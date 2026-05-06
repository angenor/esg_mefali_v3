<script setup lang="ts">
import { Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from 'chart.js'
import { useCarbon } from '~/composables/useCarbon'
import { useCarbonStore } from '~/stores/carbon'
import { useUiStore } from '~/stores/ui'
import { useSources } from '~/composables/useSources'
import SourceLink from '~/components/sources/SourceLink.vue'
import SourceModal from '~/components/sources/SourceModal.vue'
import type { CarbonSummary, BenchmarkResponse } from '~/types/carbon'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement)

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const carbonStore = useCarbonStore()
const uiStore = useUiStore()
const { fetchAssessment, fetchSummary, fetchBenchmark, loading, error } = useCarbon()

const summary = ref<CarbonSummary | null>(null)
const benchmark = ref<BenchmarkResponse | null>(null)
const allAssessments = ref<import('~/types/carbon').CarbonAssessmentSummary[]>([])
const assessmentId = computed(() => route.query.id as string | undefined)

onMounted(async () => {
  if (!assessmentId.value) {
    await loadLatestAssessment()
    return
  }

  await fetchAssessment(assessmentId.value)
  summary.value = await fetchSummary(assessmentId.value)

  await Promise.all([
    loadBenchmark(),
    loadHistory(),
  ])
})

async function loadLatestAssessment() {
  const { fetchAssessments } = useCarbon()
  await fetchAssessments('completed', 1, 1)
  const latest = carbonStore.latestCompleted
  if (latest) {
    await fetchAssessment(latest.id)
    summary.value = await fetchSummary(latest.id)
    await Promise.all([
      loadBenchmark(),
      loadHistory(),
    ])
  }
}

async function loadBenchmark() {
  if (carbonStore.currentAssessment?.sector) {
    benchmark.value = await fetchBenchmark(carbonStore.currentAssessment.sector)
  }
}

async function loadHistory() {
  const { fetchAssessments } = useCarbon()
  await fetchAssessments('completed', 1, 50)
  allAssessments.value = carbonStore.assessments
}

// F01 - Recherche dynamique de la source ADEME pour les facteurs d'emission
const ademeSourceId = ref<string | null>(null)
const selectedSourceId = ref<string | null>(null)
const sourceModalVisible = ref(false)
const { searchSources } = useSources()

onMounted(async () => {
  // Resoudre dynamiquement l'ID de la source ADEME (Base Carbone v23) pour le picto.
  try {
    const result = await searchSources('Base Carbone', { publisher: 'ADEME', pageSize: 1 })
    if (result && result.items.length > 0) {
      ademeSourceId.value = result.items[0].id
    }
  } catch {
    // Pas de source resolue - le picto sera masque automatiquement
  }
})

function handleOpenSource(sourceId: string) {
  selectedSourceId.value = sourceId
  sourceModalVisible.value = true
}

const categoryLabels: Record<string, string> = {
  energy: 'Energie',
  transport: 'Transport',
  waste: 'Dechets',
  industrial: 'Processus industriels',
  agriculture: 'Agriculture',
}

const categoryColors: Record<string, string> = {
  energy: '#F59E0B',
  transport: '#3B82F6',
  waste: '#10B981',
  industrial: '#8B5CF6',
  agriculture: '#EC4899',
}

// Donnees pour le graphique donut
const doughnutData = computed(() => {
  if (!summary.value) return null
  const categories = Object.entries(summary.value.by_category)
  return {
    labels: categories.map(([key]) => categoryLabels[key] ?? key),
    datasets: [{
      data: categories.map(([, val]) => Math.round(val.emissions_tco2e * 100) / 100),
      backgroundColor: categories.map(([key]) => categoryColors[key] ?? '#94A3B8'),
    }],
  }
})

// Donnees pour le graphique de comparaison sectorielle
const benchmarkChartData = computed(() => {
  if (!summary.value || !summary.value.sector_benchmark?.sector_average_tco2e) return null
  return {
    labels: ['Votre empreinte', 'Moyenne du secteur'],
    datasets: [{
      label: 'tCO2e/an',
      data: [summary.value.total_emissions_tco2e, summary.value.sector_benchmark.sector_average_tco2e],
      backgroundColor: ['#10B981', '#94A3B8'],
    }],
  }
})

// Donnees pour l'evolution temporelle
const historyChartData = computed(() => {
  if (allAssessments.value.length < 2) return null
  const sorted = [...allAssessments.value]
    .filter(a => a.total_emissions_tco2e !== null)
    .sort((a, b) => a.year - b.year)
  return {
    labels: sorted.map(a => String(a.year)),
    datasets: [{
      label: 'Emissions (tCO2e)',
      data: sorted.map(a => a.total_emissions_tco2e),
      backgroundColor: '#10B981',
    }],
  }
})

function positionLabel(position: string): string {
  const labels: Record<string, string> = {
    well_below_average: 'Bien en-dessous de la moyenne',
    below_average: 'En-dessous de la moyenne',
    average: 'Dans la moyenne',
    above_average: 'Au-dessus de la moyenne',
    well_above_average: 'Bien au-dessus de la moyenne',
    unknown: 'Non disponible',
  }
  return labels[position] ?? position
}

function positionColor(position: string): string {
  if (position.includes('below')) return 'text-emerald-600 dark:text-emerald-400'
  if (position === 'average') return 'text-amber-600 dark:text-amber-400'
  return 'text-red-500 dark:text-red-400'
}
</script>

<template>
  <div class="flex flex-col h-full bg-surface-bg dark:bg-surface-dark-bg">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border">
      <div class="flex items-center gap-3">
        <NuxtLink
          to="/carbon"
          class="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </NuxtLink>
        <h1 class="text-xl font-bold text-surface-text dark:text-surface-dark-text">
          Resultats Empreinte Carbone
        </h1>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-6">
      <!-- Chargement -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>

      <!-- Erreur -->
      <div v-else-if="error" class="text-center py-12 text-red-500 dark:text-red-400">
        {{ error }}
      </div>

      <!-- Pas de donnees -->
      <div v-else-if="!summary" class="text-center py-12">
        <p class="text-gray-500 dark:text-gray-400">
          Aucun bilan carbone termine. Demarrez un bilan dans le chat.
        </p>
        <button
          type="button"
          class="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors"
          @click="uiStore.openChatWidget()"
        >
          Demarrer un bilan
        </button>
      </div>

      <!-- Resultats -->
      <div v-else class="max-w-4xl mx-auto space-y-8">
        <!-- Total + Donut -->
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-6">
            Bilan carbone {{ summary.year }}
          </h2>
          <div class="flex flex-col md:flex-row items-center justify-center gap-8">
            <!-- Total emissions -->
            <div class="text-center">
              <p class="text-5xl font-bold text-surface-text dark:text-surface-dark-text">
                {{ summary.total_emissions_tco2e.toFixed(1) }}
              </p>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                tCO2e / an
                <!-- F01 picto source ADEME pour les facteurs d'emission -->
                <SourceLink
                  v-if="ademeSourceId"
                  :source-id="ademeSourceId"
                  aria-label="Voir la source des facteurs d'emission ADEME"
                  @open="handleOpenSource"
                />
              </p>
              <!-- Position sectorielle -->
              <p
                v-if="summary.sector_benchmark"
                class="text-sm mt-2 font-medium"
                :class="positionColor(summary.sector_benchmark.position)"
              >
                {{ positionLabel(summary.sector_benchmark.position) }}
              </p>
            </div>
            <!-- Donut chart -->
            <div v-if="doughnutData" class="w-64 h-64" data-guide-target="carbon-donut-chart">
              <Doughnut :data="doughnutData" :options="{ responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom' } } }" />
            </div>
          </div>
        </div>

        <!-- Ventilation par categorie -->
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Repartition par categorie
          </h2>
          <div class="space-y-3">
            <div
              v-for="(data, category) in summary.by_category"
              :key="category"
              class="flex items-center gap-4"
            >
              <span class="text-sm font-medium text-gray-600 dark:text-gray-400 w-40">
                {{ categoryLabels[category] ?? category }}
              </span>
              <div class="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :style="{ width: `${data.percentage}%`, backgroundColor: categoryColors[category] ?? '#94A3B8' }"
                />
              </div>
              <span class="text-sm font-bold text-surface-text dark:text-surface-dark-text w-24 text-right">
                {{ data.emissions_tco2e.toFixed(2) }} tCO2e
              </span>
              <span class="text-xs text-gray-400 w-12 text-right">
                {{ data.percentage.toFixed(0) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- Equivalences parlantes -->
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            En equivalent...
          </h2>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div
              v-for="equiv in summary.equivalences"
              :key="equiv.label"
              class="text-center p-4 rounded-lg bg-gray-50 dark:bg-dark-hover"
            >
              <p class="text-3xl font-bold text-surface-text dark:text-surface-dark-text">
                {{ equiv.value }}
              </p>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {{ equiv.label }}
              </p>
            </div>
          </div>
        </div>

        <!-- Plan de reduction (Phase 5) -->
        <div
          v-if="summary.reduction_plan"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
          data-guide-target="carbon-reduction-plan"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Plan de reduction
          </h2>
          <!-- Quick wins -->
          <div v-if="summary.reduction_plan.quick_wins?.length" class="mb-6">
            <h3 class="text-sm font-semibold text-emerald-600 dark:text-emerald-400 uppercase mb-3">
              Quick wins (0-6 mois)
            </h3>
            <div class="space-y-2">
              <div
                v-for="(action, idx) in summary.reduction_plan.quick_wins"
                :key="idx"
                class="flex items-center justify-between p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg"
              >
                <span class="text-sm text-surface-text dark:text-surface-dark-text">{{ action.action }}</span>
                <div class="flex items-center gap-4 text-sm">
                  <span class="text-emerald-600 dark:text-emerald-400 font-medium">
                    -{{ action.reduction_tco2e }} tCO2e
                  </span>
                  <span class="text-gray-500 dark:text-gray-400">
                    {{ action.savings_fcfa.toLocaleString('fr-FR') }} FCFA
                  </span>
                </div>
              </div>
            </div>
          </div>
          <!-- Long terme -->
          <div v-if="summary.reduction_plan.long_term?.length">
            <h3 class="text-sm font-semibold text-blue-600 dark:text-blue-400 uppercase mb-3">
              Long terme (6-24 mois)
            </h3>
            <div class="space-y-2">
              <div
                v-for="(action, idx) in summary.reduction_plan.long_term"
                :key="idx"
                class="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg"
              >
                <span class="text-sm text-surface-text dark:text-surface-dark-text">{{ action.action }}</span>
                <div class="flex items-center gap-4 text-sm">
                  <span class="text-blue-600 dark:text-blue-400 font-medium">
                    -{{ action.reduction_tco2e }} tCO2e
                  </span>
                  <span class="text-gray-500 dark:text-gray-400">
                    {{ action.savings_fcfa.toLocaleString('fr-FR') }} FCFA
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Comparaison sectorielle (Phase 6) -->
        <div
          v-if="benchmarkChartData"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
          data-guide-target="carbon-benchmark"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Comparaison sectorielle
          </h2>
          <div class="h-64">
            <Bar
              :data="benchmarkChartData"
              :options="{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                  y: { beginAtZero: true, title: { display: true, text: 'tCO2e/an' } },
                },
              }"
            />
          </div>
        </div>

        <!-- Evolution temporelle -->
        <div
          v-if="historyChartData"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
        >
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
            Evolution de l'empreinte carbone
          </h2>
          <div class="h-64">
            <Bar
              :data="historyChartData"
              :options="{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                  y: { beginAtZero: true, title: { display: true, text: 'tCO2e' } },
                },
              }"
            />
          </div>
        </div>
        <div
          v-else-if="allAssessments.length === 1"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6"
        >
          <p class="text-sm text-gray-500 dark:text-gray-400 text-center">
            Le graphique d'evolution apparaitra apres votre deuxieme bilan carbone.
          </p>
        </div>
      </div>
    </div>

    <!-- F01 SourceModal pour afficher le detail de la source -->
    <SourceModal
      :source-id="selectedSourceId"
      :visible="sourceModalVisible"
      @close="sourceModalVisible = false"
    />
  </div>
</template>
