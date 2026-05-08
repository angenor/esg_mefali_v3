<script setup lang="ts">
// F09 PRIO 3 — Création d'un indicateur.
import { ref } from 'vue'
import SimpleEntityForm, {
  type FieldDef,
} from '~/components/admin/forms/SimpleEntityForm.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const { createEntity } = useAdminCatalog('indicator')
const router = useRouter()
const loading = ref(false)
const error = ref('')

const fields: FieldDef[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, placeholder: 'E1' },
  {
    key: 'pillar',
    label: 'Pilier',
    type: 'select',
    required: true,
    options: [
      { value: 'environment', label: 'Environnement' },
      { value: 'social', label: 'Social' },
      { value: 'governance', label: 'Gouvernance' },
    ],
  },
  { key: 'label', label: 'Libellé', type: 'text', required: true },
  { key: 'description', label: 'Description', type: 'textarea', required: true },
  { key: 'question', label: 'Question PME', type: 'textarea', required: true },
  {
    key: 'source_id',
    label: 'UUID de la source',
    type: 'text',
    required: true,
  },
]

async function onSubmit(values: Record<string, unknown>) {
  loading.value = true
  error.value = ''
  try {
    const created = await createEntity(values)
    router.push(`/admin/indicators/${(created as { id: string }).id}`)
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
      Nouvel indicateur
    </h1>
    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <SimpleEntityForm
      :fields="fields"
      submit-label="Créer l'indicateur"
      :loading="loading"
      @submit="onSubmit"
      @cancel="router.push('/admin/indicators')"
    />
  </div>
</template>
