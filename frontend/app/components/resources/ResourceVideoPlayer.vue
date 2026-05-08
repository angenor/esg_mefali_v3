<script setup lang="ts">
// F20 — Lecteur vidéo (iframe sandboxée pour YouTube/Vimeo, video native pour /uploads).
import { computed } from 'vue'

interface Props {
  videoUrl: string
}

const props = defineProps<Props>()

const isYoutube = computed<boolean>(() =>
  /^https:\/\/(www\.)?(youtube\.com\/embed\/|youtu\.be\/)/.test(props.videoUrl),
)

const isVimeo = computed<boolean>(() =>
  /^https:\/\/(www\.)?(vimeo\.com\/|player\.vimeo\.com\/video\/)/.test(
    props.videoUrl,
  ),
)

const isLocal = computed<boolean>(() => props.videoUrl.startsWith('/uploads/'))

const embedUrl = computed<string>(() => {
  if (isYoutube.value) {
    if (props.videoUrl.includes('/embed/')) return props.videoUrl
    const id = props.videoUrl.split('youtu.be/')[1]?.split('?')[0]
    return id ? `https://www.youtube.com/embed/${id}` : props.videoUrl
  }
  if (isVimeo.value) {
    if (props.videoUrl.includes('player.vimeo.com')) return props.videoUrl
    const id = props.videoUrl.split('vimeo.com/')[1]?.split('?')[0]
    return id ? `https://player.vimeo.com/video/${id}` : props.videoUrl
  }
  return props.videoUrl
})
</script>

<template>
  <div
    class="aspect-video w-full overflow-hidden rounded-lg bg-black"
    role="region"
    aria-label="Lecteur vidéo"
  >
    <iframe
      v-if="isYoutube || isVimeo"
      :src="embedUrl"
      class="h-full w-full"
      frameborder="0"
      allowfullscreen
      sandbox="allow-scripts allow-same-origin allow-presentation"
      title="Lecteur vidéo"
    />
    <video
      v-else-if="isLocal"
      :src="videoUrl"
      controls
      class="h-full w-full"
    />
    <div
      v-else
      class="flex h-full items-center justify-center p-6 text-center text-white"
    >
      <a
        :href="videoUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="text-emerald-400 hover:underline"
      >
        Voir la vidéo
      </a>
    </div>
  </div>
</template>
