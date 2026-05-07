<script setup lang="ts">
import { useCompanyProfile } from '~/composables/useCompanyProfile'
import { useCompanyStore } from '~/stores/company'

definePageMeta({
  layout: 'default',
})

const companyStore = useCompanyStore()
const { loading, error, fetchProfile, updateProfile, fetchCompletion } = useCompanyProfile()

const identityCompletion = computed(() => companyStore.completion?.identity_completion ?? 0)
const esgCompletion = computed(() => companyStore.completion?.esg_completion ?? 0)
const overallCompletion = computed(() => companyStore.completion?.overall_completion ?? 0)

async function handleFieldUpdate(field: string, value: string | number | boolean | null) {
  await updateProfile({ [field]: value })
}

onMounted(async () => {
  await fetchProfile()
  await fetchCompletion()
})
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <!-- En-tête -->
    <div class="mb-8">
      <h2 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
        Profil Entreprise
      </h2>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Complétez votre profil pour recevoir des conseils ESG personnalisés.
      </p>
    </div>

    <!-- Erreur -->
    <div
      v-if="error"
      class="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
    >
      <p class="text-sm text-red-700 dark:text-red-400">{{ error }}</p>
    </div>

    <!-- Chargement initial -->
    <div v-if="!companyStore.profile && loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-3 border-brand-green border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Formulaire -->
    <ProfileForm
      v-else-if="companyStore.profile"
      :profile="companyStore.profile"
      :identity-completion="identityCompletion"
      :esg-completion="esgCompletion"
      :overall-completion="overallCompletion"
      :loading="loading"
      @update="handleFieldUpdate"
    />
  </div>
</template>
