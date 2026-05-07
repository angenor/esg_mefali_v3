<script setup lang="ts">
import { onMounted } from 'vue'
import { useDataPrivacy } from '~/composables/useDataPrivacy'

definePageMeta({ middleware: 'auth' })

const { useInventory } = useDataPrivacy()
const { data, loading, error, fetchInventory } = useInventory()

onMounted(fetchInventory)
</script>

<template>
  <section
    class="max-w-5xl mx-auto bg-surface-bg dark:bg-surface-dark-bg text-surface-text dark:text-surface-dark-text"
  >
    <header class="mb-6">
      <NuxtLink
        to="/mes-donnees"
        class="text-sm text-gray-600 dark:text-gray-400 hover:underline"
      >
        ← Retour à Mes données
      </NuxtLink>
      <h1 class="mt-2 text-2xl font-semibold">Inventaire de mes données</h1>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        Vue détaillée de vos données stockées sur la plateforme.
      </p>
    </header>

    <div
      v-if="loading"
      class="rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6 text-center text-sm text-gray-600 dark:text-gray-400"
    >
      Chargement de l'inventaire…
    </div>
    <div
      v-else-if="error"
      class="rounded-lg border border-red-300 bg-red-50 dark:bg-red-900/30 dark:border-red-700 p-4 text-sm text-red-700 dark:text-red-300"
      aria-live="assertive"
    >
      Erreur : {{ error }}
    </div>
    <div v-else-if="data">
      <DataInventoryTable
        :counts="data.counts"
        :last-modified="data.last_modified"
      />
      <div class="mt-6">
        <DataExportButton />
      </div>
    </div>
  </section>
</template>
