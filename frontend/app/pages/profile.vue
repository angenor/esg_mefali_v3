<script setup lang="ts">
import { computed } from 'vue'

definePageMeta({
  layout: 'default',
})

const route = useRoute()

const tabs = [
  { key: 'company', label: 'Entreprise', path: '/profile/company' },
  { key: 'projects', label: 'Mes Projets', path: '/profile/projects' },
] as const

const activeTab = computed(() => {
  if (route.path.startsWith('/profile/projects')) return 'projects'
  return 'company'
})

// F06 — Redirection automatique vers /profile/company quand on est sur /profile
onMounted(() => {
  if (route.path === '/profile' || route.path === '/profile/') {
    navigateTo('/profile/company', { replace: true })
  }
})
</script>

<template>
  <div class="min-h-screen bg-surface-bg dark:bg-surface-dark-bg">
    <div class="max-w-5xl mx-auto px-4 py-8">
      <h1
        class="text-2xl font-bold text-gray-900 dark:text-surface-dark-text mb-6"
      >
        Profil
      </h1>
      <!-- Onglets -->
      <nav
        class="flex gap-1 border-b border-gray-200 dark:border-dark-border mb-8"
        role="tablist"
      >
        <NuxtLink
          v-for="tab in tabs"
          :key="tab.key"
          :to="tab.path"
          role="tab"
          :aria-selected="activeTab === tab.key"
          class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors"
          :class="
            activeTab === tab.key
              ? 'border-brand-green text-brand-green dark:text-emerald-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-surface-text dark:hover:text-surface-dark-text'
          "
        >
          {{ tab.label }}
        </NuxtLink>
      </nav>

      <NuxtPage />
    </div>
  </div>
</template>
