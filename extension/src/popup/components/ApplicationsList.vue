<script setup lang="ts">
import { onMounted } from "vue";
import { useApplicationsStore } from "@/stores/applications";
import EmptyState from "./EmptyState.vue";
import { t } from "@/shared/i18n";

const apps = useApplicationsStore();

onMounted(() => {
  void apps.fetchActive();
});

function openDeepLink(url: string): void {
  if (typeof chrome !== "undefined" && chrome.tabs?.create) {
    chrome.tabs.create({ url });
  } else {
    window.open(url, "_blank");
  }
}
</script>

<template>
  <section class="dashboard">
    <h2>{{ t("dashboard_title") }}</h2>
    <p v-if="apps.loading" class="loading">{{ t("loading") }}</p>
    <p v-else-if="apps.error" role="alert" class="error">{{ apps.error }}</p>
    <EmptyState v-else-if="apps.items.length === 0" />
    <ul v-else class="apps-list">
      <li
        v-for="item in apps.items"
        :key="item.id"
        class="app-row"
        @click="openDeepLink(item.deep_link)"
        @keydown.enter="openDeepLink(item.deep_link)"
        tabindex="0"
        role="link"
        :aria-label="`${item.offer_name} — ${item.status_label_fr}`"
      >
        <div class="offer-name">{{ item.offer_name }}</div>
        <div class="status-line">
          <span class="status-badge">{{ item.status_label_fr }}</span>
          <span class="updated">{{
            new Date(item.updated_at).toLocaleDateString("fr-FR")
          }}</span>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
h2 {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}
.apps-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}
.app-row {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.app-row:hover,
.app-row:focus {
  background: #f3f4f6;
  outline: 2px solid #10b981;
  outline-offset: -2px;
}
.offer-name {
  font-weight: 600;
  font-size: 13px;
}
.status-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}
.status-badge {
  background: #d1fae5;
  color: #047857;
  border-radius: 12px;
  padding: 2px 8px;
}
.updated {
  color: #6b7280;
}
.loading,
.error {
  font-size: 12px;
  margin: 0;
}
.error {
  color: #b91c1c;
}
</style>
