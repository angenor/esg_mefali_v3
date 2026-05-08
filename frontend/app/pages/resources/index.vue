<script setup lang="ts">
// F20 — Page publique : liste filtrable de la bibliothèque ressources.
import { onMounted, ref, watch } from 'vue'
import { useResources } from '~/composables/useResources'
import type {
  ResourceFiltersQuery,
  ResourceListItem,
} from '~/types/resource'
import ResourceCard from '~/components/resources/ResourceCard.vue'
import ResourceFilters from '~/components/resources/ResourceFilters.vue'

const { listResources } = useResources()

const filters = ref<ResourceFiltersQuery>({
  page: 1,
  limit: 20,
})
const items = ref<ResourceListItem[]>([])
const total = ref<number>(0)
const loading = ref<boolean>(false)
const error = ref<string | null>(null)

async function refresh(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const resp = await listResources(filters.value)
    items.value = resp.items
    total.value = resp.total
  } catch (err) {
    error.value =
      err instanceof Error
        ? err.message
        : 'Impossible de charger les ressources.'
  } finally {
    loading.value = false
  }
}

watch(filters, () => void refresh(), { deep: true })

onMounted(() => void refresh())
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-6xl">
    <header class="mb-8">
      <h1
        class="text-3xl font-bold text-surface-text dark:text-surface-dark-text mb-2"
      >
        Bibliothèque de ressources
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Guides ESG, modèles de documents, fiches pratiques par intermédiaire et
        FAQ pour vous accompagner dans votre démarche.
      </p>
    </header>

    <div class="grid gap-6 lg:grid-cols-[280px_1fr]">
      <aside>
        <ResourceFilters v-model="filters" />
      </aside>

      <main>
        <p
          v-if="!loading"
          class="text-sm text-gray-500 dark:text-gray-400 mb-4"
        >
          {{ total }} ressource{{ total > 1 ? 's' : '' }} disponible{{
            total > 1 ? 's' : ''
          }}
        </p>

        <div
          v-if="loading"
          class="text-center py-10 text-gray-500 dark:text-gray-400"
          role="status"
        >
          Chargement…
        </div>
        <div
          v-else-if="error"
          class="rounded-md border border-red-300 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300"
          role="alert"
        >
          {{ error }}
        </div>
        <div
          v-else-if="items.length === 0"
          class="rounded-md border border-gray-200 bg-white p-8 text-center text-gray-500 dark:border-dark-border dark:bg-dark-card dark:text-gray-400"
        >
          Aucune ressource ne correspond à votre recherche.
        </div>
        <div v-else class="grid gap-4 md:grid-cols-2">
          <ResourceCard
            v-for="r in items"
            :key="r.id"
            :resource="r"
          />
        </div>
      </main>
    </div>
  </div>
</template>
