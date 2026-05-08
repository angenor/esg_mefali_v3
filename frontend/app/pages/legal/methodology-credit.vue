<template>
  <div class="min-h-screen bg-surface-bg dark:bg-surface-dark-bg py-10 px-4">
    <div class="max-w-4xl mx-auto">
      <header class="mb-8">
        <h1
          class="text-3xl font-bold text-surface-text dark:text-surface-dark-text"
        >
          Méthodologie de scoring crédit
        </h1>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          Cette page expose publiquement les facteurs, leur pondération et leur
          source vérifiée pour garantir la transparence et l'auditabilité du
          score crédit alternatif (F18).
        </p>
        <div
          v-if="methodology"
          class="mt-4 inline-block px-3 py-1 text-sm bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300 rounded-full"
          aria-label="Version de la méthodologie"
        >
          Version {{ methodology.version }}
        </div>
      </header>

      <section
        v-if="error"
        class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-300"
        role="alert"
      >
        {{ error }}
      </section>

      <section
        v-else-if="loading"
        class="p-6 text-gray-600 dark:text-gray-400"
        aria-live="polite"
      >
        Chargement de la méthodologie…
      </section>

      <section
        v-else-if="!methodology || methodology.factors.length === 0"
        class="p-6 bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg text-gray-600 dark:text-gray-400"
      >
        Aucun facteur publié pour le moment.
      </section>

      <section v-else class="space-y-4" aria-label="Liste des facteurs publiés">
        <article
          v-for="factor in methodology.factors"
          :key="factor.id"
          class="p-5 bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border rounded-lg"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1">
              <h2
                class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
              >
                {{ factor.name }}
              </h2>
              <p
                class="mt-1 text-sm text-gray-600 dark:text-gray-400"
              >
                Catégorie :
                <span class="font-medium">{{ factor.category }}</span>
              </p>
              <p
                class="mt-2 text-surface-text dark:text-surface-dark-text"
              >
                {{ factor.description }}
              </p>
            </div>
            <div
              class="flex flex-col items-end gap-2"
            >
              <span
                class="px-3 py-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300 rounded-full text-sm font-semibold"
                :aria-label="`Poids ${factor.weight}`"
              >
                Poids : {{ factor.weight }}
              </span>
              <a
                :href="`/sources/${factor.source_id}`"
                class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                :aria-label="`Source vérifiée pour ${factor.name}`"
              >
                Source vérifiée
              </a>
            </div>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCreditAlternativeData } from '~/composables/useCreditAlternativeData'
import type { MethodologyResponse } from '~/types/creditAlternative'

definePageMeta({ auth: false })

const methodology = ref<MethodologyResponse | null>(null)
const loading = ref(true)
const error = ref('')

const { getMethodology } = useCreditAlternativeData()

onMounted(async () => {
  try {
    methodology.value = await getMethodology()
  } catch (e) {
    error.value = (e as Error).message || 'Erreur lors du chargement'
  } finally {
    loading.value = false
  }
})
</script>
