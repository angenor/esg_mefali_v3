<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AttestationStatusBadge from '~/components/attestations/AttestationStatusBadge.vue'
import RevokeAttestationModal from '~/components/attestations/RevokeAttestationModal.vue'
import { useAuthStore } from '~/stores/auth'
import type { AttestationStatus, AttestationSummary } from '~/types/attestation'

definePageMeta({ layout: 'admin' })

const authStore = useAuthStore()
const config = useRuntimeConfig()
const router = useRouter()

const attestations = ref<AttestationSummary[]>([])
const loading = ref(false)
const error = ref('')
const filterStatus = ref<'' | AttestationStatus>('')
const filterAccount = ref('')
const showRevokeModal = ref(false)
const revokingId = ref<string | null>(null)
const toastMessage = ref('')
const toastType = ref<'success' | 'error'>('success')

function getHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(authStore.accessToken
      ? { Authorization: `Bearer ${authStore.accessToken}` }
      : {}),
  }
}

const apiBase = config.public.apiBase as string

async function loadAttestations() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    if (filterStatus.value) params.set('status', filterStatus.value)
    if (filterAccount.value) params.set('account_id', filterAccount.value)
    const url = `${apiBase}/admin/attestations${
      params.toString() ? '?' + params.toString() : ''
    }`
    const response = await fetch(url, { headers: getHeaders() })
    if (response.status === 403) {
      // Pas admin → redirection dashboard.
      await router.push('/dashboard')
      return
    }
    if (!response.ok) {
      throw new Error('Erreur lors du chargement')
    }
    attestations.value = await response.json()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function statusOf(a: AttestationSummary): AttestationStatus {
  if (a.revoked_at) return 'revoked'
  if (new Date(a.valid_until).getTime() < Date.now()) return 'expired'
  return 'authentic'
}

function fmtDate(s: string | null): string {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('fr-FR')
}

function shortUuid(uuid: string | undefined): string {
  if (!uuid) return ''
  return uuid.slice(0, 8) + '…'
}

function openRevoke(id: string) {
  revokingId.value = id
  showRevokeModal.value = true
}

async function handleRevokeConfirm(reason: string) {
  if (!revokingId.value) return
  try {
    const response = await fetch(
      `${apiBase}/admin/attestations/${revokingId.value}/revoke`,
      {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ reason }),
      },
    )
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || 'Échec de la révocation')
    }
    toastMessage.value = 'Attestation révoquée'
    toastType.value = 'success'
    setTimeout(() => (toastMessage.value = ''), 3500)
    await loadAttestations()
  } catch (e) {
    toastMessage.value = e instanceof Error ? e.message : 'Erreur'
    toastType.value = 'error'
    setTimeout(() => (toastMessage.value = ''), 3500)
  } finally {
    showRevokeModal.value = false
    revokingId.value = null
  }
}

const sortedAttestations = computed(() =>
  [...attestations.value].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  ),
)

const revokingDisplayId = computed(() => {
  if (!revokingId.value) return undefined
  return attestations.value.find((x) => x.id === revokingId.value)?.display_id
})

onMounted(loadAttestations)
</script>

<template>
  <div class="flex flex-col h-full">
    <header
      class="border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card px-6 py-4"
    >
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 class="text-xl font-bold text-gray-900 dark:text-white">
            Administration des attestations
          </h1>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            Toutes les attestations émises (cross-tenant). Révocation admin disponible.
          </p>
        </div>
      </div>
      <div class="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">
            Statut
          </label>
          <select
            v-model="filterStatus"
            class="px-3 py-1.5 text-sm bg-white dark:bg-dark-input text-gray-900 dark:text-white border border-gray-300 dark:border-dark-border rounded-md"
            @change="loadAttestations"
          >
            <option value="">Tous</option>
            <option value="authentic">Authentique</option>
            <option value="revoked">Révoquée</option>
            <option value="expired">Expirée</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">
            Tenant (account_id)
          </label>
          <input
            v-model="filterAccount"
            type="text"
            placeholder="UUID partiel ou complet"
            class="px-3 py-1.5 text-sm bg-white dark:bg-dark-input text-gray-900 dark:text-white border border-gray-300 dark:border-dark-border rounded-md w-64"
            @blur="loadAttestations"
            @keyup.enter="loadAttestations"
          >
        </div>
        <button
          type="button"
          class="px-3 py-1.5 text-sm font-medium bg-gray-100 dark:bg-dark-input text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-dark-border rounded hover:bg-gray-200 dark:hover:bg-dark-hover"
          @click="loadAttestations"
        >
          Actualiser
        </button>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-6">
      <div v-if="loading" class="text-center text-gray-500">Chargement…</div>
      <div v-else-if="error" class="text-rose-600">{{ error }}</div>
      <div v-else-if="!sortedAttestations.length" class="text-center text-gray-500">
        Aucune attestation trouvée.
      </div>
      <div v-else class="overflow-x-auto">
        <table class="min-w-full bg-white dark:bg-dark-card text-sm">
          <thead
            class="border-b border-gray-200 dark:border-dark-border text-left text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400"
          >
            <tr>
              <th class="px-3 py-2">Display ID</th>
              <th class="px-3 py-2">Tenant</th>
              <th class="px-3 py-2">User</th>
              <th class="px-3 py-2">Type</th>
              <th class="px-3 py-2">Statut</th>
              <th class="px-3 py-2">Délivrée</th>
              <th class="px-3 py-2">Valide jusqu'au</th>
              <th class="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="a in sortedAttestations"
              :key="a.id"
              class="border-b border-gray-100 dark:border-dark-border/50 hover:bg-gray-50 dark:hover:bg-dark-hover"
            >
              <td class="px-3 py-2 font-mono text-xs">{{ a.display_id }}</td>
              <td class="px-3 py-2 font-mono text-xs">{{ shortUuid(a.account_id) }}</td>
              <td class="px-3 py-2 font-mono text-xs">{{ shortUuid(a.user_id) }}</td>
              <td class="px-3 py-2">{{ a.attestation_type }}</td>
              <td class="px-3 py-2">
                <AttestationStatusBadge :status="statusOf(a)" size="sm" />
              </td>
              <td class="px-3 py-2 text-xs">{{ fmtDate(a.valid_from) }}</td>
              <td class="px-3 py-2 text-xs">{{ fmtDate(a.valid_until) }}</td>
              <td class="px-3 py-2">
                <button
                  v-if="!a.revoked_at"
                  type="button"
                  class="px-2 py-1 text-xs font-medium bg-rose-50 dark:bg-rose-900/30 text-rose-700 dark:text-rose-200 border border-rose-200 dark:border-rose-700 rounded hover:bg-rose-100 dark:hover:bg-rose-900/50"
                  @click="openRevoke(a.id)"
                >
                  Révoquer
                </button>
                <span v-else class="text-xs text-gray-400">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>

    <RevokeAttestationModal
      v-model="showRevokeModal"
      :attestation-display-id="revokingDisplayId"
      @confirm="handleRevokeConfirm"
    />

    <div
      v-if="toastMessage"
      :class="[
        'fixed bottom-4 right-4 z-50 px-4 py-2 rounded-md shadow-lg text-sm font-medium',
        toastType === 'success'
          ? 'bg-emerald-600 text-white'
          : 'bg-rose-600 text-white',
      ]"
      role="status"
      aria-live="polite"
    >
      {{ toastMessage }}
    </div>
  </div>
</template>
