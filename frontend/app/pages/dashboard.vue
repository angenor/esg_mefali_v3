<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useDashboard } from '~/composables/useDashboard'

definePageMeta({ layout: 'default' })

const { store, fetchSummary } = useDashboard()

onMounted(async () => {
  await fetchSummary()
})

// Sous-titre ESG avec date de dernière évaluation
const esgSubtitle = computed(() => {
  const esg = store.summary?.esg
  if (!esg?.last_assessment_date) return null
  const d = new Date(esg.last_assessment_date)
  return `Dernière éval. : ${d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })}`
})

// Sous-titre carbone avec année
const carbonSubtitle = computed(() => {
  const carbon = store.summary?.carbon
  if (!carbon) return null
  let label = `Bilan ${carbon.year}`
  if (carbon.variation_percent !== null && carbon.variation_percent !== undefined) {
    const sign = carbon.variation_percent > 0 ? '+' : ''
    label += ` — ${sign}${carbon.variation_percent}% vs année préc.`
  }
  return label
})

// Sous-titre crédit avec date de calcul
const creditSubtitle = computed(() => {
  const credit = store.summary?.credit
  if (!credit?.last_calculated) return null
  const d = new Date(credit.last_calculated)
  return `Calculé le ${d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })}`
})
</script>

<template>
  <div class="p-4 md:p-6 max-w-7xl mx-auto">
    <!-- En-tête -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Tableau de bord
      </h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
        Vue synthétique de votre performance ESG et financière
      </p>
    </div>

    <!-- Squelette de chargement -->
    <template v-if="store.loading">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div
          v-for="i in 4"
          :key="i"
          class="bg-gray-100 dark:bg-dark-card rounded-xl h-36 animate-pulse"
        />
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="bg-gray-100 dark:bg-dark-card rounded-xl h-64 animate-pulse" />
        <div class="bg-gray-100 dark:bg-dark-card rounded-xl h-64 animate-pulse" />
      </div>
    </template>

    <!-- Contenu principal -->
    <template v-else>
      <!-- Message d'erreur -->
      <div
        v-if="store.error"
        class="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4"
      >
        <p class="text-sm text-red-700 dark:text-red-400">{{ store.error }}</p>
        <button
          class="mt-2 text-xs text-red-600 dark:text-red-500 hover:underline"
          @click="fetchSummary"
        >
          Réessayer
        </button>
      </div>

      <!-- Grille des 4 scores (2x2 desktop, 1 col mobile) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        <!-- Score ESG -->
        <ScoreCard
          data-guide-target="dashboard-esg-card"
          label="Score ESG"
          icon="🌍"
          :score="store.summary?.esg?.score ?? null"
          :grade="store.summary?.esg?.grade ?? null"
          :trend="store.summary?.esg?.trend ?? null"
          :subtitle="esgSubtitle"
        >
          <!-- Piliers ESG en mini affichage -->
          <div
            v-if="store.summary?.esg?.pillar_scores && Object.keys(store.summary.esg.pillar_scores).length > 0"
            class="grid grid-cols-3 gap-2 mt-1"
          >
            <div
              v-for="(val, key) in store.summary.esg.pillar_scores"
              :key="key"
              class="text-center"
            >
              <span class="text-xs text-gray-400 dark:text-gray-600 block capitalize">
                {{ key === 'environment' ? 'Env.' : key === 'social' ? 'Social' : 'Gov.' }}
              </span>
              <span class="text-sm font-semibold text-surface-text dark:text-surface-dark-text">
                {{ Math.round(Number(val)) }}
              </span>
            </div>
          </div>
          <template v-else>
            <NuxtLink
              to="/esg"
              class="text-xs text-green-600 dark:text-green-400 hover:underline"
            >
              Démarrer l'évaluation →
            </NuxtLink>
          </template>
        </ScoreCard>

        <!-- Score Carbone -->
        <ScoreCard
          data-guide-target="dashboard-carbon-card"
          label="Empreinte Carbone"
          icon="💨"
          :score="store.summary?.carbon?.total_tco2e ?? null"
          :grade="null"
          :subtitle="carbonSubtitle"
        >
          <template v-if="store.summary?.carbon">
            <div class="text-xs text-gray-500 dark:text-gray-500">
              <span class="font-medium text-surface-text dark:text-surface-dark-text">
                {{ store.summary.carbon.total_tco2e.toFixed(1) }} tCO₂e
              </span>
              <span class="ml-1" v-if="store.summary.carbon.top_category">
                — {{ store.summary.carbon.top_category }}
              </span>
            </div>
          </template>
          <template v-else>
            <NuxtLink
              to="/carbon"
              class="text-xs text-green-600 dark:text-green-400 hover:underline"
            >
              Calculer mon empreinte →
            </NuxtLink>
          </template>
        </ScoreCard>

        <!-- Score Crédit -->
        <ScoreCard
          data-guide-target="dashboard-credit-card"
          label="Crédit Vert"
          icon="⭐"
          :score="store.summary?.credit?.score ?? null"
          :grade="store.summary?.credit?.grade ?? null"
          :subtitle="creditSubtitle"
        >
          <template v-if="!store.summary?.credit">
            <NuxtLink
              to="/credit-score"
              class="text-xs text-green-600 dark:text-green-400 hover:underline"
            >
              Générer mon score →
            </NuxtLink>
          </template>
        </ScoreCard>

        <!-- Financement -->
        <FinancingCard data-guide-target="dashboard-financing-card" :financing="store.summary?.financing ?? null" />
      </div>

      <!-- F21 (US1) — Cards par offre -->
      <section class="mt-6">
        <ApplicationStatusCardList
          :cards="store.summary?.financing?.applications_by_offer ?? []"
          :total-active="store.summary?.financing?.active_applications_count ?? 0"
        />
      </section>

      <!-- F21 (US3) — Carte UEMOA des intermédiaires actifs -->
      <section class="mt-6">
        <IntermediariesMap :intermediaries="store.summary?.financing?.active_intermediaries ?? []" />
      </section>

      <!-- Section prochaines actions + activité récente (2 colonnes desktop) -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Prochaines actions -->
        <section>
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold text-surface-text dark:text-surface-dark-text">
              Prochaines actions
            </h2>
            <NuxtLink
              to="/action-plan"
              class="text-xs text-green-600 dark:text-green-400 hover:underline"
            >
              Voir tout →
            </NuxtLink>
          </div>
          <NextActions :actions="store.summary?.next_actions ?? []" />
        </section>

        <!-- Activité récente -->
        <section>
          <h2 class="text-base font-semibold text-surface-text dark:text-surface-dark-text mb-3">
            Activité récente
          </h2>
          <ActivityFeed :events="store.summary?.recent_activity ?? []" />
        </section>
      </div>

      <!-- Badges -->
      <section class="mt-6">
        <BadgeGrid :badges="store.summary?.badges ?? []" />
      </section>
    </template>
  </div>
</template>
