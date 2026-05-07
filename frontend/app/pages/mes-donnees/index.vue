<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuth } from '~/composables/useAuth'
import { useDataPrivacy } from '~/composables/useDataPrivacy'

definePageMeta({ middleware: 'auth' })

const { useDeletion } = useDataPrivacy()
const { cancelDeletion } = useDeletion()

interface AccountInfo {
  deletion_scheduled_at: string | null
}

const account = ref<AccountInfo | null>(null)
const cancelLoading = ref(false)

async function fetchAccountInfo() {
  const { apiFetch } = useAuth()
  try {
    const me = await apiFetch<{ account: { deletion_scheduled_at?: string } | null }>(
      '/api/auth/me',
    )
    account.value = {
      deletion_scheduled_at: me.account?.deletion_scheduled_at ?? null,
    }
  } catch {
    account.value = null
  }
}

async function handleCancel() {
  cancelLoading.value = true
  await cancelDeletion()
  await fetchAccountInfo()
  cancelLoading.value = false
}

onMounted(fetchAccountInfo)

interface Card {
  to: string
  title: string
  description: string
  emoji: string
}

const CARDS: Card[] = [
  {
    to: '/mes-donnees/inventaire',
    title: 'Inventaire de mes données',
    description: 'Consultez le détail des données stockées sur votre compte.',
    emoji: '📦',
  },
  {
    to: '/mes-donnees/inventaire',
    title: 'Exporter mes données',
    description:
      'Téléchargez toutes vos données au format JSON (RGPD Art. 15 + 20).',
    emoji: '📥',
  },
  {
    to: '/mes-donnees/consentements',
    title: 'Mes consentements',
    description: 'Gérez les 7 consentements granulaires de votre compte.',
    emoji: '✅',
  },
  {
    to: '/mes-donnees/supprimer',
    title: 'Supprimer mon compte',
    description:
      'Programmez la suppression définitive de votre compte (RGPD Art. 17).',
    emoji: '🗑️',
  },
]
</script>

<template>
  <section
    class="max-w-5xl mx-auto bg-surface-bg dark:bg-surface-dark-bg text-surface-text dark:text-surface-dark-text"
  >
    <header class="mb-6">
      <h1 class="text-2xl font-semibold">Mes données personnelles</h1>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        Conformément au RGPD (Art. 15, 17, 20) et aux lois applicables (Côte
        d'Ivoire 2013-450, UEMOA n°20/2010), vous pouvez à tout moment
        consulter, exporter, modifier vos consentements ou demander la
        suppression de votre compte.
      </p>
    </header>

    <DeletionScheduledBanner
      v-if="account?.deletion_scheduled_at"
      :scheduled-at="account.deletion_scheduled_at"
      :loading="cancelLoading"
      class="mb-6"
      @cancel="handleCancel"
    />

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <NuxtLink
        v-for="card in CARDS"
        :key="card.title"
        :to="card.to"
        class="group flex items-start gap-3 rounded-lg border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card p-4 hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500"
      >
        <span class="text-2xl" aria-hidden="true">{{ card.emoji }}</span>
        <div>
          <h3 class="text-sm font-semibold">{{ card.title }}</h3>
          <p class="mt-1 text-xs text-gray-600 dark:text-gray-400">
            {{ card.description }}
          </p>
        </div>
      </NuxtLink>
    </div>

    <p class="mt-8 text-xs text-gray-500 dark:text-gray-400">
      Pour toute question RGPD :
      <a
        href="mailto:privacy@esg-mefali.com"
        class="underline hover:text-emerald-600 dark:hover:text-emerald-400"
      >
        privacy@esg-mefali.com
      </a>
      —
      <NuxtLink
        to="/legal/privacy"
        class="underline hover:text-emerald-600 dark:hover:text-emerald-400"
      >
        Politique de confidentialité
      </NuxtLink>
    </p>
  </section>
</template>
