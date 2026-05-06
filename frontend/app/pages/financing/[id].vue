<script setup lang="ts">
import { useFinancing } from '~/composables/useFinancing'
import { useFinancingStore } from '~/stores/financing'
import { useSources } from '~/composables/useSources'
import SourceLink from '~/components/sources/SourceLink.vue'
import SourceModal from '~/components/sources/SourceModal.vue'
import type { Fund, FundMatch, AccessType } from '~/types/financing'

definePageMeta({
  layout: 'default',
})

const route = useRoute()
const fundId = route.params.id as string
const financingStore = useFinancingStore()
const { fetchFundDetail, fetchMatchDetail, updateMatchStatus, updateMatchIntermediary, fetchPreparationSheet, loading, error } = useFinancing()

const fund = ref<Fund | null>(null)
const match = ref<FundMatch | null>(null)
const showIntermediaryModal = ref(false)
const downloadingPdf = ref(false)

// F01 - Source GCF/BOAD pour les chiffres financement (montants min/max)
const fundingSourceId = ref<string | null>(null)
const selectedSourceId = ref<string | null>(null)
const sourceModalVisible = ref(false)
const { searchSources } = useSources()

onMounted(async () => {
  const [fundData, matchData] = await Promise.all([
    fetchFundDetail(fundId),
    fetchMatchDetail(fundId),
  ])
  fund.value = fundData
  match.value = matchData
  // Resoudre dynamiquement la source officielle du fonds (publisher = nom du fonds)
  try {
    const publisherCandidates = ['GCF', 'BOAD', 'IFC', 'AfDB']
    for (const publisher of publisherCandidates) {
      const result = await searchSources('', { publisher, pageSize: 1 })
      if (result && result.items.length > 0) {
        fundingSourceId.value = result.items[0].id
        break
      }
    }
  } catch {
    // Pas de source resolue
  }
})

function handleOpenSource(sourceId: string) {
  selectedSourceId.value = sourceId
  sourceModalVisible.value = true
}

// --- Helpers ---

function accessBadge(accessType: AccessType): { label: string; color: string } {
  const badges: Record<AccessType, { label: string; color: string }> = {
    direct: { label: 'Acces direct', color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' },
    intermediary_required: { label: 'Via intermediaire', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' },
    mixed: { label: 'Mixte', color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300' },
  }
  return badges[accessType] ?? { label: accessType, color: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300' }
}

function scoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-600 dark:text-emerald-400'
  if (score >= 50) return 'text-blue-600 dark:text-blue-400'
  if (score >= 30) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-500 dark:text-red-400'
}

function scoreBg(score: number): string {
  if (score >= 70) return 'bg-emerald-100 dark:bg-emerald-900/30'
  if (score >= 50) return 'bg-blue-100 dark:bg-blue-900/30'
  if (score >= 30) return 'bg-amber-100 dark:bg-amber-900/30'
  return 'bg-red-100 dark:bg-red-900/30'
}

function formatAmount(amount: number | null): string {
  if (!amount) return '-'
  if (amount >= 1_000_000_000) return `${(amount / 1_000_000_000).toFixed(1)} Md FCFA`
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(0)} M FCFA`
  return `${amount.toLocaleString('fr-FR')} FCFA`
}

function criteriaLabel(key: string): string {
  const labels: Record<string, string> = {
    sector: 'Secteur',
    esg: 'Score ESG',
    size: 'Taille',
    location: 'Localisation',
    documents: 'Documents',
  }
  return labels[key] ?? key
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    suggested: 'Suggere',
    interested: 'Interesse',
    contacting_intermediary: 'Contact intermediaire',
    applying: 'En candidature',
    submitted: 'Soumis',
    accepted: 'Accepte',
    rejected: 'Rejete',
  }
  return labels[status] ?? status
}

// --- Actions ---

async function markInterested() {
  if (!match.value) return
  const result = await updateMatchStatus(match.value.id, 'interested')
  if (result) {
    match.value = { ...match.value, status: 'interested' }
    showIntermediaryModal.value = true
  }
}

async function chooseIntermediary(intermediaryId: string) {
  if (!match.value) return
  const result = await updateMatchIntermediary(match.value.id, intermediaryId)
  if (result) {
    match.value = { ...match.value, status: 'contacting_intermediary', contacted_intermediary_id: intermediaryId }
    showIntermediaryModal.value = false
  }
}

async function downloadPreparationSheet() {
  if (!match.value) return
  downloadingPdf.value = true
  try {
    const blob = await fetchPreparationSheet(match.value.id)
    if (blob) {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `fiche-preparation-${fund.value?.name?.replace(/\s+/g, '-').toLowerCase() ?? 'fonds'}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    }
  } finally {
    downloadingPdf.value = false
  }
}

// Sous-scores sous forme de barres
const criteriaEntries = computed(() => {
  if (!match.value?.matching_criteria) return []
  return Object.entries(match.value.matching_criteria).map(([key, value]) => ({
    key,
    label: criteriaLabel(key),
    score: value as number,
  }))
})

// Parcours d'acces — etapes
const pathwaySteps = computed(() => {
  if (!match.value?.access_pathway) return []
  const pathway = match.value.access_pathway
  return pathway.steps || []
})
</script>

<template>
  <div class="flex flex-col h-full bg-surface-bg dark:bg-surface-dark-bg">
    <!-- Header -->
    <div class="flex items-center gap-4 px-6 py-4 border-b border-gray-200 dark:border-dark-border">
      <NuxtLink to="/financing" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
        </svg>
      </NuxtLink>
      <div v-if="fund" class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <h1 class="text-xl font-bold text-surface-text dark:text-surface-dark-text truncate">{{ fund.name }}</h1>
          <span class="text-xs px-2 py-0.5 rounded-full shrink-0" :class="accessBadge(fund.access_type).color">
            {{ accessBadge(fund.access_type).label }}
          </span>
        </div>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ fund.organization }}</p>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>

      <div v-else-if="fund" class="max-w-4xl mx-auto space-y-6">

        <!-- Score de compatibilite -->
        <div v-if="match" class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">Votre compatibilite</h2>
          <div class="flex items-center gap-6 mb-4">
            <div class="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold" :class="[scoreBg(match.compatibility_score), scoreColor(match.compatibility_score)]">
              {{ match.compatibility_score }}
            </div>
            <div class="flex-1 space-y-2">
              <div v-for="entry in criteriaEntries" :key="entry.key" class="flex items-center gap-3">
                <span class="text-xs text-gray-500 dark:text-gray-400 w-24 shrink-0">{{ entry.label }}</span>
                <div class="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                  <div class="h-2 rounded-full transition-all" :class="entry.score >= 70 ? 'bg-emerald-500' : entry.score >= 50 ? 'bg-blue-500' : entry.score >= 30 ? 'bg-amber-500' : 'bg-red-500'" :style="{ width: `${entry.score}%` }" />
                </div>
                <span class="text-xs font-medium w-8 text-right" :class="scoreColor(entry.score)">{{ entry.score }}</span>
              </div>
            </div>
          </div>

          <!-- Criteres manquants -->
          <div v-if="match.missing_criteria && Object.keys(match.missing_criteria).length" class="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
            <p class="text-sm font-medium text-amber-800 dark:text-amber-300 mb-1">Criteres a ameliorer</p>
            <ul class="text-xs text-amber-700 dark:text-amber-400 space-y-1">
              <li v-for="(items, key) in match.missing_criteria" :key="key">
                <span class="font-medium">{{ criteriaLabel(key as string) }}</span> : {{ (items as string[]).join(', ') }}
              </li>
            </ul>
          </div>

          <!-- Bouton interet + preparation -->
          <div class="mt-4 flex items-center gap-3">
            <button
              v-if="match.status === 'suggested'"
              class="px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium"
              @click="markInterested"
            >
              Je suis interesse
            </button>
            <template v-else>
              <span class="text-sm text-gray-500 dark:text-gray-400">
                Statut : <span class="font-medium text-surface-text dark:text-surface-dark-text">{{ statusLabel(match.status) }}</span>
              </span>
              <button
                v-if="match.status !== 'suggested'"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium inline-flex items-center gap-2 disabled:opacity-50"
                :disabled="downloadingPdf"
                @click="downloadPreparationSheet"
              >
                <svg v-if="!downloadingPdf" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
                <div v-else class="w-4 h-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Preparer ma visite
              </button>
            </template>
          </div>
        </div>

        <!-- Description -->
        <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-3">Description</h2>
          <p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{{ fund.description }}</p>
          <div class="flex flex-wrap gap-4 mt-4 text-sm text-gray-500 dark:text-gray-400">
            <div v-if="fund.min_amount_xof || fund.max_amount_xof">
              <span class="font-medium text-surface-text dark:text-surface-dark-text">Montant :</span>
              {{ formatAmount(fund.min_amount_xof) }} - {{ formatAmount(fund.max_amount_xof) }}
              <!-- F01 picto source des montants -->
              <SourceLink
                v-if="fundingSourceId"
                :source-id="fundingSourceId"
                aria-label="Voir la source des montants du fonds"
                @open="handleOpenSource"
              />
            </div>
            <div v-if="fund.typical_timeline_months">
              <span class="font-medium text-surface-text dark:text-surface-dark-text">Duree :</span>
              ~{{ fund.typical_timeline_months }} mois
            </div>
            <div v-if="fund.website_url">
              <a :href="fund.website_url" target="_blank" rel="noopener" class="text-brand-green hover:underline">Site web</a>
            </div>
          </div>
        </div>

        <!-- Criteres d'eligibilite -->
        <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-3">Criteres d'eligibilite</h2>
          <div class="grid gap-3 md:grid-cols-2 text-sm">
            <div v-if="fund.sectors_eligible.length">
              <span class="font-medium text-surface-text dark:text-surface-dark-text">Secteurs :</span>
              <div class="flex flex-wrap gap-1 mt-1">
                <span v-for="s in fund.sectors_eligible" :key="s" class="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{{ s }}</span>
              </div>
            </div>
            <div v-if="fund.esg_requirements.min_score">
              <span class="font-medium text-surface-text dark:text-surface-dark-text">Score ESG minimum :</span>
              <span class="text-gray-600 dark:text-gray-400"> {{ fund.esg_requirements.min_score }}/100</span>
            </div>
          </div>

          <!-- Documents requis -->
          <div v-if="fund.required_documents.length" class="mt-4">
            <span class="text-sm font-medium text-surface-text dark:text-surface-dark-text">Documents requis :</span>
            <ul class="mt-1 space-y-1">
              <li v-for="doc in fund.required_documents" :key="doc" class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" />
                </svg>
                {{ doc.replace(/_/g, ' ') }}
              </li>
            </ul>
          </div>
        </div>

        <!-- Comment acceder (parcours d'acces) -->
        <div class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-3">Comment acceder</h2>

          <!-- Message d'acces -->
          <div v-if="match?.access_pathway" class="mb-4 p-3 rounded-lg" :class="fund.access_type === 'direct' ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-blue-50 dark:bg-blue-900/20'">
            <p class="text-sm" :class="fund.access_type === 'direct' ? 'text-emerald-700 dark:text-emerald-300' : 'text-blue-700 dark:text-blue-300'">
              {{ (match.access_pathway as any)?.message || (fund.access_type === 'direct' ? 'Vous pouvez candidater directement.' : 'Ce fonds necessite un intermediaire.') }}
            </p>
          </div>

          <!-- Etapes du parcours -->
          <div v-if="fund.application_process.length" class="space-y-3">
            <div v-for="step in fund.application_process" :key="step.step" class="flex gap-3">
              <div class="flex flex-col items-center">
                <div class="w-7 h-7 rounded-full bg-brand-green text-white flex items-center justify-center text-xs font-bold shrink-0">
                  {{ step.step }}
                </div>
                <div v-if="step.step < fund.application_process.length" class="w-0.5 flex-1 bg-gray-200 dark:bg-gray-600 mt-1" />
              </div>
              <div class="pb-4">
                <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text">{{ step.title }}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ step.description }}</p>
              </div>
            </div>
          </div>

          <!-- Intermediaires disponibles -->
          <div v-if="fund.access_type !== 'direct' && fund.intermediaries.length" class="mt-6">
            <h3 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3">Intermediaires disponibles</h3>
            <div class="space-y-3">
              <div
                v-for="inter in fund.intermediaries"
                :key="inter.id"
                class="flex items-start gap-3 p-3 rounded-lg border border-gray-100 dark:border-dark-border"
                :class="inter.is_primary ? 'bg-emerald-50/50 dark:bg-emerald-900/10' : 'bg-white dark:bg-dark-card'"
              >
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-surface-text dark:text-surface-dark-text">{{ inter.name }}</span>
                    <span v-if="inter.is_primary" class="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">Recommande</span>
                  </div>
                  <p v-if="inter.role" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ inter.role }}</p>
                  <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ inter.city }}</p>
                  <p v-if="inter.typical_fees" class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ inter.typical_fees }}</p>
                </div>
                <button
                  v-if="match && (match.status === 'interested' || match.status === 'suggested')"
                  class="text-xs px-3 py-1.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors shrink-0"
                  @click="chooseIntermediary(inter.id)"
                >
                  Contacter
                </button>
              </div>
            </div>
          </div>

          <!-- Conseils -->
          <div v-if="fund.success_tips" class="mt-6 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
            <p class="text-sm font-medium text-amber-800 dark:text-amber-300 mb-1">Conseils</p>
            <p class="text-xs text-amber-700 dark:text-amber-400 leading-relaxed">{{ fund.success_tips }}</p>
          </div>
        </div>

        <!-- Timeline estimee -->
        <div v-if="fund.typical_timeline_months" class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6">
          <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-2">Timeline estimee</h2>
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <span class="text-lg font-bold text-blue-600 dark:text-blue-400">{{ fund.typical_timeline_months }}</span>
            </div>
            <div>
              <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text">{{ fund.typical_timeline_months }} mois</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">Duree typique du processus complet</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modale choix intermediaire -->
    <Teleport to="body">
      <div v-if="showIntermediaryModal && fund" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" @click.self="showIntermediaryModal = false">
        <div class="bg-white dark:bg-dark-card rounded-2xl shadow-xl max-w-md w-full mx-4 p-6">
          <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-2">Choisir un intermediaire</h3>
          <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Selectionnez l'intermediaire que vous souhaitez contacter pour ce fonds.</p>
          <div class="space-y-2 max-h-60 overflow-y-auto">
            <button
              v-for="inter in fund.intermediaries"
              :key="inter.id"
              class="w-full text-left p-3 rounded-lg border border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors"
              @click="chooseIntermediary(inter.id)"
            >
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-surface-text dark:text-surface-dark-text">{{ inter.name }}</span>
                <span v-if="inter.is_primary" class="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">Recommande</span>
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ inter.city }} — {{ inter.role }}</p>
            </button>
          </div>
          <button class="mt-4 w-full py-2 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200" @click="showIntermediaryModal = false">
            Plus tard
          </button>
        </div>
      </div>
    </Teleport>

    <!-- F01 SourceModal pour afficher le detail de la source -->
    <SourceModal
      :source-id="selectedSourceId"
      :visible="sourceModalVisible"
      @close="sourceModalVisible = false"
    />
  </div>
</template>
