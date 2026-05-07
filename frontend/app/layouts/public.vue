<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const queryLang = (route.query.lang as string) || ''
const isEn = queryLang === 'en'

const brandLabel = isEn
  ? 'ESG Mefali — Sustainable finance platform'
  : 'ESG Mefali — Plateforme de finance durable'
const headerTitle = isEn
  ? 'ESG Mefali — Attestation Verification'
  : 'ESG Mefali — Vérification d\'attestation'
</script>

<template>
  <div class="min-h-screen flex flex-col bg-gray-50 text-gray-900">
    <header
      class="border-b border-gray-200 bg-white"
      role="banner"
    >
      <div class="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
        <div
          class="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold"
          aria-hidden="true"
        >
          M
        </div>
        <h1 class="text-base sm:text-lg font-semibold">{{ headerTitle }}</h1>
      </div>
    </header>

    <main class="flex-1" role="main">
      <slot />
    </main>

    <footer
      class="border-t border-gray-200 bg-white text-xs text-gray-500"
      role="contentinfo"
    >
      <div
        class="max-w-3xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2"
      >
        <span>&copy; {{ new Date().getFullYear() }} {{ brandLabel }}</span>
        <a href="/legal" class="hover:underline">{{
          isEn ? 'Legal' : 'Mentions légales'
        }}</a>
      </div>
    </footer>
  </div>
</template>
