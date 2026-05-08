<script setup lang="ts">
// F09 PRIO 3 — Création d'un intermédiaire (stub PRIO 3 ; le backend
// admin.intermediaries_router actuellement ne supporte que list/get/publish.
// La création complète d'intermédiaire reste sous le router F07.).
definePageMeta({ middleware: 'admin', layout: 'admin' })
</script>

<template>
  <div class="px-6 py-8 max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold mb-4 text-surface-text dark:text-surface-dark-text">
      Nouvel intermédiaire
    </h1>
    <div
      class="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 p-4 text-sm text-amber-800 dark:text-amber-300"
    >
      La création complète d'intermédiaire passe par le module F07. Cette page
      sera enrichie avec un formulaire dédié (CRUD admin) post-MVP. Les
      intermédiaires existants peuvent être consultés et publiés depuis
      <NuxtLink to="/admin/intermediaries" class="underline">la liste</NuxtLink>.
    </div>
  </div>
</template>
