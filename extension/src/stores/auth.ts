import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { authExchange, AuthExpiredError } from "@/shared/api";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(null);
  const email = ref<string | null>(null);
  const status = ref<"idle" | "loading" | "error">("idle");
  const errorMessage = ref<string | null>(null);

  const isAuthenticated = computed(() => !!token.value);

  async function loadFromStorage(): Promise<void> {
    if (typeof chrome === "undefined" || !chrome.storage?.session) return;
    return new Promise<void>((resolve) => {
      chrome.storage.session.get(["extension_token", "extension_email"], (res) => {
        token.value = (res?.extension_token as string | undefined) ?? null;
        email.value = (res?.extension_email as string | undefined) ?? null;
        resolve();
      });
    });
  }

  async function persist(): Promise<void> {
    if (typeof chrome === "undefined" || !chrome.storage?.session) return;
    return new Promise<void>((resolve) => {
      chrome.storage.session.set(
        {
          extension_token: token.value,
          extension_email: email.value,
        },
        () => resolve(),
      );
    });
  }

  async function clearStorage(): Promise<void> {
    if (typeof chrome === "undefined" || !chrome.storage?.session) return;
    return new Promise<void>((resolve) => {
      chrome.storage.session.remove(
        ["extension_token", "extension_email"],
        () => resolve(),
      );
    });
  }

  async function login(emailInput: string, password: string): Promise<void> {
    status.value = "loading";
    errorMessage.value = null;
    try {
      const resp = await authExchange(emailInput, password);
      token.value = resp.access_token;
      email.value = emailInput;
      await persist();
      status.value = "idle";
    } catch (err) {
      status.value = "error";
      errorMessage.value =
        err instanceof Error ? err.message : "Erreur inconnue";
      throw err;
    }
  }

  async function logout(): Promise<void> {
    token.value = null;
    email.value = null;
    await clearStorage();
    status.value = "idle";
    errorMessage.value = null;
  }

  function handleAuthExpired(): void {
    token.value = null;
    email.value = null;
    void clearStorage();
  }

  return {
    token,
    email,
    status,
    errorMessage,
    isAuthenticated,
    loadFromStorage,
    login,
    logout,
    handleAuthExpired,
  };
});
