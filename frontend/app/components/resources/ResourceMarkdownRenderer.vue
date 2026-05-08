<script setup lang="ts">
// F20 — Rendu markdown sécurisé (sanitization basique sans dépendance externe).
// FR-032 : empêche XSS via stripping des balises script/iframe.
import { computed } from 'vue'

interface Props {
  content: string | null | undefined
}

const props = defineProps<Props>()

const escapeMap: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => escapeMap[c] ?? c)
}

function renderInline(text: string): string {
  // Liens markdown [texte](url) — on n'autorise que http/https.
  let out = text
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => {
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="text-emerald-600 hover:underline dark:text-emerald-400">${escapeHtml(label)}</a>`
  })
  // Bold **txt**
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // Italic *txt*
  out = out.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  // Code `txt`
  out = out.replace(
    /`([^`]+)`/g,
    '<code class="px-1 py-0.5 rounded bg-gray-100 text-sm dark:bg-dark-input">$1</code>',
  )
  return out
}

const html = computed<string>(() => {
  if (!props.content) return ''
  // Strip dangerous tags BEFORE escaping so we lose them.
  const safeRaw = props.content.replace(
    /<\s*\/?\s*(script|iframe|object|embed|style)[^>]*>/gi,
    '',
  )

  const lines = safeRaw.split(/\r?\n/)
  const out: string[] = []
  let inList = false

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      continue
    }
    if (line.startsWith('### ')) {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      out.push(
        `<h3 class="text-lg font-semibold mt-5 mb-2 text-surface-text dark:text-surface-dark-text">${renderInline(escapeHtml(line.slice(4)))}</h3>`,
      )
    } else if (line.startsWith('## ')) {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      out.push(
        `<h2 class="text-xl font-semibold mt-6 mb-3 text-surface-text dark:text-surface-dark-text">${renderInline(escapeHtml(line.slice(3)))}</h2>`,
      )
    } else if (line.startsWith('# ')) {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      out.push(
        `<h1 class="text-2xl font-bold mt-6 mb-4 text-surface-text dark:text-surface-dark-text">${renderInline(escapeHtml(line.slice(2)))}</h1>`,
      )
    } else if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        out.push('<ul class="list-disc pl-6 my-3 space-y-1">')
        inList = true
      }
      out.push(
        `<li class="text-surface-text dark:text-surface-dark-text">${renderInline(escapeHtml(line.replace(/^[-*]\s+/, '')))}</li>`,
      )
    } else if (/^\d+\.\s+/.test(line)) {
      if (!inList) {
        out.push('<ol class="list-decimal pl-6 my-3 space-y-1">')
        inList = true
      }
      out.push(
        `<li class="text-surface-text dark:text-surface-dark-text">${renderInline(escapeHtml(line.replace(/^\d+\.\s+/, '')))}</li>`,
      )
    } else {
      if (inList) {
        out.push('</ul>')
        inList = false
      }
      out.push(
        `<p class="my-3 text-surface-text dark:text-surface-dark-text leading-relaxed">${renderInline(escapeHtml(line))}</p>`,
      )
    }
  }
  if (inList) out.push('</ul>')
  return out.join('\n')
})
</script>

<template>
  <div
    class="prose prose-sm max-w-none dark:prose-invert"
    role="article"
    v-html="html"
  />
</template>
