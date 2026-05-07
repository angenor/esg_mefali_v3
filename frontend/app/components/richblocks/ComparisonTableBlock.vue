<script setup lang="ts">
// F11 — ComparisonTableBlock : tableau comparatif typé 2-5 sujets.
// Formate cellules par type (money/percentage/duration/rating/boolean),
// highlight winner par row, sources cliquables, responsive (cartes < 768px).

import { computed } from 'vue'
import { useCurrency } from '~/composables/useCurrency'
import SourceLink from '~/components/sources/SourceLink.vue'
import type {
  ComparisonRowProps,
  ComparisonTableBlockProps,
  ComparisonValueProps,
} from '~/types/richblocks'

const props = defineProps<ComparisonTableBlockProps>()

const emit = defineEmits<{
  navigate: [url: string]
  'open-source': [sourceId: string]
}>()

const { format } = useCurrency()

// Parser une duration "12 mois" / "45 jours" en jours pour comparaison.
function parseDurationDays(value: string | number): number | null {
  if (typeof value === 'number') return value
  const match = value.match(/(\d+(?:[.,]\d+)?)\s*(jour|jours|mois|semaine|semaines|an|ans)/i)
  if (!match) return null
  const num = Number.parseFloat((match[1] ?? '').replace(',', '.'))
  if (!Number.isFinite(num)) return null
  const unit = (match[2] ?? '').toLowerCase()
  if (unit.startsWith('jour')) return num
  if (unit.startsWith('semaine')) return num * 7
  if (unit.startsWith('mois')) return num * 30
  if (unit.startsWith('an')) return num * 365
  return null
}

function parsePercentage(value: string | number): number | null {
  if (typeof value === 'number') return value
  const match = value.match(/(\d+(?:[.,]\d+)?)\s*%/)
  if (match) return Number.parseFloat((match[1] ?? '').replace(',', '.'))
  const direct = Number.parseFloat(value.replace(',', '.'))
  return Number.isFinite(direct) ? direct : null
}

function parseMoney(v: ComparisonValueProps): number | null {
  if (v.money) {
    const amt = Number.parseFloat(v.money.amount)
    return Number.isFinite(amt) ? amt : null
  }
  if (typeof v.value === 'number') return v.value
  const direct = Number.parseFloat(String(v.value).replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(direct) ? direct : null
}

function parseRating(value: string | number): number | null {
  if (typeof value === 'number') return value
  const match = value.match(/(\d+(?:[.,]\d+)?)\s*\/?\s*\d*/)
  if (!match) return null
  return Number.parseFloat((match[1] ?? '').replace(',', '.'))
}

function getNumericValue(row: ComparisonRowProps, val: ComparisonValueProps): number | null {
  switch (row.type) {
    case 'money':
      return parseMoney(val)
    case 'percentage':
      return parsePercentage(val.value)
    case 'duration':
      return parseDurationDays(val.value)
    case 'rating':
      return parseRating(val.value)
    case 'boolean': {
      const n = typeof val.value === 'number' ? val.value : Number.parseFloat(String(val.value))
      return Number.isFinite(n) ? n : null
    }
    default:
      return null
  }
}

// Calculer pour chaque row l'index de la cellule gagnante
const winnerIndices = computed<(number | null)[]>(() => {
  if (!props.highlightWinner) {
    return props.rows.map(() => null)
  }
  return props.rows.map((row) => {
    if (row.type === 'text' || row.type === 'boolean') {
      // Pas de comparaison numérique pour text ; pour boolean on accepte True > False
      if (row.type === 'boolean') {
        const nums = row.values.map((v) => getNumericValue(row, v))
        const validNums = nums.filter((n): n is number => n !== null)
        if (validNums.length === 0) return null
        const target = row.higherIsBetter ? Math.max(...validNums) : Math.min(...validNums)
        return nums.findIndex((n) => n === target)
      }
      return null
    }
    const nums = row.values.map((v) => getNumericValue(row, v))
    const validNums = nums.filter((n): n is number => n !== null)
    if (validNums.length === 0) return null
    const target = row.higherIsBetter ? Math.max(...validNums) : Math.min(...validNums)
    return nums.findIndex((n) => n === target)
  })
})

function formatValue(row: ComparisonRowProps, val: ComparisonValueProps): string {
  switch (row.type) {
    case 'money':
      return val.money ? format(val.money) : String(val.value)
    case 'percentage': {
      const n = parsePercentage(val.value)
      if (n != null) return `${n} %`
      return String(val.value)
    }
    case 'duration':
      return String(val.value)
    case 'rating': {
      const n = parseRating(val.value)
      return n != null ? `${n}/5` : String(val.value)
    }
    case 'boolean': {
      const n = typeof val.value === 'number' ? val.value : Number.parseFloat(String(val.value))
      return n > 0 ? '✓' : '✗'
    }
    default:
      return String(val.value)
  }
}

function handleHeaderClick(subjectId: string) {
  const subject = props.subjects.find((s) => s.id === subjectId)
  if (subject?.drilldownUrl) {
    emit('navigate', subject.drilldownUrl)
  }
}

function handleSourceClick(sid: string) {
  emit('open-source', sid)
}
</script>

<template>
  <div class="comparison-table-block my-3 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4">
    <h3
      v-if="title"
      class="text-sm font-semibold text-gray-900 dark:text-surface-dark-text mb-3"
    >
      {{ title }}
    </h3>

    <!-- Vue desktop : table classique (md+) -->
    <div class="hidden md:block overflow-x-auto">
      <table
        class="w-full border-collapse"
        :aria-label="title"
        role="table"
      >
        <caption class="sr-only">{{ title }}</caption>
        <thead>
          <tr class="border-b border-gray-200 dark:border-dark-border">
            <th
              class="text-left text-xs font-medium text-gray-600 dark:text-gray-400 px-2 py-2"
              scope="col"
            >
              Critère
            </th>
            <th
              v-for="subj in subjects"
              :key="subj.id"
              scope="col"
              class="text-left px-2 py-2"
            >
              <button
                v-if="subj.drilldownUrl"
                type="button"
                :data-test="`comparison-header-${subj.id}`"
                class="text-xs font-semibold text-gray-900 dark:text-surface-dark-text hover:text-emerald-700 dark:hover:text-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded"
                @click="handleHeaderClick(subj.id)"
              >
                {{ subj.label }}
                <span v-if="subj.sublabel" class="block text-xs font-normal text-gray-500 dark:text-gray-400">
                  {{ subj.sublabel }}
                </span>
              </button>
              <div v-else>
                <span class="text-xs font-semibold text-gray-900 dark:text-surface-dark-text">
                  {{ subj.label }}
                </span>
                <span v-if="subj.sublabel" class="block text-xs font-normal text-gray-500 dark:text-gray-400">
                  {{ subj.sublabel }}
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, rowIdx) in rows"
            :key="rowIdx"
            class="border-b border-gray-100 dark:border-dark-border/50"
          >
            <td class="px-2 py-2 text-xs text-gray-700 dark:text-gray-300">
              {{ row.label }}
            </td>
            <td
              v-for="(val, valIdx) in row.values"
              :key="valIdx"
              class="px-2 py-2 text-sm text-gray-900 dark:text-surface-dark-text relative"
              :class="{
                'bg-emerald-50 dark:bg-emerald-900/20 font-semibold winner': winnerIndices[rowIdx] === valIdx,
              }"
              :data-winner="winnerIndices[rowIdx] === valIdx ? 'true' : 'false'"
            >
              <span>{{ formatValue(row, val) }}</span>
              <span
                v-if="val.annotation"
                class="block text-xs text-gray-500 dark:text-gray-400"
              >
                {{ val.annotation }}
              </span>
              <SourceLink
                v-if="val.sourceId"
                :source-id="val.sourceId"
                aria-label="Voir la source de cette cellule"
                @open="handleSourceClick"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Vue mobile : cartes verticales (< 768px) -->
    <div class="md:hidden space-y-3">
      <div
        v-for="subj in subjects"
        :key="subj.id"
        class="rounded-lg border border-gray-200 dark:border-dark-border p-3"
      >
        <p class="text-sm font-semibold text-gray-900 dark:text-surface-dark-text mb-2">
          {{ subj.label }}
          <span v-if="subj.sublabel" class="text-xs font-normal text-gray-500 dark:text-gray-400">
            ({{ subj.sublabel }})
          </span>
        </p>
        <dl class="space-y-1">
          <div
            v-for="(row, rowIdx) in rows"
            :key="rowIdx"
            class="flex justify-between gap-2 text-xs"
          >
            <dt class="text-gray-500 dark:text-gray-400">{{ row.label }}</dt>
            <dd
              class="text-gray-900 dark:text-surface-dark-text"
              :class="{
                'text-emerald-700 dark:text-emerald-300 font-semibold': winnerIndices[rowIdx] !== null && row.values[winnerIndices[rowIdx] as number]?.subjectId === subj.id,
              }"
            >
              {{ formatValue(row, row.values.find((v) => v.subjectId === subj.id)!) }}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  </div>
</template>
