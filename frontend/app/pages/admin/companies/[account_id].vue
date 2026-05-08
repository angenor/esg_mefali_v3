<script setup lang="ts">
// F09 PRIO 3 — Vue overview d'un compte PME (cross-tenant admin).
//
// Onglets : Profil / Projets F06 / Candidatures / Évaluations
// (ESG/Carbone/Crédit) / Attestations.
//
// L'appel GET /api/admin/companies/{id} déclenche un audit_log view_admin
// avec dédup quotidienne (visible côté PME via /historique).
import { onMounted, ref } from 'vue'
import { useAdminCompanies, type AdminCompanyOverview } from '~/composables/useAdminCompanies'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const route = useRoute()
const { getCompanyOverview } = useAdminCompanies()

const overview = ref<AdminCompanyOverview | null>(null)
const error = ref('')
const tab = ref<'profile' | 'projects' | 'applications' | 'scores' | 'attestations' | 'users'>('profile')

async function load() {
  try {
    overview.value = await getCompanyOverview(route.params.account_id as string)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  }
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <div v-if="error" class="text-red-600 dark:text-red-400">{{ error }}</div>
    <div v-else-if="overview">
      <header class="mb-6">
        <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
          {{ overview.account.name }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Plan : {{ overview.account.plan }} · Compte
          {{ overview.account.is_active ? 'actif' : 'désactivé' }}
        </p>
        <div
          v-if="overview.account.deletion_scheduled_at"
          class="mt-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 p-2 text-xs text-amber-800 dark:text-amber-300"
        >
          ⚠ Suppression programmée le
          {{ new Date(overview.account.deletion_scheduled_at).toLocaleDateString('fr-FR') }}
        </div>
      </header>

      <!-- Tabs -->
      <div
        class="flex flex-wrap gap-1 border-b border-gray-200 dark:border-dark-border mb-6"
        role="tablist"
      >
        <button
          v-for="t in [
            { key: 'profile', label: 'Profil' },
            { key: 'users', label: `Utilisateurs (${overview.users.length})` },
            { key: 'projects', label: `Projets (${overview.projects.length})` },
            { key: 'applications', label: `Candidatures (${overview.applications.length})` },
            { key: 'scores', label: 'Scores' },
            { key: 'attestations', label: `Attestations (${overview.attestations.length})` },
          ]"
          :key="t.key"
          type="button"
          role="tab"
          :aria-selected="tab === t.key"
          :class="[
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px',
            tab === t.key
              ? 'border-emerald-600 text-emerald-700 dark:text-emerald-400'
              : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-surface-text dark:hover:text-surface-dark-text',
          ]"
          @click="tab = t.key as typeof tab"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- Profil -->
      <section
        v-if="tab === 'profile'"
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 space-y-3"
      >
        <h2 class="text-lg font-semibold mb-3">Profil entreprise</h2>
        <div v-if="overview.company_profile">
          <dl class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt class="text-gray-500 dark:text-gray-400">Nom commercial</dt>
              <dd class="font-medium text-surface-text dark:text-surface-dark-text">
                {{ overview.company_profile.company_name ?? '—' }}
              </dd>
            </div>
            <div>
              <dt class="text-gray-500 dark:text-gray-400">Secteur</dt>
              <dd class="font-medium text-surface-text dark:text-surface-dark-text">
                {{ overview.company_profile.sector ?? '—' }}
              </dd>
            </div>
            <div>
              <dt class="text-gray-500 dark:text-gray-400">Pays</dt>
              <dd class="font-medium text-surface-text dark:text-surface-dark-text">
                {{ overview.company_profile.country ?? '—' }}
              </dd>
            </div>
            <div>
              <dt class="text-gray-500 dark:text-gray-400">Effectifs</dt>
              <dd class="font-medium text-surface-text dark:text-surface-dark-text">
                {{ overview.company_profile.employee_count ?? '—' }}
              </dd>
            </div>
          </dl>
        </div>
        <p v-else class="text-sm text-gray-500 dark:text-gray-400">
          Profil non renseigné par la PME.
        </p>
      </section>

      <!-- Utilisateurs -->
      <section
        v-if="tab === 'users'"
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6"
      >
        <h2 class="text-lg font-semibold mb-3">Utilisateurs</h2>
        <table class="w-full text-sm">
          <thead class="bg-gray-50 dark:bg-gray-800/40 text-left">
            <tr>
              <th class="px-3 py-2">Email</th>
              <th class="px-3 py-2">Rôle</th>
              <th class="px-3 py-2">Actif</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="u in overview.users"
              :key="u.id as string"
              class="border-t border-gray-200 dark:border-dark-border"
            >
              <td class="px-3 py-2">{{ u.email }}</td>
              <td class="px-3 py-2 text-gray-600 dark:text-gray-400">{{ u.role }}</td>
              <td class="px-3 py-2">{{ u.is_active ? 'Oui' : 'Non' }}</td>
            </tr>
            <tr v-if="overview.users.length === 0">
              <td colspan="3" class="px-3 py-6 text-center text-gray-500">
                Aucun utilisateur.
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Projets -->
      <section
        v-if="tab === 'projects'"
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6"
      >
        <h2 class="text-lg font-semibold mb-3">Projets verts (F06)</h2>
        <ul v-if="overview.projects.length > 0" class="space-y-2 text-sm">
          <li
            v-for="p in overview.projects"
            :key="p.id as string"
            class="rounded-lg bg-gray-50 dark:bg-gray-800/40 px-3 py-2"
          >
            <div class="font-medium">{{ p.name }}</div>
            <div class="text-xs text-gray-500 dark:text-gray-400">
              {{ p.status }} · {{ p.maturity ?? '—' }}
            </div>
          </li>
        </ul>
        <p v-else class="text-sm text-gray-500 dark:text-gray-400">Aucun projet.</p>
      </section>

      <!-- Candidatures -->
      <section
        v-if="tab === 'applications'"
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6"
      >
        <h2 class="text-lg font-semibold mb-3">Candidatures fonds</h2>
        <ul v-if="overview.applications.length > 0" class="space-y-2 text-sm">
          <li
            v-for="a in overview.applications"
            :key="a.id as string"
            class="rounded-lg bg-gray-50 dark:bg-gray-800/40 px-3 py-2"
          >
            <div class="font-medium">Application {{ String(a.id).slice(0, 8) }}…</div>
            <div class="text-xs text-gray-500 dark:text-gray-400">{{ a.status }}</div>
          </li>
        </ul>
        <p v-else class="text-sm text-gray-500 dark:text-gray-400">Aucune candidature.</p>
      </section>

      <!-- Scores -->
      <section
        v-if="tab === 'scores'"
        class="grid grid-cols-3 gap-4"
      >
        <div
          class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-4"
        >
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Évaluations ESG
          </p>
          <p class="mt-1 text-2xl font-bold">
            {{ overview.scores.esg_assessments_count }}
          </p>
        </div>
        <div
          class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-4"
        >
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Bilans carbone
          </p>
          <p class="mt-1 text-2xl font-bold">
            {{ overview.scores.carbon_assessments_count }}
          </p>
        </div>
        <div
          class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-4"
        >
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Scores crédit
          </p>
          <p class="mt-1 text-2xl font-bold">
            {{ overview.scores.credit_scores_count }}
          </p>
        </div>
      </section>

      <!-- Attestations -->
      <section
        v-if="tab === 'attestations'"
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6"
      >
        <h2 class="text-lg font-semibold mb-3">Attestations (F08)</h2>
        <ul v-if="overview.attestations.length > 0" class="space-y-2 text-sm">
          <li
            v-for="a in overview.attestations"
            :key="a.id as string"
            class="rounded-lg bg-gray-50 dark:bg-gray-800/40 px-3 py-2 flex justify-between items-center"
          >
            <div>
              <div class="font-medium">{{ a.display_id }}</div>
              <div class="text-xs text-gray-500 dark:text-gray-400">
                {{ a.attestation_type }}
                <span
                  v-if="a.revoked_at"
                  class="ml-2 inline-block rounded-full bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300 px-2 py-0.5 text-[10px]"
                >
                  Révoquée
                </span>
              </div>
            </div>
          </li>
        </ul>
        <p v-else class="text-sm text-gray-500 dark:text-gray-400">Aucune attestation.</p>
      </section>
    </div>
  </div>
</template>
