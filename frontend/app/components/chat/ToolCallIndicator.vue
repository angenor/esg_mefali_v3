<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  toolName: string
  args?: Record<string, unknown>
}

const props = defineProps<Props>()

/**
 * Mapping des noms de tools vers des labels francais pour l'affichage.
 */
const TOOL_LABELS: Record<string, string> = {
  // Profilage
  update_company_profile: 'Mise a jour du profil...',
  get_company_profile: 'Consultation du profil...',

  // ESG
  create_esg_assessment: 'Creation de l\'evaluation ESG...',
  save_esg_criterion_score: 'Sauvegarde du critere ESG...',
  finalize_esg_assessment: 'Finalisation de l\'evaluation ESG...',
  get_esg_assessment: 'Consultation de l\'evaluation ESG...',

  // Carbone
  create_carbon_assessment: 'Creation du bilan carbone...',
  save_emission_entry: 'Enregistrement de l\'emission...',
  finalize_carbon_assessment: 'Finalisation du bilan carbone...',
  get_carbon_summary: 'Consultation du bilan carbone...',

  // Financement
  search_compatible_funds: 'Recherche de fonds compatibles...',
  save_fund_interest: 'Enregistrement de l\'interet...',
  get_fund_details: 'Consultation des details du fonds...',
  create_fund_application: 'Creation du dossier de candidature...',

  // Application
  generate_application_section: 'Generation de la section...',
  update_application_section: 'Mise a jour de la section...',
  get_application_checklist: 'Consultation de la checklist...',
  simulate_financing: 'Simulation financiere en cours...',
  export_application: 'Export du dossier...',

  // Credit
  generate_credit_score: 'Calcul du score de credit...',
  get_credit_score: 'Consultation du score de credit...',
  generate_credit_certificate: 'Generation de l\'attestation...',

  // Documents
  analyze_uploaded_document: 'Analyse du document...',
  get_document_analysis: 'Consultation de l\'analyse...',
  list_user_documents: 'Liste des documents...',

  // Plan d'action
  generate_action_plan: 'Generation du plan d\'action...',
  update_action_item: 'Mise a jour de l\'action...',
  get_action_plan: 'Consultation du plan d\'action...',

  // Chat lecture
  get_user_dashboard_summary: 'Consultation du tableau de bord...',
  get_company_profile_chat: 'Consultation du profil...',
  get_esg_assessment_chat: 'Consultation du score ESG...',
  get_carbon_summary_chat: 'Consultation du bilan carbone...',

  // F12 — Mémoire contextuelle
  recall_history: 'Recherche dans l\'historique de conversation...',
}

const label = computed(() => {
  return TOOL_LABELS[props.toolName] || `Execution de ${props.toolName}...`
})
</script>

<template>
  <div
    class="flex items-center gap-2 px-3 py-2 text-sm rounded-lg
           bg-blue-50 dark:bg-blue-900/20
           border border-blue-200 dark:border-blue-800
           text-blue-700 dark:text-blue-300
           animate-pulse"
  >
    <!-- Icone spinner -->
    <svg
      class="w-4 h-4 animate-spin shrink-0"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>

    <span>{{ label }}</span>
  </div>
</template>
