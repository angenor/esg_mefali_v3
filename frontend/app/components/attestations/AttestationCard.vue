<script setup lang="ts">
import { computed } from 'vue'
import AttestationStatusBadge from './AttestationStatusBadge.vue'
import type { AttestationStatus, AttestationSummary } from '~/types/attestation'

interface Props {
  attestation: AttestationSummary
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'revoke', id: string): void
  (e: 'download', id: string): void
  (e: 'copy-url', url: string): void
  (e: 'renew', type: string): void
}>()

const typeLabels: Record<string, string> = {
  credit_score: 'Score de crédit',
  esg_assessment: 'Évaluation ESG',
  combined: 'Combinée (crédit + ESG)',
}

const status = computed<AttestationStatus>(() => {
  if (props.attestation.revoked_at) return 'revoked'
  const now = new Date().getTime()
  const validUntil = new Date(props.attestation.valid_until).getTime()
  if (validUntil < now) return 'expired'
  return 'authentic'
})

const isExpiringSoon = computed(() => {
  if (status.value !== 'authentic') return false
  const now = new Date().getTime()
  const validUntil = new Date(props.attestation.valid_until).getTime()
  const daysLeft = Math.floor((validUntil - now) / (1000 * 60 * 60 * 24))
  return daysLeft >= 0 && daysLeft <= 30
})

const daysLeft = computed(() => {
  const now = new Date().getTime()
  const validUntil = new Date(props.attestation.valid_until).getTime()
  return Math.max(0, Math.floor((validUntil - now) / (1000 * 60 * 60 * 24)))
})

function fmtDate(s: string | null): string {
  if (!s) return ''
  return new Date(s).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}
</script>

<template>
  <article
    role="article"
    :aria-label="`Attestation ${attestation.display_id}`"
    class="bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow"
  >
    <div class="flex items-start justify-between gap-3 mb-3">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span
            class="font-mono text-base font-bold text-gray-900 dark:text-white truncate"
          >
            {{ attestation.display_id }}
          </span>
          <AttestationStatusBadge :status="status" size="sm" />
        </div>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          {{ typeLabels[attestation.attestation_type] || attestation.attestation_type }}
        </p>
      </div>
    </div>

    <div class="space-y-1 text-sm mb-4">
      <div class="flex items-center justify-between">
        <span class="text-gray-500 dark:text-gray-400">Délivrée :</span>
        <span class="text-gray-900 dark:text-gray-200 font-medium">{{
          fmtDate(attestation.valid_from)
        }}</span>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-gray-500 dark:text-gray-400">Valide jusqu'au :</span>
        <span class="text-gray-900 dark:text-gray-200 font-medium">{{
          fmtDate(attestation.valid_until)
        }}</span>
      </div>
      <div v-if="status === 'revoked' && attestation.revoked_reason" class="pt-1">
        <p class="text-xs text-rose-700 dark:text-rose-300 italic">
          Révoquée le {{ fmtDate(attestation.revoked_at) }} —
          {{ attestation.revoked_reason }}
        </p>
      </div>
      <div
        v-if="isExpiringSoon"
        class="pt-1 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded"
      >
        <p class="text-xs text-amber-800 dark:text-amber-200">
          Expire bientôt — il vous reste {{ daysLeft }} jour{{ daysLeft > 1 ? 's' : '' }}.
          <button
            type="button"
            class="underline hover:no-underline ml-1"
            @click="emit('renew', attestation.attestation_type)"
          >
            Renouveler
          </button>
        </p>
      </div>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        type="button"
        class="px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded hover:bg-emerald-700 dark:bg-emerald-700 dark:hover:bg-emerald-800 transition-colors"
        @click="emit('download', attestation.id)"
      >
        Télécharger PDF
      </button>
      <button
        type="button"
        class="px-3 py-1.5 text-xs font-medium bg-gray-100 dark:bg-dark-input text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-dark-border rounded hover:bg-gray-200 dark:hover:bg-dark-hover transition-colors"
        @click="emit('copy-url', attestation.verification_url)"
      >
        Copier URL de vérification
      </button>
      <button
        v-if="status === 'authentic'"
        type="button"
        class="px-3 py-1.5 text-xs font-medium bg-rose-50 dark:bg-rose-900/30 text-rose-700 dark:text-rose-200 border border-rose-200 dark:border-rose-700 rounded hover:bg-rose-100 dark:hover:bg-rose-900/50 transition-colors"
        @click="emit('revoke', attestation.id)"
      >
        Révoquer
      </button>
    </div>
  </article>
</template>
