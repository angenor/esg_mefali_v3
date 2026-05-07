<script setup lang="ts">
import { useFinancing } from '~/composables/useFinancing'
import { useFinancingStore } from '~/stores/financing'
import { useUiStore } from '~/stores/ui'
import type {
  AccessType,
  FundMatchSummary,
  FundSummary,
  IntermediarySummary,
  OfferSummary,
} from '~/types/financing'

definePageMeta({
  layout: 'default',
})

const financingStore = useFinancingStore()
const uiStore = useUiStore()
const {
  fetchMatches, fetchFunds, fetchIntermediaries,
  listOffers,
  loading, error,
} = useFinancing()

// F07 — Feature flag (default false) : true → vue Cards Offres
const runtimeConfig = useRuntimeConfig()
const useOfferView = computed(() => Boolean(runtimeConfig.public.useOfferView))

const offers = ref<OfferSummary[]>([])

async function loadOffers(): Promise<void> {
  try {
    const result = await listOffers({ limit: 50 })
    offers.value = result.items
  } catch {
    // erreurs gérées par le composable
  }
}

onMounted(() => {
  if (useOfferView.value) {
    loadOffers()
  } else {
    fetchMatches()
    fetchFunds()
    fetchIntermediaries()
  }
})

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

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    suggested: 'Suggere',
    interested: 'Interesse',
    contacting_intermediary: 'Contact inter.',
    applying: 'En candidature',
    submitted: 'Soumis',
    accepted: 'Accepte',
    rejected: 'Rejete',
  }
  return labels[status] ?? status
}

function fundTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    international: 'International',
    regional: 'Regional',
    national: 'National',
    carbon_market: 'Marche carbone',
    local_bank_green_line: 'Ligne verte bancaire',
  }
  return labels[type] ?? type
}

function orgTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    bank: 'Banque',
    development_bank: 'Banque de dev.',
    un_agency: 'Agence ONU',
    ngo: 'ONG',
    government_agency: 'Agence gouv.',
    consulting_firm: 'Cabinet conseil',
    carbon_developer: 'Dev. carbone',
  }
  return labels[type] ?? type
}

// --- Filtres fonds ---
const fundTypeFilter = ref('')
const accessTypeFilter = ref('')
const sectorFilter = ref('')
const statusFilter = ref('')
const minAmountFilter = ref<number | null>(null)
const maxAmountFilter = ref<number | null>(null)

// Secteurs uniques extraits des fonds
const availableSectors = computed(() => {
  const sectors = new Set<string>()
  for (const fund of financingStore.funds) {
    for (const s of fund.sectors_eligible) {
      sectors.add(s)
    }
  }
  return [...sectors].sort()
})

const filteredFunds = computed(() => {
  let items = financingStore.funds
  if (fundTypeFilter.value) items = items.filter(f => f.fund_type === fundTypeFilter.value)
  if (accessTypeFilter.value) items = items.filter(f => f.access_type === accessTypeFilter.value)
  if (sectorFilter.value) items = items.filter(f => f.sectors_eligible.includes(sectorFilter.value))
  if (statusFilter.value) items = items.filter(f => f.status === statusFilter.value)
  if (minAmountFilter.value != null) items = items.filter(f => !f.max_amount_xof || f.max_amount_xof >= minAmountFilter.value!)
  if (maxAmountFilter.value != null) items = items.filter(f => !f.min_amount_xof || f.min_amount_xof <= maxAmountFilter.value!)
  return items
})

// --- Filtre intermediaires ---
const orgTypeFilter = ref('')
const countryFilter = ref('')
const selectedIntermediary = ref<IntermediarySummary | null>(null)

const availableCountries = computed(() => {
  const countries = new Set<string>()
  for (const inter of financingStore.intermediaries) {
    countries.add(inter.country)
  }
  return [...countries].sort()
})

const filteredIntermediaries = computed(() => {
  let items = financingStore.intermediaries
  if (orgTypeFilter.value) items = items.filter(i => i.organization_type === orgTypeFilter.value)
  if (countryFilter.value) items = items.filter(i => i.country === countryFilter.value)
  return items
})

const tabs = [
  { key: 'recommendations', label: 'Recommandations' },
  { key: 'funds', label: 'Tous les fonds' },
  { key: 'intermediaries', label: 'Intermediaires' },
] as const
</script>

<template>
  <div class="flex flex-col h-full bg-surface-bg dark:bg-surface-dark-bg">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border">
      <div>
        <h1 class="text-xl font-bold text-surface-text dark:text-surface-dark-text">Financement Vert</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ useOfferView ? 'Offres = Couples Fonds × Intermédiaire' : "Fonds verts, matching et parcours d'acces" }}
        </p>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-2 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium"
        @click="uiStore.openChatWidget()"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clip-rule="evenodd" />
        </svg>
        Conseils IA
      </button>
    </div>

    <!-- F07 — Vue Cards Offres (feature flag USE_OFFER_VIEW) -->
    <div v-if="useOfferView" class="flex-1 overflow-auto px-6 py-6">
      <div v-if="loading" class="text-center py-12 text-gray-500 dark:text-gray-400">
        Chargement des offres...
      </div>
      <div
        v-else-if="offers.length === 0"
        class="rounded-lg border-2 border-dashed border-gray-300 dark:border-dark-border p-8 text-center text-gray-500 dark:text-gray-400"
      >
        Aucune offre publiée disponible.
      </div>
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <OfferCard
          v-for="offer in offers"
          :key="offer.id"
          :offer="offer"
        />
      </div>
    </div>

    <!-- Vue legacy (Cards Fonds + intermédiaires) si flag inactif -->
    <template v-else>

    <!-- Tabs -->
    <div class="flex border-b border-gray-200 dark:border-dark-border px-6">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="financingStore.activeTab === tab.key
          ? 'border-brand-green text-brand-green'
          : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
        @click="financingStore.setActiveTab(tab.key)"
      >
        {{ tab.label }}
        <span
          v-if="tab.key === 'recommendations' && financingStore.matchesTotal > 0"
          class="ml-1.5 text-xs px-1.5 py-0.5 rounded-full bg-brand-green text-white"
        >{{ financingStore.matchesTotal }}</span>
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6" data-guide-target="financing-fund-list">
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-green" />
      </div>

      <!-- Error: ESG requise -->
      <div v-else-if="financingStore.error && String(financingStore.error).toLowerCase().includes('esg')" class="text-center py-12">
        <div class="w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mx-auto mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-amber-600 dark:text-amber-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-lg font-medium text-surface-text dark:text-surface-dark-text mb-2">Evaluation ESG requise</h3>
        <p class="text-gray-500 dark:text-gray-400 mb-4 max-w-md mx-auto">Pour recevoir des recommandations de financement, vous devez d'abord completer votre evaluation ESG.</p>
        <NuxtLink to="/esg" class="inline-flex items-center gap-2 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium">
          Realiser mon evaluation ESG
        </NuxtLink>
      </div>

      <!-- Error: profil incomplet -->
      <div v-else-if="financingStore.error && String(financingStore.error).toLowerCase().includes('profil')" class="text-center py-12">
        <div class="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-blue-600 dark:text-blue-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-lg font-medium text-surface-text dark:text-surface-dark-text mb-2">Profil incomplet</h3>
        <p class="text-gray-500 dark:text-gray-400 mb-4 max-w-md mx-auto">Completez votre profil entreprise pour que nous puissions identifier les financements adaptes.</p>
        <NuxtLink to="/profile" class="inline-flex items-center gap-2 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium">
          Completer mon profil
        </NuxtLink>
      </div>

      <!-- Error: generique -->
      <div v-else-if="financingStore.error" class="text-center py-12">
        <div class="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-red-600 dark:text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
        </div>
        <h3 class="text-lg font-medium text-surface-text dark:text-surface-dark-text mb-2">Erreur de chargement</h3>
        <p class="text-gray-500 dark:text-gray-400 mb-4 max-w-md mx-auto">{{ financingStore.error }}</p>
        <button class="inline-flex items-center gap-2 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium" @click="fetchMatches(); fetchFunds(); fetchIntermediaries()">
          Reessayer
        </button>
      </div>

      <!-- Tab: Recommandations -->
      <template v-else-if="financingStore.activeTab === 'recommendations'">
        <div v-if="!financingStore.hasMatches" class="flex flex-col items-center justify-center py-16 text-center">
          <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-emerald-600 dark:text-emerald-400" viewBox="0 0 20 20" fill="currentColor">
              <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z" />
              <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clip-rule="evenodd" />
            </svg>
          </div>
          <h3 class="text-lg font-medium text-surface-text dark:text-surface-dark-text mb-2">Aucune recommandation</h3>
          <p class="text-gray-500 dark:text-gray-400 mb-4 max-w-md">Completez votre profil et evaluation ESG pour recevoir des recommandations de financements verts.</p>
          <div class="flex flex-wrap items-center justify-center gap-3">
            <NuxtLink to="/profile" class="inline-flex items-center gap-2 px-4 py-2 border border-brand-green text-brand-green rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors text-sm font-medium">
              Completer mon profil
            </NuxtLink>
            <NuxtLink to="/esg" class="inline-flex items-center gap-2 px-4 py-2 bg-brand-green text-white rounded-lg hover:bg-emerald-600 transition-colors text-sm font-medium">
              Evaluation ESG
            </NuxtLink>
          </div>
        </div>

        <div v-else class="space-y-4">
          <NuxtLink
            v-for="match in financingStore.matches"
            :key="match.id"
            :to="`/financing/${match.fund.id}`"
            class="block bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5 hover:shadow-md dark:hover:bg-dark-hover transition-all"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <h3 class="text-base font-semibold text-surface-text dark:text-surface-dark-text truncate">{{ match.fund.name }}</h3>
                  <span class="text-xs px-2 py-0.5 rounded-full shrink-0" :class="accessBadge(match.fund.access_type).color">
                    {{ accessBadge(match.fund.access_type).label }}
                  </span>
                </div>
                <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">{{ match.fund.organization }}</p>
                <div class="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                  <span v-if="match.fund.min_amount_xof || match.fund.max_amount_xof">
                    {{ formatAmount(match.fund.min_amount_xof) }} - {{ formatAmount(match.fund.max_amount_xof) }}
                  </span>
                  <span v-if="match.estimated_timeline_months">~{{ match.estimated_timeline_months }} mois</span>
                  <span v-if="match.recommended_intermediaries.length" class="text-blue-600 dark:text-blue-400">
                    {{ match.recommended_intermediaries[0].name }}
                  </span>
                </div>
              </div>
              <div class="flex flex-col items-center shrink-0">
                <div class="w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold" :class="[scoreBg(match.compatibility_score), scoreColor(match.compatibility_score)]">
                  {{ match.compatibility_score }}
                </div>
                <span class="text-[10px] text-gray-400 mt-1">compatibilite</span>
              </div>
            </div>
          </NuxtLink>
        </div>
      </template>

      <!-- Tab: Tous les fonds -->
      <template v-else-if="financingStore.activeTab === 'funds'">
        <!-- Filtres -->
        <div class="flex flex-wrap gap-3 mb-6">
          <select v-model="fundTypeFilter" class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text">
            <option value="">Tous les types</option>
            <option value="international">International</option>
            <option value="regional">Regional</option>
            <option value="national">National</option>
            <option value="carbon_market">Marche carbone</option>
            <option value="local_bank_green_line">Ligne verte bancaire</option>
          </select>
          <select v-model="accessTypeFilter" class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text">
            <option value="">Tous les acces</option>
            <option value="direct">Acces direct</option>
            <option value="intermediary_required">Via intermediaire</option>
            <option value="mixed">Mixte</option>
          </select>
          <select v-model="sectorFilter" class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text">
            <option value="">Tous les secteurs</option>
            <option v-for="s in availableSectors" :key="s" :value="s">{{ s }}</option>
          </select>
          <select v-model="statusFilter" class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text">
            <option value="">Tous les statuts</option>
            <option value="active">Actif</option>
            <option value="closed">Clos</option>
            <option value="upcoming">A venir</option>
          </select>
          <input
            v-model.number="minAmountFilter"
            type="number"
            placeholder="Montant min (FCFA)"
            class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text w-44"
          />
          <input
            v-model.number="maxAmountFilter"
            type="number"
            placeholder="Montant max (FCFA)"
            class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text w-44"
          />
        </div>

        <div v-if="!filteredFunds.length" class="text-center py-12 text-gray-500 dark:text-gray-400">
          Aucun fonds ne correspond aux filtres.
        </div>

        <div v-else class="grid gap-4 md:grid-cols-2">
          <NuxtLink
            v-for="fund in filteredFunds"
            :key="fund.id"
            :to="`/financing/${fund.id}`"
            class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5 hover:shadow-md dark:hover:bg-dark-hover transition-all"
          >
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text truncate">{{ fund.name }}</h3>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">{{ fund.organization }}</p>
            <div class="flex flex-wrap gap-2 mb-3">
              <span class="text-xs px-2 py-0.5 rounded-full" :class="accessBadge(fund.access_type).color">
                {{ accessBadge(fund.access_type).label }}
              </span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                {{ fundTypeLabel(fund.fund_type) }}
              </span>
              <span v-if="fund.status !== 'active'" class="text-xs px-2 py-0.5 rounded-full" :class="fund.status === 'upcoming' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'">
                {{ fund.status === 'upcoming' ? 'A venir' : 'Clos' }}
              </span>
            </div>
            <div class="flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span v-if="fund.min_amount_xof || fund.max_amount_xof">{{ formatAmount(fund.min_amount_xof) }} - {{ formatAmount(fund.max_amount_xof) }}</span>
              <span v-if="fund.typical_timeline_months">~{{ fund.typical_timeline_months }} mois</span>
            </div>
          </NuxtLink>
        </div>
      </template>

      <!-- Tab: Intermediaires -->
      <template v-else-if="financingStore.activeTab === 'intermediaries'">
        <!-- Filtres -->
        <div class="flex flex-wrap gap-3 mb-6">
          <select v-model="orgTypeFilter" class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text">
            <option value="">Tous les types</option>
            <option value="bank">Banque</option>
            <option value="development_bank">Banque de developpement</option>
            <option value="un_agency">Agence ONU</option>
            <option value="ngo">ONG</option>
            <option value="government_agency">Agence gouvernementale</option>
            <option value="consulting_firm">Cabinet conseil</option>
            <option value="carbon_developer">Developpeur carbone</option>
          </select>
          <select v-model="countryFilter" class="text-sm border border-gray-200 dark:border-dark-border rounded-lg px-3 py-2 bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text">
            <option value="">Tous les pays</option>
            <option v-for="c in availableCountries" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>

        <div v-if="!filteredIntermediaries.length" class="text-center py-12 text-gray-500 dark:text-gray-400">
          Aucun intermediaire ne correspond aux filtres.
        </div>

        <div v-else class="grid gap-4 md:grid-cols-2">
          <div
            v-for="inter in filteredIntermediaries"
            :key="inter.id"
            class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-5 hover:shadow-md dark:hover:bg-dark-hover transition-all cursor-pointer"
            @click="selectedIntermediary = selectedIntermediary?.id === inter.id ? null : inter"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <h3 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-1">{{ inter.name }}</h3>
                <div class="flex flex-wrap gap-2 mb-2">
                  <span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                    {{ orgTypeLabel(inter.organization_type) }}
                  </span>
                  <span class="text-xs text-gray-500 dark:text-gray-400">{{ inter.city }}, {{ inter.country }}</span>
                </div>
              </div>
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-400 shrink-0 mt-1 transition-transform" :class="selectedIntermediary?.id === inter.id ? 'rotate-180' : ''" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </div>
            <div class="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
              <span v-if="Object.keys(inter.services_offered).filter(k => inter.services_offered[k]).length">
                {{ Object.keys(inter.services_offered).filter(k => inter.services_offered[k]).length }} services
              </span>
            </div>

            <!-- Detail inline -->
            <div v-if="selectedIntermediary?.id === inter.id" class="mt-3 pt-3 border-t border-gray-100 dark:border-dark-border space-y-2">
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div v-if="Object.keys(inter.services_offered).length">
                  <span class="font-medium text-surface-text dark:text-surface-dark-text">Services :</span>
                  <div class="flex flex-wrap gap-1 mt-1">
                    <span
                      v-for="(val, key) in inter.services_offered"
                      :key="key"
                      class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                    >{{ String(key).replace(/_/g, ' ') }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
    </template>
  </div>
</template>
