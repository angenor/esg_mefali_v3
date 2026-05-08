<script setup lang="ts">
import { t } from "@/shared/i18n";
</script>

<template>
  <div class="empty">
    <p>{{ t("dashboard_empty_state") }}</p>
  </div>
</template>

<style scoped>
.empty {
  padding: 24px 8px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}
</style>
