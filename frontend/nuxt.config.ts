// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  ssr: false,
  devtools: { enabled: true },

  modules: [
    '@pinia/nuxt',
  ],

  postcss: {
    plugins: {
      '@tailwindcss/postcss': {},
    },
  },

  typescript: {
    strict: true,
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000/api',
      // F07 — Feature flag : true = afficher les Cards Offres ; false = vue Cards Fonds legacy.
      // Default false en MVP F07 ; bascule effective post-F14 (matching offre).
      useOfferView: process.env.NUXT_PUBLIC_USE_OFFER_VIEW === 'true',
    },
  },

  css: ['~/assets/css/main.css'],

  components: [
    {
      path: '~/components',
      pathPrefix: false,
    },
  ],

  future: {
    compatibilityVersion: 4,
  },
})
