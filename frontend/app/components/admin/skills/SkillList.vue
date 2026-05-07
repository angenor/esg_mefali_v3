<script setup lang="ts">
// F23 — Liste paginée des Skills avec filtres + actions.
import { computed, onMounted, ref, watch } from 'vue'
import { useAdminSkills } from '~/composables/useAdminSkills'
import type { SkillListItem } from '~/types/skills'

const emit = defineEmits<{
  (e: 'edit', id: string): void
  (e: 'delete', id: string): void
  (e: 'publish', id: string): void
}>()

const { listSkills, deleteSkill, publishSkill } = useAdminSkills()

const items = ref<SkillListItem[]>([])
const total = ref(0)
const page = ref(1)
const limit = ref(20)
const filters = ref({
  domain: '',
  status: '',
  q: '',
})
const loading = ref(false)
const error = ref<string | null>(null)

const totalPages = computed(() => Math.ceil(total.value / limit.value))

async function load() {
  loading.value = true
  error.value = null
  try {
    const resp = await listSkills({
      page: page.value,
      limit: limit.value,
      domain: filters.value.domain || undefined,
      status: (filters.value.status as 'draft' | 'published' | undefined) || undefined,
      q: filters.value.q || undefined,
    })
    items.value = resp.items
    total.value = resp.total
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function onDelete(id: string) {
  if (!confirm('Supprimer cette skill (uniquement drafts) ?')) return
  try {
    await deleteSkill(id)
    await load()
    emit('delete', id)
  } catch (e) {
    alert(`Erreur suppression: ${(e as Error).message}`)
  }
}

async function onPublish(id: string) {
  if (!confirm('Publier cette skill ? Le gating eval va être déclenché.')) return
  try {
    await publishSkill(id)
    await load()
    emit('publish', id)
  } catch (e: any) {
    if (e?.detail?.detail?.eval_report) {
      alert(
        `Gate failed (${(e.detail.detail.eval_report.success_rate * 100).toFixed(0)}% < 90%)`,
      )
    } else {
      alert(`Erreur publication: ${e.message}`)
    }
  }
}

watch([filters, page, limit], () => load(), { deep: true })

onMounted(() => load())

function statusBadge(s: string): string {
  if (s === 'published')
    return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
  return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
}
</script>

<template>
  <div class="bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-dark-border p-4">
    <!-- Filtres -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
      <input
        v-model="filters.q"
        type="text"
        placeholder="Recherche par nom..."
        class="px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
      />
      <select
        v-model="filters.domain"
        class="px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
      >
        <option value="">Tous les domaines</option>
        <option value="diagnostic_esg">Diagnostic ESG</option>
        <option value="scoring_referentiel">Scoring référentiel</option>
        <option value="carbon_calc">Calcul carbone</option>
        <option value="dossier">Dossier</option>
        <option value="intermediaire">Intermédiaire</option>
        <option value="attestation">Attestation</option>
        <option value="credit_score">Score crédit</option>
      </select>
      <select
        v-model="filters.status"
        class="px-3 py-2 rounded border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-input text-surface-text dark:text-surface-dark-text"
      >
        <option value="">Tous les statuts</option>
        <option value="draft">Brouillon</option>
        <option value="published">Publié</option>
      </select>
      <div class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
        <span>{{ total }} skill(s)</span>
      </div>
    </div>

    <!-- Erreurs -->
    <div v-if="error" class="mb-4 px-3 py-2 rounded bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">
      {{ error }}
    </div>

    <!-- Tableau -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-gray-200 dark:border-dark-border">
            <th class="py-2 px-3 text-gray-600 dark:text-gray-400">Nom</th>
            <th class="py-2 px-3 text-gray-600 dark:text-gray-400">Domaine</th>
            <th class="py-2 px-3 text-gray-600 dark:text-gray-400">Version</th>
            <th class="py-2 px-3 text-gray-600 dark:text-gray-400">Statut</th>
            <th class="py-2 px-3 text-gray-600 dark:text-gray-400">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.id"
            class="border-b border-gray-100 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-hover"
          >
            <td class="py-2 px-3 font-medium text-surface-text dark:text-surface-dark-text">
              {{ item.name }}
            </td>
            <td class="py-2 px-3 text-gray-600 dark:text-gray-400">{{ item.domain }}</td>
            <td class="py-2 px-3 text-gray-600 dark:text-gray-400">{{ item.version }}</td>
            <td class="py-2 px-3">
              <span :class="['px-2 py-0.5 rounded text-xs font-medium', statusBadge(item.status)]">
                {{ item.status }}
              </span>
            </td>
            <td class="py-2 px-3 space-x-2">
              <button
                class="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                @click="$emit('edit', item.id)"
              >
                Éditer
              </button>
              <button
                v-if="item.status === 'draft'"
                class="text-green-600 hover:text-green-800 dark:text-green-400"
                @click="onPublish(item.id)"
              >
                Publier
              </button>
              <button
                v-if="item.status === 'draft'"
                class="text-red-600 hover:text-red-800 dark:text-red-400"
                @click="onDelete(item.id)"
              >
                Supprimer
              </button>
            </td>
          </tr>
          <tr v-if="!loading && items.length === 0">
            <td colspan="5" class="py-8 text-center text-gray-400 dark:text-gray-500">
              Aucune skill.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="mt-4 flex items-center justify-between text-sm">
      <button
        class="px-3 py-1 rounded border border-gray-300 dark:border-dark-border text-surface-text dark:text-surface-dark-text disabled:opacity-50"
        :disabled="page <= 1"
        @click="page = page - 1"
      >
        Précédent
      </button>
      <span class="text-gray-600 dark:text-gray-400">Page {{ page }} / {{ totalPages }}</span>
      <button
        class="px-3 py-1 rounded border border-gray-300 dark:border-dark-border text-surface-text dark:text-surface-dark-text disabled:opacity-50"
        :disabled="page >= totalPages"
        @click="page = page + 1"
      >
        Suivant
      </button>
    </div>
  </div>
</template>
