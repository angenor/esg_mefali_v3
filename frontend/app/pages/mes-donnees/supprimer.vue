<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuth } from '~/composables/useAuth'
import { useDataPrivacy } from '~/composables/useDataPrivacy'

definePageMeta({ middleware: 'auth' })

const { useDeletion } = useDataPrivacy()
const { scheduleDeletion, cancelDeletion } = useDeletion()

const account = ref<{ deletion_scheduled_at: string | null } | null>(null)
const modalOpen = ref(false)
const submitting = ref(false)
const confirmation = ref<string | null>(null)
const errorMessage = ref<string | null>(null)

async function fetchAccount() {
  const { apiFetch } = useAuth()
  try {
    const me = await apiFetch<{
      account: { deletion_scheduled_at?: string } | null
    }>('/api/auth/me')
    account.value = {
      deletion_scheduled_at: me.account?.deletion_scheduled_at ?? null,
    }
  } catch {
    account.value = { deletion_scheduled_at: null }
  }
}

async function onConfirm(password: string, confirmationText: string) {
  submitting.value = true
  errorMessage.value = null
  const result = await scheduleDeletion(password, confirmationText)
  submitting.value = false
  if (result) {
    confirmation.value = result.message
    modalOpen.value = false
    await fetchAccount()
  } else {
    errorMessage.value =
      'La suppression n\'a pas pu être programmée. Vérifiez votre mot de passe et réessayez.'
  }
}

async function onCancelDeletion() {
  submitting.value = true
  await cancelDeletion()
  submitting.value = false
  confirmation.value = 'Suppression annulée. Votre compte reste actif.'
  await fetchAccount()
}

onMounted(fetchAccount)
</script>

<template>
  <section
    class="max-w-3xl mx-auto bg-surface-bg dark:bg-surface-dark-bg text-surface-text dark:text-surface-dark-text"
  >
    <header class="mb-6">
      <NuxtLink
        to="/mes-donnees"
        class="text-sm text-gray-600 dark:text-gray-400 hover:underline"
      >
        ← Retour à Mes données
      </NuxtLink>
      <h1 class="mt-2 text-2xl font-semibold">Supprimer mon compte</h1>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        Conformément à votre droit à l'effacement (RGPD Art. 17), vous pouvez
        demander la suppression définitive de votre compte. Un délai de grâce
        de 30 jours s'applique pour vous protéger d'une suppression
        accidentelle.
      </p>
    </header>

    <div
      v-if="confirmation"
      class="mb-4 rounded-lg border border-emerald-300 bg-emerald-50 dark:bg-emerald-900/30 dark:border-emerald-700 p-4 text-sm text-emerald-800 dark:text-emerald-200"
      aria-live="polite"
    >
      {{ confirmation }}
    </div>

    <div
      v-if="account?.deletion_scheduled_at"
      class="space-y-4"
    >
      <DeletionScheduledBanner
        :scheduled-at="account.deletion_scheduled_at"
        :loading="submitting"
        @cancel="onCancelDeletion"
      />
    </div>
    <div v-else class="space-y-4">
      <div
        class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4 text-sm text-gray-700 dark:text-gray-300"
      >
        <p class="font-medium">Conséquences de la suppression :</p>
        <ul class="mt-2 list-disc list-inside space-y-1">
          <li>Vos candidatures en cours seront annulées.</li>
          <li>
            Vos attestations crédit en cours de validité seront révoquées.
          </li>
          <li>
            Toutes vos données (profil, projets, conversations, documents)
            seront effacées définitivement à J+30.
          </li>
          <li>
            L'historique d'audit RGPD sera anonymisé (conservé 6 ans pour
            conformité légale).
          </li>
        </ul>
      </div>

      <button
        type="button"
        class="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
        @click="modalOpen = true"
      >
        Supprimer mon compte définitivement
      </button>

      <p
        v-if="errorMessage"
        class="text-sm text-red-700 dark:text-red-400"
        aria-live="assertive"
      >
        {{ errorMessage }}
      </p>
    </div>

    <DeletionConfirmModal
      :open="modalOpen"
      @confirm="onConfirm"
      @cancel="modalOpen = false"
    />
  </section>
</template>
