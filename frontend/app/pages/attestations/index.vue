<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AttestationCard from '~/components/attestations/AttestationCard.vue'
import RevokeAttestationModal from '~/components/attestations/RevokeAttestationModal.vue'
import { useAttestations } from '~/composables/useAttestations'
import type { AttestationSummary, AttestationType } from '~/types/attestation'

definePageMeta({ layout: 'default' })

const {
  loading,
  error,
  generateAttestation,
  listAttestations,
  revokeAttestation,
  downloadPdf,
  copyToClipboard,
} = useAttestations()

const attestations = ref<AttestationSummary[]>([])
const showGenerateModal = ref(false)
const showRevokeModal = ref(false)
const revokingId = ref<string | null>(null)
const generatingType = ref<AttestationType>('combined')
const generating = ref(false)
const toastMessage = ref('')
const toastType = ref<'success' | 'error'>('success')

const sortedAttestations = computed(() =>
  [...attestations.value].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  ),
)

const revokingDisplayId = computed(() => {
  if (!revokingId.value) return undefined
  const a = attestations.value.find((x) => x.id === revokingId.value)
  return a?.display_id
})

async function refresh() {
  attestations.value = await listAttestations()
}

function showToast(msg: string, type: 'success' | 'error' = 'success') {
  toastMessage.value = msg
  toastType.value = type
  setTimeout(() => {
    toastMessage.value = ''
  }, 4000)
}

async function handleGenerate() {
  generating.value = true
  try {
    const a = await generateAttestation(generatingType.value)
    showGenerateModal.value = false
    if (a) {
      showToast(`Attestation générée : ${a.display_id}`, 'success')
      // Copier l'URL de vérification automatiquement
      await copyToClipboard(a.verification_url)
      await refresh()
    } else {
      showToast(error.value || 'Échec de la génération', 'error')
    }
  } finally {
    generating.value = false
  }
}

function openRevokeModal(id: string) {
  revokingId.value = id
  showRevokeModal.value = true
}

async function handleRevokeConfirm(reason: string) {
  if (!revokingId.value) return
  const result = await revokeAttestation(revokingId.value, reason)
  if (result) {
    showToast('Attestation révoquée avec succès', 'success')
    await refresh()
  } else {
    showToast(error.value || 'Échec de la révocation', 'error')
  }
  showRevokeModal.value = false
  revokingId.value = null
}

async function handleDownload(id: string) {
  const a = attestations.value.find((x) => x.id === id)
  const filename = a ? `${a.display_id}.pdf` : 'attestation.pdf'
  const ok = await downloadPdf(id, filename)
  if (!ok) showToast(error.value || 'Téléchargement échoué', 'error')
}

async function handleCopyUrl(url: string) {
  const ok = await copyToClipboard(url)
  showToast(ok ? 'URL copiée' : 'Copie échouée', ok ? 'success' : 'error')
}

function handleRenew(type: string) {
  generatingType.value = type as AttestationType
  showGenerateModal.value = true
}

onMounted(refresh)
</script>

<template>
  <div class="flex flex-col h-full">
    <header
      class="border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card px-6 py-4"
    >
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-900 dark:text-white">
            Mes attestations
          </h1>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            Attestations signées Ed25519 vérifiables hors-plateforme via QR code
          </p>
        </div>
        <button
          type="button"
          class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium"
          @click="showGenerateModal = true"
        >
          Générer une attestation vérifiable
        </button>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-6">
      <div v-if="loading" class="text-center py-10 text-gray-500 dark:text-gray-400">
        Chargement…
      </div>
      <div
        v-else-if="!sortedAttestations.length"
        class="text-center py-12 max-w-md mx-auto"
      >
        <p class="text-gray-700 dark:text-gray-300 mb-3">
          Vous n'avez pas encore généré d'attestation.
        </p>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Générez une attestation vérifiable pour partager votre score crédit ou ESG
          avec un partenaire fonds. Le QR code embarqué permettra à votre banquier de
          vérifier l'authenticité hors-plateforme.
        </p>
        <button
          type="button"
          class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium"
          @click="showGenerateModal = true"
        >
          Créer ma première attestation
        </button>
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <AttestationCard
          v-for="att in sortedAttestations"
          :key="att.id"
          :attestation="att"
          @revoke="openRevokeModal"
          @download="handleDownload"
          @copy-url="handleCopyUrl"
          @renew="handleRenew"
        />
      </div>
    </main>

    <!-- Modal génération -->
    <Teleport v-if="showGenerateModal" to="body">
      <div
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
        @click.self="showGenerateModal = false"
      >
        <div
          class="w-full max-w-md bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg shadow-xl p-6"
          role="dialog"
          aria-modal="true"
        >
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-3">
            Générer une attestation vérifiable
          </h2>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Choisissez le type d'attestation à générer. Le PDF sera signé Ed25519
            et un QR code pointant vers la page publique de vérification y sera
            embarqué.
          </p>
          <div class="space-y-2 mb-4">
            <label
              v-for="opt in [
                { value: 'combined', label: 'Combinée (crédit + ESG)' },
                { value: 'credit_score', label: 'Score de crédit uniquement' },
                { value: 'esg_assessment', label: 'Évaluation ESG uniquement' },
              ]"
              :key="opt.value"
              class="flex items-center gap-3 p-3 rounded-md border border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover cursor-pointer"
            >
              <input
                v-model="generatingType"
                type="radio"
                :value="opt.value"
                class="text-emerald-600 focus:ring-emerald-500"
              >
              <span class="text-sm text-gray-700 dark:text-gray-200">{{
                opt.label
              }}</span>
            </label>
          </div>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="px-4 py-2 text-sm font-medium bg-gray-100 dark:bg-dark-input text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-dark-border rounded hover:bg-gray-200 dark:hover:bg-dark-hover"
              @click="showGenerateModal = false"
            >
              Annuler
            </button>
            <button
              type="button"
              class="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
              :disabled="generating"
              @click="handleGenerate"
            >
              {{ generating ? 'Génération…' : 'Générer' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Modal révocation -->
    <RevokeAttestationModal
      v-model="showRevokeModal"
      :attestation-display-id="revokingDisplayId"
      @confirm="handleRevokeConfirm"
    />

    <!-- Toast simple -->
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
