<script setup lang="ts">
// F09 — Création d'une nouvelle source réglementaire.
import { ref } from 'vue'
import { useAdminSources } from '~/composables/useAdminSources'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const { createSource } = useAdminSources()

const url = ref('')
const title = ref('')
const publisher = ref('')
const version = ref('')
const datePubli = ref('')
const page = ref<number | null>(null)
const section = ref('')

const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const created = await createSource({
      url: url.value,
      title: title.value,
      publisher: publisher.value,
      version: version.value,
      date_publi: datePubli.value,
      page: page.value,
      section: section.value || null,
    })
    await navigateTo(`/admin/sources/${created.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text mb-6">
      Nouvelle source
    </h1>

    <form
      class="space-y-4 bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6"
      @submit.prevent="submit"
    >
      <div>
        <label class="block text-sm font-medium mb-1">URL</label>
        <input
          v-model="url"
          type="url"
          required
          class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
        />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Titre</label>
        <input
          v-model="title"
          type="text"
          required
          class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
        />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium mb-1">Publisher</label>
          <input
            v-model="publisher"
            type="text"
            required
            class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">Version</label>
          <input
            v-model="version"
            type="text"
            required
            class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
          />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium mb-1">Date publi</label>
          <input
            v-model="datePubli"
            type="date"
            required
            class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">Page (optionnel)</label>
          <input
            v-model.number="page"
            type="number"
            min="1"
            class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
          />
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Section (optionnel)</label>
        <input
          v-model="section"
          type="text"
          class="w-full rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input px-3 py-2"
        />
      </div>

      <p
        v-if="error"
        class="text-sm text-red-600 dark:text-red-400"
        role="alert"
      >
        {{ error }}
      </p>

      <div class="flex items-center gap-3">
        <button
          type="submit"
          :disabled="loading"
          class="rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 disabled:opacity-50"
        >
          <span v-if="loading">Création…</span>
          <span v-else>Créer</span>
        </button>
        <NuxtLink
          to="/admin/sources"
          class="text-sm text-gray-600 dark:text-gray-400 hover:underline"
        >
          Annuler
        </NuxtLink>
      </div>
    </form>
  </div>
</template>
