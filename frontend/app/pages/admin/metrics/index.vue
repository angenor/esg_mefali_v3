<script setup lang="ts">
// F09 PRIO 3 — Dashboard métriques admin (overview).
import { onMounted, ref } from 'vue'
import MetricsCard from '~/components/admin/MetricsCard.vue'
import {
  useAdminMetrics,
  type AdminMetricsOverview,
} from '~/composables/useAdminMetrics'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const { fetchOverview } = useAdminMetrics()
const data = ref<AdminMetricsOverview | null>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchOverview()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-7xl mx-auto">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Métriques globales
      </h1>
      <button
        type="button"
        :disabled="loading"
        class="rounded-lg border border-gray-300 dark:border-dark-border px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-dark-hover disabled:opacity-50"
        data-testid="metrics-refresh"
        @click="load"
      >
        {{ loading ? 'Chargement…' : 'Rafraîchir' }}
      </button>
    </header>

    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>

    <div v-if="data" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricsCard
        title="Sources catalogue"
        :main-value="data.sources.total"
        icon="📚"
        color="blue"
        :sub-metrics="
          Object.entries(data.sources.breakdown).map(([k, v]) => ({
            label: k,
            value: v,
            highlight:
              k === 'verified'
                ? 'green'
                : k === 'pending'
                ? 'amber'
                : k === 'outdated'
                ? 'red'
                : 'gray',
          }))
        "
      />

      <MetricsCard
        title="Comptes PME"
        :main-value="data.accounts.total"
        icon="🏢"
        color="emerald"
        :sub-metrics="[
          { label: 'Actifs', value: data.accounts.active, highlight: 'green' },
          { label: 'Désactivés', value: data.accounts.inactive, highlight: 'gray' },
          { label: 'Nouveaux 30j', value: data.accounts.new_30d, highlight: 'blue' },
          {
            label: 'Suppression programmée',
            value: data.accounts.pending_deletion,
            highlight: 'amber',
          },
        ]"
      />

      <MetricsCard
        title="Candidatures"
        :main-value="data.applications.total"
        icon="📨"
        color="violet"
        :sub-metrics="[
          {
            label: 'Taux de soumission',
            value: `${(data.applications.submission_rate * 100).toFixed(1)}%`,
            highlight: 'blue',
          },
          ...Object.entries(data.applications.by_status).map(([k, v]) => ({
            label: k,
            value: v,
          })),
        ]"
      />

      <MetricsCard
        title="Attestations (F08)"
        :main-value="data.attestations.total"
        icon="🛡️"
        color="amber"
        :sub-metrics="[
          { label: 'Actives', value: data.attestations.active, highlight: 'green' },
          { label: 'Révoquées', value: data.attestations.revoked, highlight: 'red' },
          { label: 'Expirées', value: data.attestations.expired, highlight: 'gray' },
        ]"
      />
    </div>

    <p
      v-if="data"
      class="mt-6 text-xs text-gray-500 dark:text-gray-400 text-center"
    >
      Généré le
      {{ new Date(data.generated_at).toLocaleString('fr-FR') }}
      —
      <span :class="data.llm_costs.available ? '' : 'italic'">
        Coûts LLM : {{ data.llm_costs.note }}
      </span>
    </p>
  </div>
</template>
