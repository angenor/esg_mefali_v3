<script setup lang="ts">
// F09 PRIO 3 — Création d'un référentiel.
import { ref } from 'vue'
import SimpleEntityForm, {
  type FieldDef,
} from '~/components/admin/forms/SimpleEntityForm.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const { createEntity } = useAdminCatalog('referential')
const router = useRouter()

const fields: FieldDef[] = [
  {
    key: 'code',
    label: 'Code',
    type: 'text',
    required: true,
    placeholder: 'mefali',
  },
  {
    key: 'label',
    label: 'Libellé',
    type: 'text',
    required: true,
    placeholder: 'Référentiel ESG Mefali',
  },
  {
    key: 'description',
    label: 'Description',
    type: 'textarea',
    required: true,
  },
  {
    key: 'source_id',
    label: 'UUID de la source',
    type: 'text',
    required: true,
    placeholder: '00000000-0000-0000-0000-000000000000',
    helpText: 'La source doit exister dans /admin/sources (verified pour publish).',
  },
]

const loading = ref(false)
const error = ref('')

async function onSubmit(values: Record<string, unknown>) {
  loading.value = true
  error.value = ''
  try {
    const created = await createEntity(values as Partial<Record<string, unknown>>)
    router.push(`/admin/referentials/${(created as { id: string }).id}`)
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
      Nouveau référentiel
    </h1>

    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>

    <SimpleEntityForm
      :fields="fields"
      submit-label="Créer le référentiel"
      :loading="loading"
      @submit="onSubmit"
      @cancel="router.push('/admin/referentials')"
    />
  </div>
</template>
