<script setup lang="ts">
// F09 — Détail d'une source avec workflow 4-yeux.
import { computed, onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import { useAuthStore } from '~/stores/auth'
import {
  useAdminSources,
  type AdminSource,
  type DependentsReport,
} from '~/composables/useAdminSources'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const route = useRoute()
const auth = useAuthStore()
const sourceId = String(route.params.id)

const { getSource, verifySource, markOutdated, getDependents, deleteSource } =
  useAdminSources()

const source = ref<AdminSource | null>(null)
const dependents = ref<DependentsReport | null>(null)
const error = ref('')
const loading = ref(false)
const verifyLoading = ref(false)
const outdatedReason = ref('')
const showOutdatedForm = ref(false)
const showImpactModal = ref(false)

const isCreator = computed(
  () =>
    !!auth.user &&
    !!source.value &&
    String(source.value.captured_by) === String(auth.user.id),
)

const canVerify = computed(
  () =>
    !!source.value &&
    source.value.verification_status === 'pending' &&
    !isCreator.value,
)

async function fetchAll() {
  loading.value = true
  error.value = ''
  try {
    source.value = await getSource(sourceId)
    dependents.value = await getDependents(sourceId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  } finally {
    loading.value = false
  }
}

async function onVerify() {
  if (!canVerify.value) return
  verifyLoading.value = true
  error.value = ''
  try {
    source.value = await verifySource(sourceId)
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: unknown } }).data?.detail
    if (
      detail &&
      typeof detail === 'object' &&
      (detail as { error?: string }).error === 'four_eyes_violation'
    ) {
      error.value =
        'Règle des 4-yeux : un autre admin doit valider cette source.'
    } else {
      error.value = e instanceof Error ? e.message : 'Erreur'
    }
  } finally {
    verifyLoading.value = false
  }
}

async function onMarkOutdated() {
  if (!outdatedReason.value || outdatedReason.value.length < 5) {
    error.value = 'Motif requis (≥ 5 caractères).'
    return
  }
  try {
    source.value = await markOutdated(sourceId, outdatedReason.value)
    showOutdatedForm.value = false
    outdatedReason.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  }
}

async function onDelete(force = false) {
  try {
    await deleteSource(sourceId, force)
    await navigateTo('/admin/sources')
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: unknown } }).data?.detail
    if (
      detail &&
      typeof detail === 'object' &&
      (detail as { error?: string }).error === 'has_dependents'
    ) {
      showImpactModal.value = true
    } else {
      error.value = e instanceof Error ? e.message : 'Erreur'
    }
  }
}

onMounted(fetchAll)
</script>

<template>
  <div class="px-6 py-8 max-w-4xl mx-auto">
    <div v-if="loading">Chargement…</div>
    <div v-else-if="!source" class="text-red-600">Source introuvable.</div>
    <div v-else>
      <div class="mb-6 flex items-center justify-between">
        <h1
          class="text-2xl font-bold text-surface-text dark:text-surface-dark-text"
        >
          {{ source.title }}
        </h1>
        <StatusBadge :variant="source.verification_status" />
      </div>

      <div
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 space-y-3"
      >
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Publisher : <span class="font-medium">{{ source.publisher }}</span>
        </p>
        <p class="text-sm">
          <a
            :href="source.url"
            target="_blank"
            rel="noopener"
            class="text-blue-600 hover:underline break-all"
            >Ouvrir le document officiel ↗</a
          >
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Version : {{ source.version }} · Date : {{ source.date_publi }}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Capturée par : {{ source.captured_by }}
          <span v-if="source.verified_by">
            · Validée par : {{ source.verified_by }}
          </span>
        </p>
      </div>

      <div
        v-if="error"
        class="my-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
        role="alert"
      >
        {{ error }}
      </div>

      <div class="mt-6 flex flex-wrap gap-3">
        <button
          v-if="canVerify"
          type="button"
          :disabled="verifyLoading"
          class="rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 text-sm disabled:opacity-50"
          @click="onVerify"
        >
          {{ verifyLoading ? 'Validation…' : 'Marquer comme vérifiée' }}
        </button>
        <p
          v-else-if="
            source.verification_status === 'pending' && isCreator
          "
          class="text-xs text-gray-500 dark:text-gray-400"
        >
          Vous avez créé cette source ; un autre admin doit la valider
          (règle des 4-yeux).
        </p>

        <button
          v-if="source.verification_status === 'verified'"
          type="button"
          class="rounded-lg bg-yellow-600 hover:bg-yellow-700 text-white font-medium px-4 py-2 text-sm"
          @click="showOutdatedForm = !showOutdatedForm"
        >
          Marquer obsolète
        </button>
        <button
          type="button"
          class="rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2 text-sm"
          @click="onDelete(false)"
        >
          Supprimer
        </button>
      </div>

      <div
        v-if="showOutdatedForm"
        class="mt-4 bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-300 dark:border-yellow-800 rounded-lg p-4"
      >
        <label class="block text-sm font-medium mb-1">
          Motif d'obsolescence
        </label>
        <textarea
          v-model="outdatedReason"
          rows="2"
          class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm"
        ></textarea>
        <button
          type="button"
          class="mt-2 rounded-lg bg-yellow-600 hover:bg-yellow-700 text-white font-medium px-3 py-1.5 text-sm"
          @click="onMarkOutdated"
        >
          Confirmer
        </button>
      </div>

      <div
        v-if="dependents && dependents.total > 0"
        class="mt-6 bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-4"
      >
        <h2 class="font-semibold mb-2">Entités dépendantes ({{ dependents.total }})</h2>
        <ul class="text-sm space-y-1">
          <li v-if="dependents.indicators.length">
            {{ dependents.indicators.length }} indicators
          </li>
          <li v-if="dependents.criteria.length">
            {{ dependents.criteria.length }} criteria
          </li>
          <li v-if="dependents.skills.length">
            {{ dependents.skills.length }} skills
          </li>
          <li v-if="dependents.emission_factors.length">
            {{ dependents.emission_factors.length }} emission_factors
          </li>
          <li v-if="dependents.simulation_factors.length">
            {{ dependents.simulation_factors.length }} simulation_factors
          </li>
        </ul>
      </div>

      <!-- Modal d'impact pour delete force -->
      <div
        v-if="showImpactModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      >
        <div
          class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 max-w-md mx-4"
        >
          <h3 class="font-bold mb-2">Suppression bloquée</h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Cette source possède des entités dépendantes. Pour forcer la
            suppression cascade, confirmez ci-dessous.
          </p>
          <div class="flex gap-2 justify-end">
            <button
              type="button"
              class="rounded-lg border border-gray-300 dark:border-dark-border px-4 py-2 text-sm"
              @click="showImpactModal = false"
            >
              Annuler
            </button>
            <button
              type="button"
              class="rounded-lg bg-red-700 hover:bg-red-800 text-white px-4 py-2 text-sm"
              @click="onDelete(true)"
            >
              Forcer la suppression
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
