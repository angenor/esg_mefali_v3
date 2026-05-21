<script setup lang="ts">
// F25 — Fiche détaillée d'une liaison fonds × intermédiaire.
// Affiche paire (avec liens NuxtLink vers fiches respectives), bornes
// d'accréditation, plafond Money + source F01 si présente.
// MoneyDisplay, SourceLink, SuccessorBanner auto-importés (Nuxt pathPrefix: false).
import CatalogIncoherenceBadge from './CatalogIncoherenceBadge.vue'
import SuccessorBanner from './SuccessorBanner.vue'
import type { FundIntermediaryDetail } from '~/types/adminCatalog'

interface Props {
  detail: FundIntermediaryDetail
}

defineProps<Props>()

function formatDate(value: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleDateString('fr-FR')
  } catch {
    return value
  }
}
</script>

<template>
  <article
    class="space-y-6 rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-6"
  >
    <header class="flex flex-wrap items-start gap-3 justify-between">
      <div>
        <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text">
          {{ detail.fund_name }}
          <span class="text-gray-400 dark:text-gray-500">×</span>
          {{ detail.intermediary_name }}
        </h2>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 font-mono">{{ detail.id }}</p>
      </div>
      <div class="flex items-center gap-2">
        <span
          v-if="detail.is_active"
          class="inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/40 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:text-emerald-200 ring-1 ring-emerald-300 dark:ring-emerald-700"
        >
          Accréditation active
        </span>
        <span
          v-else
          class="inline-flex items-center rounded-full bg-rose-100 dark:bg-rose-900/40 px-2 py-0.5 text-xs font-medium text-rose-800 dark:text-rose-200 ring-1 ring-rose-300 dark:ring-rose-700"
        >
          Accréditation expirée
        </span>
        <CatalogIncoherenceBadge v-if="detail.has_incoherence" />
      </div>
    </header>

    <SuccessorBanner
      v-if="detail.superseded_by"
      :successor-id="detail.superseded_by"
      base-path="/admin/catalog/fund-intermediaries"
      cta-label="Voir la liaison successeur"
      :current-version="detail.version ?? null"
    />

    <dl class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <dt class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Accréditation depuis</dt>
        <dd class="mt-1 text-sm text-surface-text dark:text-surface-dark-text">{{ formatDate(detail.accredited_from) }}</dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Accréditation jusqu'au</dt>
        <dd class="mt-1 text-sm text-surface-text dark:text-surface-dark-text">
          {{ detail.accredited_to ? formatDate(detail.accredited_to) : 'Sans terme' }}
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Plafond par fonds</dt>
        <dd class="mt-1 text-sm text-surface-text dark:text-surface-dark-text">
          <MoneyDisplay
            v-if="detail.max_amount_per_fund_money"
            :amount="detail.max_amount_per_fund_money.amount"
            :currency="detail.max_amount_per_fund_money.currency"
            mode="both"
          />
          <span v-else class="text-gray-400 dark:text-gray-500">Non renseigné</span>
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Source d'accréditation</dt>
        <dd class="mt-1 text-sm">
          <SourceLink
            v-if="detail.accreditation_source"
            :source-id="detail.accreditation_source.id"
            :title="detail.accreditation_source.title ?? 'Source'"
          />
          <span v-else class="text-gray-400 dark:text-gray-500">Aucune source attachée</span>
        </dd>
      </div>
    </dl>

    <footer class="flex flex-wrap items-center gap-3 border-t border-gray-200 dark:border-dark-border pt-4">
      <NuxtLink
        :to="detail.fund_link"
        class="rounded-md border border-gray-300 dark:border-dark-border px-3 py-2 text-sm font-medium text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
      >
        Voir le fonds
      </NuxtLink>
      <NuxtLink
        :to="detail.intermediary_link"
        class="rounded-md border border-gray-300 dark:border-dark-border px-3 py-2 text-sm font-medium text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
      >
        Voir l'intermédiaire
      </NuxtLink>
      <NuxtLink
        to="/admin/catalog?tab=fund_intermediaries"
        class="ml-auto text-sm text-red-700 dark:text-red-300 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
      >
        ← Retour au catalogue
      </NuxtLink>
    </footer>
  </article>
</template>
