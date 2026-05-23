<script setup lang="ts">
/**
 * F047 (US3) — Aperçu structurel du rapport ESIA-light + bouton génération PDF.
 *
 * 7 sections obligatoires + annexe sources F01 (D7). Génération synchrone
 * < 30 s p95 (SC-003) — l'utilisateur voit un spinner pendant le traitement.
 * Dark mode complet, ARIA region.
 */
import { computed, ref } from 'vue'

interface Props {
  projectId: string
  assessmentId: string
  /** Si l'évaluation n'est pas finalisée, le bouton est désactivé. */
  isFinalized: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'generated', filename: string): void }>()

const SECTIONS = [
  'Résumé exécutif',
  'Description du projet',
  'Diagnostic E&S (baseline)',
  'Impacts identifiés',
  "Mesures d'atténuation",
  'Engagement des parties prenantes',
  'Indicateurs de suivi (M&E)',
]

const loading = ref(false)
const error = ref('')

const tooltip = computed(() =>
  props.isFinalized
    ? "Génère le PDF ESIA-light (≤ 30 s)."
    : "Veuillez d'abord finaliser l'évaluation.",
)

async function generate(): Promise<void> {
  if (!props.isFinalized) return
  loading.value = true
  error.value = ''
  try {
    const auth = (await import('~/stores/auth')).useAuthStore()
    const config = useRuntimeConfig()
    const url = `${config.public.apiBase}/projects/${props.projectId}/esg-assessment/${props.assessmentId}/report`
    const headers: Record<string, string> = {
      Accept: 'application/pdf',
      ...(auth.accessToken ? { Authorization: `Bearer ${auth.accessToken}` } : {}),
    }
    const res = await fetch(url, { method: 'POST', headers })
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(`Génération impossible (${res.status}) : ${detail}`)
    }
    const blob = await res.blob()
    const filename = `esia-${props.assessmentId}.pdf`
    // Téléchargement automatique (D4).
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    emit('generated', filename)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erreur inattendue.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section
    role="region"
    aria-labelledby="esia-preview-title"
    class="rounded-xl border border-gray-200 bg-white p-5
           dark:border-dark-border dark:bg-dark-card"
    data-testid="esia-report-preview"
  >
    <header class="mb-3 flex items-center justify-between gap-3">
      <h3
        id="esia-preview-title"
        class="text-base font-semibold text-surface-text dark:text-surface-dark-text"
      >
        Rapport ESIA-light
      </h3>
      <span
        class="text-[11px] uppercase tracking-wide text-gray-500
               dark:text-gray-400"
      >
        Génération à la demande
      </span>
    </header>

    <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">
      Le rapport ESIA-light condense votre évaluation en 7 sections
      consommables par un bailleur vert (GCF, FEM, BOAD, AFD) +
      annexe « Sources et références » F01.
    </p>

    <ol
      class="mb-4 grid list-decimal grid-cols-1 gap-1 pl-5 text-sm
             text-surface-text marker:text-emerald-600
             dark:text-surface-dark-text dark:marker:text-emerald-400
             sm:grid-cols-2"
      data-testid="esia-sections-outline"
    >
      <li v-for="s in SECTIONS" :key="s">{{ s }}</li>
    </ol>

    <div class="flex items-center gap-3">
      <button
        type="button"
        :disabled="!isFinalized || loading"
        :title="tooltip"
        :aria-disabled="!isFinalized || loading"
        class="inline-flex items-center gap-2 rounded-md bg-emerald-700
               px-4 py-2 text-sm font-semibold text-white shadow-sm
               hover:bg-emerald-800 focus:outline-none focus:ring-2
               focus:ring-emerald-500 focus:ring-offset-1
               disabled:cursor-not-allowed disabled:opacity-60
               dark:bg-emerald-600 dark:hover:bg-emerald-500"
        data-testid="esia-generate-button"
        @click="generate"
      >
        <span v-if="loading" aria-hidden="true">⏳</span>
        <span v-else aria-hidden="true">📄</span>
        {{ loading ? 'Génération en cours…' : 'Générer le rapport ESIA' }}
      </button>
      <span
        v-if="loading"
        class="text-xs text-gray-500 dark:text-gray-400"
        aria-live="polite"
      >
        Cela peut prendre jusqu'à 30 secondes…
      </span>
    </div>

    <p
      v-if="error"
      role="alert"
      class="mt-3 rounded ring-1 ring-red-300 bg-red-50 p-2 text-xs
             text-red-800 dark:bg-red-900/20 dark:text-red-300"
    >
      {{ error }}
    </p>
  </section>
</template>
