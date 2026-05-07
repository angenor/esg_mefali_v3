<script setup lang="ts">
// F23 — Page admin création d'une nouvelle skill.
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import SkillForm from '~/components/admin/skills/SkillForm.vue'
import { useAdminSkills } from '~/composables/useAdminSkills'
import type { SkillCreate } from '~/types/skills'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const router = useRouter()
const { createSkill } = useAdminSkills()
const error = ref<string | null>(null)
const submitting = ref(false)

async function onSubmit(payload: SkillCreate) {
  submitting.value = true
  error.value = null
  try {
    const created = await createSkill(payload)
    router.push(`/admin/skills/${created.id}`)
  } catch (e: any) {
    error.value =
      e?.detail?.detail?.code
        ? `Erreur (${e.detail.detail.code}): ${JSON.stringify(e.detail.detail)}`
        : (e as Error).message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="max-w-5xl mx-auto p-4">
    <h2 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text mb-4">
      Nouvelle skill
    </h2>
    <p
      v-if="error"
      class="mb-4 px-3 py-2 rounded bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm"
    >
      {{ error }}
    </p>
    <SkillForm mode="create" @submit="onSubmit" />
  </div>
</template>
