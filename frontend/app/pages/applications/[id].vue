<script setup lang="ts">
import { useApplications } from '~/composables/useApplications'
import { useApplicationsStore } from '~/stores/applications'
import { useSources } from '~/composables/useSources'
import SourceLink from '~/components/sources/SourceLink.vue'
import SourceModal from '~/components/sources/SourceModal.vue'

definePageMeta({ layout: 'default' })

const route = useRoute()
const appStore = useApplicationsStore()
const {
  fetchApplication,
  generateSection,
  updateSection,
  updateStatus,
  exportApplication,
  simulateFinancing,
  generatePrepSheet,
  loading,
  error,
} = useApplications()

const generatingSection = ref<string | null>(null)
const editorContent = ref('')
const editingSection = ref<string | null>(null)
const confirmRegenerate = ref<string | null>(null)
const simulationLoading = ref(false)

// F01 - source officielle du fonds (montants/frais/delais)
const fundingSourceId = ref<string | null>(null)
const selectedSourceId = ref<string | null>(null)
const sourceModalVisible = ref(false)
const { searchSources } = useSources()

onMounted(async () => {
  const id = route.params.id as string
  await fetchApplication(id)
  // Resoudre dynamiquement la source officielle (publishers candidates)
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

const app = computed(() => appStore.currentApplication)
const activeTab = computed({
  get: () => appStore.activeTab,
  set: (val: string) => appStore.setActiveTab(val),
})

const tabs = computed(() => {
  const baseTabs = [
    { key: 'sections', label: 'Sections' },
    { key: 'checklist', label: 'Checklist' },
  ]
  if (app.value && app.value.target_type !== 'fund_direct') {
    baseTabs.push({ key: 'prep', label: 'Fiche de préparation' })
  }
  baseTabs.push({ key: 'simulation', label: 'Simulation' })
  return baseTabs
})

const TARGET_TYPE_LABELS: Record<string, string> = {
  fund_direct: 'Candidature directe',
  intermediary_bank: 'Via banque partenaire',
  intermediary_agency: "Via agence d'implémentation",
  intermediary_developer: 'Via développeur carbone',
}

const TARGET_TYPE_COLORS: Record<string, string> = {
  fund_direct: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  intermediary_bank: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  intermediary_agency: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  intermediary_developer: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
}

const SECTION_STATUS_LABELS: Record<string, string> = {
  not_generated: 'Non rédigée',
  generated: 'Générée',
  validated: 'Validée',
}

const SECTION_STATUS_COLORS: Record<string, string> = {
  not_generated: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  generated: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  validated: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
}

async function handleGenerateSection(sectionKey: string) {
  if (!app.value) return
  // Si la section est deja generee, demander confirmation
  const section = app.value.sections[sectionKey]
  if (section?.status === 'generated') {
    confirmRegenerate.value = sectionKey
    return
  }
  await doGenerateSection(sectionKey)
}

async function doGenerateSection(sectionKey: string) {
  if (!app.value) return
  confirmRegenerate.value = null
  generatingSection.value = sectionKey
  await generateSection(app.value.id, sectionKey)
  generatingSection.value = null
}

function cancelRegenerate() {
  confirmRegenerate.value = null
}

function startEditing(sectionKey: string) {
  if (!app.value) return
  const section = app.value.sections[sectionKey]
  editorContent.value = section?.content || ''
  editingSection.value = sectionKey
}

async function saveEditing() {
  if (!app.value || !editingSection.value) return
  await updateSection(app.value.id, editingSection.value, editorContent.value)
  editingSection.value = null
}

function cancelEditing() {
  editingSection.value = null
  editorContent.value = ''
}

async function validateSection(sectionKey: string) {
  if (!app.value) return
  await updateSection(app.value.id, sectionKey, undefined, 'validated')
}

async function handleExport(format: 'pdf' | 'docx') {
  if (!app.value) return
  await exportApplication(app.value.id, format)
}

async function handleSimulate() {
  if (!app.value) return
  simulationLoading.value = true
  await simulateFinancing(app.value.id)
  simulationLoading.value = false
}

async function handleDownloadPrepSheet() {
  if (!app.value) return
  await generatePrepSheet(app.value.id)
}

function formatXOF(amount: number): string {
  return new Intl.NumberFormat('fr-FR').format(amount) + ' FCFA'
}
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <!-- Chargement -->
    <div v-if="loading && !app" class="flex items-center justify-center py-20">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
    </div>

    <!-- Erreur -->
    <div v-else-if="error && !app" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
      <p class="text-red-700 dark:text-red-400">{{ error }}</p>
    </div>

    <!-- Contenu -->
    <template v-else-if="app">
      <!-- En-tête -->
      <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6 mb-6">
        <div class="flex items-start justify-between mb-4">
          <div>
            <div class="flex items-center gap-3 mb-2">
              <NuxtLink to="/applications" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
              </NuxtLink>
              <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
                {{ app.fund.name }}
              </h1>
            </div>
            <p class="text-gray-500 dark:text-gray-400">{{ app.fund.organization }}</p>
          </div>
          <!-- Badge destinataire -->
          <span :class="['px-3 py-1 rounded-full text-sm font-medium', TARGET_TYPE_COLORS[app.target_type] || '']">
            {{ TARGET_TYPE_LABELS[app.target_type] || app.target_type }}
          </span>
        </div>

        <!-- Intermediaire (si present) -->
        <div v-if="app.intermediary" class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
          <h3 class="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-2">Intermédiaire</h3>
          <div class="text-sm text-blue-600 dark:text-blue-400 space-y-1">
            <p class="font-medium">{{ app.intermediary.name }}</p>
            <p v-if="app.intermediary.contact_email">
              <a :href="`mailto:${app.intermediary.contact_email}`" class="underline">{{ app.intermediary.contact_email }}</a>
            </p>
            <p v-if="app.intermediary.contact_phone">
              <a :href="`tel:${app.intermediary.contact_phone}`" class="underline">{{ app.intermediary.contact_phone }}</a>
            </p>
            <p v-if="app.intermediary.physical_address">{{ app.intermediary.physical_address }}</p>
          </div>
        </div>

        <!-- Statut + Actions -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="text-sm text-gray-500 dark:text-gray-400">Statut :</span>
            <span class="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
              {{ app.status_label }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
              @click="handleExport('pdf')"
            >
              Export PDF
            </button>
            <button
              class="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              @click="handleExport('docx')"
            >
              Export Word
            </button>
          </div>
        </div>
      </div>

      <!-- Onglets -->
      <div class="border-b border-gray-200 dark:border-dark-border mb-6">
        <nav class="flex gap-6">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :class="[
              'pb-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.key
                ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
            ]"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <!-- Onglet Sections -->
      <div v-if="activeTab === 'sections'" class="space-y-4">
        <div
          v-for="(section, key) in app.sections"
          :key="key"
          class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl overflow-hidden"
        >
          <!-- Header section -->
          <div class="flex items-center justify-between px-5 py-3 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-dark-border">
            <div class="flex items-center gap-3">
              <h3 class="font-medium text-surface-text dark:text-surface-dark-text">{{ section.title }}</h3>
              <span :class="['px-2 py-0.5 rounded-full text-xs font-medium', SECTION_STATUS_COLORS[section.status] || '']">
                {{ SECTION_STATUS_LABELS[section.status] || section.status }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <button
                v-if="section.status !== 'validated'"
                class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                :disabled="generatingSection === key"
                @click="handleGenerateSection(key as string)"
              >
                <span v-if="generatingSection === key" class="flex items-center gap-1">
                  <div class="animate-spin rounded-full h-3 w-3 border-b-2 border-white" />
                  Génération...
                </span>
                <span v-else>{{ section.status === 'not_generated' ? 'Générer' : 'Regénérer' }}</span>
              </button>
              <button
                v-if="section.content && section.status !== 'validated'"
                class="px-3 py-1.5 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                @click="startEditing(key as string)"
              >
                Modifier
              </button>
              <button
                v-if="section.status === 'generated'"
                class="px-3 py-1.5 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
                @click="validateSection(key as string)"
              >
                Valider
              </button>
            </div>
          </div>

          <!-- Confirmation de regeneration -->
          <div
            v-if="confirmRegenerate === key"
            class="px-5 py-3 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800"
          >
            <p class="text-sm text-amber-700 dark:text-amber-300 mb-2">
              Le contenu actuel sera remplacé. Voulez-vous regénérer cette section ?
            </p>
            <div class="flex gap-2">
              <button
                class="px-3 py-1.5 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700"
                @click="doGenerateSection(key as string)"
              >
                Confirmer
              </button>
              <button
                class="px-3 py-1.5 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg"
                @click="cancelRegenerate"
              >
                Annuler
              </button>
            </div>
          </div>

          <!-- Contenu -->
          <div class="p-5">
            <template v-if="editingSection === key">
              <textarea
                v-model="editorContent"
                class="w-full h-64 p-3 border border-gray-300 dark:border-dark-border rounded-lg bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text font-mono text-sm"
              />
              <div class="flex justify-end gap-2 mt-3">
                <button
                  class="px-4 py-2 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg"
                  @click="cancelEditing"
                >
                  Annuler
                </button>
                <button
                  class="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
                  @click="saveEditing"
                >
                  Enregistrer
                </button>
              </div>
            </template>
            <template v-else-if="section.content">
              <div class="prose dark:prose-invert max-w-none" v-html="section.content" />
            </template>
            <template v-else>
              <p class="text-gray-400 dark:text-gray-500 italic">
                Section non encore rédigée. Cliquez sur "Générer" pour créer le contenu.
              </p>
            </template>
          </div>
        </div>
      </div>

      <!-- Onglet Checklist -->
      <div v-if="activeTab === 'checklist'" class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
        <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
          Documents requis
        </h3>
        <div v-if="app.checklist.length === 0" class="text-gray-400 dark:text-gray-500 italic">
          Aucun document requis.
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="item in app.checklist"
            :key="item.key"
            class="flex items-center justify-between py-3 border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <div class="flex items-center gap-3">
              <div
                :class="[
                  'w-5 h-5 rounded-full flex items-center justify-center',
                  item.status === 'provided'
                    ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-400'
                    : 'bg-gray-100 text-gray-400 dark:bg-gray-700 dark:text-gray-500',
                ]"
              >
                <svg v-if="item.status === 'provided'" class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                </svg>
                <div v-else class="w-2 h-2 rounded-full bg-current" />
              </div>
              <span class="text-sm text-surface-text dark:text-surface-dark-text">{{ item.name }}</span>
            </div>
            <span
              :class="[
                'text-xs font-medium px-2 py-0.5 rounded-full',
                item.status === 'provided'
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300'
                  : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
              ]"
            >
              {{ item.status === 'provided' ? 'Fourni' : 'Manquant' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Onglet Fiche de préparation -->
      <div v-if="activeTab === 'prep' && app.target_type !== 'fund_direct'" class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text">
            Fiche de préparation
          </h3>
        </div>

        <div v-if="app.intermediary" class="space-y-4">
          <p class="text-gray-600 dark:text-gray-400">
            Cette fiche résume votre entreprise, votre score ESG, votre bilan carbone et les documents disponibles
            pour préparer votre rendez-vous avec <strong>{{ app.intermediary.name }}</strong>.
          </p>

          <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 class="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-2">Contact intermédiaire</h4>
            <div class="text-sm text-blue-600 dark:text-blue-400 space-y-1">
              <p><strong>{{ app.intermediary.name }}</strong></p>
              <p v-if="app.intermediary.contact_email">
                Email : <a :href="`mailto:${app.intermediary.contact_email}`" class="underline">{{ app.intermediary.contact_email }}</a>
              </p>
              <p v-if="app.intermediary.contact_phone">
                Tél : <a :href="`tel:${app.intermediary.contact_phone}`" class="underline">{{ app.intermediary.contact_phone }}</a>
              </p>
              <p v-if="app.intermediary.physical_address">Adresse : {{ app.intermediary.physical_address }}</p>
            </div>
          </div>

          <button
            class="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
            @click="handleDownloadPrepSheet"
          >
            Télécharger la fiche PDF
          </button>
        </div>
        <div v-else class="text-gray-400 dark:text-gray-500 italic">
          Aucun intermédiaire associé à ce dossier.
        </div>
      </div>

      <!-- Onglet Simulation -->
      <div v-if="activeTab === 'simulation'" class="space-y-6">
        <!-- Pas encore de simulation -->
        <div v-if="!app.simulation" class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6 text-center">
          <div class="text-gray-400 dark:text-gray-500 mb-4">
            <svg class="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
            Simulateur de financement
          </h3>
          <p class="text-gray-500 dark:text-gray-400 mb-4">
            Estimez le montant éligible, le ROI vert, la timeline et l'impact carbone de votre projet.
          </p>
          <button
            class="px-6 py-2.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
            :disabled="simulationLoading"
            @click="handleSimulate"
          >
            <span v-if="simulationLoading" class="flex items-center gap-2">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Simulation en cours...
            </span>
            <span v-else>Lancer la simulation</span>
          </button>
        </div>

        <!-- Résultats de simulation -->
        <template v-else>
          <!-- Montant éligible -->
          <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
            <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
              Estimation de financement
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div class="bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-4">
                <p class="text-xs text-emerald-600 dark:text-emerald-400 font-medium mb-1">Montant éligible estimé</p>
                <p class="text-xl font-bold text-emerald-700 dark:text-emerald-300">
                  {{ formatXOF(app.simulation.eligible_amount_xof as number) }}
                </p>
              </div>
              <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
                <p class="text-xs text-blue-600 dark:text-blue-400 font-medium mb-1">Économies annuelles estimées</p>
                <p class="text-xl font-bold text-blue-700 dark:text-blue-300">
                  {{ formatXOF((app.simulation.roi_green as Record<string, number>).annual_savings_xof) }}
                </p>
              </div>
              <div class="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4">
                <p class="text-xs text-purple-600 dark:text-purple-400 font-medium mb-1">Retour sur investissement</p>
                <p class="text-xl font-bold text-purple-700 dark:text-purple-300">
                  {{ (app.simulation.roi_green as Record<string, number>).payback_months }} mois
                </p>
              </div>
            </div>
          </div>

          <!-- Impact carbone + frais -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
              <h4 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3">Impact carbone estimé</h4>
              <div class="flex items-center gap-3">
                <div class="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                  <svg class="w-6 h-6 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                </div>
                <div>
                  <p class="text-2xl font-bold text-green-700 dark:text-green-300">
                    {{ app.simulation.carbon_impact_tco2e }} tCO2e
                  </p>
                  <p class="text-xs text-gray-500 dark:text-gray-400">réduction estimée</p>
                </div>
              </div>
            </div>
            <div v-if="(app.simulation.intermediary_fees_xof as number) > 0" class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
              <h4 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-3">Frais d'intermédiaire estimés</h4>
              <div class="flex items-center gap-3">
                <div class="w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center">
                  <svg class="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p class="text-2xl font-bold text-amber-700 dark:text-amber-300">
                    {{ formatXOF(app.simulation.intermediary_fees_xof as number) }}
                  </p>
                  <p class="text-xs text-gray-500 dark:text-gray-400">frais estimés</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Timeline -->
          <div class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-xl p-6">
            <h4 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text mb-4">
              Timeline estimée
            </h4>
            <div class="space-y-3">
              <div
                v-for="(step, index) in (app.simulation.timeline as Array<{step: string; duration_weeks: string}>)"
                :key="index"
                class="flex items-center gap-4"
              >
                <div class="flex flex-col items-center">
                  <div class="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center text-sm font-bold text-emerald-600 dark:text-emerald-400">
                    {{ index + 1 }}
                  </div>
                  <div v-if="index < (app.simulation.timeline as Array<unknown>).length - 1" class="w-0.5 h-6 bg-gray-200 dark:bg-gray-700 mt-1" />
                </div>
                <div class="flex-1 py-2">
                  <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text">{{ step.step }}</p>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{{ step.duration_weeks }} semaines</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Relancer -->
          <div class="text-center">
            <button
              class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              :disabled="simulationLoading"
              @click="handleSimulate"
            >
              Relancer la simulation
            </button>
          </div>
        </template>
      </div>
    </template>

    <!-- F01 SourceModal pour afficher le detail de la source -->
    <SourceModal
      :source-id="selectedSourceId"
      :visible="sourceModalVisible"
      @close="sourceModalVisible = false"
    />
  </div>
</template>
