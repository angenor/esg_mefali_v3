<script setup lang="ts">
// F20 — Page admin : liste paginée + actions Publier / Archiver / Supprimer.
import { onMounted, ref } from 'vue'
import { useAdminResources } from '~/composables/useAdminResources'
import type { ResourceListItem } from '~/types/resource'
import ResourceTypeBadge from '~/components/resources/ResourceTypeBadge.vue'

definePageMeta({ middleware: ['admin'], layout: 'admin' })

const { adminList, adminPublish, adminArchive, adminDelete } = useAdminResources()

const items = ref<ResourceListItem[]>([])
const total = ref<number>(0)
const loading = ref<boolean>(false)
const error = ref<string | null>(null)

async function refresh(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const resp = await adminList()
    items.value = resp.items
    total.value = resp.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur de chargement.'
  } finally {
    loading.value = false
  }
}

async function publishItem(id: string): Promise<void> {
  try {
    await adminPublish(id)
    await refresh()
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : 'Publication impossible.'
  }
}

async function archiveItem(id: string): Promise<void> {
  await adminArchive(id)
  await refresh()
}

async function deleteItem(id: string): Promise<void> {
  if (!window.confirm('Supprimer ce brouillon ?')) return
  await adminDelete(id)
  await refresh()
}

onMounted(() => void refresh())
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-6xl">
    <header class="flex items-center justify-between mb-6">
      <div>
        <h1
          class="text-2xl font-bold text-surface-text dark:text-surface-dark-text"
        >
          Gestion des ressources
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ total }} ressource{{ total > 1 ? 's' : '' }} au total
        </p>
      </div>
      <NuxtLink
        to="/admin/resources/new"
        class="px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition"
      >
        + Nouvelle ressource
      </NuxtLink>
    </header>

    <div
      v-if="error"
      class="rounded-md border border-red-300 bg-red-50 p-3 mb-4 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300"
      role="alert"
    >
      {{ error }}
    </div>

    <div
      v-if="loading"
      class="text-center py-10 text-gray-500 dark:text-gray-400"
    >
      Chargement…
    </div>

    <table
      v-else
      class="w-full text-sm border border-gray-200 rounded-md overflow-hidden dark:border-dark-border"
    >
      <thead class="bg-gray-50 dark:bg-dark-hover">
        <tr>
          <th class="px-3 py-2 text-left">Titre</th>
          <th class="px-3 py-2 text-left">Type</th>
          <th class="px-3 py-2 text-left">Statut</th>
          <th class="px-3 py-2 text-left">Version</th>
          <th class="px-3 py-2 text-right">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-200 dark:divide-dark-border">
        <tr
          v-for="r in items"
          :key="r.id"
          class="bg-white dark:bg-dark-card"
        >
          <td class="px-3 py-2 text-surface-text dark:text-surface-dark-text">
            <NuxtLink
              :to="`/admin/resources/${r.id}`"
              class="hover:underline text-emerald-600 dark:text-emerald-400"
            >
              {{ r.title }}
            </NuxtLink>
          </td>
          <td class="px-3 py-2">
            <ResourceTypeBadge :type="r.type" />
          </td>
          <td class="px-3 py-2">
            <span
              :class="{
                'text-amber-600 dark:text-amber-400':
                  r.publication_status === 'draft',
                'text-emerald-600 dark:text-emerald-400':
                  r.publication_status === 'published',
                'text-gray-500 dark:text-gray-400':
                  r.publication_status === 'archived',
              }"
            >
              {{ r.publication_status }}
            </span>
          </td>
          <td class="px-3 py-2 text-gray-600 dark:text-gray-400">
            {{ r.version }}
          </td>
          <td class="px-3 py-2 text-right space-x-2">
            <button
              v-if="r.publication_status === 'draft'"
              type="button"
              class="text-emerald-600 hover:underline dark:text-emerald-400"
              @click="publishItem(r.id)"
            >
              Publier
            </button>
            <button
              v-if="r.publication_status === 'published'"
              type="button"
              class="text-amber-600 hover:underline dark:text-amber-400"
              @click="archiveItem(r.id)"
            >
              Archiver
            </button>
            <button
              v-if="r.publication_status === 'draft'"
              type="button"
              class="text-red-600 hover:underline dark:text-red-400"
              @click="deleteItem(r.id)"
            >
              Supprimer
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
