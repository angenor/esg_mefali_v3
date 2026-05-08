import { describe, it, expect, beforeEach } from "vitest";
import {
  injectOverlay,
  dismissOverlay,
  wasDismissedThisSession,
} from "../src/content/overlay";

describe("overlay", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    try {
      window.sessionStorage.clear();
    } catch {
      /* ignore */
    }
  });

  it("injectOverlay crée un bandeau avec offer_name en textContent", () => {
    const banner = injectOverlay({
      offer_id: "abc-123",
      offer_name: "<script>XSS</script>",
      source_id: null,
      confidence: 1.0,
    });
    expect(banner.id).toBe("esg-mefali-overlay-banner");
    expect(banner.getAttribute("role")).toBe("status");
    // le offer_name doit être présent en textContent (pas en HTML)
    expect(banner.textContent).toContain("<script>XSS</script>");
    // mais pas comme balise script réelle
    expect(banner.querySelector("script")).toBeNull();
  });

  it("injectOverlay ajoute le lien source si source_id présent", () => {
    injectOverlay({
      offer_id: "abc",
      offer_name: "Off",
      source_id: "src-uuid",
      confidence: 1.0,
    });
    const links = Array.from(document.querySelectorAll("a"));
    const sourceLink = links.find((a) => a.href.includes("/sources/src-uuid"));
    expect(sourceLink).toBeDefined();
  });

  it("dismissOverlay supprime l'élément", () => {
    injectOverlay({
      offer_id: "x",
      offer_name: "Off",
      source_id: null,
      confidence: 1.0,
    });
    expect(document.getElementById("esg-mefali-overlay-banner")).not.toBeNull();
    dismissOverlay();
    expect(document.getElementById("esg-mefali-overlay-banner")).toBeNull();
  });

  it("idempotent : appel double ne duplique pas", () => {
    injectOverlay({
      offer_id: "x",
      offer_name: "Off",
      source_id: null,
      confidence: 1.0,
    });
    injectOverlay({
      offer_id: "x",
      offer_name: "Off",
      source_id: null,
      confidence: 1.0,
    });
    expect(document.querySelectorAll("#esg-mefali-overlay-banner").length).toBe(
      1,
    );
  });

  it("close button persiste la fermeture en sessionStorage", () => {
    injectOverlay({
      offer_id: "x",
      offer_name: "Off",
      source_id: null,
      confidence: 1.0,
    });
    const closeBtn = document
      .getElementById("esg-mefali-overlay-banner")
      ?.querySelector("button");
    expect(closeBtn).toBeDefined();
    closeBtn?.click();
    expect(wasDismissedThisSession()).toBe(true);
  });
});
