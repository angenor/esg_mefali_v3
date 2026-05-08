<script setup lang="ts">
// F14 — Page liste paginée des matches d'un projet avec filtres
// URL-synchronisés (min_score, bottleneck, fund_id).

import { computed, onMounted, ref, watch } from 'vue'
import BottleneckBadge from '~/components/matching/BottleneckBadge.vue'
import { useMatching } from '~/composables/useMatching'
import { useMatchesStore } from '~/stores/matches'
import type { MatchBottleneck, OfferMatch } from '~/types/matching'

definePageMeta({ layout: false })

const route = useRoute()
const router = useRouter()
const matchesStore = useMatchesStore()
const { listMatches, recomputeMatches, loading, error } = useMatching()

const projectId = (route.params as { id: string }).id

const minScore = ref<number>(
  Number.parseInt((route.query.min_score as string) ?? '0', 10) || 0,
)
const bottleneck = ref<MatchBottleneck | ''>(
  ((route.query.bottleneck as string) ?? '') as MatchBottleneck | '',
)
const fundId = ref<string>((route.query.fund_id as string) ?? '')
const page = ref<number>(
  Number.parseInt((route.query.page as string) ?? '1', 10) || 1,
)
const limit = 25

const items = ref<OfferMatch[]>([])
const total = ref<number>(0)
const errorMsg = ref<string | null>(null)

async function load() {
  errorMsg.value = null
  const filters = {
    minScore: minScore.value > 0 ? minScore.value : undefined,
    bottleneck: bottleneck.value || undefined,
    fundId: fundId.value || undefined,
    page: page.value,
    limit,
  }
  const result = await listMatches(projectId, filters)
  if (!result) {
    errorMsg.value = error.value || 'Impossible de charger les matches.'
    return
  }
  items.value = result.items
  total.value = result.total
  matchesStore.setMatches(projectId, result.items, result.total)
}

function syncUrl() {
  const query: Record<string, string> = {}
  if (minScore.value > 0) query.min_score = String(minScore.value)
  if (bottleneck.value) query.bottleneck = bottleneck.value
  if (fundId.value) query.fund_id = fundId.value
  if (page.value > 1) query.page = String(page.value)
  router.replace({ query })
}

watch([minScore, bottleneck, fundId], () => {
  page.value = 1
  syncUrl()
  load()
})

watch(page, () => {
  syncUrl()
  load()
})

async function onRecompute() {
  errorMsg.value = null
  const r = await recomputeMatches(projectId)
  if (!r) {
    errorMsg.value = error.value || 'Erreur de recalcul.'
    return
  }
  // Polling simple : recharger après 1s
  setTimeout(() => {
    load()
  }, 1000)
}

const totalPages = computed(() =>
  total.value === 0 ? 1 : Math.ceil(total.value / limit),
)

onMounted(load)
</script>

<template>
  <div class="max-w-5xl mx-auto p-4 sm:p-6">
    <header class="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-xl font-bold text-gray-900 dark:text-surface-dark-text">
          Tous les matches du projet
        </h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {{ total }} match(es) — page {{ page }}/{{ totalPages }}
        </p>
      </div>
      <button
        type="button"
        class="px-3 py-2 text-sm rounded-md border border-emerald-500 bg-white dark:bg-dark-card text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 disabled:opacity-50"
        :disabled="loading"
        :aria-busy="loading"
        data-testid="recompute-matches-page-btn"
        @click="onRecompute"
      >
        {{ loading ? 'Recalcul…' : 'Recalculer' }}
      </button>
    </header>

    <!-- Filtres -->
    <div
      class="mb-4 grid grid-cols-1 sm:grid-cols-3 gap-3 rounded-md border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4"
    >
      <div>
        <label
          for="min-score"
          class="block text-xs font-medium text-gray-700 dark:text-gray-300"
        >
          Score minimum : {{ minScore }}
        </label>
        <input
          id="min-score"
          v-model.number="minScore"
          type="range"
          min="0"
          max="100"
          step="5"
          class="mt-1 w-full accent-emerald-500"
          data-testid="filter-min-score"
        />
      </div>
      <div>
        <label
          for="bottleneck"
          class="block text-xs font-medium text-gray-700 dark:text-gray-300"
        >
          Goulot d'étranglement
        </label>
        <select
          id="bottleneck"
          v-model="bottleneck"
          class="mt-1 w-full rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm py-1.5 px-2 dark:text-surface-dark-text"
          data-testid="filter-bottleneck"
        >
          <option value="">Tous</option>
          <option value="fund">Critères du fonds</option>
          <option value="intermediary">Critères de l'intermédiaire</option>
          <option value="balanced">Profil équilibré</option>
        </select>
      </div>
      <div>
        <label
          for="fund-id"
          class="block text-xs font-medium text-gray-700 dark:text-gray-300"
        >
          ID fonds (filtre)
        </label>
        <input
          id="fund-id"
          v-model.trim="fundId"
          type="text"
          class="mt-1 w-full rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm py-1.5 px-2 dark:text-surface-dark-text"
          placeholder="UUID du fonds"
          data-testid="filter-fund-id"
        />
      </div>
    </div>

    <div
      v-if="errorMsg"
      class="mb-3 rounded-md border border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-950/30 p-3 text-sm text-rose-700 dark:text-rose-300"
      role="alert"
    >
      {{ errorMsg }}
    </div>

    <div
      v-if="loading && items.length === 0"
      class="flex items-center justify-center py-12"
      role="status"
      aria-label="Chargement"
    >
      <div
        class="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"
      />
    </div>

    <div
      v-else-if="items.length === 0"
      class="rounded-md border border-dashed border-gray-300 dark:border-dark-border p-8 text-center"
      data-testid="matches-empty-state"
    >
      <p class="text-sm text-gray-600 dark:text-gray-400">
        Aucun match ne correspond aux filtres actuels.
      </p>
    </div>

    <ul v-else role="list" class="space-y-3">
      <li
        v-for="match in items"
        :key="match.id"
        class="rounded-md border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4"
        :data-testid="`match-row-${match.id}`"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p
              class="text-sm font-semibold text-surface-text dark:text-surface-dark-text"
            >
              Offre {{ match.offerId }}
            </p>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              Fonds {{ match.fundScore }}/100 · Intermédiaire
              {{ match.intermediaryScore }}/100 · Calculé le
              {{ new Date(match.computedAt).toLocaleDateString('fr-FR') }}
            </p>
          </div>
          <div class="flex items-center gap-3">
            <span
              class="text-lg font-bold tabular-nums text-surface-text dark:text-surface-dark-text"
              :aria-label="`Score global ${match.globalScore} sur 100`"
            >
              {{ match.globalScore }}/100
            </span>
            <BottleneckBadge :bottleneck="match.bottleneck" />
          </div>
        </div>
      </li>
    </ul>

    <!-- Pagination -->
    <nav
      v-if="totalPages > 1"
      class="mt-4 flex items-center justify-between"
      aria-label="Pagination des matches"
    >
      <button
        type="button"
        class="px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text disabled:opacity-50"
        :disabled="page <= 1"
        data-testid="pagination-prev"
        @click="page = page - 1"
      >
        Précédent
      </button>
      <span class="text-xs text-gray-500 dark:text-gray-400">
        Page {{ page }} / {{ totalPages }}
      </span>
      <button
        type="button"
        class="px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card text-surface-text dark:text-surface-dark-text disabled:opacity-50"
        :disabled="page >= totalPages"
        data-testid="pagination-next"
        @click="page = page + 1"
      >
        Suivant
      </button>
    </nav>
  </div>
</template>
