<script setup lang="ts">
// F16 — Carte détaillée d'une simulation pour 1 offre.
// Rend cost_breakdown, ROI, carbon, timeline, MoneyDisplay, SourceLink,
// badges factor_status pending/outdated. Dark mode complet.

import { computed } from 'vue'
import MoneyDisplay from '~/components/ui/MoneyDisplay.vue'
import SourceLink from '~/components/sources/SourceLink.vue'
import type { SimulationResult } from '~/types/simulator'

interface Props {
  result: SimulationResult
  isCheapest?: boolean
  isFastest?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isCheapest: false,
  isFastest: false,
})

const emit = defineEmits<{
  'open-source': [sourceId: string]
}>()

const totalWeeksMax = computed(() =>
  props.result.timeline
    .filter((s) => s.step_id !== 'preparation')
    .reduce((acc, s) => acc + (s.weeks_max ?? 0), 0),
)

const instrumentLabel = computed(() => {
  const map: Record<string, string> = {
    subvention: 'Subvention',
    pret_concessionnel: 'Prêt concessionnel',
    equity: 'Equity',
    blending: 'Blending',
  }
  return map[props.result.roi.instrument] ?? props.result.roi.instrument
})

function statusBadgeClass(status: string | null): string {
  if (status === 'pending') {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
  }
  if (status === 'outdated') {
    return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
  }
  return ''
}

function statusBadgeLabel(status: string | null): string {
  if (status === 'pending') return 'en attente de vérification'
  if (status === 'outdated') return 'source obsolète'
  return ''
}
</script>

<template>
  <article
    class="rounded-lg border bg-white dark:bg-dark-card border-gray-200 dark:border-dark-border p-5 shadow-sm"
    :class="{
      'ring-2 ring-emerald-500': isCheapest,
      'ring-2 ring-blue-500': isFastest && !isCheapest,
    }"
    role="region"
    aria-label="Détail de la simulation"
  >
    <header class="flex items-start justify-between mb-4">
      <div>
        <h3
          class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
        >
          Simulation
        </h3>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Offre {{ result.offer_id.slice(0, 8) }}
        </p>
      </div>
      <div class="flex flex-col items-end gap-1">
        <span
          v-if="isCheapest"
          class="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
        >
          Moins chère
        </span>
        <span
          v-if="isFastest"
          class="px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
        >
          Plus rapide
        </span>
      </div>
    </header>

    <!-- Coût total -->
    <section class="mb-5">
      <h4 class="text-sm font-semibold mb-2 text-surface-text dark:text-surface-dark-text">
        Coût total
      </h4>
      <dl class="space-y-2 text-sm">
        <div class="flex items-center justify-between">
          <dt class="text-gray-700 dark:text-gray-300">Principal</dt>
          <dd class="font-medium text-surface-text dark:text-surface-dark-text">
            <MoneyDisplay :money="result.principal" />
          </dd>
        </div>
        <div class="flex items-center justify-between">
          <dt class="text-gray-700 dark:text-gray-300 flex items-center">
            Frais d'instruction
            <SourceLink
              v-if="result.cost_breakdown.doc_fee.source_id"
              :source-id="result.cost_breakdown.doc_fee.source_id"
              @open="(id) => emit('open-source', id)"
            />
            <span
              v-if="result.cost_breakdown.doc_fee.factor_status && statusBadgeLabel(result.cost_breakdown.doc_fee.factor_status)"
              class="ml-2 px-2 py-0.5 text-xs rounded"
              :class="statusBadgeClass(result.cost_breakdown.doc_fee.factor_status)"
            >
              {{ statusBadgeLabel(result.cost_breakdown.doc_fee.factor_status) }}
            </span>
          </dt>
          <dd class="font-medium text-surface-text dark:text-surface-dark-text">
            <MoneyDisplay :money="result.cost_breakdown.doc_fee.amount" />
          </dd>
        </div>
        <div class="flex items-center justify-between">
          <dt class="text-gray-700 dark:text-gray-300 flex items-center">
            Frais cumulés sur durée
            <SourceLink
              v-if="result.cost_breakdown.total_fees_over_duration.source_id"
              :source-id="result.cost_breakdown.total_fees_over_duration.source_id"
              @open="(id) => emit('open-source', id)"
            />
          </dt>
          <dd class="font-medium text-surface-text dark:text-surface-dark-text">
            <MoneyDisplay :money="result.cost_breakdown.total_fees_over_duration.amount" />
          </dd>
        </div>
        <div class="flex items-center justify-between">
          <dt class="text-gray-700 dark:text-gray-300 flex items-center">
            Garantie immobilisée
            <SourceLink
              v-if="result.cost_breakdown.guarantee_required.source_id"
              :source-id="result.cost_breakdown.guarantee_required.source_id"
              @open="(id) => emit('open-source', id)"
            />
          </dt>
          <dd class="font-medium text-surface-text dark:text-surface-dark-text">
            <MoneyDisplay :money="result.cost_breakdown.guarantee_required.amount" />
          </dd>
        </div>
        <div class="flex items-center justify-between">
          <dt class="text-gray-700 dark:text-gray-300 flex items-center">
            Marge de change
            <SourceLink
              v-if="result.cost_breakdown.fx_margin.source_id"
              :source-id="result.cost_breakdown.fx_margin.source_id"
              @open="(id) => emit('open-source', id)"
            />
          </dt>
          <dd class="font-medium text-surface-text dark:text-surface-dark-text">
            <MoneyDisplay :money="result.cost_breakdown.fx_margin.amount" />
          </dd>
        </div>
        <div
          class="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-dark-border"
        >
          <dt class="font-semibold text-surface-text dark:text-surface-dark-text">
            Total
          </dt>
          <dd class="font-bold text-emerald-700 dark:text-emerald-400 text-base">
            <MoneyDisplay :money="result.cost_breakdown.total_cost" />
          </dd>
        </div>
      </dl>
    </section>

    <!-- ROI -->
    <section class="mb-5">
      <h4 class="text-sm font-semibold mb-2 text-surface-text dark:text-surface-dark-text">
        Retour sur investissement
      </h4>
      <p class="text-sm text-gray-700 dark:text-gray-300">
        <span class="font-medium">Instrument :</span> {{ instrumentLabel }}
      </p>
      <p class="text-sm text-gray-700 dark:text-gray-300 mt-1">
        {{ result.roi.notes_fr }}
      </p>
      <p
        v-if="result.roi.payback_months"
        class="text-sm text-gray-700 dark:text-gray-300 mt-1"
      >
        Amortissement estimé : {{ result.roi.payback_months }} mois
      </p>
    </section>

    <!-- Impact carbone -->
    <section class="mb-5">
      <h4 class="text-sm font-semibold mb-2 text-surface-text dark:text-surface-dark-text">
        Impact carbone
      </h4>
      <p
        v-if="result.carbon_impact.tco2e_per_year"
        class="text-sm text-gray-700 dark:text-gray-300"
      >
        {{ result.carbon_impact.tco2e_per_year }} tCO₂e/an
        <SourceLink
          v-if="result.carbon_impact.factor_source_id"
          :source-id="result.carbon_impact.factor_source_id"
          @open="(id) => emit('open-source', id)"
        />
        <span
          v-if="result.carbon_impact.is_approximate"
          class="ml-2 px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
        >
          estimation approximative
        </span>
      </p>
      <p
        v-else
        class="text-sm text-gray-500 dark:text-gray-400 italic"
      >
        Impact non estimé
        <span v-if="result.carbon_impact.degraded_reason">
          ({{ result.carbon_impact.degraded_reason }})
        </span>
      </p>
    </section>

    <!-- Timeline -->
    <section>
      <h4 class="text-sm font-semibold mb-2 text-surface-text dark:text-surface-dark-text">
        Timeline ({{ totalWeeksMax }} semaines max)
      </h4>
      <ol class="space-y-2 text-sm">
        <li
          v-for="step in result.timeline"
          :key="step.step_id"
          class="flex items-center justify-between"
        >
          <span class="text-gray-700 dark:text-gray-300 flex items-center">
            {{ step.label_fr }}
            <SourceLink
              v-if="step.source_id"
              :source-id="step.source_id"
              @open="(id) => emit('open-source', id)"
            />
          </span>
          <span
            v-if="step.weeks_min !== null && step.weeks_max !== null"
            class="font-medium text-surface-text dark:text-surface-dark-text"
          >
            {{ step.weeks_min }}-{{ step.weeks_max }} sem.
          </span>
          <span
            v-else
            class="text-xs text-gray-500 dark:text-gray-400 italic"
          >
            Délai non disponible
          </span>
        </li>
      </ol>
    </section>
  </article>
</template>
