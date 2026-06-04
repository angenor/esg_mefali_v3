<script setup lang="ts">
import { useApplications } from '~/composables/useApplications'
import { useApplicationsStore } from '~/stores/applications'
import type { ApplicationSummary } from '~/stores/applications'
import ApplicationProjectLink from '~/components/applications/ApplicationProjectLink.vue'

definePageMeta({ layout: 'default' })

const appStore = useApplicationsStore()
const { fetchApplications, loading, error } = useApplications()

const statusFilter = ref<string>('')

onMounted(() => {
  fetchApplications()
})

const filteredApplications = computed(() => {
  if (!statusFilter.value) return appStore.applications
  return appStore.applications.filter(a => a.status === statusFilter.value)
})

const TARGET_TYPE_LABELS: Record<string, string> = {
  fund_direct: 'Direct',
  intermediary_bank: 'Via banque',
  intermediary_agency: 'Via agence',
  intermediary_developer: 'Via développeur carbone',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  preparing_documents: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  in_progress: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300',
  review: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  ready_for_intermediary: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  ready_for_fund: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  submitted_to_intermediary: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300',
  submitted_to_fund: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300',
  under_review: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
  accepted: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
}

function getStatusColor(status: string): string {
  return STATUS_COLORS[status] || 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
}

function progressPercent(app: ApplicationSummary): number {
  const p = app.sections_progress
  if (p.total === 0) return 0
  return Math.round((p.generated / p.total) * 100)
}
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <!-- En-tête -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
          Dossiers de Candidature
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Gérez vos dossiers de candidature aux fonds verts
        </p>
      </div>
      <!-- Filtre par statut -->
      <select
        v-model="statusFilter"
        class="px-3 py-2 text-sm border border-gray-300 dark:border-dark-border rounded-lg bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:ring-2 focus:ring-emerald-500"
      >
        <option value="">Tous les statuts</option>
        <option value="draft">Brouillon</option>
        <option value="preparing_documents">Préparation des documents</option>
        <option value="in_progress">Rédaction en cours</option>
        <option value="review">Relecture</option>
        <option value="ready_for_intermediary">Prêt pour l'intermédiaire</option>
        <option value="ready_for_fund">Prêt pour soumission</option>
        <option value="submitted_to_intermediary">Soumis à l'intermédiaire</option>
        <option value="submitted_to_fund">Soumis au fonds</option>
        <option value="under_review">En cours d'examen</option>
        <option value="accepted">Accepté</option>
        <option value="rejected">Rejeté</option>
      </select>
    </div>

    <!-- Chargement -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      <span class="ml-3 text-gray-500 dark:text-gray-400">Chargement...</span>
    </div>

    <!-- Erreur -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
      <p class="text-red-700 dark:text-red-400">{{ error }}</p>
    </div>

    <!-- État vide -->
    <div v-else-if="!appStore.hasApplications" class="text-center py-20">
      <div class="text-gray-400 dark:text-gray-500 mb-4">
        <svg class="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h3 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">Aucun dossier</h3>
      <p class="text-gray-500 dark:text-gray-400">
        Créez votre premier dossier depuis la page Financement en choisissant un fonds.
      </p>
    </div>

    <!-- Liste -->
    <div v-else class="space-y-4">
      <NuxtLink
        v-for="app in filteredApplications"
        :key="app.id"
        :to="`/applications/${app.id}`"
        class="block bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-5 hover:shadow-md dark:hover:bg-dark-hover transition-all"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text">
                {{ app.fund_name }}
              </h3>
              <span :class="['px-2 py-0.5 rounded-full text-xs font-medium', getStatusColor(app.status)]">
                {{ app.status_label }}
              </span>
            </div>
            <div class="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
              <span class="inline-flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
                {{ TARGET_TYPE_LABELS[app.target_type] || app.target_type }}
              </span>
              <!-- 050 — rappel discret du projet lié (lien 1:1, F06) -->
              <ApplicationProjectLink
                v-if="app.project"
                :project="app.project"
                variant="compact"
                class="max-w-[16rem]"
              />
              <span v-if="app.intermediary_name" class="inline-flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
                {{ app.intermediary_name }}
              </span>
              <span>Créé le {{ formatDate(app.created_at) }}</span>
            </div>
          </div>
          <!-- Progression -->
          <div class="text-right ml-4">
            <div class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {{ app.sections_progress.generated }}/{{ app.sections_progress.total }} sections
            </div>
            <div class="w-32 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                class="h-full bg-emerald-500 rounded-full transition-all"
                :style="{ width: `${progressPercent(app)}%` }"
              />
            </div>
            <!-- 049 (US5) — badge compact M/N documents fournis -->
            <div
              v-if="app.checklist_progress && app.checklist_progress.total > 0"
              class="mt-2 inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
            >
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {{ app.checklist_progress.provided }}/{{ app.checklist_progress.total }} documents
            </div>
          </div>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>
