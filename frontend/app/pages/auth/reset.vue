<script setup lang="ts">
// F09 — Page publique de reset password.
//
// Lit le token depuis la query (?token=xxx), demande un nouveau mot de
// passe et appelle POST /api/auth/reset-password.
import { computed, ref } from 'vue'

definePageMeta({
  layout: false,
})

const route = useRoute()

const token = computed<string>(() => {
  const v = route.query.token
  return typeof v === 'string' ? v : ''
})

const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)

const config = useRuntimeConfig()
const apiBase = (config.public.apiBase as string) || '/api'

async function submit() {
  error.value = ''
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Les deux mots de passe ne correspondent pas.'
    return
  }
  if (newPassword.value.length < 8) {
    error.value = 'Le mot de passe doit faire au moins 8 caractères.'
    return
  }
  if (!token.value) {
    error.value = 'Token manquant ou invalide.'
    return
  }
  loading.value = true
  try {
    const response = await $fetch(`${apiBase}/auth/reset-password`, {
      method: 'POST',
      body: {
        token: token.value,
        new_password: newPassword.value,
      },
    })
    if ((response as { success?: boolean }).success) {
      success.value = true
      setTimeout(() => navigateTo('/login'), 2500)
    } else {
      error.value = 'Réinitialisation impossible.'
    }
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: string } })?.data?.detail
    if (detail === 'token_expired') {
      error.value = 'Ce lien de réinitialisation a expiré.'
    } else if (detail === 'token_already_used') {
      error.value = 'Ce lien a déjà été utilisé.'
    } else if (detail === 'token_invalid') {
      error.value = 'Lien invalide. Demandez un nouveau lien.'
    } else {
      error.value = e instanceof Error ? e.message : 'Erreur inattendue.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    class="min-h-screen flex items-center justify-center bg-surface-bg dark:bg-surface-dark-bg px-4"
  >
    <div class="w-full max-w-md">
      <div class="bg-white dark:bg-dark-card rounded-2xl shadow-lg p-8">
        <div class="text-center mb-8">
          <h1
            class="text-2xl font-bold text-surface-text dark:text-surface-dark-text"
          >
            Réinitialiser le mot de passe
          </h1>
          <p class="text-gray-500 dark:text-gray-400 mt-2">
            Choisissez un nouveau mot de passe sécurisé.
          </p>
        </div>

        <div
          v-if="success"
          class="rounded-lg bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-800 p-4 text-green-800 dark:text-green-200"
        >
          Mot de passe réinitialisé avec succès. Redirection vers la page de
          connexion…
        </div>

        <form v-else class="space-y-4" @submit.prevent="submit">
          <div>
            <label
              for="new-password"
              class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
            >
              Nouveau mot de passe
            </label>
            <input
              id="new-password"
              v-model="newPassword"
              type="password"
              minlength="8"
              required
              autocomplete="new-password"
              class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label
              for="confirm-password"
              class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
            >
              Confirmation
            </label>
            <input
              id="confirm-password"
              v-model="confirmPassword"
              type="password"
              minlength="8"
              required
              autocomplete="new-password"
              class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2 text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <p
            v-if="error"
            class="text-sm text-red-600 dark:text-red-400"
            role="alert"
          >
            {{ error }}
          </p>

          <button
            type="submit"
            :disabled="loading || !token"
            class="w-full rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="loading">Validation…</span>
            <span v-else>Réinitialiser</span>
          </button>

          <p class="text-xs text-center text-gray-500 dark:text-gray-400">
            Vous vous souvenez de votre mot de passe ?
            <NuxtLink to="/login" class="text-blue-600 hover:underline">
              Connexion
            </NuxtLink>
          </p>
        </form>
      </div>
    </div>
  </div>
</template>
