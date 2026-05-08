<script setup lang="ts">
import { useReports } from '~/composables/useReports'
import { useCarbonReports } from '~/composables/useCarbonReports'
import type { ReportResponse, ReportListResponse } from '~/types/report'
import type { CarbonReportListItem } from '~/types/carbon-report'

definePageMeta({
  layout: 'default',
})

const { listReports, downloadReport, loading, error } = useReports()
const carbonReportsApi = useCarbonReports()

// F21 (US5) — Onglets ESG | Carbone.
const activeTab = ref<'esg' | 'carbon'>('esg')
const carbonReports = ref<CarbonReportListItem[]>([])
const carbonTotal = ref(0)

const reports = ref<ReportResponse[]>([])
const total = ref(0)
const page = ref(1)
const limit = ref(20)
const previewReportId = ref<string | null>(null)

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const statusLabels: Record<string, string> = {
  generating: 'En cours',
  completed: 'Termine',
  failed: 'Echoue',
}

const statusClasses: Record<string, string> = {
  generating: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function togglePreview(reportId: string): void {
  previewReportId.value = previewReportId.value === reportId ? null : reportId
}

function getPreviewUrl(reportId: string): string {
  const authStore = useAuthStore()
  return `${apiBase}/reports/${reportId}/download?token=${encodeURIComponent(authStore.accessToken || '')}`
}

async function loadReports(): Promise<void> {
  const result = await listReports(page.value, limit.value)
  if (result) {
    reports.value = result.items
    total.value = result.total
  }
}

async function loadCarbonReports(): Promise<void> {
  const result = await carbonReportsApi.list(1, 20)
  if (result) {
    carbonReports.value = result.items
    carbonTotal.value = result.total
  }
}

function setTab(tab: 'esg' | 'carbon'): void {
  activeTab.value = tab
  if (tab === 'carbon' && carbonReports.value.length === 0) {
    loadCarbonReports()
  }
}

const totalPages = computed(() => Math.ceil(total.value / limit.value))

function goToPage(p: number): void {
  if (p >= 1 && p <= totalPages.value) {
    page.value = p
    loadReports()
  }
}

onMounted(async () => {
  await loadReports()
  await loadCarbonReports()
})

// Import store
import { useAuthStore } from '~/stores/auth'
</script>

<template>
  <div class="flex flex-col h-full bg-surface-bg dark:bg-surface-dark-bg">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-bold text-surface-text dark:text-surface-dark-text">
          Mes rapports
        </h1>
      </div>
      <span class="text-sm text-gray-500 dark:text-gray-400">
        {{ activeTab === 'esg' ? total : carbonTotal }} rapport{{ (activeTab === 'esg' ? total : carbonTotal) > 1 ? 's' : '' }}
      </span>
    </div>

    <!-- F21 (US5) — Onglets ESG | Carbone -->
    <div
      class="px-6 pt-4 border-b border-gray-200 dark:border-dark-border"
      role="tablist"
      aria-label="Type de rapport"
      data-testid="reports-tabs"
    >
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'esg'"
        :class="[
          'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
          activeTab === 'esg'
            ? 'border-emerald-600 text-emerald-700 dark:text-emerald-400'
            : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200',
        ]"
        data-testid="tab-esg"
        @click="setTab('esg')"
      >
        ESG ({{ total }})
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'carbon'"
        :class="[
          'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
          activeTab === 'carbon'
            ? 'border-emerald-600 text-emerald-700 dark:text-emerald-400'
            : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200',
        ]"
        data-testid="tab-carbon"
        @click="setTab('carbon')"
      >
        Carbone ({{ carbonTotal }})
      </button>
    </div>

    <div v-show="activeTab === 'esg'" class="flex-1 overflow-y-auto p-6" data-testid="esg-reports-panel">
      <!-- Chargement -->
      <div v-if="loading && reports.length === 0" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>

      <!-- Erreur -->
      <div v-else-if="error" class="text-center py-12 text-red-500 dark:text-red-400">
        {{ error }}
      </div>

      <!-- Liste vide -->
      <div v-else-if="reports.length === 0" class="text-center py-12">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p class="text-gray-500 dark:text-gray-400 mb-2">
          Aucun rapport genere
        </p>
        <p class="text-sm text-gray-400 dark:text-gray-500">
          Generez un rapport depuis la page de resultats ESG.
        </p>
        <NuxtLink
          to="/esg"
          class="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors"
        >
          Aller aux evaluations
        </NuxtLink>
      </div>

      <!-- Tableau des rapports -->
      <div v-else class="max-w-4xl mx-auto">
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl overflow-hidden">
          <table class="w-full">
            <thead>
              <tr class="bg-gray-50 dark:bg-dark-hover border-b border-gray-200 dark:border-dark-border">
                <th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Date
                </th>
                <th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Type
                </th>
                <th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Statut
                </th>
                <th class="text-right px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Taille
                </th>
                <th class="text-right px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-dark-border">
              <template v-for="report in reports" :key="report.id">
                <tr class="hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors">
                  <td class="px-4 py-3 text-sm text-surface-text dark:text-surface-dark-text">
                    {{ formatDate(report.created_at) }}
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                    Conformite ESG
                  </td>
                  <td class="px-4 py-3">
                    <span
                      class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                      :class="statusClasses[report.status] || ''"
                    >
                      {{ statusLabels[report.status] || report.status }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-sm text-right text-gray-500 dark:text-gray-400">
                    {{ formatSize(report.file_size) }}
                  </td>
                  <td class="px-4 py-3 text-right">
                    <div class="flex items-center justify-end gap-2">
                      <!-- Previsualisation -->
                      <button
                        v-if="report.status === 'completed'"
                        class="p-1.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors rounded-md hover:bg-gray-100 dark:hover:bg-dark-hover"
                        title="Previsualiser"
                        @click="togglePreview(report.id)"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                      <!-- Telecharger -->
                      <button
                        v-if="report.status === 'completed'"
                        class="p-1.5 text-gray-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors rounded-md hover:bg-gray-100 dark:hover:bg-dark-hover"
                        title="Telecharger"
                        @click="downloadReport(report.id)"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
                <!-- Previsualisation inline -->
                <tr v-if="previewReportId === report.id">
                  <td colspan="5" class="px-4 py-4 bg-gray-50 dark:bg-dark-hover">
                    <div class="rounded-lg overflow-hidden border border-gray-200 dark:border-dark-border" style="height: 600px;">
                      <iframe
                        :src="getPreviewUrl(report.id)"
                        class="w-full h-full"
                        frameborder="0"
                      />
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-6">
          <button
            class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-dark-border text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page === 1"
            @click="goToPage(page - 1)"
          >
            Precedent
          </button>
          <span class="text-sm text-gray-500 dark:text-gray-400">
            Page {{ page }} / {{ totalPages }}
          </span>
          <button
            class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-dark-border text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page === totalPages"
            @click="goToPage(page + 1)"
          >
            Suivant
          </button>
        </div>
      </div>
    </div>

    <!-- F21 (US5) — Onglet Carbone -->
    <div
      v-show="activeTab === 'carbon'"
      class="flex-1 overflow-y-auto p-6"
      data-testid="carbon-reports-panel"
    >
      <div v-if="carbonReportsApi.loading.value && carbonReports.length === 0" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>
      <div v-else-if="carbonReports.length === 0" class="text-center py-12">
        <p class="text-gray-500 dark:text-gray-400 mb-2">
          Aucun rapport carbone genere.
        </p>
        <NuxtLink
          to="/carbon"
          class="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors"
        >
          Aller au calculateur carbone
        </NuxtLink>
      </div>
      <div v-else class="max-w-4xl mx-auto">
        <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl overflow-hidden">
          <table class="w-full">
            <thead>
              <tr class="bg-gray-50 dark:bg-dark-hover border-b border-gray-200 dark:border-dark-border">
                <th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Date</th>
                <th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Statut</th>
                <th class="text-right px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Taille</th>
                <th class="text-right px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-dark-border">
              <tr v-for="r in carbonReports" :key="r.id" :data-testid="`carbon-report-row-${r.id}`">
                <td class="px-4 py-3 text-sm">{{ formatDate(r.created_at) }}</td>
                <td class="px-4 py-3">
                  <span class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium" :class="statusClasses[r.status] || ''">
                    {{ statusLabels[r.status] || r.status }}
                  </span>
                </td>
                <td class="px-4 py-3 text-sm text-right text-gray-500 dark:text-gray-400">{{ formatSize(r.file_size) }}</td>
                <td class="px-4 py-3 text-right">
                  <button
                    v-if="r.status === 'completed' || r.status === 'ready'"
                    class="p-1.5 text-gray-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors rounded-md hover:bg-gray-100 dark:hover:bg-dark-hover"
                    :title="`Telecharger le rapport carbone du ${formatDate(r.created_at)}`"
                    :data-testid="`carbon-download-${r.id}`"
                    @click="carbonReportsApi.download(r.id)"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
