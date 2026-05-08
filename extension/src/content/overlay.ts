// F24 — Bandeau « Offre détectée » injecté par le content script.
// Sécurité : crée des éléments via document.createElement + textContent
// (anti-XSS strict — jamais innerHTML).

import { t } from "@/shared/i18n";
import type { DetectResponse } from "@/shared/types";

const OVERLAY_ID = "esg-mefali-overlay-banner";
const APP_BASE_URL = "https://app.esg-mefali.com";

function styleEl(el: HTMLElement, styles: Record<string, string>): void {
  for (const [k, v] of Object.entries(styles)) {
    el.style.setProperty(k, v);
  }
}

export function dismissOverlay(): void {
  const existing = document.getElementById(OVERLAY_ID);
  if (existing && existing.parentNode) {
    existing.parentNode.removeChild(existing);
  }
}

export function injectOverlay(
  payload: DetectResponse,
  doc: Document = document,
): HTMLElement {
  // Idempotent : retire l'ancien si présent.
  const previous = doc.getElementById(OVERLAY_ID);
  if (previous && previous.parentNode) {
    previous.parentNode.removeChild(previous);
  }

  const banner = doc.createElement("div");
  banner.id = OVERLAY_ID;
  banner.setAttribute("role", "status");
  banner.setAttribute("aria-live", "polite");
  styleEl(banner, {
    position: "fixed",
    top: "0",
    left: "0",
    right: "0",
    "z-index": "2147483646",
    background: "#047857",
    color: "white",
    padding: "10px 16px",
    "font-family":
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    "font-size": "14px",
    display: "flex",
    "align-items": "center",
    gap: "12px",
    "box-shadow": "0 2px 8px rgba(0,0,0,0.2)",
  });

  const label = doc.createElement("strong");
  label.textContent = `${t("overlay_offer_detected")} : `;
  banner.appendChild(label);

  const offerName = doc.createElement("span");
  offerName.textContent = payload.offer_name; // textContent → safe
  banner.appendChild(offerName);

  const spacer = doc.createElement("span");
  styleEl(spacer, { flex: "1" });
  banner.appendChild(spacer);

  // Bouton « Voir cette offre »
  const viewBtn = doc.createElement("a");
  viewBtn.href = `${APP_BASE_URL}/financing/offers/${encodeURIComponent(payload.offer_id)}`;
  viewBtn.target = "_blank";
  viewBtn.rel = "noopener noreferrer";
  viewBtn.textContent = t("overlay_view_button");
  styleEl(viewBtn, {
    background: "white",
    color: "#047857",
    "border-radius": "4px",
    padding: "4px 10px",
    "text-decoration": "none",
    "font-weight": "600",
  });
  banner.appendChild(viewBtn);

  // Lien source si présent
  if (payload.source_id) {
    const sourceLink = doc.createElement("a");
    sourceLink.href = `${APP_BASE_URL}/sources/${encodeURIComponent(payload.source_id)}`;
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    sourceLink.textContent = t("overlay_source_link");
    styleEl(sourceLink, {
      color: "white",
      "text-decoration": "underline",
      "font-size": "12px",
    });
    banner.appendChild(sourceLink);
  }

  // Bouton fermer
  const closeBtn = doc.createElement("button");
  closeBtn.type = "button";
  closeBtn.textContent = "✕";
  closeBtn.setAttribute("aria-label", t("overlay_close_button"));
  styleEl(closeBtn, {
    background: "transparent",
    border: "0",
    color: "white",
    cursor: "pointer",
    "font-size": "16px",
    "margin-left": "4px",
  });
  closeBtn.addEventListener("click", () => {
    dismissOverlay();
    try {
      window.sessionStorage.setItem(
        "esg-mefali-overlay-dismissed",
        location.href,
      );
    } catch {
      /* ignore */
    }
  });
  banner.appendChild(closeBtn);

  doc.body.appendChild(banner);
  return banner;
}

export function wasDismissedThisSession(href: string = location.href): boolean {
  try {
    return window.sessionStorage.getItem("esg-mefali-overlay-dismissed") === href;
  } catch {
    return false;
  }
}
