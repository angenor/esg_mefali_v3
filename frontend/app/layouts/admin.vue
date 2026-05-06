<script setup lang="ts">
// F02 — Layout dedie au back-office Admin.
//
// Differenciation visuelle marquee (accent rouge) pour eviter toute
// confusion avec le layout PME et signaler que les actions effectuees
// ici sont privilegiees (gestion catalogue, sources, comptes PME).
//
// Sidebar pre-cablee avec des entrees factices F02 ; les vraies routes
// (catalogue, sources, comptes, metriques) sont peuplees par F09.
import { computed } from 'vue'
import { useAuthStore } from '~/stores/auth'
import { useAuth } from '~/composables/useAuth'

const auth = useAuthStore()
const { logout } = useAuth()

// Items de navigation. Les entrees pointent vers des routes futures (F09).
// Tant qu'elles ne sont pas peuplees, le clic ne casse rien (404 explicite).
const navItems = [
  { label: 'Sante du systeme', icon: '🩺', to: '/admin/health' },
  { label: 'Catalogue fonds', icon: '📚', to: '/admin/catalog' },
  { label: 'Sources reglementaires', icon: '📜', to: '/admin/sources' },
  { label: 'Comptes PME', icon: '🏢', to: '/admin/accounts' },
  { label: 'Metriques globales', icon: '📊', to: '/admin/metrics' },
]

const adminEmail = computed(() => auth.user?.email ?? '')
const adminFullName = computed(() => auth.user?.full_name ?? 'Admin')

async function onLogout() {
  await logout()
}
</script>

<template>
  <div
    class="flex h-screen overflow-hidden bg-red-50 dark:bg-red-950 text-surface-text dark:text-surface-dark-text"
  >
    <!-- Sidebar admin (accent rouge) -->
    <aside
      class="hidden lg:flex w-64 flex-col border-r border-red-200 dark:border-red-800 bg-white dark:bg-red-950/40"
    >
      <div
        class="flex items-center gap-3 px-5 py-4 border-b border-red-200 dark:border-red-800"
      >
        <span aria-hidden="true" class="text-2xl">🛡️</span>
        <div class="flex flex-col">
          <span class="text-sm font-semibold text-red-800 dark:text-red-200">
            ESG Mefali
          </span>
          <span class="text-xs text-red-600 dark:text-red-300">
            Console Admin
          </span>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto py-4">
        <NuxtLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-5 py-2.5 text-sm font-medium text-red-900 dark:text-red-100 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
          active-class="bg-red-200 dark:bg-red-900 text-red-900 dark:text-red-50"
        >
          <span aria-hidden="true">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </NuxtLink>
      </nav>

      <div
        class="border-t border-red-200 dark:border-red-800 px-5 py-4 flex flex-col gap-2"
      >
        <div class="text-xs text-red-700 dark:text-red-300 truncate">
          {{ adminFullName }}
        </div>
        <div class="text-xs text-red-600 dark:text-red-400 truncate">
          {{ adminEmail }}
        </div>
        <button
          type="button"
          class="mt-2 inline-flex items-center justify-center gap-1 rounded-md bg-red-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-800 dark:bg-red-800 dark:hover:bg-red-700 transition-colors"
          @click="onLogout"
        >
          Se deconnecter
        </button>
      </div>
    </aside>

    <!-- Contenu principal admin -->
    <div class="flex-1 flex flex-col min-w-0">
      <header
        class="flex items-center justify-between border-b border-red-200 dark:border-red-800 bg-white/90 dark:bg-red-950/40 px-6 py-3"
      >
        <div class="flex items-center gap-3">
          <h1
            class="text-base font-semibold text-red-900 dark:text-red-100 tracking-tight"
          >
            Console d'administration
          </h1>
          <RoleBadge role="ADMIN" size="md" />
        </div>
        <div class="hidden md:flex items-center gap-3">
          <span class="text-xs text-red-700 dark:text-red-300">
            Zone privilegiee
          </span>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-6">
        <slot />
      </main>
    </div>
  </div>
</template>
