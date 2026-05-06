<script setup lang="ts">
definePageMeta({
  layout: false,
})

const { register, detectCountry, login } = useAuth()
const route = useRoute()

// F02 — invitation : si un token est passe en query, l'utilisateur rejoint
// l'Account de l'invitant au lieu de creer un nouvel Account.
const inviteToken = computed<string | null>(() => {
  const value = route.query.invite
  if (typeof value === 'string' && value.length > 0) return value
  return null
})

const form = reactive({
  email: '',
  password: '',
  full_name: '',
  company_name: '',
  country: '' as string,
})
const error = ref('')
const loading = ref(false)
const countries = ref<string[]>([])
const detecting = ref(true)

// Détecter le pays et charger la liste au montage
onMounted(async () => {
  try {
    const { detected_country, supported_countries } = await detectCountry()
    countries.value = supported_countries
    if (detected_country) {
      form.country = detected_country
    }
  } catch {
    // Silencieux : si la détection échoue, l'utilisateur choisira manuellement
  } finally {
    detecting.value = false
  }
})

async function handleRegister() {
  error.value = ''
  loading.value = true
  try {
    await register({
      ...form,
      country: form.country || null,
      // F02 — relai du token d'invitation, ignore par le backend si null.
      invite_token: inviteToken.value,
    })
    await login(form.email, form.password)
    await navigateTo('/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Erreur lors de l'inscription"
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
          <p class="text-gray-500 dark:text-gray-400 mt-2">Creer un compte</p>
        </div>

        <!-- F02 — banniere invitation team -->
        <div
          v-if="inviteToken"
          class="mb-4 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/30 p-3 text-sm text-emerald-800 dark:text-emerald-200"
        >
          Vous rejoignez une equipe existante via une invitation.
          Votre compte sera rattache a l'entreprise correspondante.
        </div>

        <form class="space-y-4" @submit.prevent="handleRegister">
          <div v-if="error" class="bg-red-50 dark:bg-red-900/20 text-brand-red text-sm rounded-lg p-3">
            {{ error }}
          </div>

          <div>
            <label for="full_name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Nom complet
            </label>
            <input
              id="full_name"
              v-model="form.full_name"
              type="text"
              required
              autocomplete="name"
              class="w-full px-4 py-2.5 border border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text rounded-lg focus:ring-2 focus:ring-brand-green focus:border-transparent outline-none"
              placeholder="Amadou Diallo"
            />
          </div>

          <div>
            <label for="company_name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Nom de l'entreprise
            </label>
            <input
              id="company_name"
              v-model="form.company_name"
              type="text"
              required
              class="w-full px-4 py-2.5 border border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text rounded-lg focus:ring-2 focus:ring-brand-green focus:border-transparent outline-none"
              placeholder="EcoSolaire SARL"
            />
          </div>

          <div>
            <label for="country" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Pays
            </label>
            <select
              id="country"
              v-model="form.country"
              required
              :disabled="detecting"
              class="w-full px-4 py-2.5 border border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text rounded-lg focus:ring-2 focus:ring-brand-green focus:border-transparent outline-none disabled:opacity-60"
            >
              <option v-if="detecting" value="">Détection en cours...</option>
              <option v-else value="" disabled>Sélectionnez un pays</option>
              <option v-for="c in countries" :key="c" :value="c">{{ c }}</option>
            </select>
            <p v-if="!detecting && form.country" class="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Détecté automatiquement — modifiable si besoin.
            </p>
          </div>

          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Adresse email
            </label>
            <input
              id="email"
              v-model="form.email"
              type="email"
              required
              autocomplete="email"
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
              v-model="form.password"
              type="password"
              required
              minlength="8"
              autocomplete="new-password"
              class="w-full px-4 py-2.5 border border-gray-300 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text rounded-lg focus:ring-2 focus:ring-brand-green focus:border-transparent outline-none"
              placeholder="Minimum 8 caracteres"
            />
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2.5 bg-brand-green text-white font-medium rounded-lg hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ loading ? 'Inscription...' : "S'inscrire" }}
          </button>
        </form>

        <p class="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
          Deja un compte ?
          <NuxtLink to="/login" class="text-brand-green font-medium hover:underline">
            Se connecter
          </NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>
