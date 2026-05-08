import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "../src/stores/auth";

describe("authStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("non authentifié par défaut", () => {
    const auth = useAuthStore();
    expect(auth.isAuthenticated).toBe(false);
  });

  it("login stocke le token via chrome.storage.session", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "tk-1",
          refresh_token: "rt-1",
          scope: "extension",
          expires_in: 3600,
        }),
        { status: 200 },
      ),
    );

    const auth = useAuthStore();
    await auth.login("user@x.fr", "Password1!");
    expect(auth.isAuthenticated).toBe(true);
    expect(auth.token).toBe("tk-1");

    // vérifie que chrome.storage.session a bien été écrit
    await new Promise<void>((resolve) =>
      (globalThis as any).chrome.storage.session.get(
        ["extension_token"],
        (res: any) => {
          expect(res.extension_token).toBe("tk-1");
          resolve();
        },
      ),
    );
  });

  it("login échoué propage l'erreur", async () => {
    (globalThis as any).fetch = vi
      .fn()
      .mockResolvedValue(new Response('{"detail":"Identifiants invalides"}', { status: 401 }));
    const auth = useAuthStore();
    await expect(auth.login("u@x.fr", "Password1!")).rejects.toBeTruthy();
    expect(auth.status).toBe("error");
    expect(auth.isAuthenticated).toBe(false);
  });

  it("logout efface le token", async () => {
    const auth = useAuthStore();
    auth.token = "tk-2";
    auth.email = "u@x.fr";
    await auth.logout();
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.token).toBeNull();
  });

  it("loadFromStorage restaure le token", async () => {
    (globalThis as any).chrome.storage.session.set({
      extension_token: "tk-stored",
      extension_email: "stored@x.fr",
    });
    const auth = useAuthStore();
    await auth.loadFromStorage();
    expect(auth.token).toBe("tk-stored");
    expect(auth.email).toBe("stored@x.fr");
  });

  it("handleAuthExpired clear le token", async () => {
    const auth = useAuthStore();
    auth.token = "tk";
    auth.handleAuthExpired();
    expect(auth.isAuthenticated).toBe(false);
  });
});
