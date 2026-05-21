<script setup lang="ts">
// F25 — Onglets ARIA `tablist` du catalogue admin avec compteurs.
// Navigation clavier (flèches gauche/droite) supportée pour conformité WAI-ARIA.
import { computed, nextTick, ref } from 'vue'
import type { CatalogSummary, CatalogTab } from '~/types/adminCatalog'

interface Props {
  modelValue: CatalogTab
  summary: CatalogSummary | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), { loading: false })

const emit = defineEmits<{
  (event: 'update:modelValue', value: CatalogTab): void
}>()

const tabs: ReadonlyArray<{ key: CatalogTab; label: string }> = [
  { key: 'funds', label: 'Fonds' },
  { key: 'intermediaries', label: 'Intermédiaires' },
  { key: 'offers', label: 'Offres' },
  { key: 'fund_intermediaries', label: 'Liaisons fonds × intermédiaires' },
]

const tabRefs = ref<Record<CatalogTab, HTMLButtonElement | null>>({
  funds: null,
  intermediaries: null,
  offers: null,
  fund_intermediaries: null,
})

function setTabRef(key: CatalogTab, el: Element | null) {
  tabRefs.value[key] = (el as HTMLButtonElement) ?? null
}

function totalForTab(key: CatalogTab): number | null {
  if (!props.summary) return null
  if (key === 'fund_intermediaries') return props.summary.fund_intermediaries.total
  return props.summary[key].total
}

function select(tab: CatalogTab) {
  emit('update:modelValue', tab)
}

async function onKeydown(event: KeyboardEvent, currentTab: CatalogTab) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  const index = tabs.findIndex((t) => t.key === currentTab)
  if (index < 0) return
  const next =
    event.key === 'ArrowRight'
      ? tabs[(index + 1) % tabs.length]
      : tabs[(index - 1 + tabs.length) % tabs.length]
  select(next.key)
  await nextTick()
  tabRefs.value[next.key]?.focus()
}
</script>

<template>
  <div role="tablist" aria-label="Catalogue admin" class="flex flex-wrap gap-1 border-b border-gray-200 dark:border-dark-border">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      :ref="(el) => setTabRef(tab.key, el)"
      type="button"
      role="tab"
      :aria-selected="modelValue === tab.key"
      :tabindex="modelValue === tab.key ? 0 : -1"
      :class="[
        'inline-flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-dark-card',
        modelValue === tab.key
          ? 'border-red-700 dark:border-red-400 text-red-800 dark:text-red-200'
          : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-surface-text dark:hover:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover',
      ]"
      @click="select(tab.key)"
      @keydown="onKeydown($event, tab.key)"
    >
      <span>{{ tab.label }}</span>
      <span
        v-if="totalForTab(tab.key) !== null"
        :class="[
          'inline-flex items-center justify-center min-w-[1.75rem] rounded-full px-2 py-0.5 text-xs font-semibold',
          modelValue === tab.key
            ? 'bg-red-700 text-white dark:bg-red-300 dark:text-red-950'
            : 'bg-gray-100 dark:bg-dark-hover text-gray-700 dark:text-gray-300',
        ]"
        :aria-label="`${totalForTab(tab.key)} éléments`"
      >
        {{ totalForTab(tab.key) }}
      </span>
      <span
        v-else-if="loading"
        class="inline-block h-3 w-6 rounded bg-gray-200 dark:bg-dark-hover animate-pulse"
        aria-hidden="true"
      />
    </button>
  </div>
</template>
