<script setup lang="ts">
import type { Offer } from '~/types/financing'

interface Props {
  offer: Offer
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'compare', fundId: string): void
  (e: 'apply', offerId: string): void
}>()

function handleCompare(fundId: string): void {
  emit('compare', fundId)
}

function handleApply(offerId: string): void {
  emit('apply', offerId)
}
</script>

<template>
  <article class="space-y-6">
    <header class="space-y-3">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        {{ offer.name }}
      </h1>
      <div class="flex flex-wrap items-center gap-2">
        <span
          v-for="lang in offer.accepted_languages"
          :key="lang"
          class="inline-flex items-center rounded-full bg-blue-100 dark:bg-blue-900/30 px-3 py-1 text-sm font-medium text-blue-700 dark:text-blue-300"
        >
          Langue : {{ lang }}
        </span>
        <span
          class="inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-3 py-1 text-sm font-medium text-emerald-700 dark:text-emerald-300"
        >
          Statut : {{ offer.publication_status === 'published' ? 'Publiée' : 'Brouillon' }}
        </span>
      </div>
    </header>

    <section
      v-if="offer.fund"
      class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5"
    >
      <h2 class="mb-3 text-lg font-semibold text-gray-900 dark:text-white">
        Fonds source
      </h2>
      <div class="space-y-1">
        <p class="text-base font-medium text-gray-900 dark:text-white">
          {{ offer.fund.name }}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          {{ offer.fund.organization }}
        </p>
        <NuxtLink
          v-if="offer.fund_id"
          :to="`/financing/funds/${offer.fund_id}`"
          class="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
        >
          Voir le fonds source →
        </NuxtLink>
      </div>
    </section>

    <section
      v-if="offer.intermediary"
      class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5"
    >
      <h2 class="mb-3 text-lg font-semibold text-gray-900 dark:text-white">
        Intermédiaire
      </h2>
      <div class="space-y-1">
        <p class="text-base font-medium text-gray-900 dark:text-white">
          {{ offer.intermediary.name }}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          {{ offer.intermediary.country }}
        </p>
        <NuxtLink
          v-if="offer.intermediary_id"
          :to="`/financing/intermediaries/${offer.intermediary_id}`"
          class="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
        >
          Voir l'intermédiaire →
        </NuxtLink>
      </div>
    </section>

    <section
      class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5"
    >
      <EffectiveCriteriaList :criteria="offer.effective_criteria" />
    </section>

    <section
      class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5"
    >
      <EffectiveDocumentsList :documents="offer.effective_required_documents" />
    </section>

    <section
      class="rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-5"
    >
      <EffectiveFees :fees="offer.effective_fees" />
    </section>

    <section
      v-if="offer.notes"
      class="rounded-xl border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-5"
    >
      <h2 class="mb-2 text-lg font-semibold text-amber-800 dark:text-amber-300">
        Notes
      </h2>
      <p class="text-sm text-amber-700 dark:text-amber-200 whitespace-pre-line">
        {{ offer.notes }}
      </p>
    </section>

    <footer class="flex flex-wrap gap-3">
      <button
        type="button"
        class="inline-flex items-center justify-center rounded-lg bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition focus:outline-none focus:ring-2 focus:ring-blue-500"
        :aria-label="`Comparer avec autres offres pour ce fonds`"
        @click="handleCompare(offer.fund_id)"
      >
        Comparer avec autres offres pour ce fonds
      </button>
      <button
        type="button"
        class="inline-flex items-center justify-center rounded-lg bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition focus:outline-none focus:ring-2 focus:ring-emerald-500"
        :aria-label="`Candidater à cette offre`"
        @click="handleApply(offer.id)"
      >
        Candidater
      </button>
    </footer>
  </article>
</template>
