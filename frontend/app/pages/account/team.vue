<script setup lang="ts">
// F02 — Gestion d'equipe PME (US3 invitations).
//
// Permet a un utilisateur PME d'inviter un collaborateur, de visualiser
// les invitations en cours, de retirer un membre et de revoquer une
// invitation pending. Le lien d'invitation est livre par le backend via
// LoggingEmailDelivery (logs structures cote serveur).
import { onMounted, ref } from 'vue'
import { useAccountTeam } from '~/composables/useAccountTeam'
import { useAuthStore } from '~/stores/auth'

// Le middleware d'authentification est applique globalement via
// `app/middleware/auth.global.ts` ; il ne doit pas etre reference par nom
// dans `definePageMeta` (sinon Nuxt leve "Unknown route middleware: 'auth'"
// car les middlewares globaux ne sont pas exposes au registre nomme).

const auth = useAuthStore()
const {
  members,
  pendingInvitations,
  loading,
  error,
  listTeam,
  inviteMember,
  removeMember,
  revokeInvitation,
} = useAccountTeam()

const inviteEmail = ref('')
const inviteFeedback = ref<string | null>(null)
const memberToRemove = ref<{ id: string; full_name: string } | null>(null)

onMounted(listTeam)

async function onInvite() {
  inviteFeedback.value = null
  const email = inviteEmail.value.trim()
  if (email.length === 0) return
  const invitation = await inviteMember(email)
  if (invitation) {
    inviteFeedback.value = `Invitation envoyée à ${email}`
    inviteEmail.value = ''
  }
}

async function onConfirmRemove() {
  if (!memberToRemove.value) return
  const ok = await removeMember(memberToRemove.value.id)
  if (ok) {
    memberToRemove.value = null
  }
}

function askRemove(member: { id: string; full_name: string }) {
  memberToRemove.value = member
}

function cancelRemove() {
  memberToRemove.value = null
}

async function onRevokeInvitation(invitationId: string) {
  await revokeInvitation(invitationId)
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <header class="mb-6">
      <h1
        class="text-2xl font-bold text-surface-text dark:text-surface-dark-text"
      >
        Equipe de l'entreprise
      </h1>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Gerez les collaborateurs ayant acces aux donnees de
        <span class="font-medium">{{ auth.account?.name ?? 'votre compte' }}</span
        >.
      </p>
    </header>

    <!-- Bloc invitation -->
    <section
      class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 mb-6 shadow-sm"
    >
      <h2
        class="text-base font-semibold text-surface-text dark:text-surface-dark-text mb-3"
      >
        Inviter un collaborateur
      </h2>
      <form class="flex flex-col sm:flex-row gap-3" @submit.prevent="onInvite">
        <input
          v-model="inviteEmail"
          type="email"
          required
          placeholder="collaborateur@exemple.com"
          class="flex-1 rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-sm text-surface-text dark:text-surface-dark-text placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <button
          type="submit"
          :disabled="loading"
          class="inline-flex items-center justify-center gap-1 rounded-md bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-700 dark:hover:bg-emerald-800 px-4 py-2 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ loading ? 'Envoi...' : 'Inviter' }}
        </button>
      </form>
      <p
        v-if="inviteFeedback"
        class="mt-3 text-sm text-emerald-700 dark:text-emerald-300"
      >
        {{ inviteFeedback }}
      </p>
      <p
        v-if="error"
        class="mt-3 text-sm text-red-700 dark:text-red-300"
        role="alert"
      >
        {{ error }}
      </p>
    </section>

    <!-- Liste des membres -->
    <section
      class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 mb-6 shadow-sm"
    >
      <h2
        class="text-base font-semibold text-surface-text dark:text-surface-dark-text mb-3"
      >
        Membres ({{ members.length }})
      </h2>
      <div v-if="members.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
        Aucun membre pour l'instant.
      </div>
      <ul v-else class="divide-y divide-gray-200 dark:divide-dark-border">
        <li
          v-for="member in members"
          :key="member.id"
          class="py-3 flex items-center justify-between gap-3"
        >
          <div class="flex flex-col">
            <span
              class="text-sm font-medium text-surface-text dark:text-surface-dark-text"
            >
              {{ member.full_name }}
            </span>
            <span class="text-xs text-gray-500 dark:text-gray-400">
              {{ member.email }}
            </span>
          </div>
          <div class="flex items-center gap-3">
            <RoleBadge :role="member.role" />
            <button
              v-if="member.id !== auth.user?.id"
              type="button"
              class="text-xs font-medium text-red-700 dark:text-red-300 hover:text-red-900 dark:hover:text-red-100 hover:underline"
              @click="askRemove(member)"
            >
              Retirer
            </button>
          </div>
        </li>
      </ul>
    </section>

    <!-- Invitations pending -->
    <section
      v-if="pendingInvitations.length > 0"
      class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 shadow-sm"
    >
      <h2
        class="text-base font-semibold text-surface-text dark:text-surface-dark-text mb-3"
      >
        Invitations en cours ({{ pendingInvitations.length }})
      </h2>
      <ul class="divide-y divide-gray-200 dark:divide-dark-border">
        <li
          v-for="invitation in pendingInvitations"
          :key="invitation.id"
          class="py-3 flex items-center justify-between gap-3"
        >
          <div class="flex flex-col">
            <span
              class="text-sm font-medium text-surface-text dark:text-surface-dark-text"
            >
              {{ invitation.email }}
            </span>
            <span class="text-xs text-gray-500 dark:text-gray-400">
              Envoyee par {{ invitation.invited_by.full_name }} —
              expire le
              {{ new Date(invitation.expires_at).toLocaleDateString('fr-FR') }}
            </span>
          </div>
          <button
            type="button"
            class="text-xs font-medium text-red-700 dark:text-red-300 hover:text-red-900 dark:hover:text-red-100 hover:underline"
            @click="onRevokeInvitation(invitation.id)"
          >
            Revoquer
          </button>
        </li>
      </ul>
    </section>

    <!-- Modale de confirmation suppression -->
    <div
      v-if="memberToRemove"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      @click.self="cancelRemove"
    >
      <div
        class="max-w-md w-full mx-4 rounded-lg bg-white dark:bg-dark-card p-6 shadow-xl border border-gray-200 dark:border-dark-border"
      >
        <h3
          class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-2"
        >
          Retirer ce collaborateur ?
        </h3>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-5">
          {{ memberToRemove.full_name }} perdra l'acces aux donnees de
          {{ auth.account?.name ?? 'votre compte' }}. Cette action est
          reversible : il faudra le ré-inviter pour lui rendre l'acces.
        </p>
        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 text-sm rounded-md border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-hover"
            @click="cancelRemove"
          >
            Annuler
          </button>
          <button
            type="button"
            :disabled="loading"
            class="px-4 py-2 text-sm rounded-md bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-800 text-white font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            @click="onConfirmRemove"
          >
            {{ loading ? 'Retrait...' : 'Confirmer le retrait' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
