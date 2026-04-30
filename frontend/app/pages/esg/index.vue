<script setup lang="ts">
import { useEsg } from '~/composables/useEsg'
import { useEsgStore } from '~/stores/esg'
import { useUiStore } from '~/stores/ui'
import { useToast } from '~/composables/useToast'

definePageMeta({
  layout: 'default',
})

const esgStore = useEsgStore()
const uiStore = useUiStore()
const { fetchAssessments, createAssessment, loading, error, sessionExpired } = useEsg()
const toast = useToast()

// Patch E : guard synchrone contre le double-clic (le flag asynchrone `loading`
// ne se met a true qu'apres la resolution de la microtache).
const isCreating = ref(false)

onMounted(() => {
  fetchAssessments()
})

// Spec fix-esg-scoring-node-routing : avant d'ouvrir le chat, creer une row
// draft cote backend pour eviter le scenario « 6 confirmations widget acceptees
// sans aucune row creee ». En cas d'echec API, ne pas ouvrir le chat et notifier.
async function startNewAssessment(): Promise<void> {
  if (isCreating.value) return
  isCreating.value = true
  try {
    const assessment = await createAssessment()
    if (!assessment) {
      // Patch F : si la session a expire, useEsg.handleAuthFailure() a deja
      // declenche la redirection /login — on n'affiche pas de toast d'erreur
      // (evite un flash juste avant la redirection, NFR9).
      if (!sessionExpired.value) {
        toast.error(error.value || 'Impossible de créer l\'évaluation. Réessayez.')
      }
      return
    }
    await fetchAssessments()
    uiStore.openChatWidget()
  } finally {
    isCreating.value = false
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'Brouillon',
    in_progress: 'En cours',
    completed: 'Terminee',
  }
  return labels[status] ?? status
}

function statusColor(status: string): string {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
    in_progress: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
    completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  }
  return colors[status] ?? 'bg-gray-100 text-gray-600'
}

function scoreColor(score: number | null): string {
  if (score === null) return 'text-gray-400'
  if (score < 40) return 'text-red-500'
  if (score < 70) return 'text-amber-500'
  return 'text-emerald-500'
}
</script>

<template>
  <div class="flex flex-col h-full bg-surface-bg dark:bg-surface-dark-bg">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border">
      <div>
        <h1 class="text-xl font-bold text-surface-text dark:text-surface-dark-text">
          Evaluation ESG
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Evaluez et suivez les performances ESG de votre entreprise
        </p>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-2 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium disabled:opacity-60"
        :disabled="loading || isCreating"
        @click="startNewAssessment"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
        </svg>
        Nouvelle evaluation
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-6">
      <!-- Etat de chargement -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>

      <!-- Erreur -->
      <div
        v-else-if="error"
        class="text-center py-12 text-red-500 dark:text-red-400"
      >
        {{ error }}
      </div>

      <!-- Aucune evaluation -->
      <div
        v-else-if="!esgStore.hasAssessments"
        class="flex flex-col items-center justify-center py-16 text-center"
      >
        <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-emerald-600 dark:text-emerald-400" viewBox="0 0 20 20" fill="currentColor">
            <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
            <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-2">
          Aucune evaluation ESG
        </h3>
        <p class="text-gray-500 dark:text-gray-400 max-w-md mb-6">
          Demarrez votre premiere evaluation ESG dans le chat. Notre assistant vous guidera a travers les 30 criteres environnementaux, sociaux et de gouvernance.
        </p>
        <button
          type="button"
          class="inline-flex items-center gap-2 px-6 py-3 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium disabled:opacity-60"
          :disabled="loading || isCreating"
          @click="startNewAssessment"
        >
          Demarrer dans le chat
        </button>
      </div>

      <!-- Liste des evaluations -->
      <div v-else class="space-y-4">
        <div
          v-for="assessment in esgStore.assessments"
          :key="assessment.id"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-5 hover:shadow-md transition-shadow"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-4">
              <!-- Score cercle -->
              <div
                class="w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold"
                :class="assessment.overall_score !== null
                  ? 'bg-emerald-50 dark:bg-emerald-900/20'
                  : 'bg-gray-100 dark:bg-gray-700'"
              >
                <span :class="scoreColor(assessment.overall_score)">
                  {{ assessment.overall_score !== null ? Math.round(assessment.overall_score) : '—' }}
                </span>
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-surface-text dark:text-surface-dark-text">
                    Evaluation v{{ assessment.version }}
                  </span>
                  <span
                    class="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="statusColor(assessment.status)"
                  >
                    {{ statusLabel(assessment.status) }}
                  </span>
                </div>
                <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  Secteur : {{ assessment.sector }} &middot; {{ formatDate(assessment.created_at) }}
                </p>
              </div>
            </div>
            <NuxtLink
              v-if="assessment.status === 'completed'"
              :to="`/esg/results?id=${assessment.id}`"
              class="inline-flex items-center gap-1 text-sm text-brand-green hover:underline"
            >
              Voir les resultats
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
              </svg>
            </NuxtLink>
            <button
              v-else
              type="button"
              class="inline-flex items-center gap-1 text-sm text-amber-600 dark:text-amber-400 hover:underline"
              @click="uiStore.openChatWidget()"
            >
              Continuer
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <!-- Mini barres de pilier si completed -->
          <div
            v-if="assessment.status === 'completed' && assessment.overall_score !== null"
            class="flex gap-4 mt-4 pt-3 border-t border-gray-100 dark:border-dark-border/50"
          >
            <div class="flex-1">
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-500 dark:text-gray-400">Env.</span>
                <span class="font-medium text-emerald-600 dark:text-emerald-400">
                  {{ Math.round(assessment.environment_score ?? 0) }}
                </span>
              </div>
              <div class="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full">
                <div
                  class="h-full bg-emerald-500 rounded-full"
                  :style="{ width: `${assessment.environment_score ?? 0}%` }"
                />
              </div>
            </div>
            <div class="flex-1">
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-500 dark:text-gray-400">Social</span>
                <span class="font-medium text-blue-600 dark:text-blue-400">
                  {{ Math.round(assessment.social_score ?? 0) }}
                </span>
              </div>
              <div class="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full">
                <div
                  class="h-full bg-blue-500 rounded-full"
                  :style="{ width: `${assessment.social_score ?? 0}%` }"
                />
              </div>
            </div>
            <div class="flex-1">
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-500 dark:text-gray-400">Gouv.</span>
                <span class="font-medium text-violet-600 dark:text-violet-400">
                  {{ Math.round(assessment.governance_score ?? 0) }}
                </span>
              </div>
              <div class="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full">
                <div
                  class="h-full bg-violet-500 rounded-full"
                  :style="{ width: `${assessment.governance_score ?? 0}%` }"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
