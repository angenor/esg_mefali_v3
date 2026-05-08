import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  apiFetch,
  authExchange,
  detectUrl,
  AuthExpiredError,
  NetworkError,
} from "../src/shared/api";

describe("apiFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("ajoute le bearer header depuis chrome.storage.session", async () => {
    (globalThis as any).chrome.storage.session.set({ extension_token: "tok" });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    (globalThis as any).fetch = fetchMock;

    await apiFetch("/some-path");

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["Authorization"]).toBe("Bearer tok");
  });

  it("ne met pas de bearer si withAuth=false", async () => {
    (globalThis as any).chrome.storage.session.set({ extension_token: "tok" });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
    (globalThis as any).fetch = fetchMock;

    await apiFetch("/x", { withAuth: false });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["Authorization"]).toBeUndefined();
  });

  it("retourne null sur 204", async () => {
    (globalThis as any).fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    const out = await apiFetch("/detect", { method: "POST" });
    expect(out).toBeNull();
  });

  it("lève AuthExpiredError sur 401", async () => {
    (globalThis as any).fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 401 }));
    await expect(apiFetch("/x")).rejects.toBeInstanceOf(AuthExpiredError);
  });

  it("lève NetworkError sur fetch fail", async () => {
    (globalThis as any).fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("network down"));
    await expect(apiFetch("/x")).rejects.toBeInstanceOf(NetworkError);
  });

  it("authExchange poste vers le bon endpoint", async () => {
    const body = {
      access_token: "a",
      refresh_token: "b",
      scope: "extension",
      expires_in: 100,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    (globalThis as any).fetch = fetchMock;
    const resp = await authExchange("u@x.fr", "Password1!");
    expect(resp.scope).toBe("extension");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/extension/v1/auth/exchange");
    expect(opts.method).toBe("POST");
  });

  it("detectUrl renvoie null sur 204", async () => {
    (globalThis as any).fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    const m = await detectUrl("https://x.fr");
    expect(m).toBeNull();
  });
});
