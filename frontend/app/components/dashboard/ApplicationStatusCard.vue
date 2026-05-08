<script setup lang="ts">
// F21 (US1) — Card d'une candidature affichée sur le dashboard.
// Granularité par Offre = couple (Fonds × Intermédiaire) — F07.

import type { ApplicationCard } from '~/types/dashboard'

interface Props {
  card: ApplicationCard
}

const props = defineProps<Props>()

function formatDateFr(value: string | null): string {
  if (!value) return 'Aucune échéance'
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    const dd = String(d.getUTCDate()).padStart(2, '0')
    const mm = String(d.getUTCMonth() + 1).padStart(2, '0')
    const yyyy = d.getUTCFullYear()
    return `${dd}/${mm}/${yyyy}`
  } catch {
    return value
  }
}

function statusColor(status: string): string {
  if (status === 'rejected') return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
  if (status === 'accepted') return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
  if (status.startsWith('submitted') || status === 'under_review')
    return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
  return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
}
</script>

<template>
  <article
    class="bg-white dark:bg-dark-card rounded-xl shadow-sm border border-gray-200 dark:border-dark-border p-4 flex flex-col gap-3"
    :data-testid="`application-card-${card.application_id}`"
    role="article"
    :aria-label="`Candidature ${card.fund_name} via ${card.intermediary_name}`"
  >
    <!-- En-tête : fund + intermédiaire -->
    <header class="flex items-start gap-3">
      <div class="flex flex-col flex-1 min-w-0">
        <h3 class="text-sm font-semibold text-surface-text dark:text-surface-dark-text truncate">
          {{ card.fund_name }}
        </h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
          via {{ card.intermediary_name }}
        </p>
      </div>
      <span
        :class="['text-[10px] font-medium px-2 py-1 rounded-full whitespace-nowrap', statusColor(card.status)]"
        data-testid="application-status-badge"
      >
        {{ card.current_step }}
      </span>
    </header>

    <!-- Échéance -->
    <div class="text-xs text-gray-600 dark:text-gray-400">
      <span class="font-medium">Prochaine échéance :</span>
      <span class="ml-1" data-testid="application-deadline">{{ formatDateFr(card.next_deadline) }}</span>
    </div>

    <!-- Bouton détail -->
    <NuxtLink
      :to="`/applications/${card.application_id}`"
      class="self-start text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 hover:underline"
      data-testid="application-detail-link"
    >
      Voir le détail →
    </NuxtLink>
  </article>
</template>
