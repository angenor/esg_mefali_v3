import { describe, it, expect, beforeEach, vi } from "vitest";

// Importer dans un beforeEach pour isoler le state de cache
async function importSW() {
  vi.resetModules();
  return await import("../src/background/service_worker");
}

describe("service_worker handleDetect", () => {
  beforeEach(() => {
    (globalThis as any).fetch = vi.fn();
  });

  it("renvoie match=null si non authentifié sans appeler l'API", async () => {
    const { handleDetect } = await importSW();
    const resp = await handleDetect({
      type: "DETECT_URL",
      url: "https://example.com",
    });
    expect(resp).toEqual({ ok: true, match: null });
    expect((globalThis as any).fetch).not.toHaveBeenCalled();
  });

  it("appelle l'API si authentifié et cache le résultat", async () => {
    (globalThis as any).chrome.storage.session.set({
      extension_token: "tok",
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          offer_id: "abc",
          offer_name: "Off",
          source_id: null,
          confidence: 1.0,
        }),
        { status: 200 },
      ),
    );

    const { handleDetect } = await importSW();
    const resp1 = await handleDetect({
      type: "DETECT_URL",
      url: "https://x.fr",
    });
    expect(resp1.ok).toBe(true);
    if (resp1.ok) expect(resp1.match?.offer_id).toBe("abc");

    // 2e appel → cache hit (pas de second fetch).
    const resp2 = await handleDetect({
      type: "DETECT_URL",
      url: "https://x.fr",
    });
    expect(resp2.ok).toBe(true);
    expect((globalThis as any).fetch).toHaveBeenCalledTimes(1);
  });

  it("renvoie ok=false sur 401 (auth expired)", async () => {
    (globalThis as any).chrome.storage.session.set({
      extension_token: "tok",
    });
    (globalThis as any).fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 401 }));

    const { handleDetect } = await importSW();
    const resp = await handleDetect({
      type: "DETECT_URL",
      url: "https://q.fr",
    });
    expect(resp.ok).toBe(false);
    if (!resp.ok) expect(resp.error).toBe("AUTH_EXPIRED");
  });
});
