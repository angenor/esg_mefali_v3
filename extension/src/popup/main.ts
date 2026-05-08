import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { useAuthStore } from "@/stores/auth";

async function bootstrap(): Promise<void> {
  const pinia = createPinia();
  const app = createApp(App);
  app.use(pinia);

  const auth = useAuthStore();
  await auth.loadFromStorage();

  // Listener message AUTH_EXPIRED issu du SW.
  if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg && (msg as { type?: string }).type === "AUTH_EXPIRED") {
        auth.handleAuthExpired();
      }
    });
  }

  app.mount("#app");
}

void bootstrap();
