<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import LoginForm from "./components/LoginForm.vue";
import ApplicationsList from "./components/ApplicationsList.vue";
import { t } from "@/shared/i18n";

const auth = useAuthStore();
</script>

<template>
  <div class="root">
    <header class="header">
      <h1>{{ t("app_name") }}</h1>
      <button
        v-if="auth.isAuthenticated"
        type="button"
        class="logout-btn"
        @click="auth.logout()"
        :aria-label="t('popup_logout')"
      >
        {{ t("popup_logout") }}
      </button>
    </header>
    <LoginForm v-if="!auth.isAuthenticated" />
    <ApplicationsList v-else />
  </div>
</template>

<style scoped>
.root {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 8px;
}
.header h1 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #047857;
}
.logout-btn {
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
}
.logout-btn:hover {
  background: #f3f4f6;
}
</style>
