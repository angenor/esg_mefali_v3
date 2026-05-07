<script setup lang="ts">
// F11 — KPICardBlock : carte KPI typée pour un chiffre clé sourcé.
// Rendu inline dans le chat, supporte dark mode, source cliquable F01,
// drill-down navigation, ARIA accessibilité.

import { computed } from 'vue'
import { useCurrency } from '~/composables/useCurrency'
import SourceLink from '~/components/sources/SourceLink.vue'
import type { KPICardBlockProps } from '~/types/richblocks'

const props = defineProps<KPICardBlockProps>()

const emit = defineEmits<{
  navigate: [url: string]
  'open-source': [sourceId: string]
}>()

const { format } = useCurrency()

// Affichage de la valeur : valueMoney prioritaire si fourni
const displayValue = computed(() => {
  if (props.valueMoney) {
    return format(props.valueMoney)
  }
  return props.value
})

// Direction du delta (déduite si absente)
const direction = computed(() => {
  if (props.deltaDirection) return props.deltaDirection
  if (props.delta == null) return 'neutral'
  if (props.delta > 0) return 'up'
  if (props.delta < 0) return 'down'
  return 'neutral'
})

// Couleur du delta : deltaIsGood prioritaire ; sinon heuristique up=vert, down=rouge.
const deltaIsGood = computed(() => {
  if (props.deltaIsGood != null) return props.deltaIsGood
  // Heuristique : up = vert, down = rouge.
  return direction.value === 'up'
})

const deltaColorClass = computed(() => {
  if (props.delta == null) return ''
  return deltaIsGood.value
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-rose-600 dark:text-rose-400'
})

const deltaArrow = computed(() => {
  switch (direction.value) {
    case 'up': return '↑'
    case 'down': return '↓'
    default: return '→'
  }
})

const deltaText = computed(() => {
  if (props.delta == null) return ''
  const abs = Math.abs(props.delta)
  // Formater 12 → "12" ; 12.5 → "12,5" ; éviter "12.0"
  const txt = Number.isInteger(abs) ? String(abs) : abs.toFixed(1).replace('.', ',')
  return `${deltaArrow.value} ${txt}`
})

// Couleur de gradient selon `color`.
const colorClasses = computed(() => {
  const map: Record<string, string> = {
    emerald:
      'from-emerald-50 to-white dark:from-emerald-950/30 dark:to-dark-card border-emerald-200 dark:border-emerald-900/40',
    blue:
      'from-blue-50 to-white dark:from-blue-950/30 dark:to-dark-card border-blue-200 dark:border-blue-900/40',
    rose:
      'from-rose-50 to-white dark:from-rose-950/30 dark:to-dark-card border-rose-200 dark:border-rose-900/40',
    amber:
      'from-amber-50 to-white dark:from-amber-950/30 dark:to-dark-card border-amber-200 dark:border-amber-900/40',
    violet:
      'from-violet-50 to-white dark:from-violet-950/30 dark:to-dark-card border-violet-200 dark:border-violet-900/40',
  }
  return map[props.color] ?? map.emerald
})

const ariaLabel = computed(() => {
  const parts: string[] = ['KPI', `${props.title}`, `${displayValue.value}`]
  if (props.delta != null && props.deltaLabel) {
    parts.push(`${deltaText.value} ${props.deltaLabel}`)
  } else if (props.delta != null) {
    parts.push(deltaText.value)
  }
  return parts.join(', ')
})

function handleCardClick() {
  if (props.drilldownUrl) {
    emit('navigate', props.drilldownUrl)
  }
}

function handleSourceClick(sid: string) {
  emit('open-source', sid)
}
</script>

<template>
  <div
    data-test="kpi-card-root"
    class="kpi-card-block my-3 rounded-xl border bg-gradient-to-br p-4 transition-all duration-200"
    :class="[
      colorClasses,
      drilldownUrl ? 'cursor-pointer hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 dark:focus:ring-offset-dark-card' : '',
    ]"
    :tabindex="drilldownUrl ? 0 : undefined"
    :role="drilldownUrl ? 'link' : undefined"
    :aria-label="ariaLabel"
    @click="handleCardClick"
    @keydown.enter="handleCardClick"
    @keydown.space.prevent="handleCardClick"
  >
    <div class="flex items-start gap-3">
      <!-- Icône à gauche (placeholder visuel — heroicon name accepté) -->
      <div
        v-if="icon"
        class="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-lg bg-white/60 dark:bg-dark-card/40 text-gray-700 dark:text-gray-200"
        aria-hidden="true"
      >
        <!-- icône simplifiée : on affiche une lettre placeholder ; le SVG complet
             dépend du sous-set heroicons à intégrer en finalisation. -->
        <span class="text-xs font-semibold uppercase">{{ (icon ?? '').slice(0, 2) }}</span>
      </div>

      <div class="flex-1 min-w-0">
        <!-- Titre -->
        <p
          class="text-xs font-medium uppercase tracking-wide text-gray-600 dark:text-gray-400"
        >
          {{ title }}
        </p>

        <!-- Valeur principale -->
        <p
          class="mt-1 text-2xl font-bold text-gray-900 dark:text-surface-dark-text"
        >
          {{ displayValue }}
        </p>

        <!-- Delta -->
        <div
          v-if="delta != null"
          class="mt-1 flex items-center gap-1 text-sm font-medium"
          :class="deltaColorClass"
        >
          <span aria-hidden="true">{{ deltaText }}</span>
          <span v-if="deltaLabel" class="text-gray-500 dark:text-gray-400 font-normal">
            {{ deltaLabel }}
          </span>
        </div>
      </div>

      <!-- Picto Source (F01) -->
      <div
        v-if="sourceId"
        class="flex-shrink-0 self-end"
        @click.stop
      >
        <SourceLink
          :source-id="sourceId"
          aria-label="Voir la source de ce KPI"
          @open="handleSourceClick"
        />
      </div>
    </div>
  </div>
</template>
