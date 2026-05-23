<script setup lang="ts">
/**
 * F047 — Widget de réponse à un critère ESG-projet.
 * MVP : qcu yes/no/partial + champ source (XOR avec coche "non sourcée").
 */
import { computed, ref, watch } from 'vue'
import type {
  ProjectEsgCriterionResponseSavePayload,
  ResponseType,
} from '~/types/projectEsg'

interface CriterionLike {
  id: string
  code: string
  label: string
  is_required: boolean
}

interface Props {
  criterion: CriterionLike
  initial?: {
    response_value?: Record<string, unknown>
    source_id?: string | null
    unsourced?: boolean
  }
  disabled?: boolean
}
const props = defineProps<Props>()
const emit = defineEmits<{
  save: [payload: ProjectEsgCriterionResponseSavePayload]
}>()

const responseType = ref<ResponseType>('qcu')
const choice = ref<string>(
  (props.initial?.response_value?.choice as string) ?? '',
)
const sourceId = ref<string>(props.initial?.source_id ?? '')
const unsourced = ref<boolean>(props.initial?.unsourced ?? false)

// XOR : si on coche "non sourcée", on vide la source ; et inversement
watch(unsourced, (v) => {
  if (v) sourceId.value = ''
})
watch(sourceId, (v) => {
  if (v) unsourced.value = false
})

const xorValid = computed(
  () => (sourceId.value !== '' ) !== unsourced.value,
)
const canSave = computed(() => choice.value !== '' && xorValid.value)

function onSave() {
  if (!canSave.value) return
  emit('save', {
    criterion_id: props.criterion.id,
    response_type: responseType.value,
    response_value: { choice: choice.value },
    source_id: sourceId.value || null,
    unsourced: unsourced.value,
  })
}
</script>

<template>
  <section
    :aria-labelledby="`crit-${criterion.id}`"
    class="p-4 rounded-lg ring-1 ring-gray-200 dark:ring-dark-border bg-white dark:bg-dark-card"
  >
    <header class="flex items-start gap-2 mb-3">
      <span
        v-if="criterion.is_required"
        class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
        aria-label="Critère obligatoire"
      >
        Requis
      </span>
      <span class="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-500 mt-0.5">
        {{ criterion.code }}
      </span>
    </header>

    <h3
      :id="`crit-${criterion.id}`"
      class="text-sm font-medium text-surface-text dark:text-surface-dark-text mb-3"
    >
      {{ criterion.label }}
    </h3>

    <fieldset class="space-y-2 mb-4" :disabled="disabled">
      <legend class="sr-only">Réponse au critère</legend>
      <label
        v-for="opt in [
          { value: 'yes', label: 'Oui — mesure en place' },
          { value: 'partial', label: 'Partiellement' },
          { value: 'no', label: 'Non' },
        ]"
        :key="opt.value"
        class="flex items-center gap-2 cursor-pointer text-sm text-surface-text dark:text-surface-dark-text"
      >
        <input
          v-model="choice"
          type="radio"
          :name="`crit-${criterion.id}-choice`"
          :value="opt.value"
          class="text-emerald-600 focus:ring-emerald-500"
        />
        {{ opt.label }}
      </label>
    </fieldset>

    <div class="space-y-2 border-t border-gray-100 dark:border-dark-border pt-3">
      <label class="block text-xs font-medium text-gray-600 dark:text-gray-400">
        Source F01 (référence officielle)
      </label>
      <input
        v-model="sourceId"
        type="text"
        :disabled="disabled || unsourced"
        placeholder="UUID de la source citée"
        class="w-full px-3 py-1.5 text-sm rounded ring-1 ring-gray-200 dark:ring-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
      />
      <label class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
        <input
          v-model="unsourced"
          type="checkbox"
          :disabled="disabled"
          class="text-amber-600 focus:ring-amber-500"
        />
        Réponse non sourcée (à éviter — F01 exige une source)
      </label>
      <p
        v-if="!xorValid"
        class="text-xs text-red-600 dark:text-red-400"
        role="alert"
      >
        Choisissez soit une source, soit la case "non sourcée" (pas les deux,
        pas aucune).
      </p>
    </div>

    <div class="mt-4 flex justify-end">
      <button
        type="button"
        :disabled="!canSave || disabled"
        class="px-4 py-1.5 text-sm font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
        @click="onSave"
      >
        Enregistrer
      </button>
    </div>
  </section>
</template>
