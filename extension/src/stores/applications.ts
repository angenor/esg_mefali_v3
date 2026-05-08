import { defineStore } from "pinia";
import { ref } from "vue";
import { fetchActiveApplications } from "@/shared/api";
import type { ActiveApplicationItem } from "@/shared/types";

export const useApplicationsStore = defineStore("applications", () => {
  const items = ref<ActiveApplicationItem[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchActive(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      items.value = await fetchActiveApplications();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Erreur";
      items.value = [];
    } finally {
      loading.value = false;
    }
  }

  function reset(): void {
    items.value = [];
    error.value = null;
    loading.value = false;
  }

  return { items, loading, error, fetchActive, reset };
});
