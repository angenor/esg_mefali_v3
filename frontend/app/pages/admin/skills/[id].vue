<script setup lang="ts">
// F23 — Page admin édition d'une skill existante (+ test/publish).
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SkillEvalRunner from '~/components/admin/skills/SkillEvalRunner.vue'
import SkillForm from '~/components/admin/skills/SkillForm.vue'
import { useAdminSkills } from '~/composables/useAdminSkills'
import type { SkillRead, SkillUpdate } from '~/types/skills'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const route = useRoute()
const router = useRouter()
const { getSkill, updateSkill, publishSkill, unpublishSkill } = useAdminSkills()

const skill = ref<SkillRead | null>(null)
const error = ref<string | null>(null)
const loading = ref(false)

const skillId = String(route.params.id)

async function load() {
  loading.value = true
  try {
    skill.value = await getSkill(skillId)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function onSubmit(payload: SkillUpdate) {
  error.value = null
  try {
    const updated = await updateSkill(skillId, payload)
    skill.value = updated
    if (updated.id !== skillId) {
      // Nouvelle version draft créée → rediriger.
      router.push(`/admin/skills/${updated.id}`)
    }
  } catch (e: any) {
    error.value =
      e?.detail?.detail?.code
        ? `Erreur (${e.detail.detail.code})`
        : (e as Error).message
  }
}

async function onPublish() {
  if (!confirm('Publier cette skill ? Le gating eval va être déclenché.')) return
  try {
    await publishSkill(skillId)
    await load()
  } catch (e: any) {
    if (e?.detail?.detail?.eval_report) {
      const r = e.detail.detail.eval_report
      alert(
        `Gate failed (${(r.success_rate * 100).toFixed(0)}% < 90%) — ${r.failed} cas en échec`,
      )
    } else {
      alert(`Erreur publication: ${e.message}`)
    }
  }
}

async function onUnpublish() {
  try {
    await unpublishSkill(skillId)
    await load()
  } catch (e) {
    alert(`Erreur: ${(e as Error).message}`)
  }
}
</script>

<template>
  <div class="max-w-5xl mx-auto p-4 space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Skill {{ skill?.name ?? '...' }}
        <span v-if="skill" class="text-sm font-normal text-gray-500 dark:text-gray-400">
          v{{ skill.version }} · {{ skill.status }}
        </span>
      </h2>
      <div class="flex gap-2">
        <button
          v-if="skill && skill.status === 'draft'"
          class="px-3 py-1.5 rounded bg-green-600 hover:bg-green-700 text-white text-sm"
          @click="onPublish"
        >
          Publier
        </button>
        <button
          v-if="skill && skill.status === 'published'"
          class="px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-700 text-white text-sm"
          @click="onUnpublish"
        >
          Dépublier
        </button>
      </div>
    </div>

    <p
      v-if="error"
      class="px-3 py-2 rounded bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm"
    >
      {{ error }}
    </p>

    <p v-if="loading" class="text-gray-500 dark:text-gray-400">Chargement...</p>

    <template v-if="skill">
      <SkillForm mode="edit" :initial="skill" @submit="onSubmit" />
      <SkillEvalRunner :skill-id="skill.id" />
    </template>
  </div>
</template>
