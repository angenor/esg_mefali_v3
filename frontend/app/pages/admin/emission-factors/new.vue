<script setup lang="ts">
// F09 PRIO 3 — Création facteur d'émission.
import { ref } from 'vue'
import SimpleEntityForm, { type FieldDef } from '~/components/admin/forms/SimpleEntityForm.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const { createEntity } = useAdminCatalog('emission_factor')
const router = useRouter()
const loading = ref(false)
const error = ref('')

const fields: FieldDef[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, placeholder: 'electricity_ci_2024' },
  { key: 'label', label: 'Libellé', type: 'text', required: true },
  {
    key: 'category',
    label: 'Catégorie',
    type: 'select',
    required: true,
    options: [
      { value: 'energy', label: 'Énergie' },
      { value: 'transport', label: 'Transport' },
      { value: 'waste', label: 'Déchets' },
      { value: 'industrial', label: 'Industriel' },
      { value: 'agriculture', label: 'Agriculture' },
      { value: 'purchases', label: 'Achats' },
    ],
  },
  { key: 'country', label: 'Pays (ISO 2 ou global)', type: 'text', required: true, placeholder: 'CI' },
  { key: 'year', label: 'Année', type: 'number', required: true, min: 2000, max: 2100 },
  { key: 'value', label: 'Valeur', type: 'number', required: true, min: 0 },
  { key: 'unit', label: 'Unité', type: 'text', required: true, placeholder: 'kgCO2e/kWh' },
  { key: 'source_id', label: 'UUID source (ADEME, IPCC, IEA)', type: 'text', required: true },
]

async function onSubmit(values: Record<string, unknown>) {
  loading.value = true
  error.value = ''
  try {
    const created = await createEntity(values)
    router.push(`/admin/emission-factors/${(created as { id: string }).id}`)
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
      Nouveau facteur d'émission
    </h1>
    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <SimpleEntityForm
      :fields="fields"
      submit-label="Créer le facteur"
      :loading="loading"
      @submit="onSubmit"
      @cancel="router.push('/admin/emission-factors')"
    />
  </div>
</template>
