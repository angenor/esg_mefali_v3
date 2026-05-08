// F24 — Content script : détecte l'URL courante au chargement et envoie un
// message DETECT_URL au service worker. Si match, injecte l'overlay.

import { injectOverlay, wasDismissedThisSession } from "./overlay";
import type { DetectMessage, DetectMessageResponse } from "@/shared/types";

const MIN_CONFIDENCE = 0.8;

async function requestDetect(url: string): Promise<DetectMessageResponse> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
      resolve({ ok: false, error: "no chrome runtime" });
      return;
    }
    const message: DetectMessage = { type: "DETECT_URL", url };
    chrome.runtime.sendMessage(message, (resp: DetectMessageResponse) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, error: chrome.runtime.lastError.message ?? "" });
        return;
      }
      resolve(resp);
    });
  });
}

export async function runDetection(): Promise<void> {
  if (wasDismissedThisSession()) return;
  const url = window.location.href;
  if (!url.startsWith("http://") && !url.startsWith("https://")) return;
  const resp = await requestDetect(url);
  if (!resp.ok) return;
  if (!resp.match) return;
  if (resp.match.confidence < MIN_CONFIDENCE) return;
  injectOverlay(resp.match);
}

// Lance la détection après le chargement complet.
if (typeof window !== "undefined") {
  if (document.readyState === "complete") {
    void runDetection();
  } else {
    window.addEventListener("load", () => {
      void runDetection();
    });
  }

  // SPA navigation : popstate.
  window.addEventListener("popstate", () => {
    void runDetection();
  });
}
