<script setup lang="ts">
// F09 PRIO 3 — Création offre (Fund × Intermediary).
import { ref } from 'vue'
import SimpleEntityForm, { type FieldDef } from '~/components/admin/forms/SimpleEntityForm.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const { createEntity } = useAdminCatalog('offer')
const router = useRouter()
const loading = ref(false)
const error = ref('')

const fields: FieldDef[] = [
  {
    key: 'fund_id',
    label: 'UUID Fonds',
    type: 'text',
    required: true,
    helpText: 'Le fonds doit être en BDD (cf. /admin/funds).',
  },
  {
    key: 'intermediary_id',
    label: 'UUID Intermédiaire',
    type: 'text',
    required: true,
    helpText: 'L\'intermédiaire doit être en BDD (cf. /admin/intermediaries). Utiliser le code DIRECT pour accès direct.',
  },
]

async function onSubmit(values: Record<string, unknown>) {
  loading.value = true
  error.value = ''
  try {
    const created = await createEntity(values)
    router.push(`/admin/offers/${(created as { id: string }).id}`)
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
      Nouvelle offre
    </h1>
    <div
      v-if="error"
      class="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-300"
    >
      {{ error }}
    </div>
    <SimpleEntityForm
      :fields="fields"
      submit-label="Créer l'offre"
      :loading="loading"
      @submit="onSubmit"
      @cancel="router.push('/admin/offers')"
    />
  </div>
</template>
