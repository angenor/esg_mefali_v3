<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { t } from "@/shared/i18n";

const auth = useAuthStore();
const email = ref("");
const password = ref("");
const localError = ref<string | null>(null);

async function onSubmit(): Promise<void> {
  localError.value = null;
  try {
    await auth.login(email.value, password.value);
  } catch (err) {
    if (err instanceof Error && err.message.toLowerCase().includes("réseau")) {
      localError.value = t("popup_login_error_network");
    } else {
      localError.value = t("popup_login_error_invalid");
    }
  }
}

function openRegister(): void {
  if (typeof chrome !== "undefined" && chrome.tabs?.create) {
    chrome.tabs.create({ url: "https://app.esg-mefali.com/register" });
  } else {
    window.open("https://app.esg-mefali.com/register", "_blank");
  }
}
</script>

<template>
  <form class="login-form" @submit.prevent="onSubmit">
    <h2>{{ t("popup_login_title") }}</h2>
    <label class="field">
      <span>{{ t("popup_login_email") }}</span>
      <input
        v-model="email"
        type="email"
        required
        autocomplete="email"
        :aria-label="t('popup_login_email')"
        :disabled="auth.status === 'loading'"
      />
    </label>
    <label class="field">
      <span>{{ t("popup_login_password") }}</span>
      <input
        v-model="password"
        type="password"
        required
        minlength="8"
        autocomplete="current-password"
        :aria-label="t('popup_login_password')"
        :disabled="auth.status === 'loading'"
      />
    </label>
    <button
      type="submit"
      class="submit-btn"
      :disabled="auth.status === 'loading'"
    >
      {{ auth.status === "loading" ? t("loading") : t("popup_login_submit") }}
    </button>
    <p v-if="localError" role="alert" class="error">{{ localError }}</p>
    <button type="button" class="link-btn" @click="openRegister">
      {{ t("popup_register_link") }}
    </button>
  </form>
</template>

<style scoped>
.login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
h2 {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 4px 0;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}
.field input {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 14px;
}
.field input:focus {
  outline: 2px solid #10b981;
  outline-offset: 1px;
  border-color: #10b981;
}
.submit-btn {
  background: #047857;
  color: white;
  border: 0;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
  font-weight: 600;
}
.submit-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}
.submit-btn:hover:not(:disabled) {
  background: #065f46;
}
.error {
  color: #b91c1c;
  font-size: 12px;
  margin: 0;
}
.link-btn {
  background: transparent;
  border: 0;
  color: #047857;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}
</style>
