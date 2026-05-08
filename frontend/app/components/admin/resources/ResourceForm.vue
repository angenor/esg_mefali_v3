<script setup lang="ts">
// F20 — Formulaire admin pour créer/éditer une ressource.
import { computed, ref, watch } from 'vue'
import type {
  Resource,
  ResourceCreatePayload,
  ResourceLanguage,
  ResourceTargetAudience,
  ResourceType,
} from '~/types/resource'
import { RESOURCE_TYPE_LABELS } from '~/types/resource'

interface Props {
  initial?: Partial<Resource> | null
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  submit: [payload: ResourceCreatePayload]
}>()

const TYPES: ResourceType[] = [
  'guide',
  'template_doc',
  'video',
  'faq',
  'intermediary_guide',
]
const AUDIENCES: ResourceTargetAudience[] = [
  'pme_micro',
  'pme_small',
  'pme_medium',
]

const form = ref<ResourceCreatePayload>({
  type: (props.initial?.type as ResourceType) ?? 'guide',
  title: props.initial?.title ?? '',
  slug: props.initial?.slug ?? '',
  description: props.initial?.description ?? '',
  content_md: props.initial?.content_md ?? '',
  file_url: props.initial?.file_url ?? null,
  video_url: props.initial?.video_url ?? null,
  duration_seconds: props.initial?.duration_seconds ?? null,
  category: props.initial?.category ?? [],
  target_audience: props.initial?.target_audience ?? [],
  language: (props.initial?.language as ResourceLanguage) ?? 'fr',
  source_id: props.initial?.source_id ?? '',
  intermediary_id: props.initial?.intermediary_id ?? null,
})

const categoriesText = ref<string>((props.initial?.category ?? []).join(', '))

watch(categoriesText, (val: string) => {
  form.value.category = val
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
})

const showIntermediaryField = computed<boolean>(
  () => form.value.type === 'intermediary_guide',
)

function toggleAudience(a: ResourceTargetAudience): void {
  const set = new Set(form.value.target_audience)
  if (set.has(a)) set.delete(a)
  else set.add(a)
  form.value.target_audience = Array.from(set)
}

function onSubmit(): void {
  emit('submit', { ...form.value })
}
</script>

<template>
  <form
    class="space-y-5"
    @submit.prevent="onSubmit"
  >
    <div>
      <label
        for="resource-type"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Type
      </label>
      <select
        id="resource-type"
        v-model="form.type"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      >
        <option v-for="t in TYPES" :key="t" :value="t">
          {{ RESOURCE_TYPE_LABELS[t] }}
        </option>
      </select>
    </div>

    <div>
      <label
        for="resource-title"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Titre
      </label>
      <input
        id="resource-title"
        v-model="form.title"
        type="text"
        required
        maxlength="200"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div>
      <label
        for="resource-slug"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Slug URL
      </label>
      <input
        id="resource-slug"
        v-model="form.slug"
        type="text"
        required
        pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div>
      <label
        for="resource-description"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Description courte
      </label>
      <input
        id="resource-description"
        v-model="form.description"
        type="text"
        required
        maxlength="500"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div>
      <label
        for="resource-content"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Contenu (markdown)
      </label>
      <textarea
        id="resource-content"
        v-model="form.content_md"
        rows="12"
        class="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div v-if="form.type === 'template_doc'">
      <label
        for="resource-file"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        URL du fichier (.docx, .xlsx, .pdf)
      </label>
      <input
        id="resource-file"
        v-model="form.file_url"
        type="text"
        placeholder="/uploads/resources/exemple.docx"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div v-if="form.type === 'video'">
      <label
        for="resource-video"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        URL vidéo (YouTube/Vimeo)
      </label>
      <input
        id="resource-video"
        v-model="form.video_url"
        type="url"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div>
      <label
        for="resource-categories"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Catégories (séparées par virgules)
      </label>
      <input
        id="resource-categories"
        v-model="categoriesText"
        type="text"
        placeholder="governance, environment"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <fieldset>
      <legend class="text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Audience cible
      </legend>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="a in AUDIENCES"
          :key="a"
          type="button"
          :class="[
            'px-3 py-1 text-xs rounded-full border transition',
            form.target_audience.includes(a)
              ? 'bg-emerald-600 border-emerald-600 text-white'
              : 'border-gray-300 text-gray-700 dark:border-dark-border dark:text-gray-300',
          ]"
          @click="toggleAudience(a)"
        >
          {{ a }}
        </button>
      </div>
    </fieldset>

    <div>
      <label
        for="resource-source"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Source F01 (UUID, vérifiée)
      </label>
      <input
        id="resource-source"
        v-model="form.source_id"
        type="text"
        required
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div v-if="showIntermediaryField">
      <label
        for="resource-intermediary"
        class="block text-sm font-medium text-surface-text dark:text-surface-dark-text mb-1"
      >
        Intermédiaire (UUID)
      </label>
      <input
        id="resource-intermediary"
        v-model="form.intermediary_id"
        type="text"
        class="w-full rounded-md border border-gray-300 px-3 py-2 dark:border-dark-border dark:bg-dark-input dark:text-surface-dark-text"
      />
    </div>

    <div class="flex justify-end gap-2 pt-4 border-t border-gray-200 dark:border-dark-border">
      <button
        type="submit"
        :disabled="loading"
        class="px-4 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition"
      >
        Enregistrer
      </button>
    </div>
  </form>
</template>
