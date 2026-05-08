<script setup lang="ts">
// F21 (US2) — Bouton « Générer rapport carbone PDF ».
// Désactivé si bilan non finalisé ou si une génération est déjà en cours.

import { ref } from 'vue'
import { useCarbonReports } from '~/composables/useCarbonReports'

interface Props {
  assessmentId: string
  isFinalized: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  ready: [reportId: string]
  failed: [reason: string]
}>()

const { generate, pollUntilReady, error, loading } = useCarbonReports()
const isGenerating = ref(false)
const lastReportId = ref<string | null>(null)
const successMessage = ref<string>('')

async function onClick() {
  if (!props.isFinalized || isGenerating.value) return
  isGenerating.value = true
  successMessage.value = ''
  const result = await generate(props.assessmentId)
  if (!result) {
    isGenerating.value = false
    emit('failed', error.value || 'Erreur inconnue')
    return
  }
  lastReportId.value = result.id
  const finalStatus = await pollUntilReady(result.id)
  isGenerating.value = false
  if (finalStatus === 'ready' || finalStatus === 'completed') {
    successMessage.value = 'Rapport prêt — vous pouvez le télécharger.'
    emit('ready', result.id)
  } else if (finalStatus === 'failed') {
    emit('failed', "La génération a échoué.")
  } else {
    successMessage.value = 'Génération en cours… Réessayez dans quelques instants.'
  }
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <button
      type="button"
      :disabled="!isFinalized || isGenerating || loading"
      class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed text-white text-sm font-medium transition shadow-sm"
      data-testid="generate-carbon-report-btn"
      :aria-label="isFinalized ? 'Générer le rapport carbone PDF' : 'Bilan non finalisé'"
      @click="onClick"
    >
      <span v-if="isGenerating">Génération en cours…</span>
      <span v-else-if="!isFinalized">Bilan non finalisé</span>
      <span v-else>Générer le rapport carbone PDF</span>
    </button>
    <p
      v-if="successMessage"
      class="text-xs text-emerald-600 dark:text-emerald-400"
      role="status"
      data-testid="carbon-report-success"
    >{{ successMessage }}</p>
    <p
      v-if="error"
      class="text-xs text-red-600 dark:text-red-400"
      role="alert"
      data-testid="carbon-report-error"
    >{{ error }}</p>
  </div>
</template>
