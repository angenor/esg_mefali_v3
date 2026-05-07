<script setup lang="ts">
import { onMounted } from 'vue'
import { useConsentsStore } from '~/stores/consents'
import type { ConsentType } from '~/composables/useDataPrivacy'

definePageMeta({ middleware: 'auth' })

const store = useConsentsStore()

onMounted(() => store.fetchAll())

async function handleToggle(type: ConsentType, granted: boolean) {
  if (granted) {
    await store.grant(type)
  } else {
    await store.revoke(type)
  }
}
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
      <h1 class="mt-2 text-2xl font-semibold">Mes consentements</h1>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        Activez ou désactivez les traitements de données non-essentiels. Les
        traitements essentiels (analyse profil, analyse documents IA,
        génération attestation crédit) sont nécessaires au fonctionnement du
        service ; vous pouvez les révoquer en supprimant votre compte.
      </p>
    </header>

    <div
      v-if="store.loading"
      class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 text-center text-sm text-gray-600 dark:text-gray-400"
    >
      Chargement des consentements…
    </div>
    <div
      v-else-if="store.error"
      class="rounded-lg border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-4 text-sm text-red-700 dark:text-red-300"
      aria-live="assertive"
    >
      Erreur : {{ store.error }}
    </div>
    <div v-else class="space-y-3">
      <ConsentToggle
        v-for="item in store.items"
        :key="item.type"
        :consent="item"
        :loading="store.loading"
        @toggle="handleToggle"
      />
    </div>
  </section>
</template>
