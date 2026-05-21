<script setup lang="ts">
// F25 — Wrapper léger vers la fiche détail admin existante.
// Décision D6 research : on ne duplique pas le contenu ; on redirige.
import { onMounted } from 'vue'
import { useRoute, useRouter } from '#app'

definePageMeta({
  layout: 'admin',
  middleware: 'admin',
})

const route = useRoute()
const router = useRouter()

onMounted(() => {
  const id = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
  if (id) {
    router.replace(`/admin/funds/${id}`)
  }
})
</script>

<template>
  <div class="flex items-center justify-center py-12 text-sm text-gray-500 dark:text-gray-400">
    Redirection vers la fiche du fonds…
  </div>
</template>
