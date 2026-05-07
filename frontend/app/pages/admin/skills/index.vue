<script setup lang="ts">
// F23 — Page admin liste Skills.
import { useRouter } from 'vue-router'
import SkillList from '~/components/admin/skills/SkillList.vue'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const router = useRouter()

function onEdit(id: string) {
  router.push(`/admin/skills/${id}`)
}
</script>

<template>
  <div class="max-w-6xl mx-auto p-4">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
        Skills (Playbooks Métier)
      </h2>
      <NuxtLink
        to="/admin/skills/new"
        class="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm"
      >
        + Nouvelle skill
      </NuxtLink>
    </div>
    <SkillList @edit="onEdit" />
  </div>
</template>
