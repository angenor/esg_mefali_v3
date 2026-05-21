<script setup lang="ts">
// F25 — Bannière "Version successeur" affichée sur les fiches détail
// d'entités catalogue versionées (F04) dont `superseded_by` est non NULL.
// Si la cible n'existe plus (chaîne rompue), affiche le badge alternatif.
interface Props {
  successorId: string | null
  /**
   * Préfixe d'URL utilisé pour construire le NuxtLink. Ex :
   * `/admin/catalog/funds` pour un fonds remplacé.
   */
  basePath: string
  /** Label affiché dans le bouton ("Voir la version 2", "Voir le fonds remplaçant"). */
  ctaLabel?: string
  /** Version courante (affichée à gauche en chip). */
  currentVersion?: string | null
  /** Flag d'erreur si la cible est introuvable (chaîne rompue). */
  brokenChain?: boolean
}

withDefaults(defineProps<Props>(), {
  ctaLabel: 'Voir la version successeur',
  currentVersion: null,
  brokenChain: false,
})
</script>

<template>
  <aside
    v-if="successorId || brokenChain"
    class="flex flex-col gap-3 rounded-md border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-100 md:flex-row md:items-center md:justify-between"
    role="region"
    aria-label="Version successeur"
  >
    <div class="flex flex-wrap items-center gap-2">
      <span aria-hidden="true">🔁</span>
      <span class="font-medium">Cet élément a été remplacé</span>
      <span
        v-if="currentVersion"
        class="inline-flex items-center rounded-full bg-amber-200 dark:bg-amber-800 px-2 py-0.5 text-xs font-semibold ring-1 ring-amber-300 dark:ring-amber-700"
      >
        Version {{ currentVersion }}
      </span>
      <span v-if="brokenChain" class="text-xs text-rose-700 dark:text-rose-300">
        ⚠️ Chaîne rompue : la version successeur est introuvable.
      </span>
    </div>
    <NuxtLink
      v-if="successorId && !brokenChain"
      :to="`${basePath}/${successorId}`"
      class="inline-flex items-center justify-center rounded-md bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
    >
      {{ ctaLabel }} →
    </NuxtLink>
  </aside>
</template>
