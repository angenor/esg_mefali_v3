<script setup lang="ts">
// F23 — Formulaire 8 onglets pour création/édition d'une Skill.
import { computed, ref, watch } from 'vue'
import type { ActivationRules, GoldenExample, SkillCreate, SkillDomain, SkillRead, SkillUpdate } from '~/types/skills'
import ActivationRulesEditor from './ActivationRulesEditor.vue'
import GoldenExamplesEditor from './GoldenExamplesEditor.vue'
import SourceMultiPicker from './SourceMultiPicker.vue'
import ToolWhitelistPicker from './ToolWhitelistPicker.vue'

const props = defineProps<{
  initial?: SkillRead | null
  mode: 'create' | 'edit'
}>()

const emit = defineEmits<{
  (e: 'submit', payload: SkillCreate | SkillUpdate): void
}>()

const TABS = [
  { key: 'identite', label: 'Identité' },
  { key: 'prompt', label: 'Prompt expert' },
  { key: 'procedure', label: 'Procédure' },
  { key: 'tools', label: 'Tools' },
  { key: 'sources', label: 'Sources' },
  { key: 'activation', label: 'Activation' },
  { key: 'golden', label: 'Golden examples' },
] as const

const activeTab = ref<typeof TABS[number]['key']>('identite')

const form = ref({
  name: props.initial?.name ?? '',
  domain: (props.initial?.domain ?? 'diagnostic_esg') as SkillDomain,
  prompt_expert: props.initial?.prompt_expert ?? '',
  procedure: props.initial?.procedure ?? '',
  tool_whitelist: props.initial?.tool_whitelist ?? [],
  sources: props.initial?.sources ?? [],
  activation_rules: (props.initial?.activation_rules as ActivationRules) ?? {
    page_slugs: [],
    intent_keywords: [],
    active_module: [],
    offer_id: null,
    fund_id: null,
    intermediary_id: null,
  },
  golden_examples: (props.initial?.golden_examples as GoldenExample[]) ?? [],
})

watch(
  () => props.initial,
  (v) => {
    if (!v) return
    form.value = {
      name: v.name,
      domain: v.domain as SkillDomain,
      prompt_expert: v.prompt_expert,
      procedure: v.procedure,
      tool_whitelist: v.tool_whitelist,
      sources: v.sources,
      activation_rules: v.activation_rules,
      golden_examples: v.golden_examples,
    }
  },
)

// Compteur de tokens approximatif (1 token ≈ 4 caractères pour cl100k_base).
const promptTokensApprox = computed(() =>
  Math.ceil(form.value.prompt_expert.length / 4),
)
const procedureTokensApprox = computed(() =>
  Math.ceil(form.value.procedure.length / 4),
)

function onSubmit() {
  if (props.mode === 'create') {
    emit('submit', { ...form.value } as SkillCreate)
  } else {
    // Edit: on envoie le payload complet (sans name qui est immuable).
    const { name: _name, ...rest } = form.value
    emit('submit', rest as SkillUpdate)
  }
}
</script>

<template>
  <form
    class="bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-dark-border"
    @submit.prevent="onSubmit"
  >
    <!-- Tabs -->
    <div class="border-b border-gray-200 dark:border-dark-border flex flex-wrap gap-2 p-2">
      <button
        v-for="t in TABS"
        :key="t.key"
        type="button"
        :class="[
          'px-3 py-1.5 rounded text-sm',
          activeTab === t.key
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-dark-hover text-surface-text dark:text-surface-dark-text',
        ]"
        @click="activeTab = t.key"
      >
        {{ t.label }}
      </button>
    </div>

    <div class="p-4 space-y-3">
      <!-- Identité -->
      <div v-if="activeTab === 'identite'" class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
            Nom (skill_xxx)
          </label>
          <input
            v-model="form.name"
            type="text"
            :disabled="mode === 'edit'"
            placeholder="skill_dossier_gcf_via_boad"
            class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text disabled:opacity-50"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1">
            Domaine
          </label>
          <select
            v-model="form.domain"
            class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
          >
            <option value="diagnostic_esg">Diagnostic ESG</option>
            <option value="scoring_referentiel">Scoring référentiel</option>
            <option value="carbon_calc">Calcul carbone</option>
            <option value="dossier">Dossier</option>
            <option value="intermediaire">Intermédiaire</option>
            <option value="attestation">Attestation</option>
            <option value="credit_score">Score crédit</option>
          </select>
        </div>
      </div>

      <!-- Prompt expert -->
      <div v-if="activeTab === 'prompt'" class="space-y-2">
        <div class="flex items-center justify-between">
          <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text">
            Prompt expert (≤ 5000 tokens)
          </label>
          <span
            :class="[
              'text-xs',
              promptTokensApprox > 5000 ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400',
            ]"
          >
            ~{{ promptTokensApprox }} tokens
          </span>
        </div>
        <textarea
          v-model="form.prompt_expert"
          rows="12"
          class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text font-mono text-sm"
        ></textarea>
      </div>

      <!-- Procédure -->
      <div v-if="activeTab === 'procedure'" class="space-y-2">
        <div class="flex items-center justify-between">
          <label class="block text-sm font-medium text-surface-text dark:text-surface-dark-text">
            Procédure (≤ 3000 tokens)
          </label>
          <span
            :class="[
              'text-xs',
              procedureTokensApprox > 3000 ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400',
            ]"
          >
            ~{{ procedureTokensApprox }} tokens
          </span>
        </div>
        <textarea
          v-model="form.procedure"
          rows="10"
          class="w-full px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text font-mono text-sm"
        ></textarea>
      </div>

      <!-- Tools -->
      <div v-if="activeTab === 'tools'">
        <ToolWhitelistPicker v-model="form.tool_whitelist" />
      </div>

      <!-- Sources -->
      <div v-if="activeTab === 'sources'">
        <SourceMultiPicker v-model="form.sources" />
      </div>

      <!-- Activation rules -->
      <div v-if="activeTab === 'activation'">
        <ActivationRulesEditor v-model="form.activation_rules" />
      </div>

      <!-- Golden examples -->
      <div v-if="activeTab === 'golden'">
        <GoldenExamplesEditor
          v-model="form.golden_examples"
          :category="form.domain"
        />
      </div>
    </div>

    <div class="border-t border-gray-200 dark:border-dark-border p-4 flex justify-end gap-2">
      <button
        type="submit"
        class="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm"
      >
        {{ mode === 'create' ? 'Créer la skill' : 'Sauvegarder' }}
      </button>
    </div>
  </form>
</template>
