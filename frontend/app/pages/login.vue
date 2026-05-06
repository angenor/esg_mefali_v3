<script setup lang="ts">
definePageMeta({
  layout: false,
})

const { login } = useAuth()
const route = useRoute()

// F02 — si un token d'invitation est present dans l'URL et que
// l'utilisateur n'est pas encore connecte, on l'oriente vers /register
// pour finaliser l'inscription via le flux invitation.
const inviteToken = computed<string | null>(() => {
  const value = route.query.invite
  if (typeof value === 'string' && value.length > 0) return value
  return null
})

if (import.meta.client && inviteToken.value) {
  // Redirection client-side pour preserver le token dans la query string.
  await navigateTo({ path: '/register', query: { invite: inviteToken.value } })
}

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await login(email.value, password.value)
    await navigateTo('/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur de connexion'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-surface-bg dark:bg-surface-dark-bg px-4">
    <div class="w-full max-w-md">
      <div class="bg-white dark:bg-dark-card rounded-2xl shadow-lg p-8">
        <div class="text-center mb-8">
          <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">ESG Mefali</h1>
          <p class="text-gray-500 dark:text-gray-400 mt-2">Connectez-vous a votre compte</p>
        </div>

        <form class="space-y-5" @submit.prevent="handleLogin">
          <div v-if="error" class="bg-red-50 dark:bg-red-900/20 text-brand-red text-sm rounded-lg p-3">
            {{ error }}
          </div>

          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Adresse email
            </label>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              autocomplete="email"
              data-testid="login-email"
              class="w-full px-4 py-2.5 border border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text rounded-lg focus:ring-2 focus:ring-brand-green focus:border-transparent outline-none"
              placeholder="votre@email.com"
            />
          </div>

          <div>
            <label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Mot de passe
            </label>
            <input
              id="password"
              v-model="password"
              type="password"
              required
              autocomplete="current-password"
              data-testid="login-password"
              class="w-full px-4 py-2.5 border border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text rounded-lg focus:ring-2 focus:ring-brand-green focus:border-transparent outline-none"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            :disabled="loading"
            data-testid="login-submit"
            class="w-full py-2.5 bg-brand-green text-white font-medium rounded-lg hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ loading ? 'Connexion...' : 'Se connecter' }}
          </button>
        </form>

        <p class="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
          Pas encore de compte ?
          <NuxtLink to="/register" class="text-brand-green font-medium hover:underline">
            S'inscrire
          </NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>
