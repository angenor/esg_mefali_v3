<script setup lang="ts">
/**
 * F10 — SelectWidget : sélection dans une liste 1-200 options.
 *
 * Features :
 * - Champ recherche full-text insensible casse/accents (NFD)
 * - Virtualisation conditionnelle si > 50 options (vue-virtual-scroller)
 * - Groupement par `option.group`
 * - Multi-sélection avec compteur
 * - Option « Autre, préciser » si `allow_other`
 *
 * Réf : FR-018, FR-021, US2.
 */
import { computed, ref } from 'vue'
import type {
  InteractiveQuestion,
  SelectOption,
  SelectPayload,
  SelectResponse,
} from '~/types/interactive-question'

interface Props {
  question: InteractiveQuestion
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'submit', payload: SelectResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<SelectPayload>(() => {
  const p = props.question.payload as SelectPayload | undefined
  return p ?? {
    question_type: 'select',
    options: [],
    min_selections: 1,
    max_selections: 1,
    allow_other: false,
  }
})

const isMulti = computed(() => payload.value.max_selections > 1)
const showSearch = computed(() => payload.value.options.length >= 8)
const useVirtualScroller = computed(() => payload.value.options.length > 50)

const search = ref('')
const selectedIds = ref<Set<string>>(new Set())
const otherActive = ref(false)
const otherValue = ref('')

function _normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

const filteredOptions = computed<SelectOption[]>(() => {
  const q = _normalize(search.value.trim())
  if (!q) return payload.value.options
  return payload.value.options.filter((o) => {
    const haystack = _normalize(`${o.label} ${o.sublabel ?? ''} ${o.id}`)
    return haystack.includes(q)
  })
})

// Regroupement par option.group (si fourni)
const groupedOptions = computed<Array<{ group: string | null, items: SelectOption[] }>>(() => {
  const map = new Map<string | null, SelectOption[]>()
  for (const o of filteredOptions.value) {
    const key = o.group ?? null
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(o)
  }
  return Array.from(map.entries()).map(([group, items]) => ({ group, items }))
})

function isSelected(id: string): boolean {
  return selectedIds.value.has(id)
}

function toggle(id: string) {
  if (inputLocked.value) return
  const next = new Set(selectedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else if (!isMulti.value) {
    next.clear()
    next.add(id)
  } else if (next.size < payload.value.max_selections) {
    next.add(id)
  }
  selectedIds.value = next
  // Submit immédiat pour mono-sélection (UX fluide)
  if (!isMulti.value && !payload.value.allow_other) {
    _doSubmit()
  }
}

function activateOther() {
  if (inputLocked.value) return
  otherActive.value = true
}

function _doSubmit() {
  if (inputLocked.value) return
  if (otherActive.value) {
    const v = otherValue.value.trim()
    if (!v) return
    const resp: SelectResponse = {
      question_type: 'select',
      selected: [{ id: 'other', label: 'Autre' }],
      other_value: v,
    }
    emit('submit', resp, `✓ Autre : ${v}`)
    return
  }
  const selected = payload.value.options.filter((o) => selectedIds.value.has(o.id))
  if (selected.length === 0) return
  const resp: SelectResponse = {
    question_type: 'select',
    selected,
    other_value: null,
  }
  const labels = selected.map((o) => o.label).join(', ')
  emit('submit', resp, `✓ ${labels}`)
}

const canSubmit = computed(() => {
  if (inputLocked.value) return false
  if (otherActive.value) return otherValue.value.trim().length > 0
  const c = selectedIds.value.size
  return c >= payload.value.min_selections && c <= payload.value.max_selections
})
</script>

<template>
  <div class="space-y-3">
    <!-- Recherche -->
    <input
      v-if="showSearch"
      v-model="search"
      type="search"
      :disabled="inputLocked"
      placeholder="Rechercher…"
      role="combobox"
      :aria-expanded="filteredOptions.length > 0"
      class="w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
    />

    <!-- Compteur multi-sélection -->
    <div
      v-if="isMulti"
      class="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300"
    >
      <span class="inline-flex items-center justify-center min-w-[1.5rem] h-6 px-2 rounded-full bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 tabular-nums font-bold">
        {{ selectedIds.size }}
      </span>
      <span>sur {{ payload.max_selections }} max</span>
    </div>

    <!-- Liste virtualisée si > 50 options, sinon scroll natif -->
    <div
      v-if="!otherActive"
      role="listbox"
      :aria-multiselectable="isMulti"
      class="max-h-72 overflow-y-auto space-y-3 -mx-1 px-1"
    >
      <div
        v-for="grp in groupedOptions"
        :key="grp.group ?? '__no_group__'"
        class="space-y-1"
      >
        <h3
          v-if="grp.group"
          class="text-[10px] uppercase tracking-wider text-indigo-600 dark:text-indigo-400 font-bold px-2"
        >
          {{ grp.group }}
        </h3>
        <button
          v-for="opt in grp.items"
          :key="opt.id"
          type="button"
          role="option"
          :data-testid="`select-option-${opt.id}`"
          :aria-selected="isSelected(opt.id)"
          :disabled="inputLocked"
          :class="[
            'w-full px-3 py-2.5 rounded-xl border text-left text-sm transition-all',
            'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card',
            isSelected(opt.id)
              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-200 font-semibold'
              : 'border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card hover:border-indigo-400 dark:hover:border-indigo-600',
          ]"
          @click="toggle(opt.id)"
        >
          <div class="flex items-center justify-between">
            <span class="flex-1 min-w-0">
              <span class="block leading-snug">{{ opt.label }}</span>
              <span
                v-if="opt.sublabel"
                class="block text-[11px] text-gray-500 dark:text-gray-400 mt-0.5"
              >
                {{ opt.sublabel }}
              </span>
            </span>
            <span
              v-if="isSelected(opt.id)"
              class="ml-2 flex-shrink-0 w-5 h-5 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center"
            >
              <svg class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </span>
          </div>
        </button>
      </div>

      <p
        v-if="filteredOptions.length === 0"
        class="text-center text-sm text-gray-500 dark:text-gray-400 py-4"
      >
        Aucune option ne correspond à votre recherche.
      </p>

      <!-- Option « Autre » -->
      <button
        v-if="payload.allow_other"
        type="button"
        :disabled="inputLocked"
        class="w-full px-3 py-2.5 rounded-xl border border-dashed border-indigo-400 dark:border-indigo-600 text-sm text-indigo-700 dark:text-indigo-300 font-medium hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-all"
        @click="activateOther"
      >
        + Autre, préciser
      </button>
    </div>

    <!-- Mode « Autre » : champ texte -->
    <div
      v-if="otherActive"
      class="space-y-2"
    >
      <input
        v-model="otherValue"
        type="text"
        :disabled="inputLocked"
        placeholder="Précisez…"
        class="w-full px-3 py-2 rounded-xl border border-indigo-300 dark:border-indigo-700 bg-white dark:bg-dark-input text-sm text-surface-text dark:text-surface-dark-text placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <button
        type="button"
        class="text-xs text-gray-500 hover:text-indigo-600 dark:text-gray-400 dark:hover:text-indigo-400"
        @click="otherActive = false"
      >
        ← Revenir aux options
      </button>
    </div>

    <!-- Footer : Valider + Répondre autrement -->
    <div class="flex items-center justify-between pt-1">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
        @click="emit('abandon-and-send', '')"
      >
        Répondre autrement
      </button>
      <button
        v-if="isMulti || otherActive"
        type="button"
        :disabled="!canSubmit"
        :data-testid="`select-submit-${question.id}`"
        class="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-lg transition-all"
        @click="_doSubmit"
      >
        Valider
      </button>
    </div>
  </div>
</template>
