<script setup lang="ts">
// F09 PRIO 3 — Création constante simulateur.
import { ref } from 'vue'
import SimpleEntityForm, { type FieldDef } from '~/components/admin/forms/SimpleEntityForm.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const { createEntity } = useAdminCatalog('simulation_factor')
const router = useRouter()
const loading = ref(false)
const error = ref('')

const fields: FieldDef[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, placeholder: 'TAUX_BCEAO' },
  { key: 'label', label: 'Libellé', type: 'text', required: true },
  { key: 'value', label: 'Valeur', type: 'number', required: true },
  { key: 'unit', label: 'Unité', type: 'text', required: true, placeholder: '%' },
  { key: 'scope', label: 'Scope', type: 'text', required: true, placeholder: 'credit' },
  {
    key: 'status',
    label: 'Statut métier',
    type: 'select',
    required: true,
    options: [
      { value: 'pending', label: 'Pending (sans source)' },
      { value: 'verified', label: 'Verified (avec source)' },
    ],
    helpText: 'Verified requiert source_id. Pending requiert source_id=null.',
  },
  {
    key: 'source_id',
    label: 'UUID source (si verified)',
    type: 'text',
    required: false,
  },
]

async function onSubmit(values: Record<string, unknown>) {
  loading.value = true
  error.value = ''
  try {
    if (values.status === 'pending') values.source_id = null
    const created = await createEntity(values)
    router.push(`/admin/simulation-factors/${(created as { id: string }).id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="px-6 py-8 max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold mb-6 text-surface-text dark:text-surface-dark-text">
      Nouvelle constante simulateur
    </h1>
    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <SimpleEntityForm
      :fields="fields"
      submit-label="Créer la constante"
      :loading="loading"
      @submit="onSubmit"
      @cancel="router.push('/admin/simulation-factors')"
    />
  </div>
</template>
