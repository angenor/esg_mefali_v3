<script setup lang="ts">
// F09 PRIO 3 — Création d'un critère logique.
import { ref } from 'vue'
import SimpleEntityForm, { type FieldDef } from '~/components/admin/forms/SimpleEntityForm.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const { createEntity } = useAdminCatalog('criterion')
const router = useRouter()
const loading = ref(false)
const error = ref('')

const fields: FieldDef[] = [
  { key: 'code', label: 'Code', type: 'text', required: true },
  { key: 'label', label: 'Libellé', type: 'text', required: true },
  {
    key: 'expression',
    label: 'Expression logique (JSON)',
    type: 'json',
    required: true,
    helpText: 'Ex : {"op": "gt", "lhs": "indicator.E1", "rhs": 50}',
    rows: 6,
  },
  { key: 'source_id', label: 'UUID source', type: 'text', required: true },
]

async function onSubmit(values: Record<string, unknown>) {
  loading.value = true
  error.value = ''
  try {
    const created = await createEntity(values)
    router.push(`/admin/criteria/${(created as { id: string }).id}`)
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
      Nouveau critère
    </h1>
    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <SimpleEntityForm
      :fields="fields"
      submit-label="Créer le critère"
      :loading="loading"
      @submit="onSubmit"
      @cancel="router.push('/admin/criteria')"
    />
  </div>
</template>
