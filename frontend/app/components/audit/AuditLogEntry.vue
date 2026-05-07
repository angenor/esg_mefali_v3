<script setup lang="ts">
// F03 — Affiche un événement d'audit en français, dark mode compatible.
import { computed } from 'vue'
import type { AuditEvent } from '~/types/audit'
import { useAuthStore } from '~/stores/auth'

interface Props {
  event: AuditEvent
}

const props = defineProps<Props>()
const authStore = useAuthStore()

// Libellés en français pour chaque action
const ACTION_LABELS: Record<string, string> = {
  create: 'Création',
  update: 'Modification',
  delete: 'Suppression',
  view_admin: 'Consultation Admin',
}

const SOURCE_LABELS: Record<string, string> = {
  manual: 'Manuel',
  llm: 'Assistant IA',
  import: 'Import',
  admin: 'Admin Mefali',
}

const ENTITY_LABELS: Record<string, string> = {
  company_profiles: 'Profil entreprise',
  fund_applications: 'Candidature au fonds',
  esg_assessments: 'Évaluation ESG',
  carbon_assessments: 'Bilan carbone',
  credit_scores: 'Score de crédit',
  action_plans: "Plan d'action",
  action_items: 'Action',
  account: 'Compte',
}

const actionLabel = computed(() => ACTION_LABELS[props.event.action] ?? props.event.action)
const sourceLabel = computed(
  () => SOURCE_LABELS[props.event.source_of_change] ?? props.event.source_of_change,
)
const entityLabel = computed(
  () => ENTITY_LABELS[props.event.entity_type] ?? props.event.entity_type,
)

const actorLabel = computed(() => {
  if (props.event.action === 'view_admin') return 'Un admin Mefali'
  if (props.event.source_of_change === 'llm') return "L'assistant IA"
  if (props.event.source_of_change === 'admin') return 'Un admin Mefali'
  if (authStore.user && props.event.user_id === authStore.user.id) return 'Vous'
  return props.event.user_email ?? 'Un collaborateur'
})

const diffSummary = computed(() => {
  if (props.event.action !== 'update' || !props.event.field) return null
  const oldStr = formatValue(props.event.old_value)
  const newStr = formatValue(props.event.new_value)
  return `${props.event.field} : ${oldStr} → ${newStr}`
})

function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '∅'
  if (typeof v === 'object') {
    const obj = v as Record<string, unknown>
    if (obj._truncated) {
      return `[valeur tronquée : ${obj._truncated_size} octets]`
    }
    return JSON.stringify(v)
  }
  return String(v)
}

const relativeTime = computed(() => {
  const now = Date.now()
  const ts = new Date(props.event.timestamp).getTime()
  const diff = Math.floor((now - ts) / 1000)
  if (diff < 60) return `il y a ${diff} s`
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`
  return `il y a ${Math.floor(diff / 86400)} j`
})

// Accent couleur pour view_admin (cohérent F02 admin)
const isViewAdmin = computed(() => props.event.action === 'view_admin')
</script>

<template>
  <li
    role="listitem"
    :data-action="event.action"
    :data-source="event.source_of_change"
    class="flex flex-col gap-2 rounded-lg border p-4 transition-colors"
    :class="
      isViewAdmin
        ? 'border-orange-200 bg-orange-50 dark:border-orange-700 dark:bg-orange-950/20'
        : 'border-gray-200 bg-white dark:border-dark-border dark:bg-dark-card'
    "
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <div class="flex flex-wrap items-baseline gap-2">
        <span
          class="rounded-md px-2 py-0.5 text-xs font-semibold"
          :class="
            isViewAdmin
              ? 'bg-orange-200 text-orange-900 dark:bg-orange-800 dark:text-orange-100'
              : 'bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-100'
          "
        >
          {{ actionLabel }}
        </span>
        <span class="text-sm font-medium text-gray-900 dark:text-surface-dark-text">
          {{ entityLabel }}
        </span>
        <span class="text-xs text-gray-500 dark:text-gray-400">par {{ actorLabel }}</span>
      </div>
      <span class="text-xs text-gray-500 dark:text-gray-400">{{ relativeTime }}</span>
    </div>

    <div v-if="diffSummary" class="text-sm text-gray-700 dark:text-gray-300">
      {{ diffSummary }}
    </div>

    <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
      <span class="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800">{{ sourceLabel }}</span>
      <span class="font-mono opacity-70">
        {{ new Date(event.timestamp).toLocaleString('fr-FR') }}
      </span>
    </div>
  </li>
</template>
